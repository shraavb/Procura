"""
Purchase Order API endpoints.
"""
import logging
from typing import Optional
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.db import get_db
from models.database import PurchaseOrder, POItem, Supplier, ApprovalRequest, Organization, BOMItem
from models.schemas import (
    POResponse,
    PODetailResponse,
    POListResponse,
    POCreate,
    POApprovalRequest,
    POReceiptRequest,
)
from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pos", tags=["purchase_orders"])
settings = get_settings()


async def generate_po_number(db: AsyncSession) -> str:
    """Generate a unique PO number."""
    result = await db.execute(select(func.count()).select_from(PurchaseOrder))
    count = result.scalar()
    return f"PO-{datetime.now().strftime('%Y%m')}-{count + 1:04d}"


async def get_default_org(db: AsyncSession) -> Organization:
    """Get or create default organization for demo."""
    result = await db.execute(select(Organization).limit(1))
    org = result.scalar_one_or_none()
    if not org:
        org = Organization(name="Demo Organization")
        db.add(org)
        await db.commit()
        await db.refresh(org)
    return org


@router.get("", response_model=POListResponse)
async def list_purchase_orders(
    status: Optional[str] = None,
    supplier_id: Optional[int] = None,
    bom_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List purchase orders with filtering."""
    query = select(PurchaseOrder).options(selectinload(PurchaseOrder.supplier))

    if status:
        query = query.where(PurchaseOrder.status == status)
    if supplier_id:
        query = query.where(PurchaseOrder.supplier_id == supplier_id)
    if bom_id:
        query = query.where(PurchaseOrder.bom_id == bom_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    query = query.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    pos = result.scalars().all()

    return POListResponse(
        items=pos,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=POResponse)
async def create_purchase_order(
    po: POCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new purchase order."""
    org = await get_default_org(db)

    # Verify supplier exists
    result = await db.execute(
        select(Supplier).where(Supplier.id == po.supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Create PO
    db_po = PurchaseOrder(
        organization_id=org.id,
        po_number=await generate_po_number(db),
        supplier_id=po.supplier_id,
        bom_id=po.bom_id,
        required_date=po.required_date,
        ship_to_address=po.ship_to_address,
        notes=po.notes,
        status="draft",
    )
    db.add(db_po)
    await db.flush()  # Get PO ID

    # Add line items
    subtotal = Decimal(0)
    for idx, item_data in enumerate(po.items, start=1):
        extended = item_data.quantity * item_data.unit_price
        item = POItem(
            po_id=db_po.id,
            line_number=item_data.line_number or idx,
            part_number=item_data.part_number,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_of_measure=item_data.unit_of_measure,
            unit_price=item_data.unit_price,
            extended_price=extended,
        )
        db.add(item)
        subtotal += extended

    # Calculate totals
    db_po.subtotal = subtotal
    db_po.total = subtotal + (db_po.tax or 0) + (db_po.shipping or 0)

    # Check if approval required
    db_po.requires_approval = db_po.total >= settings.po_approval_threshold

    await db.commit()
    await db.refresh(db_po)

    return db_po


@router.get("/{po_id}", response_model=PODetailResponse)
async def get_purchase_order(po_id: int, db: AsyncSession = Depends(get_db)):
    """Get PO details with all line items."""
    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items),
        )
        .where(PurchaseOrder.id == po_id)
    )
    po = result.scalar_one_or_none()

    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    return po


@router.post("/{po_id}/submit", response_model=POResponse)
async def submit_for_approval(po_id: int, db: AsyncSession = Depends(get_db)):
    """Submit a draft PO for approval."""
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.supplier))
        .where(PurchaseOrder.id == po_id)
    )
    po = result.scalar_one_or_none()

    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if po.status != "draft":
        raise HTTPException(status_code=400, detail=f"Cannot submit PO in '{po.status}' status")

    if po.requires_approval:
        po.status = "pending_approval"

        # Create approval request
        approval = ApprovalRequest(
            organization_id=po.organization_id,
            entity_type="purchase_order",
            entity_id=po.id,
            request_type="po_approval",
            title=f"PO Approval: {po.po_number}",
            description=f"Purchase order for {po.supplier.name if po.supplier else 'Unknown'} - ${po.total:,.2f}",
            details={
                "po_number": po.po_number,
                "supplier_name": po.supplier.name if po.supplier else None,
                "total": float(po.total) if po.total else 0,
                "item_count": len(po.items) if po.items else 0,
            },
        )
        db.add(approval)
    else:
        po.status = "approved"
        po.approved_at = datetime.utcnow()

    await db.commit()
    await db.refresh(po)

    return po


@router.post("/{po_id}/approve", response_model=POResponse)
async def approve_purchase_order(
    po_id: int,
    approval: POApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a purchase order."""
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.supplier))
        .where(PurchaseOrder.id == po_id)
    )
    po = result.scalar_one_or_none()

    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if po.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Cannot approve PO in '{po.status}' status")

    if approval.approved:
        po.status = "approved"
        po.approved_at = datetime.utcnow()
    else:
        po.status = "draft"  # Return to draft for revision
        po.rejection_reason = approval.notes

    # Update approval request
    result = await db.execute(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.entity_type == "purchase_order",
            ApprovalRequest.entity_id == po.id,
            ApprovalRequest.status == "pending",
        )
    )
    approval_req = result.scalar_one_or_none()

    if approval_req:
        approval_req.status = "approved" if approval.approved else "rejected"
        approval_req.review_notes = approval.notes
        approval_req.reviewed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(po)

    return po


@router.post("/{po_id}/send", response_model=POResponse)
async def send_purchase_order(po_id: int, db: AsyncSession = Depends(get_db)):
    """Send approved PO to supplier."""
    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items),
        )
        .where(PurchaseOrder.id == po_id)
    )
    po = result.scalar_one_or_none()

    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if po.status != "approved":
        raise HTTPException(status_code=400, detail=f"Cannot send PO in '{po.status}' status. Must be approved first.")

    # Update PO status
    po.status = "sent"
    po.sent_at = datetime.utcnow()

    # Update linked BOM items to "ordered" status
    for po_item in po.items:
        if po_item.bom_item_id:
            result = await db.execute(
                select(BOMItem).where(BOMItem.id == po_item.bom_item_id)
            )
            bom_item = result.scalar_one_or_none()
            if bom_item:
                bom_item.status = "ordered"

    await db.commit()
    await db.refresh(po)

    return po


@router.post("/{po_id}/acknowledge", response_model=POResponse)
async def acknowledge_purchase_order(po_id: int, db: AsyncSession = Depends(get_db)):
    """Record supplier acknowledgment of PO."""
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.supplier))
        .where(PurchaseOrder.id == po_id)
    )
    po = result.scalar_one_or_none()

    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if po.status != "sent":
        raise HTTPException(status_code=400, detail=f"Cannot acknowledge PO in '{po.status}' status")

    po.status = "acknowledged"
    po.acknowledged_at = datetime.utcnow()

    await db.commit()
    await db.refresh(po)

    return po


@router.post("/{po_id}/receive", response_model=POResponse)
async def record_receipt(
    po_id: int,
    receipt: POReceiptRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record receipt of goods against PO."""
    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items),
        )
        .where(PurchaseOrder.id == po_id)
    )
    po = result.scalar_one_or_none()

    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if po.status not in ["sent", "acknowledged", "shipped"]:
        raise HTTPException(status_code=400, detail=f"Cannot receive against PO in '{po.status}' status")

    # Update received quantities
    for receipt_item in receipt.items:
        po_item = next(
            (item for item in po.items if item.id == receipt_item.get("po_item_id")),
            None
        )
        if po_item:
            po_item.received_quantity = (po_item.received_quantity or 0) + Decimal(str(receipt_item.get("received_quantity", 0)))

    # Check if fully received
    all_received = all(
        item.received_quantity >= item.quantity
        for item in po.items
    )

    if all_received:
        po.status = "received"
        po.received_at = datetime.utcnow()

    await db.commit()
    await db.refresh(po)

    return po


@router.delete("/{po_id}")
async def delete_purchase_order(po_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a purchase order (only drafts)."""
    result = await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == po_id)
    )
    po = result.scalar_one_or_none()

    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    if po.status != "draft":
        raise HTTPException(status_code=400, detail="Can only delete draft purchase orders")

    await db.delete(po)
    await db.commit()

    return {"message": "Purchase order deleted successfully"}
