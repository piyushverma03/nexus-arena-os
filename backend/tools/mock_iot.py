"""
mock_iot.py ─ Simulates sensor streams (2-second tick).

Maintains in-memory occupancy state per node and pushes to the message bus.
Supports on-demand surge injection.
"""
from __future__ import annotations
import asyncio
import random
import time
from typing import Dict, Any

# Shared occupancy state: {stadium_id: {node_id: current_occupancy}}
_occupancy: Dict[str, Dict[str, int]] = {}

# Manual surge overrides: {node_id: extra_arrivals_per_tick}
_surges: Dict[str, int] = {}

# Reference to the app's message bus (set by main.py)
_bus: Dict[str, asyncio.Queue] = {}


def init_iot(bus: Dict[str, asyncio.Queue], stadium_nodes: Dict[str, Dict[str, Any]]):
    """Pass the message bus and initial node capacities."""
    global _bus, _occupancy
    _bus = bus
    for sid, nodes in stadium_nodes.items():
        _occupancy[sid] = {
            nid: int(cap * random.uniform(0.05, 0.20))
            for nid, cap in nodes.items()
        }


def inject_surge(node_id: str, magnitude: int):
    """Inject a manual surge at a specific node (people/tick)."""
    _surges[node_id] = magnitude


def clear_surge(node_id: str):
    _surges.pop(node_id, None)


async def iot_loop():
    """Main 2-second simulation tick."""
    tick = 0
    while True:
        await asyncio.sleep(2)
        tick += 1

        for sid, nodes in _occupancy.items():
            batch = {}
            for nid, occ in nodes.items():
                # Background drift: small random arrivals/departures
                arrivals = random.randint(5, 40)
                departures = random.randint(3, 35)

                # Apply manual surge if active
                surge = _surges.get(nid, 0)
                # Decay surge by 5% per tick so it fades naturally
                if surge > 0:
                    _surges[nid] = max(0, int(surge * 0.95))
                    arrivals += surge

                new_occ = max(0, occ + arrivals - departures)
                nodes[nid] = new_occ
                batch[nid] = new_occ

            # Push to message bus
            if "live_iot_stream" in _bus:
                await _bus["live_iot_stream"].put({
                    "stadium_id": sid,
                    "occupancy": batch,
                    "tick": tick,
                    "timestamp": time.time(),
                })
