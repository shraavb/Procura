"""
Seed database with demo data.
"""
import json
import asyncio
from pathlib import Path
from decimal import Decimal

from models.db import get_sync_db_context, init_db_sync
from models.database import Organization, Supplier, Part, SupplierPart
from services.embedding import get_embedding_service
from config import get_settings

settings = get_settings()


def seed_database():
    """Seed the database with demo suppliers and parts."""
    print("Initializing database...")
    init_db_sync()

    data_dir = Path("/data/seed_data")

    with get_sync_db_context() as db:
        # Create demo organization
        org = db.query(Organization).filter(Organization.name == "Demo Organization").first()
        if not org:
            org = Organization(name="Demo Organization")
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"Created organization: {org.name}")

        # Load and seed suppliers
        suppliers_file = data_dir / "suppliers.json"
        if suppliers_file.exists():
            with open(suppliers_file) as f:
                suppliers_data = json.load(f)

            embedding_service = None
            if settings.openai_api_key:
                embedding_service = get_embedding_service()

            supplier_map = {}
            for s_data in suppliers_data:
                # Check if exists
                existing = db.query(Supplier).filter(Supplier.code == s_data["code"]).first()
                if existing:
                    supplier_map[s_data["code"]] = existing
                    print(f"Supplier already exists: {s_data['name']}")
                    continue

                supplier = Supplier(
                    organization_id=org.id,
                    name=s_data["name"],
                    code=s_data["code"],
                    description=s_data.get("description"),
                    contact_email=s_data.get("contact_email"),
                    contact_phone=s_data.get("contact_phone"),
                    lead_time_days=s_data.get("lead_time_days"),
                    capabilities=s_data.get("capabilities", []),
                    certifications=s_data.get("certifications", []),
                    status="active",
                )

                # Generate embedding for description
                if embedding_service and s_data.get("description"):
                    try:
                        embedding = asyncio.run(embedding_service.create_embedding(s_data["description"]))
                        supplier.description_embedding = embedding
                    except Exception as e:
                        print(f"Warning: Failed to create embedding for {s_data['name']}: {e}")

                db.add(supplier)
                db.commit()
                db.refresh(supplier)
                supplier_map[s_data["code"]] = supplier
                print(f"Created supplier: {supplier.name}")

        # Load and seed parts
        parts_file = data_dir / "parts.json"
        if parts_file.exists():
            with open(parts_file) as f:
                parts_data = json.load(f)

            for p_data in parts_data:
                # Check if exists
                existing = db.query(Part).filter(
                    Part.organization_id == org.id,
                    Part.part_number == p_data["part_number"]
                ).first()

                if existing:
                    part = existing
                    print(f"Part already exists: {p_data['name']}")
                else:
                    part = Part(
                        organization_id=org.id,
                        part_number=p_data["part_number"],
                        name=p_data["name"],
                        description=p_data.get("description"),
                        category=p_data.get("category"),
                        unit_of_measure=p_data.get("unit_of_measure", "EA"),
                    )

                    # Generate embedding
                    if embedding_service and p_data.get("description"):
                        try:
                            embedding = asyncio.run(embedding_service.create_embedding(p_data["description"]))
                            part.description_embedding = embedding
                        except Exception as e:
                            print(f"Warning: Failed to create embedding for {p_data['name']}: {e}")

                    db.add(part)
                    db.commit()
                    db.refresh(part)
                    print(f"Created part: {part.name}")

                # Add supplier relationships
                for sp_data in p_data.get("suppliers", []):
                    supplier = supplier_map.get(sp_data["supplier_code"])
                    if not supplier:
                        print(f"Warning: Supplier {sp_data['supplier_code']} not found")
                        continue

                    # Check if relationship exists
                    existing_sp = db.query(SupplierPart).filter(
                        SupplierPart.supplier_id == supplier.id,
                        SupplierPart.part_id == part.id
                    ).first()

                    if existing_sp:
                        continue

                    supplier_part = SupplierPart(
                        supplier_id=supplier.id,
                        part_id=part.id,
                        supplier_part_number=sp_data.get("supplier_pn"),
                        unit_price=Decimal(str(sp_data["price"])),
                        lead_time_days=sp_data.get("lead_time"),
                        min_order_qty=sp_data.get("moq", 1),
                        is_preferred=sp_data.get("preferred", False),
                    )
                    db.add(supplier_part)

                db.commit()

    print("\nDatabase seeding complete!")
    print(f"- Organization: Demo Organization")
    print(f"- Suppliers: {len(suppliers_data) if 'suppliers_data' in dir() else 0}")
    print(f"- Parts: {len(parts_data) if 'parts_data' in dir() else 0}")


if __name__ == "__main__":
    seed_database()
