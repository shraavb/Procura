"""
Supplier API endpoints.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.db import get_db
from models.database import Supplier, Part, SupplierPart, Organization
from models.schemas import (
    SupplierResponse,
    SupplierListResponse,
    SupplierCreate,
    SupplierUpdate,
    SupplierPartResponse,
    SemanticSearchRequest,
    SupplierMatchResponse,
)
from services.embedding import get_embedding_service
from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])
settings = get_settings()


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


@router.get("", response_model=SupplierListResponse)
async def list_suppliers(
    search: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List suppliers with optional filtering."""
    query = select(Supplier)

    if status:
        query = query.where(Supplier.status == status)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Supplier.name.ilike(search_term),
                Supplier.code.ilike(search_term),
                Supplier.description.ilike(search_term)
            )
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    query = query.order_by(Supplier.name).offset(skip).limit(limit)
    result = await db.execute(query)
    suppliers = result.scalars().all()

    return SupplierListResponse(
        items=suppliers,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=SupplierResponse)
async def create_supplier(
    supplier: SupplierCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new supplier."""
    org = await get_default_org(db)

    # Check for duplicate code
    if supplier.code:
        result = await db.execute(
            select(Supplier).where(Supplier.code == supplier.code)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail=f"Supplier code '{supplier.code}' already exists")

    # Create supplier
    db_supplier = Supplier(
        organization_id=org.id,
        **supplier.model_dump(),
    )

    # Generate embedding for description if available
    if supplier.description and settings.openai_api_key:
        try:
            embedding_service = get_embedding_service()
            embedding = embedding_service.create_embedding(supplier.description)
            db_supplier.description_embedding = embedding
        except Exception as e:
            logger.warning(f"Failed to create embedding for supplier: {e}")

    db.add(db_supplier)
    await db.commit()
    await db.refresh(db_supplier)

    return db_supplier


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """Get supplier by ID."""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    return supplier


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    update: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a supplier."""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    update_data = update.model_dump(exclude_unset=True)

    # Check for duplicate code if changing
    if "code" in update_data and update_data["code"] != supplier.code:
        result = await db.execute(
            select(Supplier).where(Supplier.code == update_data["code"])
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail=f"Supplier code '{update_data['code']}' already exists")

    for field, value in update_data.items():
        setattr(supplier, field, value)

    # Re-generate embedding if description changed
    if "description" in update_data and settings.openai_api_key:
        try:
            embedding_service = get_embedding_service()
            embedding = embedding_service.create_embedding(update_data["description"])
            supplier.description_embedding = embedding
        except Exception as e:
            logger.warning(f"Failed to update embedding for supplier: {e}")

    await db.commit()
    await db.refresh(supplier)

    return supplier


@router.delete("/{supplier_id}")
async def delete_supplier(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a supplier."""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    await db.delete(supplier)
    await db.commit()

    return {"message": "Supplier deleted successfully"}


@router.get("/{supplier_id}/catalog", response_model=list[SupplierPartResponse])
async def get_supplier_catalog(
    supplier_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get all parts available from a supplier."""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    result = await db.execute(
        select(SupplierPart)
        .options(selectinload(SupplierPart.part))
        .where(SupplierPart.supplier_id == supplier_id)
        .offset(skip)
        .limit(limit)
    )
    supplier_parts = result.scalars().all()

    return supplier_parts


@router.post("/search/semantic", response_model=list[SupplierMatchResponse])
async def semantic_supplier_search(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic search for suppliers matching a description.
    Uses vector similarity to find relevant suppliers.
    """
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="Semantic search unavailable: OpenAI API key not configured"
        )

    # Generate query embedding
    embedding_service = get_embedding_service()
    query_embedding = embedding_service.create_embedding(request.query)

    # Vector similarity search
    distance_expr = Supplier.description_embedding.cosine_distance(query_embedding)
    result = await db.execute(
        select(Supplier, distance_expr.label("distance"))
        .where(Supplier.description_embedding.isnot(None))
        .where(Supplier.status == "active")
        .order_by(distance_expr)
        .limit(request.top_k)
    )
    results = result.all()

    # Convert distance to confidence (1 - distance for cosine)
    matches = []
    for supplier, distance in results:
        confidence = 1 - distance
        if confidence >= request.min_confidence:
            matches.append(SupplierMatchResponse(
                supplier=supplier,
                confidence=confidence,
                reasoning=f"Semantic similarity match with {confidence:.1%} confidence based on description"
            ))

    return matches
