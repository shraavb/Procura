"""
Tools for searching and matching suppliers/parts.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session
from langchain_core.tools import tool

from models.database import Supplier, Part, SupplierPart
from services.embedding import get_embedding_service
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def search_supplier_catalog_impl(
    db: Session,
    part_number: str,
    organization_id: int,
) -> dict:
    """
    Search for exact part number matches in supplier catalog.

    Args:
        db: Database session
        part_number: Part number to search for
        organization_id: Organization ID

    Returns:
        Dictionary with matching suppliers and parts
    """
    # Normalize part number for comparison
    pn_normalized = part_number.strip().upper().replace("-", "").replace(" ", "")

    # Search in supplier_parts by supplier_part_number
    matches = (
        db.query(SupplierPart, Supplier, Part)
        .join(Supplier, SupplierPart.supplier_id == Supplier.id)
        .join(Part, SupplierPart.part_id == Part.id)
        .filter(Supplier.organization_id == organization_id)
        .filter(Supplier.status == "active")
        .all()
    )

    exact_matches = []
    fuzzy_matches = []

    for sp, supplier, part in matches:
        # Check supplier part number
        sp_pn = (sp.supplier_part_number or "").strip().upper().replace("-", "").replace(" ", "")
        part_pn = (part.part_number or "").strip().upper().replace("-", "").replace(" ", "")

        if sp_pn == pn_normalized or part_pn == pn_normalized:
            exact_matches.append({
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "supplier_code": supplier.code,
                "supplier_part_id": sp.id,
                "part_id": part.id,
                "part_number": part.part_number,
                "supplier_part_number": sp.supplier_part_number,
                "description": part.description,
                "unit_price": float(sp.unit_price) if sp.unit_price else None,
                "lead_time_days": sp.lead_time_days or supplier.lead_time_days,
                "min_order_qty": sp.min_order_qty,
                "is_preferred": sp.is_preferred,
                "confidence": 1.0,
                "match_method": "exact",
            })
        elif pn_normalized in sp_pn or pn_normalized in part_pn:
            fuzzy_matches.append({
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "supplier_code": supplier.code,
                "supplier_part_id": sp.id,
                "part_id": part.id,
                "part_number": part.part_number,
                "supplier_part_number": sp.supplier_part_number,
                "description": part.description,
                "unit_price": float(sp.unit_price) if sp.unit_price else None,
                "lead_time_days": sp.lead_time_days or supplier.lead_time_days,
                "min_order_qty": sp.min_order_qty,
                "is_preferred": sp.is_preferred,
                "confidence": 0.85,
                "match_method": "fuzzy",
            })

    # Sort by preference and price
    all_matches = exact_matches + fuzzy_matches
    all_matches.sort(key=lambda x: (
        -x["confidence"],
        -int(x["is_preferred"]),
        x["unit_price"] or 9999999,
    ))

    return {
        "part_number_searched": part_number,
        "exact_matches": len(exact_matches),
        "fuzzy_matches": len(fuzzy_matches),
        "matches": all_matches[:10],  # Top 10
    }


def semantic_part_search_impl(
    db: Session,
    description: str,
    organization_id: int,
    top_k: int = 5,
    min_similarity: float = 0.5,
) -> dict:
    """
    Semantic search for parts using description embeddings.

    Args:
        db: Database session
        description: Description to search for
        organization_id: Organization ID
        top_k: Number of results to return
        min_similarity: Minimum similarity threshold

    Returns:
        Dictionary with matching parts and suppliers
    """
    embedding_service = get_embedding_service()

    # Create query embedding
    query_embedding = embedding_service.create_embedding(description)

    # Search parts by embedding similarity
    results = (
        db.query(
            Part,
            Part.description_embedding.cosine_distance(query_embedding).label("distance")
        )
        .filter(Part.organization_id == organization_id)
        .filter(Part.description_embedding.isnot(None))
        .order_by("distance")
        .limit(top_k * 2)
        .all()
    )

    matches = []
    for part, distance in results:
        similarity = 1 - distance
        if similarity < min_similarity:
            continue

        # Get supplier options for this part
        supplier_parts = (
            db.query(SupplierPart, Supplier)
            .join(Supplier, SupplierPart.supplier_id == Supplier.id)
            .filter(SupplierPart.part_id == part.id)
            .filter(Supplier.status == "active")
            .all()
        )

        for sp, supplier in supplier_parts:
            matches.append({
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "supplier_code": supplier.code,
                "supplier_part_id": sp.id,
                "part_id": part.id,
                "part_number": part.part_number,
                "supplier_part_number": sp.supplier_part_number,
                "description": part.description,
                "unit_price": float(sp.unit_price) if sp.unit_price else None,
                "lead_time_days": sp.lead_time_days or supplier.lead_time_days,
                "min_order_qty": sp.min_order_qty,
                "is_preferred": sp.is_preferred,
                "confidence": similarity,
                "match_method": "semantic",
            })

        if len(matches) >= top_k:
            break

    # Sort by confidence and price
    matches.sort(key=lambda x: (
        -x["confidence"],
        -int(x["is_preferred"]),
        x["unit_price"] or 9999999,
    ))

    return {
        "description_searched": description,
        "matches": matches[:top_k],
    }


def find_alternative_parts_impl(
    db: Session,
    part_id: int,
    organization_id: int,
) -> dict:
    """
    Find alternative/substitute parts for a given part.

    Args:
        db: Database session
        part_id: Original part ID
        organization_id: Organization ID

    Returns:
        Dictionary with alternative parts and suppliers
    """
    # Get original part
    original = db.query(Part).filter(Part.id == part_id).first()

    if not original:
        return {
            "error": f"Part {part_id} not found",
            "alternatives": [],
        }

    # Find parts in same category with similar names
    alternatives = []

    if original.category:
        similar_parts = (
            db.query(Part)
            .filter(Part.organization_id == organization_id)
            .filter(Part.category == original.category)
            .filter(Part.id != part_id)
            .limit(10)
            .all()
        )

        for part in similar_parts:
            # Get supplier options
            supplier_parts = (
                db.query(SupplierPart, Supplier)
                .join(Supplier, SupplierPart.supplier_id == Supplier.id)
                .filter(SupplierPart.part_id == part.id)
                .filter(Supplier.status == "active")
                .all()
            )

            for sp, supplier in supplier_parts:
                alternatives.append({
                    "supplier_id": supplier.id,
                    "supplier_name": supplier.name,
                    "supplier_part_id": sp.id,
                    "part_id": part.id,
                    "part_number": part.part_number,
                    "description": part.description,
                    "unit_price": float(sp.unit_price) if sp.unit_price else None,
                    "lead_time_days": sp.lead_time_days or supplier.lead_time_days,
                    "is_alternative": True,
                })

    return {
        "original_part_id": part_id,
        "original_part_number": original.part_number,
        "alternatives": alternatives,
    }


# LangChain tool wrappers
@tool
def search_supplier_catalog(part_number: str) -> str:
    """
    Search for exact part number matches in the supplier catalog.

    Args:
        part_number: The part number to search for

    Returns:
        JSON string with matching suppliers and pricing
    """
    # Note: In actual usage, this would receive db session from context
    return f"Search for part number: {part_number}"


@tool
def semantic_part_search(description: str) -> str:
    """
    Search for parts using semantic similarity on descriptions.

    Args:
        description: Part description to search for

    Returns:
        JSON string with matching parts ranked by similarity
    """
    return f"Semantic search for: {description}"


@tool
def find_alternative_parts(part_id: int) -> str:
    """
    Find alternative or substitute parts for a given part.

    Args:
        part_id: The ID of the part to find alternatives for

    Returns:
        JSON string with alternative parts and their suppliers
    """
    return f"Find alternatives for part ID: {part_id}"
