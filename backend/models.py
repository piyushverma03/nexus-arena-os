"""
models.py ─ Pydantic schemas for all API request/response bodies.
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


# ── Auth ───────────────────────────────────────────────────────────────────────
class EmployeeLoginRequest(BaseModel):
    email: str
    password: str

class AttendeeLoginRequest(BaseModel):
    ticket_code: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    stadium_id: Optional[str] = None


# ── Venue Builder ──────────────────────────────────────────────────────────────
class NodeCreate(BaseModel):
    id: str
    label: str
    type: str = "gate"
    capacity: int = 800
    coord_x: float = 0.0
    coord_y: float = 0.0
    coord_z: float = 0.0

class EdgeCreate(BaseModel):
    from_id: str
    to_id: str
    max_flow: int = 1000
    distance: float = 100.0

class LayoutPayload(BaseModel):
    venue_name: str
    nodes: List[NodeCreate]
    edges: List[EdgeCreate]


# ── Surge Injection ────────────────────────────────────────────────────────────
class SurgeRequest(BaseModel):
    node_id: str
    magnitude: int   # people/min arriving at the node


# ── Threshold Update ───────────────────────────────────────────────────────────
class ThresholdUpdate(BaseModel):
    empty_threshold:    Optional[float] = None
    green_threshold:    Optional[float] = None
    busy_threshold:     Optional[float] = None
    critical_threshold: Optional[float] = None


# ── Flow Metrics ───────────────────────────────────────────────────────────────
class FlowMetricOut(BaseModel):
    timestamp: str
    node_id: str
    current_occupancy: int
    flux_value: float
    status: str


# ── AI Directive ───────────────────────────────────────────────────────────────
class AIDirectiveOut(BaseModel):
    id: int
    timestamp: str
    directive_type: str
    node_id: str
    message: str
    severity: str
    alt_gate: Optional[str]
    wait_time: Optional[float]
    acknowledged: bool
