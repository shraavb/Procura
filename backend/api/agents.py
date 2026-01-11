"""
Agent and workflow API endpoints.

Includes streaming support for real-time LLM and workflow updates.
Uses async database sessions for production performance.
"""
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sse_starlette.sse import EventSourceResponse

from models.db import get_db
from models.database import AgentTask, ApprovalRequest, BOMItem
from models.schemas import (
    TaskResponse,
    TaskDetailResponse,
    TaskListResponse,
    ApprovalResponse,
    ApprovalListResponse,
    ApprovalDecision,
)
from services.streaming import (
    get_streaming_service,
    create_sse_response,
    StreamEvent,
    StreamEventType,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


# WebSocket connection manager
class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)

    def disconnect(self, websocket: WebSocket, task_id: str):
        if task_id in self.active_connections:
            self.active_connections[task_id].remove(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

    async def broadcast(self, task_id: str, message: dict):
        if task_id in self.active_connections:
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass


manager = ConnectionManager()


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List agent tasks."""
    query = select(AgentTask)

    if status:
        query = query.where(AgentTask.status == status)
    if task_type:
        query = query.where(AgentTask.task_type == task_type)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated tasks
    query = query.order_by(AgentTask.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()

    return TaskListResponse(items=tasks, total=total)


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Get task details and progress."""
    result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Cancel a running task."""
    result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in ["pending", "running"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel task in '{task.status}' status")

    task.status = "cancelled"
    task.completed_at = datetime.utcnow()
    task.error_message = "Cancelled by user"

    return task


@router.get("/approvals", response_model=ApprovalListResponse)
async def list_pending_approvals(
    entity_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List pending human-in-the-loop approvals."""
    query = select(ApprovalRequest).where(ApprovalRequest.status == "pending")

    if entity_type:
        query = query.where(ApprovalRequest.entity_type == entity_type)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get approvals
    query = query.order_by(ApprovalRequest.created_at.desc())
    result = await db.execute(query)
    approvals = result.scalars().all()

    return ApprovalListResponse(items=approvals, total=total)


@router.get("/approvals/{approval_id}", response_model=ApprovalResponse)
async def get_approval(approval_id: int, db: AsyncSession = Depends(get_db)):
    """Get approval request details."""
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    return approval


@router.post("/approvals/{approval_id}", response_model=ApprovalResponse)
async def process_approval(
    approval_id: int,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
):
    """Process an approval request (approve/reject with notes)."""
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if approval.status != "pending":
        raise HTTPException(status_code=400, detail=f"Approval already processed: {approval.status}")

    approval.status = "approved" if decision.approved else "rejected"
    approval.review_notes = decision.notes
    approval.reviewed_at = datetime.utcnow()

    # Handle different entity types
    if approval.entity_type == "supplier_match":
        # Update BOM item with selected match
        item_result = await db.execute(
            select(BOMItem).where(BOMItem.id == approval.entity_id)
        )
        bom_item = item_result.scalar_one_or_none()

        if bom_item and decision.approved:
            if decision.selected_option is not None and bom_item.alternative_matches:
                # Use selected alternative
                selected = bom_item.alternative_matches[decision.selected_option]
                bom_item.matched_supplier_id = selected.get("supplier_id")
                bom_item.matched_supplier_part_id = selected.get("supplier_part_id")
                bom_item.unit_cost = selected.get("unit_price")
                bom_item.match_confidence = selected.get("confidence", 1.0)
            bom_item.status = "confirmed"
            bom_item.match_method = "manual"

    return approval


@router.websocket("/ws/tasks/{task_id}")
async def task_websocket(websocket: WebSocket, task_id: int):
    """Real-time task progress updates via WebSocket."""
    await manager.connect(websocket, str(task_id))
    try:
        while True:
            # Keep connection alive, wait for messages
            data = await websocket.receive_text()
            # Echo back for ping/pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, str(task_id))


async def broadcast_task_update(task_id: int, update: dict):
    """Broadcast task update to connected clients."""
    await manager.broadcast(str(task_id), update)


# ========== STREAMING ENDPOINTS ==========

@router.get("/stream/completion")
async def stream_llm_completion(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    request: Request = None,
):
    """
    Stream an LLM completion response using Server-Sent Events.

    This endpoint provides real-time token streaming for LLM responses,
    ideal for chat interfaces and interactive applications.

    Query Parameters:
        prompt: The user prompt to send to the LLM
        system: Optional system prompt for context
        max_tokens: Maximum tokens to generate (default: 4096)
        temperature: Sampling temperature 0-1 (default: 0.7)

    Returns:
        EventSourceResponse with streaming events:
        - start: Stream started
        - token: Individual tokens as they're generated
        - complete: Stream finished with usage stats
        - error: Any errors that occurred
    """
    streaming_service = get_streaming_service()

    return await create_sse_response(
        streaming_service.stream_completion(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    )


@router.get("/stream/workflow/{workflow_name}")
async def stream_workflow_execution(
    workflow_name: str,
    bom_id: Optional[int] = None,
    request: Request = None,
):
    """
    Stream a multi-agent workflow execution using Server-Sent Events.

    Provides real-time updates as each agent in the workflow executes,
    including progress, intermediate results, and completion status.

    Path Parameters:
        workflow_name: Name of the workflow (e.g., "bom_processing", "po_generation")

    Query Parameters:
        bom_id: Optional BOM ID for BOM-related workflows

    Returns:
        EventSourceResponse with streaming events:
        - start: Workflow started
        - thinking: Agent is processing
        - tool_result: Agent step completed
        - complete: Workflow finished
        - error: Any errors that occurred
    """
    streaming_service = get_streaming_service()

    input_data = {}
    if bom_id:
        input_data["bom_id"] = bom_id

    return await create_sse_response(
        streaming_service.stream_agent_workflow(
            workflow_name=workflow_name,
            input_data=input_data,
        )
    )
