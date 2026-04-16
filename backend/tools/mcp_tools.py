"""
mcp_tools.py ─ MCP-style callable tools used by agents and REST endpoints.

  save_user_layout(stadium_id, venue_name, nodes, edges)
  fetch_historical_flow(stadium_id, node_id, limit)
"""
from __future__ import annotations
import uuid
from typing import List, Dict, Any

from backend.database import get_conn


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 ─ save_user_layout
# ─────────────────────────────────────────────────────────────────────────────

async def save_user_layout(
    stadium_id: str,
    venue_name: str,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    total_capacity: int = 0,
) -> Dict[str, Any]:
    """
    Persist a user-defined stadium graph to Storage A.
    Upserts the stadium record, replaces all nodes and edges.
    Returns { success, stadium_id, node_count, edge_count }.
    """
    conn = get_conn()
    c = conn.cursor()

    # Upsert stadium
    c.execute(
        """INSERT INTO stadiums (id, venue_name, total_capacity)
           VALUES (?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET venue_name=excluded.venue_name,
                                         total_capacity=excluded.total_capacity""",
        (stadium_id, venue_name, total_capacity),
    )

    # Replace nodes
    c.execute("DELETE FROM nodes WHERE stadium_id = ?", (stadium_id,))
    for n in nodes:
        c.execute(
            "INSERT INTO nodes (id,stadium_id,label,type,capacity,coord_x,coord_y,coord_z) VALUES (?,?,?,?,?,?,?,?)",
            (n["id"], stadium_id, n["label"], n.get("type","gate"),
             n.get("capacity", 800), n.get("coord_x", 0), n.get("coord_y", 0), n.get("coord_z", 0)),
        )

    # Replace edges
    c.execute("DELETE FROM edges WHERE stadium_id = ?", (stadium_id,))
    for e in edges:
        c.execute(
            "INSERT INTO edges (stadium_id,from_id,to_id,max_flow,distance) VALUES (?,?,?,?,?)",
            (stadium_id, e["from_id"], e["to_id"], e.get("max_flow", 1000), e.get("distance", 100)),
        )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "stadium_id": stadium_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 ─ fetch_historical_flow
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_historical_flow(
    stadium_id: str,
    node_id: str | None = None,
    limit: int = 200,
    from_ts: str | None = None,
    to_ts: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Query Storage B for time-series flow metrics.
    Optional filters: node_id, from_ts (ISO string), to_ts (ISO string).
    Returns ordered list of metric dicts (newest first).
    """
    conn = get_conn()
    c = conn.cursor()

    query = "SELECT * FROM flow_metrics WHERE stadium_id = ?"
    params: list = [stadium_id]

    if node_id:
        query += " AND node_id = ?"
        params.append(node_id)
    if from_ts:
        query += " AND timestamp >= ?"
        params.append(from_ts)
    if to_ts:
        query += " AND timestamp <= ?"
        params.append(to_ts)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = c.execute(query, params).fetchall()
    conn.close()

    return [dict(r) for r in rows]
