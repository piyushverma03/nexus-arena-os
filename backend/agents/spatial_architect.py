"""
spatial_architect.py ─ Agent 1
Listens for: "user_input_layout"
Outputs: Saved graph to DB; Dijkstra path results on demand.
"""
from __future__ import annotations
import asyncio
import heapq
from typing import Dict, Any, List, Optional

from backend.tools.mcp_tools import save_user_layout

_bus: Dict[str, asyncio.Queue] = {}
_graph_cache: Dict[str, Any] = {}   # {stadium_id: {nodes, adjacency}}
STATUS = {"state": "IDLE"}


def init(bus: Dict[str, asyncio.Queue]):
    global _bus
    _bus = bus


def build_adjacency(nodes: List[Dict], edges: List[Dict]) -> Dict[str, List]:
    """Build adjacency list from nodes+edges for Dijkstra."""
    adj: Dict[str, List] = {n["id"]: [] for n in nodes}
    for e in edges:
        w = e.get("distance", 100)
        adj[e["from_id"]].append((e["to_id"], w))
        adj[e["to_id"]].append((e["from_id"], w))   # bidirectional
    return adj


def run_dijkstra(
    adj: Dict[str, List],
    source: str,
    target: str,
    avoid: List[str] | None = None,
) -> Optional[List[str]]:
    """Return shortest path (list of node ids) or None if unreachable."""
    avoid_set = set(avoid or [])
    dist = {v: float("inf") for v in adj}
    prev: Dict[str, Optional[str]] = {v: None for v in adj}
    dist[source] = 0
    heap = [(0, source)]

    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        if u == target:
            break
        for v, w in adj.get(u, []):
            if v in avoid_set:
                continue
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if dist[target] == float("inf"):
        return None

    path = []
    cur: Optional[str] = target
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return list(reversed(path))


def update_edge_weights(adj: Dict[str, List], congestion_map: Dict[str, float]) -> Dict[str, List]:
    """Increase edge weight proportional to destination congestion (ρ)."""
    new_adj: Dict[str, List] = {}
    for node, neighbours in adj.items():
        new_adj[node] = []
        for (nb, w) in neighbours:
            rho = congestion_map.get(nb, 0.0)
            adjusted = w * (1 + 3 * rho)   # heavier when congested
            new_adj[node].append((nb, adjusted))
    return new_adj


async def process_layout_event(event: Dict[str, Any]):
    sid = event["stadium_id"]
    nodes = event["nodes"]
    edges = event["edges"]
    venue_name = event.get("venue_name", "Unknown")

    STATUS["state"] = "BUILDING"
    result = await save_user_layout(sid, venue_name, nodes, edges)
    adj = build_adjacency(nodes, edges)
    _graph_cache[sid] = {"nodes": nodes, "edges": edges, "adjacency": adj}
    STATUS["state"] = "ACTIVE"

    await _bus["ws_broadcast"].put({
        "type": "agent_event",
        "agent": "SPATIAL",
        "message": f"Graph built for '{venue_name}' — {result['node_count']} nodes, {result['edge_count']} edges.",
        "severity": "INFO",
    })


async def run():
    STATUS["state"] = "ACTIVE"
    while True:
        event = await _bus["user_input_layout"].get()
        await process_layout_event(event)
