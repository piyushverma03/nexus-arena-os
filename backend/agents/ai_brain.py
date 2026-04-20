"""
ai_brain.py ─ Master AI Decision Engine
Listens for: "critical_status" from Flow Physicist
Outputs:
  - Employee directives (DIVERT / WAIT) → ws_broadcast
  - Attendee nudges (for pending ticket holders at affected gates) → ws_broadcast
  - Logs to ai_directives table
"""
from __future__ import annotations
import asyncio
import json
import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from backend.database import get_conn
from backend.agents.flow_physicist import mm1_wait_time

load_dotenv()
try:
    from google import genai
    from google.genai import types
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
except ImportError:
    gemini_client = None


_bus: Dict[str, asyncio.Queue] = {}
_node_meta: Dict[str, Dict[str, Any]] = {}   # {node_id: {label, capacity, type}}
STATUS = {"state": "IDLE", "directives_issued": 0}

# Gate-type nodes that can serve as diversion targets
GATE_TYPES = {"gate"}

# Suppress repeated alerts for same node within N seconds
_last_alert: Dict[str, float] = {}
ALERT_COOLDOWN = 10   # seconds


def init(bus: Dict[str, asyncio.Queue], node_meta: Dict[str, Dict[str, Any]]):
    global _bus, _node_meta
    _bus = bus
    _node_meta = node_meta


def _find_alternative_gates(
    critical_node_id: str,
    metrics: Dict[str, Any],
    max_density: float = 0.50,
) -> List[Dict[str, Any]]:
    """Return gate-type nodes below max_density, sorted by density ascending."""
    alts = []
    for nid, m in metrics.items():
        if nid == critical_node_id:
            continue
        meta = _node_meta.get(nid, {})
        if meta.get("type") not in GATE_TYPES:
            continue
        if m["density"] <= max_density:
            alts.append({**m, "label": meta.get("label", nid)})
    return sorted(alts, key=lambda x: x["density"])


def _build_employee_directive(
    node_id: str,
    node_label: str,
    density: float,
    status: str,
    alt: Optional[Dict],
    wait_min: Optional[float],
) -> str:
    pct = int(density * 100)
    status_word = "CHOKE POINT" if status == "CHOKE" else "CRITICAL"

    if alt:
        alt_pct = int(alt["density"] * 100)
        return (
            f"⚠️ [{status_word}] {node_label} is at {pct}% capacity. "
            f"DIVERT attendees to {alt['label']} (currently {alt_pct}% — {alt['status']})."
        )
    elif wait_min is not None:
        return (
            f"🚨 [{status_word}] {node_label} is at {pct}% capacity. "
            f"No alternative gates available. "
            f"Estimated wait time: {wait_min:.1f} min. "
            f"Deploy staff to manage queue."
        )
    return f"⚠️ [{status_word}] {node_label} is at {pct}% capacity."


def _build_attendee_nudge(
    node_id: str,
    node_label: str,
    alt: Optional[Dict],
    wait_min: Optional[float],
) -> str:
    if alt:
        return (
            f"Your entry gate ({node_label}) is currently very busy. "
            f"📍 Please head to {alt['label']} instead — it's much less crowded and will save you time."
        )
    elif wait_min is not None:
        return (
            f"Your entry gate ({node_label}) is at capacity. "
            f"⏱ Please wait approximately {wait_min:.0f} minutes before approaching."
        )
    return f"Your entry gate ({node_label}) is busy. Please wait for staff instructions."


def _get_pending_tickets_at_gate(stadium_id: str, gate_id: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tickets WHERE stadium_id=? AND gate_assigned=? AND entry_status='pending'",
        (stadium_id, gate_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _log_directive(
    stadium_id: str,
    directive_type: str,
    target_id: str,
    node_id: str,
    message: str,
    severity: str,
    alt_gate: Optional[str],
    wait_time: Optional[float],
):
    conn = get_conn()
    conn.execute(
        """INSERT INTO ai_directives
           (stadium_id,directive_type,target_id,node_id,message,severity,alt_gate,wait_time)
           VALUES (?,?,?,?,?,?,?,?)""",
        (stadium_id, directive_type, target_id, node_id, message, severity, alt_gate, wait_time),
    )
    conn.commit()
    conn.close()


async def process_critical_event(event: Dict[str, Any]):
    import time

    sid = event["stadium_id"]
    metrics: Dict[str, Any] = event["metrics"]
    critical_nodes: List[str] = event["critical_nodes"]

    for node_id in critical_nodes:
        # Rate-limiting per node
        now = time.time()
        if now - _last_alert.get(node_id, 0) < ALERT_COOLDOWN:
            continue
        _last_alert[node_id] = now

        m = metrics[node_id]
        meta = _node_meta.get(node_id, {})
        node_label = meta.get("label", node_id)
        density = m["density"]
        status = m["status"]

        # Only process gate-type nodes (they're the entry/diversion points)
        if meta.get("type") not in GATE_TYPES:
            continue

        # Find best alternative gate
        alternatives = _find_alternative_gates(node_id, metrics)
        best_alt = alternatives[0] if alternatives else None

        # Calculate wait time if no alternative
        wait_min = None
        if not best_alt:
            cap = meta.get("capacity", 1000)
            lam = m["current_occupancy"] / 60   # arrivals per second approx
            mu = cap / 60
            wait_min = mm1_wait_time(mu, lam)

        # ── Employee Directive & Attendee Nudge Generator ───────────────────────
        alt_label = best_alt["label"] if best_alt else "None"
        wait_val = wait_min if wait_min is not None else 0.0
        
        dyn_emp_msg = None
        dyn_nudge_msg = None
        
        if gemini_client:
            prompt = f"""You are the Nexus Arena AI Crowd Intelligence Assistant. 
A stadium gate/node '{node_label}' has high congestion (density: {int(density*100)}%, status: {status}).
Alternative diversion gate: '{alt_label}'.
Estimated wait time if no alt: {wait_val:.1f} mins.

Provide a JSON response with exactly two string keys:
"employee_msg": A concise, actionable instruction for venue staff including an emoji.
"attendee_msg": A polite, friendly nudge for attendees telling them to divert to the alternative or wait. Include an emoji.
"""
            try:
                response = await gemini_client.aio.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7
                    ),
                )
                data = json.loads(response.text)
                dyn_emp_msg = data.get("employee_msg")
                dyn_nudge_msg = data.get("attendee_msg")
            except Exception as e:
                print(f"[AI BRAIN] Gemini fallback due to error: {e}")

        emp_msg = dyn_emp_msg or _build_employee_directive(node_id, node_label, density, status, best_alt, wait_min)
        severity = "CHOKE" if status == "CHOKE" else "CRITICAL"


        alt_gate_id = best_alt["node_id"] if best_alt else None

        _log_directive(sid, "employee", "all_staff", node_id, emp_msg, severity, alt_gate_id, wait_min)

        await _bus["ws_broadcast"].put({
            "type": "ai_directive",
            "target": "employee",
            "stadium_id": sid,
            "node_id": node_id,
            "node_label": node_label,
            "message": emp_msg,
            "severity": severity,
            "alt_gate": alt_gate_id,
            "alt_gate_label": best_alt["label"] if best_alt else None,
            "wait_time": wait_min,
        })

        # ── Attendee Nudges ────────────────────────────────────────────────────
        pending = _get_pending_tickets_at_gate(sid, node_id)
        nudge_msg = dyn_nudge_msg or _build_attendee_nudge(node_id, node_label, best_alt, wait_min)


        for ticket in pending:
            _log_directive(sid, "attendee", ticket["id"], node_id, nudge_msg, severity, alt_gate_id, wait_min)
            await _bus["ws_broadcast"].put({
                "type": "attendee_nudge",
                "target": "attendee",
                "ticket_id": ticket["id"],
                "ticket_code": ticket["ticket_code"],
                "stadium_id": sid,
                "node_id": node_id,
                "node_label": node_label,
                "message": nudge_msg,
                "severity": severity,
                "alt_gate": alt_gate_id,
                "alt_gate_label": best_alt["label"] if best_alt else None,
                "wait_time": wait_min,
            })

        STATUS["directives_issued"] += 1
        # Safe print for Windows terminal encoding issues
        try:
            print(f"[AI BRAIN] {severity} at {node_label}: {emp_msg}")
        except UnicodeEncodeError:
            print(f"[AI BRAIN] {severity} at {node_label}: {emp_msg.encode('ascii', 'ignore').decode('ascii')}")



async def run():
    STATUS["state"] = "ACTIVE"
    while True:
        event = await _bus["critical_status"].get()
        await process_critical_event(event)
