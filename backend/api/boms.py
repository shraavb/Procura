"""
BOM (Bill of Materials) API endpoints.

Uses async database sessions for production performance.
"""
import os
import uuid
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.db import get_db
from models.database import BOM, BOMItem, AgentTask, Organization, SupplierPart
from models.schemas import (
    BOMResponse,
    BOMDetailResponse,
    BOMUploadResponse,
    BOMStatusResponse,
    BOMItemResponse,
    BOMItemUpdate,
    TaskResponse,
)
from config import get_settings
from core.validation import validate_file_extension, sanitize_string, check_injection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/boms", tags=["boms"])
settings = get_settings()

# File upload directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def get_default_org(db: AsyncSession) -> Organization:
    """Get or create default organization for demo."""
    result = await db.execute(select(Organization).limit(1))
    org = result.scalar_one_or_none()

    if not org:
        org = Organization(name="Demo Organization")
        db.add(org)
        await db.flush()

    return org


@router.get("", response_model=list[BOMResponse])
async def list_boms(
    status: Optional[str] = None,
    processing_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all BOMs with optional filtering."""
    query = select(BOM)

    if status:
        query = query.where(BOM.status == status)
    if processing_status:
        query = query.where(BOM.processing_status == processing_status)

    query = query.order_by(BOM.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    boms = result.scalars().all()

    return boms


@router.post("/upload", response_model=BOMUploadResponse)
async def upload_bom(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    auto_process: bool = Form(True),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a BOM file for processing.

    Accepts: Excel (.xlsx, .xls), CSV (.csv), PDF (.pdf), Images (.png, .jpg)
    """
    # Validate and sanitize inputs
    if check_injection(name):
        raise HTTPException(status_code=400, detail="Invalid characters in name")
    name = sanitize_string(name, 255)

    if description:
        if check_injection(description):
            raise HTTPException(status_code=400, detail="Invalid characters in description")
        description = sanitize_string(description, 2000)

    # Validate file type using security module
    if not validate_file_extension(file.filename, 'bom'):
        allowed_extensions = {".xlsx", ".xls", ".csv", ".pdf", ".png", ".jpg", ".jpeg"}
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Get file extension
    file_ext = os.path.splitext(file.filename)[1].lower()

    # Determine file type
    file_type_map = {
        ".xlsx": "excel",
        ".xls": "excel",
        ".csv": "csv",
        ".pdf": "pdf",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
    }
    file_type = file_type_map[file_ext]

    # Save file
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_ext}")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Get default organization
    org = await get_default_org(db)

    # Create BOM record
    bom = BOM(
        organization_id=org.id,
        name=name,
        description=description,
        source_file_url=file_path,
        source_file_name=file.filename,
        source_file_type=file_type,
        processing_status="pending" if auto_process else "draft",
    )
    db.add(bom)
    await db.flush()

    # Create processing task if auto_process
    task = None
    if auto_process:
        task = AgentTask(
            organization_id=org.id,
            task_type="bom_processing",
            entity_type="bom",
            entity_id=bom.id,
            status="pending",
            input_data={"bom_id": bom.id, "file_path": file_path},
        )
        db.add(task)
        await db.flush()

        # Queue background processing
        from agents.orchestrator import process_bom_workflow
        background_tasks.add_task(process_bom_workflow, bom.id, task.id)

    return BOMUploadResponse(
        bom=bom,
        task_id=task.id if task else 0,
        message=f"BOM uploaded successfully. {'Processing started.' if auto_process else 'Ready for manual processing.'}"
    )


@router.get("/{bom_id}", response_model=BOMDetailResponse)
async def get_bom(bom_id: int, db: AsyncSession = Depends(get_db)):
    """Get BOM details with all line items."""
    query = (
        select(BOM)
        .options(
            selectinload(BOM.items).selectinload(BOMItem.matched_supplier),
            selectinload(BOM.items).selectinload(BOMItem.matched_supplier_part).selectinload(SupplierPart.part),
            selectinload(BOM.items).selectinload(BOMItem.matched_supplier_part).selectinload(SupplierPart.supplier),
        )
        .where(BOM.id == bom_id)
    )

    result = await db.execute(query)
    bom = result.scalar_one_or_none()

    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")

    return bom


@router.get("/{bom_id}/items", response_model=list[BOMItemResponse])
async def get_bom_items(
    bom_id: int,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get all line items for a BOM."""
    query = (
        select(BOMItem)
        .options(
            selectinload(BOMItem.matched_supplier),
            selectinload(BOMItem.matched_supplier_part).selectinload(SupplierPart.part),
            selectinload(BOMItem.matched_supplier_part).selectinload(SupplierPart.supplier),
        )
        .where(BOMItem.bom_id == bom_id)
    )

    if status:
        query = query.where(BOMItem.status == status)

    query = query.order_by(BOMItem.line_number)

    result = await db.execute(query)
    items = result.scalars().all()

    return items


@router.put("/{bom_id}/items/{item_id}", response_model=BOMItemResponse)
async def update_bom_item(
    bom_id: int,
    item_id: int,
    update: BOMItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a BOM line item (manual corrections)."""
    query = select(BOMItem).where(BOMItem.id == item_id, BOMItem.bom_id == bom_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="BOM item not found")

    # Update fields
    update_data = update.model_dump(exclude_unset=True)

    # If supplier changed, try to auto-populate price from SupplierPart
    if "matched_supplier_id" in update_data and update_data["matched_supplier_id"]:
        supplier_id = update_data["matched_supplier_id"]
        item.match_method = "manual"
        item.match_confidence = 1.0

        # Try to find a SupplierPart with pricing for this part/supplier combination
        # Match by part number if available
        if item.part_number_raw:
            supplier_part_query = select(SupplierPart).where(
                SupplierPart.supplier_id == supplier_id,
                SupplierPart.supplier_part_number.ilike(f"%{item.part_number_raw}%")
            )
            result = await db.execute(supplier_part_query)
            supplier_part = result.scalar_one_or_none()

            if supplier_part and supplier_part.unit_price:
                # Auto-populate price from SupplierPart if no manual price provided
                if "unit_cost" not in update_data or update_data["unit_cost"] is None:
                    update_data["unit_cost"] = supplier_part.unit_price
                update_data["matched_supplier_part_id"] = supplier_part.id

    # Apply all updates
    for field, value in update_data.items():
        setattr(item, field, value)

    # Calculate extended_cost if unit_cost and quantity are available
    if item.unit_cost is not None and item.quantity is not None:
        from decimal import Decimal
        item.extended_cost = Decimal(str(item.unit_cost)) * Decimal(str(item.quantity))

    item.updated_at = datetime.utcnow()

    # Flush changes and refresh with relationships loaded
    await db.flush()

    # Re-fetch with eager loading to avoid async relationship issues
    query = (
        select(BOMItem)
        .where(BOMItem.id == item_id)
        .options(selectinload(BOMItem.matched_supplier))
    )
    result = await db.execute(query)
    item = result.scalar_one()

    return item


@router.post("/{bom_id}/process", response_model=TaskResponse)
async def process_bom(
    bom_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger agent workflow to process BOM."""
    result = await db.execute(select(BOM).where(BOM.id == bom_id))
    bom = result.scalar_one_or_none()

    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")

    if bom.processing_status in ["parsing", "matching", "optimizing", "generating_pos"]:
        raise HTTPException(status_code=400, detail="BOM is already being processed")

    # Reset processing state
    bom.processing_status = "pending"
    bom.processing_progress = 0
    bom.processing_step = None
    bom.processing_error = None

    # Create task
    task = AgentTask(
        organization_id=bom.organization_id,
        task_type="bom_processing",
        entity_type="bom",
        entity_id=bom.id,
        status="pending",
        input_data={"bom_id": bom.id, "file_path": bom.source_file_url},
    )
    db.add(task)
    await db.flush()

    # Queue background processing
    from agents.orchestrator import process_bom_workflow
    background_tasks.add_task(process_bom_workflow, bom.id, task.id)

    return task


@router.get("/{bom_id}/status", response_model=BOMStatusResponse)
async def get_bom_status(bom_id: int, db: AsyncSession = Depends(get_db)):
    """Get current processing status and progress."""
    result = await db.execute(select(BOM).where(BOM.id == bom_id))
    bom = result.scalar_one_or_none()

    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")

    return BOMStatusResponse(
        bom_id=bom.id,
        status=bom.status,
        processing_status=bom.processing_status,
        processing_progress=bom.processing_progress or 0,
        processing_step=bom.processing_step,
        processing_error=bom.processing_error,
        total_items=bom.total_items or 0,
        matched_items=bom.matched_items or 0,
    )


@router.delete("/{bom_id}")
async def delete_bom(bom_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a BOM and all its items."""
    result = await db.execute(select(BOM).where(BOM.id == bom_id))
    bom = result.scalar_one_or_none()

    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")

    await db.delete(bom)

    return {"message": "BOM deleted successfully"}
