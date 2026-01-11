"""
LangGraph orchestrator for multi-agent BOM processing workflow.
"""
import logging
import asyncio
from datetime import datetime
from decimal import Decimal
from typing import TypedDict, Optional, Annotated
import operator

from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from models.db import get_sync_db_context
from models.database import BOM, BOMItem, AgentTask, ApprovalRequest, Supplier, Part, SupplierPart
from tools.parsing_tools import parse_excel_bom, parse_csv_bom, validate_bom_structure
from tools.search_tools import search_supplier_catalog_impl, semantic_part_search_impl
from tools.po_tools import create_po_draft_impl, group_items_by_supplier_impl
from prompts.agent_prompts import (
    BOM_PARSER_PROMPT,
    SUPPLIER_MATCHER_PROMPT,
    PO_GENERATOR_PROMPT,
)
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WorkflowState(TypedDict):
    """State passed between agents in the workflow."""
    bom_id: int
    task_id: int
    organization_id: int
    file_path: str
    file_type: str

    # Processing results
    parsed_items: list[dict]
    matched_items: list[dict]
    unmatched_items: list[dict]
    draft_pos: list[dict]

    # Progress tracking
    current_agent: str
    current_step: str
    progress: float
    messages: Annotated[list, operator.add]

    # Control flow
    error: Optional[str]
    needs_human_review: bool
    review_items: list[dict]
    completed: bool


def get_llm():
    """Get the LLM instance."""
    return ChatAnthropic(
        model=settings.llm_model,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
    )


def update_task_progress(task_id: int, progress: float, current_step: str, current_agent: str):
    """Update task progress in database."""
    with get_sync_db_context() as db:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if task:
            task.progress = progress
            task.current_step = current_step
            task.current_agent = current_agent
            if progress > 0 and not task.started_at:
                task.started_at = datetime.utcnow()


def update_bom_progress(bom_id: int, status: str, progress: float, step: str):
    """Update BOM processing progress."""
    with get_sync_db_context() as db:
        bom = db.query(BOM).filter(BOM.id == bom_id).first()
        if bom:
            bom.processing_status = status
            bom.processing_progress = progress
            bom.processing_step = step


# ============ Agent Nodes ============

async def parser_node(state: WorkflowState) -> WorkflowState:
    """BOM Parser Agent - extracts items from uploaded file."""
    logger.info(f"Parser agent processing BOM {state['bom_id']}")

    update_task_progress(state["task_id"], 10, "Parsing BOM file", "parser")
    update_bom_progress(state["bom_id"], "parsing", 10, "Reading and parsing file")

    file_path = state["file_path"]
    file_type = state["file_type"]

    # Parse based on file type
    if file_type == "excel":
        result = parse_excel_bom.invoke({"file_path": file_path})
    elif file_type == "csv":
        result = parse_csv_bom.invoke({"file_path": file_path})
    else:
        # For PDF/image, would use vision API - simplified for demo
        result = {"success": False, "error": f"Unsupported file type: {file_type}", "items": []}

    if not result.get("success"):
        return {
            **state,
            "error": result.get("error", "Failed to parse BOM"),
            "parsed_items": [],
            "current_agent": "parser",
            "current_step": "Parse failed",
            "progress": 10,
            "messages": [f"Parser error: {result.get('error')}"],
        }

    items = result.get("items", [])

    # Validate structure
    validation = validate_bom_structure.invoke({"items": items})

    if not validation.get("valid"):
        logger.warning(f"BOM validation issues: {validation.get('issues')}")

    # Store parsed items in database
    with get_sync_db_context() as db:
        bom = db.query(BOM).filter(BOM.id == state["bom_id"]).first()
        if bom:
            # Clear existing items
            db.query(BOMItem).filter(BOMItem.bom_id == bom.id).delete()

            # Add new items
            for item in items:
                bom_item = BOMItem(
                    bom_id=bom.id,
                    line_number=item["line_number"],
                    part_number_raw=item.get("part_number_raw"),
                    description_raw=item.get("description_raw"),
                    quantity=Decimal(str(item["quantity"])),
                    unit_of_measure=item.get("unit_of_measure", "EA"),
                    status="pending",
                )
                db.add(bom_item)

            bom.total_items = len(items)
            bom.processing_progress = 25

    update_task_progress(state["task_id"], 25, f"Parsed {len(items)} items", "parser")
    update_bom_progress(state["bom_id"], "parsing", 25, f"Extracted {len(items)} line items")

    return {
        **state,
        "parsed_items": items,
        "current_agent": "parser",
        "current_step": f"Parsed {len(items)} items",
        "progress": 25,
        "messages": [f"Parsed {len(items)} items from BOM file"],
    }


async def matcher_node(state: WorkflowState) -> WorkflowState:
    """Supplier Matcher Agent - matches items to suppliers."""
    logger.info(f"Matcher agent processing {len(state['parsed_items'])} items")

    update_task_progress(state["task_id"], 30, "Matching suppliers", "matcher")
    update_bom_progress(state["bom_id"], "matching", 30, "Finding supplier matches")

    matched_items = []
    unmatched_items = []
    review_items = []

    with get_sync_db_context() as db:
        bom = db.query(BOM).filter(BOM.id == state["bom_id"]).first()
        if not bom:
            return {**state, "error": "BOM not found"}

        organization_id = bom.organization_id
        bom_items = db.query(BOMItem).filter(BOMItem.bom_id == bom.id).all()

        total_items = len(bom_items)
        for idx, bom_item in enumerate(bom_items):
            progress = 30 + (idx / total_items * 30)  # 30-60%
            update_bom_progress(state["bom_id"], "matching", progress, f"Matching item {idx + 1}/{total_items}")

            best_match = None
            alternatives = []

            # Try exact match first
            if bom_item.part_number_raw:
                result = search_supplier_catalog_impl(db, bom_item.part_number_raw, organization_id)
                if result.get("matches"):
                    best_match = result["matches"][0]
                    alternatives = result["matches"][1:5]

            # Try semantic match if no exact match
            if not best_match and bom_item.description_raw and settings.openai_api_key:
                try:
                    result = semantic_part_search_impl(
                        db, bom_item.description_raw, organization_id
                    )
                    if result.get("matches"):
                        best_match = result["matches"][0]
                        alternatives = result["matches"][1:5]
                except Exception as e:
                    logger.warning(f"Semantic search failed: {e}")

            # Update BOM item with match
            if best_match:
                bom_item.matched_supplier_id = best_match["supplier_id"]
                bom_item.matched_supplier_part_id = best_match.get("supplier_part_id")
                bom_item.unit_cost = Decimal(str(best_match["unit_price"])) if best_match.get("unit_price") else None
                bom_item.lead_time_days = best_match.get("lead_time_days")
                bom_item.match_confidence = Decimal(str(best_match["confidence"]))
                bom_item.match_method = best_match["match_method"]
                bom_item.alternative_matches = [
                    {
                        "supplier_id": alt["supplier_id"],
                        "supplier_part_id": alt.get("supplier_part_id"),
                        "supplier_name": alt["supplier_name"],
                        "unit_price": alt.get("unit_price"),
                        "confidence": alt["confidence"],
                    }
                    for alt in alternatives
                ]

                # Check if needs review
                if best_match["confidence"] < settings.match_confidence_threshold:
                    bom_item.status = "needs_review"
                    bom_item.review_reason = f"Low confidence match ({best_match['confidence']:.0%})"
                    review_items.append({
                        "bom_item_id": bom_item.id,
                        "part_number": bom_item.part_number_raw,
                        "description": bom_item.description_raw,
                        "match_confidence": best_match["confidence"],
                        "alternatives": bom_item.alternative_matches,
                    })
                else:
                    bom_item.status = "matched"

                if bom_item.unit_cost:
                    bom_item.extended_cost = bom_item.unit_cost * bom_item.quantity

                matched_items.append({
                    "id": bom_item.id,
                    "part_number_raw": bom_item.part_number_raw,
                    "matched_supplier_id": bom_item.matched_supplier_id,
                    "matched_supplier_part_id": bom_item.matched_supplier_part_id,
                    "unit_cost": float(bom_item.unit_cost) if bom_item.unit_cost else None,
                    "quantity": float(bom_item.quantity),
                })
            else:
                bom_item.status = "needs_review"
                bom_item.review_reason = "No supplier match found"
                unmatched_items.append({
                    "id": bom_item.id,
                    "part_number_raw": bom_item.part_number_raw,
                    "description_raw": bom_item.description_raw,
                })
                review_items.append({
                    "bom_item_id": bom_item.id,
                    "part_number": bom_item.part_number_raw,
                    "description": bom_item.description_raw,
                    "match_confidence": 0,
                    "alternatives": [],
                })

        # Update BOM totals
        bom.matched_items = len(matched_items)
        total_cost = sum(
            item.extended_cost for item in bom_items
            if item.extended_cost
        )
        bom.total_cost = total_cost

    update_task_progress(state["task_id"], 60, f"Matched {len(matched_items)}/{total_items} items", "matcher")
    update_bom_progress(state["bom_id"], "matching", 60, f"Matched {len(matched_items)} items")

    needs_review = len(review_items) > 0

    return {
        **state,
        "matched_items": matched_items,
        "unmatched_items": unmatched_items,
        "review_items": review_items,
        "needs_human_review": needs_review,
        "current_agent": "matcher",
        "current_step": f"Matched {len(matched_items)}/{total_items} items",
        "progress": 60,
        "messages": [f"Matched {len(matched_items)} items, {len(review_items)} need review"],
    }


async def human_review_node(state: WorkflowState) -> WorkflowState:
    """Create approval requests for items needing human review."""
    logger.info(f"Creating review requests for {len(state['review_items'])} items")

    with get_sync_db_context() as db:
        bom = db.query(BOM).filter(BOM.id == state["bom_id"]).first()
        if not bom:
            return state

        for item in state["review_items"]:
            approval = ApprovalRequest(
                organization_id=bom.organization_id,
                task_id=state["task_id"],
                entity_type="supplier_match",
                entity_id=item["bom_item_id"],
                request_type="match_review",
                title=f"Review match: {item.get('part_number') or item.get('description', 'Unknown')}",
                description=f"Confidence: {item['match_confidence']:.0%}. {len(item.get('alternatives', []))} alternatives available.",
                details=item,
            )
            db.add(approval)

        # Pause task for human review
        task = db.query(AgentTask).filter(AgentTask.id == state["task_id"]).first()
        if task:
            task.status = "paused"
            task.current_step = "Waiting for human review"

        bom.processing_status = "awaiting_review"
        bom.processing_step = f"Review {len(state['review_items'])} items"

    return {
        **state,
        "current_step": "Awaiting human review",
        "messages": [f"Created {len(state['review_items'])} review requests"],
    }


async def po_generator_node(state: WorkflowState) -> WorkflowState:
    """PO Generator Agent - creates purchase orders from matched items."""
    logger.info("PO Generator agent creating purchase orders")

    update_task_progress(state["task_id"], 70, "Generating purchase orders", "po_generator")
    update_bom_progress(state["bom_id"], "generating_pos", 70, "Creating purchase orders")

    draft_pos = []

    with get_sync_db_context() as db:
        bom = db.query(BOM).filter(BOM.id == state["bom_id"]).first()
        if not bom:
            return {**state, "error": "BOM not found"}

        # Get confirmed/matched items
        bom_items = (
            db.query(BOMItem)
            .filter(BOMItem.bom_id == bom.id)
            .filter(BOMItem.status.in_(["matched", "confirmed"]))
            .filter(BOMItem.matched_supplier_id.isnot(None))
            .all()
        )

        if not bom_items:
            return {
                **state,
                "draft_pos": [],
                "current_step": "No items to order",
                "progress": 90,
                "messages": ["No matched items available for PO generation"],
            }

        # Convert to dict for grouping
        items_dict = [
            {
                "id": item.id,
                "matched_supplier_id": item.matched_supplier_id,
                "matched_supplier_part_id": item.matched_supplier_part_id,
                "part_id": item.part_id,
                "part_number_raw": item.part_number_raw,
                "description_raw": item.description_raw,
                "quantity": float(item.quantity),
                "unit_of_measure": item.unit_of_measure,
                "unit_cost": float(item.unit_cost) if item.unit_cost else 0,
            }
            for item in bom_items
        ]

        # Group by supplier
        grouped = group_items_by_supplier_impl(items_dict)

        # Create PO for each supplier
        for supplier_id, supplier_items in grouped.items():
            result = create_po_draft_impl(
                db=db,
                organization_id=bom.organization_id,
                supplier_id=supplier_id,
                items=supplier_items,
                bom_id=bom.id,
                bom_name=bom.name,  # Track source BOM for demo visibility
            )

            if result.get("success"):
                draft_pos.append(result)

                # Update BOM items with PO reference (confirmed = PO created but not yet sent)
                for item in supplier_items:
                    bom_item = db.query(BOMItem).filter(BOMItem.id == item["bom_item_id"]).first()
                    if bom_item:
                        bom_item.status = "confirmed"

    update_task_progress(state["task_id"], 90, f"Created {len(draft_pos)} POs", "po_generator")
    update_bom_progress(state["bom_id"], "generating_pos", 90, f"Created {len(draft_pos)} purchase orders")

    return {
        **state,
        "draft_pos": draft_pos,
        "current_agent": "po_generator",
        "current_step": f"Created {len(draft_pos)} purchase orders",
        "progress": 90,
        "messages": [f"Generated {len(draft_pos)} draft purchase orders"],
    }


async def completion_node(state: WorkflowState) -> WorkflowState:
    """Mark workflow as complete."""
    logger.info(f"Completing workflow for BOM {state['bom_id']}")

    with get_sync_db_context() as db:
        task = db.query(AgentTask).filter(AgentTask.id == state["task_id"]).first()
        if task:
            task.status = "completed"
            task.progress = 100
            task.current_step = "Completed"
            task.completed_at = datetime.utcnow()
            task.output_data = {
                "parsed_items": len(state.get("parsed_items", [])),
                "matched_items": len(state.get("matched_items", [])),
                "unmatched_items": len(state.get("unmatched_items", [])),
                "draft_pos": len(state.get("draft_pos", [])),
            }

        bom = db.query(BOM).filter(BOM.id == state["bom_id"]).first()
        if bom:
            bom.processing_status = "completed"
            bom.processing_progress = 100
            bom.processing_step = "Processing complete"

    return {
        **state,
        "completed": True,
        "progress": 100,
        "current_step": "Completed",
        "messages": ["Workflow completed successfully"],
    }


# ============ Routing Logic ============

def should_review(state: WorkflowState) -> str:
    """Determine if human review is needed."""
    if state.get("needs_human_review") and state.get("review_items"):
        return "review"
    return "generate"


def check_error(state: WorkflowState) -> str:
    """Check if there was an error."""
    if state.get("error"):
        return "error"
    return "continue"


# ============ Build Workflow Graph ============

def create_bom_workflow() -> StateGraph:
    """Create the multi-agent BOM processing workflow."""

    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("parser", parser_node)
    workflow.add_node("matcher", matcher_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("po_generator", po_generator_node)
    workflow.add_node("completion", completion_node)

    # Set entry point
    workflow.set_entry_point("parser")

    # Add edges
    workflow.add_conditional_edges(
        "parser",
        check_error,
        {
            "error": END,
            "continue": "matcher",
        }
    )

    workflow.add_conditional_edges(
        "matcher",
        should_review,
        {
            "review": "human_review",
            "generate": "po_generator",
        }
    )

    # Human review pauses - in production would wait for approval
    # For demo, we continue to PO generation
    workflow.add_edge("human_review", "po_generator")

    workflow.add_edge("po_generator", "completion")
    workflow.add_edge("completion", END)

    return workflow.compile()


# ============ Entry Point ============

async def process_bom_workflow(bom_id: int, task_id: int):
    """
    Main entry point to process a BOM through the multi-agent workflow.

    Args:
        bom_id: The BOM ID to process
        task_id: The task ID for tracking
    """
    logger.info(f"Starting BOM workflow for BOM {bom_id}, task {task_id}")

    # Get BOM details
    with get_sync_db_context() as db:
        bom = db.query(BOM).filter(BOM.id == bom_id).first()
        if not bom:
            logger.error(f"BOM {bom_id} not found")
            return

        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if task:
            task.status = "running"
            task.started_at = datetime.utcnow()

        initial_state: WorkflowState = {
            "bom_id": bom_id,
            "task_id": task_id,
            "organization_id": bom.organization_id,
            "file_path": bom.source_file_url,
            "file_type": bom.source_file_type,
            "parsed_items": [],
            "matched_items": [],
            "unmatched_items": [],
            "draft_pos": [],
            "current_agent": "orchestrator",
            "current_step": "Starting",
            "progress": 0,
            "messages": [],
            "error": None,
            "needs_human_review": False,
            "review_items": [],
            "completed": False,
        }

    try:
        # Create and run workflow
        workflow = create_bom_workflow()
        result = await workflow.ainvoke(initial_state)

        logger.info(f"Workflow completed for BOM {bom_id}: {result.get('current_step')}")

    except Exception as e:
        logger.error(f"Workflow error for BOM {bom_id}: {e}")

        with get_sync_db_context() as db:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()

            bom = db.query(BOM).filter(BOM.id == bom_id).first()
            if bom:
                bom.processing_status = "failed"
                bom.processing_error = str(e)
