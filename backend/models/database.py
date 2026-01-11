"""
SQLAlchemy database models for Procura.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    Index,
    DECIMAL,
    Date,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Organization(Base):
    """Multi-tenant organization."""

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    settings = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="organization")
    suppliers = relationship("Supplier", back_populates="organization")
    parts = relationship("Part", back_populates="organization")
    boms = relationship("BOM", back_populates="organization")
    purchase_orders = relationship("PurchaseOrder", back_populates="organization")


class User(Base):
    """User account."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(50), default="user")  # admin, approver, user
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="users")


class Supplier(Base):
    """Supplier/vendor in the catalog."""

    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True)
    description = Column(Text)
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    address = Column(JSONB)
    payment_terms = Column(String(100))
    lead_time_days = Column(Integer)
    rating = Column(DECIMAL(3, 2))
    status = Column(String(50), default="active")  # active, inactive, pending
    capabilities = Column(JSONB, default=[])  # List of capability strings
    certifications = Column(JSONB, default=[])  # List of certification strings
    # Vector embedding for semantic matching
    description_embedding = Column(Vector(1536))
    extra_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="suppliers")
    supplier_parts = relationship("SupplierPart", back_populates="supplier")

    __table_args__ = (
        Index("idx_suppliers_org_status", "organization_id", "status"),
    )


class Part(Base):
    """Part/component in the catalog."""

    __tablename__ = "parts"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    part_number = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    unit_of_measure = Column(String(50), default="EA")
    specifications = Column(JSONB, default={})
    # Vector embedding for semantic search
    description_embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="parts")
    supplier_parts = relationship("SupplierPart", back_populates="part")

    __table_args__ = (
        Index("idx_parts_org_pn", "organization_id", "part_number", unique=True),
    )


class SupplierPart(Base):
    """Supplier-Part relationship with pricing."""

    __tablename__ = "supplier_parts"

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    supplier_part_number = Column(String(100))
    unit_price = Column(DECIMAL(15, 4))
    currency = Column(String(3), default="USD")
    min_order_qty = Column(Integer, default=1)
    lead_time_days = Column(Integer)
    is_preferred = Column(Boolean, default=False)
    price_breaks = Column(JSONB, default=[])  # [{qty: 100, price: 5.50}, ...]
    last_quote_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    supplier = relationship("Supplier", back_populates="supplier_parts")
    part = relationship("Part", back_populates="supplier_parts")

    __table_args__ = (
        Index("idx_supplier_parts_unique", "supplier_id", "part_id", unique=True),
    )


class BOM(Base):
    """Bill of Materials."""

    __tablename__ = "boms"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    version = Column(String(50), default="1.0")
    status = Column(String(50), default="draft")  # draft, active, archived
    source_file_url = Column(Text)
    source_file_name = Column(String(255))
    source_file_type = Column(String(50))  # excel, csv, pdf, image
    total_cost = Column(DECIMAL(15, 2))
    total_items = Column(Integer, default=0)
    matched_items = Column(Integer, default=0)
    # Processing state
    processing_status = Column(String(50), default="pending")  # pending, parsing, matching, optimizing, generating_pos, completed, failed
    processing_progress = Column(Float, default=0)  # 0-100
    processing_step = Column(String(255))  # Current step description
    processing_error = Column(Text)
    agent_run_id = Column(String(255))  # LangSmith trace ID
    extra_data = Column(JSONB, default={})
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="boms")
    items = relationship("BOMItem", back_populates="bom", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="bom")


class BOMItem(Base):
    """BOM line item."""

    __tablename__ = "bom_items"

    id = Column(Integer, primary_key=True)
    bom_id = Column(Integer, ForeignKey("boms.id", ondelete="CASCADE"), nullable=False)
    line_number = Column(Integer, nullable=False)
    # Raw data from source file
    part_number_raw = Column(String(255))
    description_raw = Column(Text)
    quantity = Column(DECIMAL(15, 4), nullable=False)
    unit_of_measure = Column(String(50))
    # Matched data
    part_id = Column(Integer, ForeignKey("parts.id"))
    matched_supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    matched_supplier_part_id = Column(Integer, ForeignKey("supplier_parts.id"))
    unit_cost = Column(DECIMAL(15, 4))
    extended_cost = Column(DECIMAL(15, 4))
    lead_time_days = Column(Integer)
    # Matching metadata
    match_confidence = Column(DECIMAL(3, 2))  # 0.00-1.00
    match_method = Column(String(50))  # exact, semantic, manual
    alternative_matches = Column(JSONB, default=[])  # [{supplier_id, confidence, price}, ...]
    # Status
    status = Column(String(50), default="pending")  # pending, matched, confirmed, ordered, needs_review
    review_reason = Column(String(255))  # Why it needs review
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    bom = relationship("BOM", back_populates="items")
    part = relationship("Part")
    matched_supplier = relationship("Supplier")
    matched_supplier_part = relationship("SupplierPart")

    __table_args__ = (
        Index("idx_bom_items_status", "bom_id", "status"),
    )


class PurchaseOrder(Base):
    """Purchase Order."""

    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    po_number = Column(String(100), unique=True, nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    bom_id = Column(Integer, ForeignKey("boms.id"))
    # Auto-generation tracking
    is_auto_generated = Column(Boolean, default=False)  # True if generated from BOM processing
    source_bom_name = Column(String(255))  # Name of the source BOM for display
    # Status workflow
    status = Column(String(50), default="draft")  # draft, pending_approval, approved, sent, acknowledged, shipped, received, cancelled
    # Financial
    subtotal = Column(DECIMAL(15, 2))
    tax = Column(DECIMAL(15, 2), default=0)
    shipping = Column(DECIMAL(15, 2), default=0)
    total = Column(DECIMAL(15, 2))
    currency = Column(String(3), default="USD")
    # Dates
    required_date = Column(Date)
    # Shipping
    ship_to_address = Column(JSONB)
    notes = Column(Text)
    # Approval workflow
    requires_approval = Column(Boolean, default=True)
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    # Tracking
    sent_at = Column(DateTime)
    acknowledged_at = Column(DateTime)
    expected_ship_date = Column(Date)
    actual_ship_date = Column(Date)
    tracking_numbers = Column(JSONB, default=[])
    received_at = Column(DateTime)
    # Metadata
    extra_data = Column(JSONB, default={})
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="purchase_orders")
    supplier = relationship("Supplier")
    bom = relationship("BOM", back_populates="purchase_orders")
    items = relationship("POItem", back_populates="purchase_order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_po_org_status", "organization_id", "status"),
    )


class POItem(Base):
    """Purchase Order line item."""

    __tablename__ = "po_items"

    id = Column(Integer, primary_key=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    line_number = Column(Integer, nullable=False)
    bom_item_id = Column(Integer, ForeignKey("bom_items.id", ondelete="SET NULL"))
    part_id = Column(Integer, ForeignKey("parts.id"))
    supplier_part_id = Column(Integer, ForeignKey("supplier_parts.id"))
    part_number = Column(String(100))
    description = Column(Text)
    quantity = Column(DECIMAL(15, 4), nullable=False)
    unit_of_measure = Column(String(50))
    unit_price = Column(DECIMAL(15, 4))
    extended_price = Column(DECIMAL(15, 4))
    received_quantity = Column(DECIMAL(15, 4), default=0)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="items")
    bom_item = relationship("BOMItem")
    part = relationship("Part")
    supplier_part = relationship("SupplierPart")


class AgentTask(Base):
    """Agent workflow task for tracking."""

    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    task_type = Column(String(100), nullable=False)  # bom_processing, supplier_matching, po_generation
    entity_type = Column(String(50))  # bom, po
    entity_id = Column(Integer)
    status = Column(String(50), default="pending")  # pending, running, completed, failed, paused
    input_data = Column(JSONB, default={})
    output_data = Column(JSONB, default={})
    progress = Column(Float, default=0)  # 0-100
    current_step = Column(String(255))
    current_agent = Column(String(100))  # Which agent is currently active
    error_message = Column(Text)
    langsmith_run_id = Column(String(255))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_agent_tasks_status", "organization_id", "status"),
    )


class ApprovalRequest(Base):
    """Human-in-the-loop approval request."""

    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("agent_tasks.id"))
    entity_type = Column(String(50), nullable=False)  # purchase_order, supplier_match, price_override
    entity_id = Column(Integer, nullable=False)
    request_type = Column(String(100))  # po_approval, match_review, price_review
    title = Column(String(255))
    description = Column(Text)
    details = Column(JSONB, default={})
    status = Column(String(50), default="pending")  # pending, approved, rejected, expired
    requested_by = Column(Integer, ForeignKey("users.id"))
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    review_notes = Column(Text)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_approvals_status", "organization_id", "status"),
    )


class AgentMemory(Base):
    """RAG memory for agent context."""

    __tablename__ = "agent_memories"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    memory_type = Column(String(50), nullable=False)  # bom_parse, supplier_match, pricing, po_generation
    content = Column(Text, nullable=False)
    summary = Column(Text)
    embedding = Column(Vector(1536))
    importance = Column(DECIMAL(3, 2), default=0.5)  # 0.0-1.0
    source_entity_type = Column(String(50))  # bom, supplier, part, po
    source_entity_id = Column(Integer)
    extra_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    accessed_at = Column(DateTime, default=datetime.utcnow)
