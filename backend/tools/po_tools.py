"""
Tools for purchase order generation and validation.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from langchain_core.tools import tool

from models.database import PurchaseOrder, POItem, Supplier, BOMItem
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def generate_po_number_impl(db: Session) -> str:
    """Generate a unique PO number."""
    count = db.query(PurchaseOrder).count()
    return f"PO-{datetime.now().strftime('%Y%m')}-{count + 1:04d}"


def create_po_draft_impl(
    db: Session,
    organization_id: int,
    supplier_id: int,
    items: list[dict],
    bom_id: Optional[int] = None,
    bom_name: Optional[str] = None,
    required_date: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Create a draft purchase order.

    Args:
        db: Database session
        organization_id: Organization ID
        supplier_id: Supplier ID
        items: List of item dictionaries with part details
        bom_id: Optional associated BOM ID
        bom_name: Optional name of source BOM (for display)
        required_date: Optional required delivery date
        notes: Optional notes

    Returns:
        Dictionary with created PO details
    """
    # Verify supplier exists
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        return {"error": f"Supplier {supplier_id} not found"}

    # Determine if this is auto-generated from a BOM
    is_auto_generated = bom_id is not None

    # Create PO
    po = PurchaseOrder(
        organization_id=organization_id,
        po_number=generate_po_number_impl(db),
        supplier_id=supplier_id,
        bom_id=bom_id,
        is_auto_generated=is_auto_generated,
        source_bom_name=bom_name,
        status="draft",
        notes=notes,
    )

    if required_date:
        try:
            po.required_date = datetime.strptime(required_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    db.add(po)
    db.flush()

    # Add line items
    subtotal = Decimal("0")
    for idx, item in enumerate(items, start=1):
        unit_price = Decimal(str(item.get("unit_price", 0)))
        quantity = Decimal(str(item.get("quantity", 1)))
        extended = unit_price * quantity

        po_item = POItem(
            po_id=po.id,
            line_number=idx,
            bom_item_id=item.get("bom_item_id"),
            part_id=item.get("part_id"),
            supplier_part_id=item.get("supplier_part_id"),
            part_number=item.get("part_number"),
            description=item.get("description"),
            quantity=quantity,
            unit_of_measure=item.get("unit_of_measure", "EA"),
            unit_price=unit_price,
            extended_price=extended,
        )
        db.add(po_item)
        subtotal += extended

    po.subtotal = subtotal
    po.total = subtotal  # Tax and shipping added later if needed
    po.requires_approval = po.total >= Decimal(str(settings.po_approval_threshold))

    db.commit()
    db.refresh(po)

    return {
        "success": True,
        "po_id": po.id,
        "po_number": po.po_number,
        "supplier_id": supplier_id,
        "supplier_name": supplier.name,
        "item_count": len(items),
        "subtotal": float(po.subtotal),
        "total": float(po.total),
        "requires_approval": po.requires_approval,
        "status": po.status,
        "is_auto_generated": po.is_auto_generated,
        "source_bom_name": po.source_bom_name,
        "bom_id": po.bom_id,
    }


def validate_po_impl(po_id: int, db: Session) -> dict:
    """
    Validate a purchase order for completeness and correctness.

    Args:
        po_id: Purchase order ID
        db: Database session

    Returns:
        Dictionary with validation results
    """
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()

    if not po:
        return {"valid": False, "errors": [f"PO {po_id} not found"]}

    errors = []
    warnings = []

    # Check supplier
    if not po.supplier_id:
        errors.append("Missing supplier")
    else:
        supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
        if not supplier:
            errors.append(f"Invalid supplier ID: {po.supplier_id}")
        elif supplier.status != "active":
            warnings.append(f"Supplier '{supplier.name}' is not active")

    # Check line items
    items = db.query(POItem).filter(POItem.po_id == po_id).all()

    if not items:
        errors.append("No line items on PO")
    else:
        for item in items:
            if not item.quantity or item.quantity <= 0:
                errors.append(f"Line {item.line_number}: Invalid quantity")
            if not item.unit_price or item.unit_price < 0:
                errors.append(f"Line {item.line_number}: Invalid unit price")
            if not item.part_number and not item.description:
                errors.append(f"Line {item.line_number}: Missing part number and description")

    # Check totals
    calculated_subtotal = sum(
        (item.extended_price or Decimal("0")) for item in items
    )
    if po.subtotal and abs(float(po.subtotal) - float(calculated_subtotal)) > 0.01:
        warnings.append(f"Subtotal mismatch: PO shows ${po.subtotal}, calculated ${calculated_subtotal}")

    # Check for unusually high amounts
    if po.total and po.total > 100000:
        warnings.append(f"High value PO: ${po.total:,.2f}")

    return {
        "valid": len(errors) == 0,
        "po_id": po_id,
        "po_number": po.po_number,
        "errors": errors,
        "warnings": warnings,
        "item_count": len(items),
        "total": float(po.total) if po.total else 0,
    }


def calculate_po_totals_impl(po_id: int, db: Session, tax_rate: float = 0, shipping: float = 0) -> dict:
    """
    Calculate and update PO totals.

    Args:
        po_id: Purchase order ID
        db: Database session
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%)
        shipping: Shipping amount

    Returns:
        Dictionary with calculated totals
    """
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()

    if not po:
        return {"error": f"PO {po_id} not found"}

    items = db.query(POItem).filter(POItem.po_id == po_id).all()

    # Calculate subtotal
    subtotal = Decimal("0")
    for item in items:
        if item.quantity and item.unit_price:
            extended = item.quantity * item.unit_price
            item.extended_price = extended
            subtotal += extended

    # Calculate tax and total
    tax = subtotal * Decimal(str(tax_rate))
    total = subtotal + tax + Decimal(str(shipping))

    # Update PO
    po.subtotal = subtotal
    po.tax = tax
    po.shipping = Decimal(str(shipping))
    po.total = total
    po.requires_approval = total >= Decimal(str(settings.po_approval_threshold))

    db.commit()

    return {
        "po_id": po_id,
        "po_number": po.po_number,
        "subtotal": float(subtotal),
        "tax": float(tax),
        "shipping": float(po.shipping),
        "total": float(total),
        "requires_approval": po.requires_approval,
    }


def group_items_by_supplier_impl(bom_items: list[dict]) -> dict[int, list[dict]]:
    """
    Group BOM items by their matched supplier.

    Args:
        bom_items: List of BOM items with supplier matches

    Returns:
        Dictionary mapping supplier_id to list of items
    """
    grouped = {}

    for item in bom_items:
        supplier_id = item.get("matched_supplier_id")
        if not supplier_id:
            continue

        if supplier_id not in grouped:
            grouped[supplier_id] = []

        grouped[supplier_id].append({
            "bom_item_id": item.get("id"),
            "part_id": item.get("part_id"),
            "supplier_part_id": item.get("matched_supplier_part_id"),
            "part_number": item.get("part_number_raw"),
            "description": item.get("description_raw"),
            "quantity": item.get("quantity"),
            "unit_of_measure": item.get("unit_of_measure"),
            "unit_price": item.get("unit_cost"),
        })

    return grouped


# LangChain tool wrappers
@tool
def create_po_draft(supplier_id: int, items: list[dict]) -> str:
    """
    Create a draft purchase order for a supplier.

    Args:
        supplier_id: The supplier ID to create PO for
        items: List of items with part_number, description, quantity, unit_price

    Returns:
        JSON string with created PO details
    """
    return f"Create PO for supplier {supplier_id} with {len(items)} items"


@tool
def validate_po(po_id: int) -> str:
    """
    Validate a purchase order for completeness.

    Args:
        po_id: The purchase order ID to validate

    Returns:
        JSON string with validation results
    """
    return f"Validate PO {po_id}"


@tool
def calculate_po_totals(po_id: int, tax_rate: float = 0, shipping: float = 0) -> str:
    """
    Calculate and update PO totals including tax and shipping.

    Args:
        po_id: The purchase order ID
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%)
        shipping: Shipping amount

    Returns:
        JSON string with calculated totals
    """
    return f"Calculate totals for PO {po_id}"
