#!/usr/bin/env python3
"""
Database seeding script for Procura demo.

Seeds the database with:
- Suppliers with capabilities and certifications
- Parts catalog with pricing from multiple suppliers
- Demo BOMs in various processing states
- Sample purchase orders
- Approval requests

Usage:
    python scripts/seed_database.py

Or with Docker:
    docker-compose exec backend python scripts/seed_database.py
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import random

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from models.db import get_sync_db_context, init_db_sync
from models.database import (
    Organization,
    Supplier,
    Part,
    SupplierPart,
    BOM,
    BOMItem,
    PurchaseOrder,
    POItem,
    AgentTask,
    ApprovalRequest,
)
from config import get_settings

settings = get_settings()

# Data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "seed_data"
DEMO_BOMS_DIR = Path(__file__).parent.parent.parent / "data" / "demo_boms"


def load_json(filename: str) -> list:
    """Load JSON file from seed data directory."""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        print(f"Warning: {filepath} not found")
        return []
    with open(filepath) as f:
        return json.load(f)


def clear_database(db):
    """Clear all data from tables (in correct order for foreign keys)."""
    print("Clearing existing data...")
    tables = [
        "approval_requests",
        "agent_tasks",
        "po_items",
        "purchase_orders",
        "bom_items",
        "boms",
        "supplier_parts",
        "parts",
        "suppliers",
        "organizations",
    ]
    for table in tables:
        try:
            db.execute(text(f"DELETE FROM {table}"))
        except Exception as e:
            print(f"  Warning: Could not clear {table}: {e}")
    db.commit()
    print("  Done.")


def seed_organization(db) -> Organization:
    """Create demo organization."""
    print("Creating organization...")
    org = Organization(
        name="Procura Demo Corp",
        settings={
            "currency": "USD",
            "po_approval_threshold": 10000.0,
            "auto_approve_trusted_suppliers": True,
            "match_confidence_threshold": 0.8,
        }
    )
    db.add(org)
    db.flush()
    print(f"  Created: {org.name}")
    return org


def seed_suppliers(db, org: Organization) -> dict:
    """Seed suppliers from JSON file."""
    print("Seeding suppliers...")
    suppliers_data = load_json("suppliers.json")
    suppliers = {}

    for data in suppliers_data:
        supplier = Supplier(
            organization_id=org.id,
            name=data["name"],
            code=data["code"],
            description=data.get("description"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            lead_time_days=data.get("lead_time_days", 5),
            capabilities=data.get("capabilities", []),
            certifications=data.get("certifications", []),
            status="active",
        )
        db.add(supplier)
        db.flush()
        suppliers[data["code"]] = supplier
        print(f"  Created: {supplier.name} ({supplier.code})")

    return suppliers


def seed_parts(db, org: Organization, suppliers: dict) -> dict:
    """Seed parts and supplier-part relationships."""
    print("Seeding parts catalog...")

    # Load both parts files
    parts_data = load_json("parts.json")
    parts_extended = load_json("parts_extended.json")
    all_parts_data = parts_data + parts_extended

    parts = {}

    for data in all_parts_data:
        # Skip if already exists
        if data["part_number"] in parts:
            continue

        part = Part(
            organization_id=org.id,
            part_number=data["part_number"],
            name=data["name"],
            description=data.get("description"),
            category=data.get("category"),
            unit_of_measure=data.get("unit_of_measure", "EA"),
        )
        db.add(part)
        db.flush()
        parts[data["part_number"]] = part

        # Add supplier-part relationships with pricing
        for sp_data in data.get("suppliers", []):
            supplier = suppliers.get(sp_data["supplier_code"])
            if supplier:
                # Generate price breaks
                base_price = sp_data["price"]
                price_breaks = [
                    {"quantity": 1, "price": base_price},
                    {"quantity": 10, "price": round(base_price * 0.95, 4)},
                    {"quantity": 100, "price": round(base_price * 0.88, 4)},
                    {"quantity": 1000, "price": round(base_price * 0.80, 4)},
                ]

                supplier_part = SupplierPart(
                    supplier_id=supplier.id,
                    part_id=part.id,
                    supplier_part_number=sp_data.get("supplier_pn"),
                    unit_price=base_price,
                    currency="USD",
                    lead_time_days=sp_data.get("lead_time", supplier.lead_time_days),
                    min_order_qty=sp_data.get("moq", 1),
                    price_breaks=price_breaks,
                    is_preferred=sp_data.get("preferred", False),
                )
                db.add(supplier_part)

        print(f"  Created: {part.part_number} - {part.name}")

    db.flush()
    return parts


def seed_boms(db, org: Organization, parts: dict, suppliers: dict) -> list:
    """Seed demo BOMs."""
    print("Seeding demo BOMs...")
    boms_data = load_json("demo_boms.json")
    boms = []

    for data in boms_data:
        bom = BOM(
            organization_id=org.id,
            name=data["name"],
            description=data.get("description"),
            status=data.get("status", "active"),
            processing_status=data.get("processing_status", "pending"),
            total_items=data.get("total_items", 0),
            matched_items=data.get("matched_items", 0),
            total_cost=data.get("total_cost"),
            source_file_name=f"{data['name'].lower().replace(' ', '_')}.csv",
            source_file_type="csv",
        )
        db.add(bom)
        db.flush()

        # Add BOM items
        for item_data in data.get("items", []):
            part = parts.get(item_data["part_number_raw"])
            supplier = None
            supplier_part = None

            if part and item_data.get("status") == "matched":
                # Find a supplier part
                for sp in db.query(SupplierPart).filter(SupplierPart.part_id == part.id).all():
                    supplier_part = sp
                    supplier = suppliers.get(list(suppliers.keys())[0])
                    break

            bom_item = BOMItem(
                bom_id=bom.id,
                line_number=item_data["line_number"],
                part_number_raw=item_data["part_number_raw"],
                description_raw=item_data.get("description_raw"),
                quantity=item_data.get("quantity", 1),
                unit_of_measure="EA",
                status=item_data.get("status", "pending"),
                match_confidence=item_data.get("match_confidence"),
                match_method="auto" if item_data.get("match_confidence", 0) > 0.8 else None,
                part_id=part.id if part else None,
                matched_supplier_id=supplier.id if supplier else None,
                matched_supplier_part_id=supplier_part.id if supplier_part else None,
                unit_cost=supplier_part.unit_price if supplier_part else None,
            )
            db.add(bom_item)

        boms.append(bom)
        print(f"  Created: {bom.name} ({len(data.get('items', []))} items)")

    db.flush()
    return boms


def seed_purchase_orders(db, org: Organization, suppliers: dict, parts: dict) -> list:
    """Seed demo purchase orders."""
    print("Seeding purchase orders...")
    pos_data = load_json("demo_purchase_orders.json")
    pos = []

    for data in pos_data:
        supplier = suppliers.get(data["supplier_code"])
        if not supplier:
            print(f"  Warning: Supplier {data['supplier_code']} not found, skipping PO")
            continue

        po = PurchaseOrder(
            organization_id=org.id,
            supplier_id=supplier.id,
            po_number=data["po_number"],
            status=data.get("status", "draft"),
            total=data.get("total", 0),
            currency=data.get("currency", "USD"),
            notes=data.get("notes"),
            approved_at=datetime.fromisoformat(data["approved_at"].replace("Z", "+00:00")) if data.get("approved_at") else None,
            sent_at=datetime.fromisoformat(data["sent_at"].replace("Z", "+00:00")) if data.get("sent_at") else None,
        )
        db.add(po)
        db.flush()

        # Add PO items
        for idx, item_data in enumerate(data.get("items", []), start=1):
            part = parts.get(item_data.get("part_number"))

            po_item = POItem(
                po_id=po.id,
                line_number=item_data.get("line_number", idx),
                part_id=part.id if part else None,
                part_number=item_data.get("part_number"),
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                extended_price=item_data.get("line_total", item_data["quantity"] * item_data["unit_price"]),
            )
            db.add(po_item)

        pos.append(po)
        print(f"  Created: {po.po_number} - ${po.total:.2f} ({po.status})")

    db.flush()
    return pos


def seed_approval_requests(db, org: Organization, pos: list, boms: list):
    """Create approval requests for pending items."""
    print("Creating approval requests...")

    # PO approval for pending POs over threshold
    for po in pos:
        if po.status == "pending" and po.total > settings.po_approval_threshold:
            approval = ApprovalRequest(
                organization_id=org.id,
                entity_type="purchase_order",
                entity_id=po.id,
                request_type="po_approval",
                title=f"PO Approval: {po.po_number}",
                description=f"Purchase order {po.po_number} exceeds approval threshold of ${settings.po_approval_threshold:,.2f}",
                status="pending",
                details={
                    "po_number": po.po_number,
                    "total": float(po.total) if po.total else 0,
                    "supplier": po.supplier.name if po.supplier else "Unknown",
                    "item_count": len(po.items) if hasattr(po, 'items') else 0,
                },
            )
            db.add(approval)
            print(f"  Created approval request for {po.po_number}")

    # Supplier match approvals for low-confidence matches
    for bom in boms:
        for item in db.query(BOMItem).filter(BOMItem.bom_id == bom.id).all():
            if item.status == "pending_review" or (item.match_confidence and item.match_confidence < 0.8):
                confidence_str = f"{item.match_confidence:.0%}" if item.match_confidence else "0%"
                approval = ApprovalRequest(
                    organization_id=org.id,
                    entity_type="supplier_match",
                    entity_id=item.id,
                    request_type="match_review",
                    title=f"Match Review: {item.part_number_raw}",
                    description=f"Low confidence match ({confidence_str}) for part {item.part_number_raw}",
                    status="pending",
                    details={
                        "bom_name": bom.name,
                        "part_number": item.part_number_raw,
                        "confidence": float(item.match_confidence) if item.match_confidence else 0,
                    },
                )
                db.add(approval)
                print(f"  Created approval request for {item.part_number_raw}")

    db.flush()


def seed_agent_tasks(db, org: Organization, boms: list):
    """Create sample agent tasks showing workflow history."""
    print("Creating agent task history...")

    for bom in boms:
        if bom.processing_status == "completed":
            # Create completed task
            task = AgentTask(
                organization_id=org.id,
                task_type="bom_processing",
                entity_type="bom",
                entity_id=bom.id,
                status="completed",
                progress=100,
                current_step="completed",
                input_data={"bom_id": bom.id},
                output_data={
                    "items_parsed": bom.total_items,
                    "items_matched": bom.matched_items,
                    "total_cost": float(bom.total_cost) if bom.total_cost else 0,
                },
                started_at=datetime.utcnow() - timedelta(hours=2),
                completed_at=datetime.utcnow() - timedelta(hours=1, minutes=45),
            )
            db.add(task)
            print(f"  Created completed task for {bom.name}")

        elif bom.processing_status == "matching":
            # Create in-progress task
            task = AgentTask(
                organization_id=org.id,
                task_type="bom_processing",
                entity_type="bom",
                entity_id=bom.id,
                status="running",
                progress=65,
                current_step="matching",
                input_data={"bom_id": bom.id},
                started_at=datetime.utcnow() - timedelta(minutes=15),
            )
            db.add(task)
            print(f"  Created in-progress task for {bom.name}")

    db.flush()


def main():
    """Main seeding function."""
    print("=" * 60)
    print("Procura Database Seeding Script")
    print("=" * 60)
    print()

    # Initialize database tables
    print("Initializing database tables...")
    init_db_sync()
    print("  Done.")
    print()

    with get_sync_db_context() as db:
        # Clear existing data
        clear_database(db)
        print()

        # Seed in order
        org = seed_organization(db)
        print()

        suppliers = seed_suppliers(db, org)
        print()

        parts = seed_parts(db, org, suppliers)
        print()

        boms = seed_boms(db, org, parts, suppliers)
        print()

        pos = seed_purchase_orders(db, org, suppliers, parts)
        print()

        seed_approval_requests(db, org, pos, boms)
        print()

        seed_agent_tasks(db, org, boms)
        print()

        # Commit all changes
        db.commit()

    print("=" * 60)
    print("Seeding complete!")
    print()
    print("Summary:")
    print(f"  - 1 Organization")
    print(f"  - {len(suppliers)} Suppliers")
    print(f"  - {len(parts)} Parts")
    print(f"  - {len(boms)} BOMs")
    print(f"  - {len(pos)} Purchase Orders")
    print("=" * 60)


if __name__ == "__main__":
    main()
