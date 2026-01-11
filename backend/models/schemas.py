"""
Pydantic schemas for API request/response models.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ============ Base Schemas ============

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ============ Supplier Schemas ============

class SupplierBase(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[dict] = None
    payment_terms: Optional[str] = None
    lead_time_days: Optional[int] = None
    capabilities: list[str] = []
    certifications: list[str] = []


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[dict] = None
    payment_terms: Optional[str] = None
    lead_time_days: Optional[int] = None
    status: Optional[str] = None
    capabilities: Optional[list[str]] = None
    certifications: Optional[list[str]] = None


class SupplierResponse(SupplierBase, BaseSchema):
    id: int
    status: str
    rating: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierResponse]
    total: int
    skip: int
    limit: int


class SupplierMatchResponse(BaseModel):
    supplier: SupplierResponse
    confidence: float
    reasoning: str


# ============ Part Schemas ============

class PartBase(BaseModel):
    part_number: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    unit_of_measure: str = "EA"
    specifications: dict = {}


class PartCreate(PartBase):
    pass


class PartResponse(PartBase, BaseSchema):
    id: int
    created_at: datetime
    updated_at: datetime


# ============ Supplier Part Schemas ============

class SupplierPartBase(BaseModel):
    supplier_part_number: Optional[str] = None
    unit_price: Decimal
    currency: str = "USD"
    min_order_qty: int = 1
    lead_time_days: Optional[int] = None
    is_preferred: bool = False
    price_breaks: list[dict] = []


class SupplierPartCreate(SupplierPartBase):
    supplier_id: int
    part_id: int


class SupplierPartResponse(SupplierPartBase, BaseSchema):
    id: int
    supplier_id: int
    part_id: int
    supplier: Optional[SupplierResponse] = None
    part: Optional[PartResponse] = None
    last_quote_date: Optional[date] = None


# ============ BOM Schemas ============

class BOMItemBase(BaseModel):
    line_number: int
    part_number_raw: Optional[str] = None
    description_raw: Optional[str] = None
    quantity: Decimal
    unit_of_measure: Optional[str] = None


class BOMItemUpdate(BaseModel):
    part_number_raw: Optional[str] = None
    description_raw: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit_of_measure: Optional[str] = None
    matched_supplier_id: Optional[int] = None
    matched_supplier_part_id: Optional[int] = None
    unit_cost: Optional[Decimal] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class BOMItemResponse(BOMItemBase, BaseSchema):
    id: int
    bom_id: int
    part_id: Optional[int] = None
    matched_supplier_id: Optional[int] = None
    matched_supplier_part_id: Optional[int] = None
    unit_cost: Optional[Decimal] = None
    extended_cost: Optional[Decimal] = None
    lead_time_days: Optional[int] = None
    match_confidence: Optional[Decimal] = None
    match_method: Optional[str] = None
    alternative_matches: list[dict] = []
    status: str
    review_reason: Optional[str] = None
    notes: Optional[str] = None
    # Nested objects
    matched_supplier: Optional[SupplierResponse] = None
    matched_supplier_part: Optional[SupplierPartResponse] = None
    created_at: datetime
    updated_at: datetime


class BOMBase(BaseModel):
    name: str
    description: Optional[str] = None
    version: str = "1.0"


class BOMCreate(BOMBase):
    pass


class BOMResponse(BOMBase, BaseSchema):
    id: int
    status: str
    source_file_name: Optional[str] = None
    source_file_type: Optional[str] = None
    total_cost: Optional[Decimal] = None
    total_items: int
    matched_items: int
    processing_status: str
    processing_progress: float
    processing_step: Optional[str] = None
    processing_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BOMDetailResponse(BOMResponse):
    items: list[BOMItemResponse] = []


class BOMUploadResponse(BaseModel):
    bom: BOMResponse
    task_id: int
    message: str


class BOMStatusResponse(BaseModel):
    bom_id: int
    status: str
    processing_status: str
    processing_progress: float
    processing_step: Optional[str] = None
    processing_error: Optional[str] = None
    total_items: int
    matched_items: int


# ============ Purchase Order Schemas ============

class POItemBase(BaseModel):
    line_number: int
    part_number: Optional[str] = None
    description: Optional[str] = None
    quantity: Decimal
    unit_of_measure: Optional[str] = None
    unit_price: Decimal
    extended_price: Optional[Decimal] = None


class POItemResponse(POItemBase, BaseSchema):
    id: int
    po_id: int
    bom_item_id: Optional[int] = None
    part_id: Optional[int] = None
    supplier_part_id: Optional[int] = None
    received_quantity: Decimal
    notes: Optional[str] = None


class POBase(BaseModel):
    supplier_id: int
    required_date: Optional[date] = None
    ship_to_address: Optional[dict] = None
    notes: Optional[str] = None


class POCreate(POBase):
    bom_id: Optional[int] = None
    items: list[POItemBase] = []


class POResponse(BaseSchema):
    id: int
    po_number: str
    supplier_id: int
    bom_id: Optional[int] = None
    # Auto-generation tracking for demo visibility
    is_auto_generated: bool = False  # True if PO was auto-generated from BOM processing
    source_bom_name: Optional[str] = None  # Name of source BOM for display
    status: str
    subtotal: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    shipping: Optional[Decimal] = None
    total: Optional[Decimal] = None
    currency: str
    required_date: Optional[date] = None
    requires_approval: bool
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    sent_at: Optional[datetime] = None
    expected_ship_date: Optional[date] = None
    received_at: Optional[datetime] = None
    supplier: Optional[SupplierResponse] = None
    created_at: datetime
    updated_at: datetime


class PODetailResponse(POResponse):
    items: list[POItemResponse] = []


class POListResponse(BaseModel):
    items: list[POResponse]
    total: int
    skip: int
    limit: int


class POApprovalRequest(BaseModel):
    approved: bool
    notes: Optional[str] = None


class POReceiptRequest(BaseModel):
    items: list[dict]  # [{po_item_id: int, received_quantity: Decimal}]
    notes: Optional[str] = None


# ============ Agent/Task Schemas ============

class TaskResponse(BaseSchema):
    id: int
    task_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    status: str
    progress: float
    current_step: Optional[str] = None
    current_agent: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class TaskDetailResponse(TaskResponse):
    input_data: dict = {}
    output_data: dict = {}
    langsmith_run_id: Optional[str] = None


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int


class ApprovalResponse(BaseSchema):
    id: int
    entity_type: str
    entity_id: int
    request_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    details: dict = {}
    status: str
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime


class ApprovalListResponse(BaseModel):
    items: list[ApprovalResponse]
    total: int


class ApprovalDecision(BaseModel):
    approved: bool
    notes: Optional[str] = None
    selected_option: Optional[int] = None  # For match reviews with alternatives


# ============ Search Schemas ============

class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    min_confidence: float = 0.5
