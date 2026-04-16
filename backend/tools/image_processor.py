"""
image_processor.py ─ Stadium map image → JSON node/edge pipeline.

Color-zone segmentation using Pillow.
Zone Color Dataset (employee guide):
  🔴 Red   (H 340-360, 0-15)  → gate
  🔵 Blue  (H 200-250)         → lobby
  🟡 Yellow(H 45-70)           → concession
  🟢 Green (H 90-150)          → floor / main arena
  ⚫ Gray  (S < 0.15)           → corridor / hallway
  🟣 Purple(H 270-310)         → vip
  🟠 Orange(H 15-45)           → restroom / medical
"""
from __future__ import annotations
import io
import math
import uuid
from typing import List, Dict, Any, Tuple

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ── Color → Zone dataset ──────────────────────────────────────────────────────
ZONE_DATASET = {
    "gate":       {"hue_range": [(340, 360), (0, 15)],  "saturation_min": 0.4, "default_capacity": 900,  "label_prefix": "Gate"},
    "lobby":      {"hue_range": [(200, 250)],            "saturation_min": 0.3, "default_capacity": 2000, "label_prefix": "Lobby"},
    "concession": {"hue_range": [(45, 70)],              "saturation_min": 0.4, "default_capacity": 400,  "label_prefix": "Concession"},
    "floor":      {"hue_range": [(90, 150)],             "saturation_min": 0.3, "default_capacity": 50000,"label_prefix": "Floor"},
    "corridor":   {"hue_range": [],                      "saturation_min": 0.0, "default_capacity": 500,  "label_prefix": "Corridor"},
    "vip":        {"hue_range": [(270, 310)],            "saturation_min": 0.3, "default_capacity": 800,  "label_prefix": "VIP"},
    "restroom":   {"hue_range": [(15, 45)],              "saturation_min": 0.3, "default_capacity": 200,  "label_prefix": "Restroom"},
}

DEFAULT_CAPACITY = {"gate": 900, "lobby": 2000, "concession": 400, "floor": 50000, "corridor": 500, "vip": 800, "restroom": 200}


def _rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    rf, gf, bf = r / 255, g / 255, b / 255
    cmax = max(rf, gf, bf)
    cmin = min(rf, gf, bf)
    delta = cmax - cmin

    if delta == 0:
        h = 0
    elif cmax == rf:
        h = 60 * (((gf - bf) / delta) % 6)
    elif cmax == gf:
        h = 60 * (((bf - rf) / delta) + 2)
    else:
        h = 60 * (((rf - gf) / delta) + 4)

    s = 0 if cmax == 0 else delta / cmax
    v = cmax
    return h, s, v


def _classify_pixel(r: int, g: int, b: int) -> str:
    h, s, v = _rgb_to_hsv(r, g, b)
    if v < 0.2:
        return "unknown"
    if s < 0.15:
        return "corridor"
    for zone, cfg in ZONE_DATASET.items():
        if zone in ("corridor", "unknown"):
            continue
        if s < cfg["saturation_min"]:
            continue
        for hmin, hmax in cfg["hue_range"]:
            if hmin <= h <= hmax:
                return zone
    return "unknown"


def _sample_grid(img: "Image.Image", grid_size: int = 20) -> List[Dict[str, Any]]:
    """Sample the image on a grid and classify each cell."""
    w, h = img.size
    cell_w = w / grid_size
    cell_h = h / grid_size
    cells = []

    for row in range(grid_size):
        for col in range(grid_size):
            cx = int((col + 0.5) * cell_w)
            cy = int((row + 0.5) * cell_h)
            r, g, b = img.getpixel((cx, cy))[:3]
            zone = _classify_pixel(r, g, b)
            if zone != "unknown":
                cells.append({
                    "zone": zone,
                    "grid_row": row,
                    "grid_col": col,
                    "pixel_x": cx,
                    "pixel_y": cy,
                })
    return cells


def _group_cells(cells: List[Dict], grid_size: int = 20) -> List[Dict[str, Any]]:
    """Merge adjacent same-zone cells into regions, return region centroids."""
    # Build grid map
    grid: Dict[Tuple[int, int], str] = {(c["grid_row"], c["grid_col"]): c["zone"] for c in cells}
    visited = set()
    regions = []

    def bfs(start_r: int, start_c: int, zone: str):
        queue = [(start_r, start_c)]
        visited.add((start_r, start_c))
        members = []
        while queue:
            r, c = queue.pop()
            members.append((r, c))
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = r+dr, c+dc
                if (nr, nc) not in visited and grid.get((nr, nc)) == zone:
                    visited.add((nr, nc))
                    queue.append((nr, nc))
        return members

    for (r, c), zone in grid.items():
        if (r, c) not in visited:
            members = bfs(r, c, zone)
            if len(members) >= 1:
                avg_r = sum(m[0] for m in members) / len(members)
                avg_c = sum(m[1] for m in members) / len(members)
                regions.append({
                    "zone": zone,
                    "size": len(members),
                    "center_row": avg_r,
                    "center_col": avg_c,
                })
    return regions


def _regions_to_graph(regions: List[Dict], img_w: int, img_h: int, stadium_scale: float = 600.0):
    """Convert regions to nodes and proximity-based edges."""
    nodes = []
    counters: Dict[str, int] = {}

    for idx, region in enumerate(regions):
        if region["size"] < 2:   # skip tiny noise regions
            continue
        zone = region["zone"]
        counters[zone] = counters.get(zone, 0) + 1
        suffix = chr(64 + counters[zone])   # A, B, C ...
        prefix = ZONE_DATASET[zone]["label_prefix"]

        # Normalize coords to [-1, 1] then scale to stadium_scale
        nx = (region["center_col"] / 20 - 0.5) * stadium_scale
        ny = -(region["center_row"] / 20 - 0.5) * stadium_scale  # flip Y

        node_id = f"{zone[:2].upper()}{suffix}"
        nodes.append({
            "id": node_id,
            "label": f"{prefix} {suffix}",
            "type": zone,
            "capacity": DEFAULT_CAPACITY.get(zone, 500),
            "coord_x": round(nx, 1),
            "coord_y": round(ny, 1),
            "coord_z": 0.0,
        })

    # Proximity edges: connect nodes within distance threshold
    edges = []
    threshold = stadium_scale * 0.55
    for i, n1 in enumerate(nodes):
        for j, n2 in enumerate(nodes):
            if j <= i:
                continue
            dist = math.hypot(n1["coord_x"] - n2["coord_x"], n1["coord_y"] - n2["coord_y"])
            if dist <= threshold:
                # Prefer gate→lobby, lobby→floor connections
                cap = min(
                    DEFAULT_CAPACITY.get(n1["type"], 500),
                    DEFAULT_CAPACITY.get(n2["type"], 500),
                )
                edges.append({
                    "from_id": n1["id"],
                    "to_id": n2["id"],
                    "max_flow": cap,
                    "distance": round(dist, 1),
                })

    return nodes, edges


async def process_stadium_image(image_bytes: bytes) -> Dict[str, Any]:
    """
    Main entry point: accepts raw image bytes, returns JSON-ready graph.
    """
    if not PIL_AVAILABLE:
        return {"error": "Pillow not installed. Run: pip install Pillow"}

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize((800, 600), Image.LANCZOS)

    cells = _sample_grid(img, grid_size=20)
    regions = _group_cells(cells, grid_size=20)
    regions_sorted = sorted(regions, key=lambda x: -x["size"])

    nodes, edges = _regions_to_graph(regions_sorted, img_w=800, img_h=600)

    return {
        "success": True,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "hint": "Preview generated from image color analysis. Edit labels and capacities before saving.",
    }
