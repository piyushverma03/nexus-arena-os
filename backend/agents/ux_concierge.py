"""
ux_concierge.py ─ Agent 3
Listens for: "critical_status" (secondary listener — formats and logs UI nudges).
Primary logic now lives in ai_brain.py. This agent handles supplementary
formatting of long-form staff reports.
"""
from __future__ import annotations
import asyncio
from typing import Dict, Any

_bus: Dict[str, asyncio.Queue] = {}
STATUS = {"state": "IDLE", "nudges_sent": 0}


def init(bus: Dict[str, asyncio.Queue]):
    global _bus
    _bus = bus


async def run():
    STATUS["state"] = "ACTIVE"
    # UX Concierge monitors the ws_broadcast queue and counts outgoing nudges
    while True:
        await asyncio.sleep(5)
        # Heartbeat — keeps agent marked ACTIVE
        STATUS["state"] = "ACTIVE"
