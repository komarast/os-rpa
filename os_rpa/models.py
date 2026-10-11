from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class QueueItemStatus(str, Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class QueueItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    queue_name: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: QueueItemStatus = QueueItemStatus.NEW
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    output_data: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class WorkflowNode(BaseModel):
    id: str
    type: str
    name: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[str] = None
    position: Optional[Dict[str, float]] = None


class WorkflowEdge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    target: str
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None
    condition: Optional[str] = None  # Optional expression evaluating to True/False for branching


class Workflow(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Workflow"
    description: Optional[str] = ""
    variables: Dict[str, Any] = Field(default_factory=dict)
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)


class ExecutionLogMessage(BaseModel):
    timestamp: str = Field(default_factory=utc_now_iso)
    level: str = "INFO"  # INFO, WARNING, ERROR, SUCCESS
    node_id: Optional[str] = None
    message: str
    details: Optional[Dict[str, Any]] = None


class ExecutionResult(BaseModel):
    workflow_id: str
    success: bool
    status: str
    error: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)
    logs: List[ExecutionLogMessage] = Field(default_factory=list)
    duration_seconds: float = 0.0

