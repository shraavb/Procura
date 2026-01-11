/**
 * API client for Procura backend
 */

const API_BASE = '/api'

// ============ Types ============

export interface Supplier {
  id: number
  name: string
  code: string | null
  description: string | null
  contact_email: string | null
  contact_phone: string | null
  lead_time_days: number | null
  status: string
  rating: number | null
  capabilities: string[]
  certifications: string[]
  created_at: string
  updated_at: string
}

export interface Part {
  id: number
  part_number: string
  name: string
  description: string | null
  category: string | null
  unit_of_measure: string
}

export interface SupplierPart {
  id: number
  supplier_id: number
  part_id: number
  supplier_part_number: string | null
  unit_price: number
  currency: string
  min_order_qty: number
  lead_time_days: number | null
  is_preferred: boolean
  price_breaks: Array<{ qty: number; price: number }>
}

export interface BOMItem {
  id: number
  bom_id: number
  line_number: number
  part_number_raw: string | null
  description_raw: string | null
  quantity: number
  unit_of_measure: string | null
  part_id: number | null
  matched_supplier_id: number | null
  matched_supplier_part_id: number | null
  unit_cost: number | null
  extended_cost: number | null
  lead_time_days: number | null
  match_confidence: number | null
  match_method: string | null
  alternative_matches: Array<{
    supplier_id: number
    supplier_name: string
    unit_price: number | null
    confidence: number
  }>
  status: string
  review_reason: string | null
  notes: string | null
  matched_supplier?: Supplier
  created_at: string
  updated_at: string
}

export interface BOM {
  id: number
  name: string
  description: string | null
  version: string
  status: string
  source_file_name: string | null
  source_file_type: string | null
  total_cost: number | null
  total_items: number
  matched_items: number
  processing_status: string
  processing_progress: number
  processing_step: string | null
  processing_error: string | null
  created_at: string
  updated_at: string
  items?: BOMItem[]
}

export interface POItem {
  id: number
  po_id: number
  line_number: number
  part_number: string | null
  description: string | null
  quantity: number
  unit_of_measure: string | null
  unit_price: number
  extended_price: number | null
  received_quantity: number
}

export interface PurchaseOrder {
  id: number
  po_number: string
  supplier_id: number
  bom_id: number | null
  status: string
  subtotal: number | null
  tax: number | null
  shipping: number | null
  total: number | null
  currency: string
  required_date: string | null
  requires_approval: boolean
  approved_by: number | null
  approved_at: string | null
  rejection_reason: string | null
  sent_at: string | null
  supplier?: Supplier
  items?: POItem[]
  created_at: string
  updated_at: string
}

export interface AgentTask {
  id: number
  task_type: string
  entity_type: string | null
  entity_id: number | null
  status: string
  progress: number
  current_step: string | null
  current_agent: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface ApprovalRequest {
  id: number
  entity_type: string
  entity_id: number
  request_type: string | null
  title: string | null
  description: string | null
  details: Record<string, unknown>
  status: string
  review_notes: string | null
  reviewed_at: string | null
  created_at: string
}

// ============ API Functions ============

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// Health
export async function healthCheck() {
  return request<{ status: string }>('/health')
}

// BOMs
export async function listBOMs(params?: {
  status?: string
  processing_status?: string
}) {
  const searchParams = new URLSearchParams()
  if (params?.status) searchParams.set('status', params.status)
  if (params?.processing_status) searchParams.set('processing_status', params.processing_status)
  const query = searchParams.toString()
  return request<BOM[]>(`/boms${query ? `?${query}` : ''}`)
}

export async function getBOM(id: number) {
  return request<BOM & { items: BOMItem[] }>(`/boms/${id}`)
}

export async function uploadBOM(file: File, name: string, description?: string, autoProcess = true) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('name', name)
  if (description) formData.append('description', description)
  formData.append('auto_process', String(autoProcess))

  const response = await fetch(`${API_BASE}/boms/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json() as Promise<{ bom: BOM; task_id: number; message: string }>
}

export async function processBOM(id: number) {
  return request<AgentTask>(`/boms/${id}/process`, { method: 'POST' })
}

export async function getBOMStatus(id: number) {
  return request<{
    bom_id: number
    status: string
    processing_status: string
    processing_progress: number
    processing_step: string | null
    total_items: number
    matched_items: number
  }>(`/boms/${id}/status`)
}

export async function updateBOMItem(bomId: number, itemId: number, data: Partial<BOMItem>) {
  return request<BOMItem>(`/boms/${bomId}/items/${itemId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteBOM(id: number) {
  return request<{ message: string }>(`/boms/${id}`, { method: 'DELETE' })
}

// Suppliers
export async function listSuppliers(params?: { search?: string; status?: string }) {
  const searchParams = new URLSearchParams()
  if (params?.search) searchParams.set('search', params.search)
  if (params?.status) searchParams.set('status', params.status)
  const query = searchParams.toString()
  return request<{ items: Supplier[]; total: number }>(`/suppliers${query ? `?${query}` : ''}`)
}

export async function getSupplier(id: number) {
  return request<Supplier>(`/suppliers/${id}`)
}

export async function createSupplier(data: Omit<Supplier, 'id' | 'created_at' | 'updated_at' | 'status' | 'rating'>) {
  return request<Supplier>('/suppliers', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function searchSuppliersSemantic(query: string, topK = 5, minConfidence = 0.5) {
  return request<Array<{ supplier: Supplier; confidence: number; reasoning: string }>>(
    '/suppliers/search/semantic',
    {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK, min_confidence: minConfidence }),
    }
  )
}

// Purchase Orders
export async function listPurchaseOrders(params?: {
  status?: string
  supplier_id?: number
  bom_id?: number
}) {
  const searchParams = new URLSearchParams()
  if (params?.status) searchParams.set('status', params.status)
  if (params?.supplier_id) searchParams.set('supplier_id', String(params.supplier_id))
  if (params?.bom_id) searchParams.set('bom_id', String(params.bom_id))
  const query = searchParams.toString()
  return request<{ items: PurchaseOrder[]; total: number }>(`/pos${query ? `?${query}` : ''}`)
}

export async function getPurchaseOrder(id: number) {
  return request<PurchaseOrder & { items: POItem[] }>(`/pos/${id}`)
}

export async function approvePurchaseOrder(id: number, approved: boolean, notes?: string) {
  return request<PurchaseOrder>(`/pos/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify({ approved, notes }),
  })
}

export async function sendPurchaseOrder(id: number) {
  return request<PurchaseOrder>(`/pos/${id}/send`, { method: 'POST' })
}

export async function submitPurchaseOrder(id: number) {
  return request<PurchaseOrder>(`/pos/${id}/submit`, { method: 'POST' })
}

// Agents/Tasks
export async function listTasks(params?: { status?: string; task_type?: string }) {
  const searchParams = new URLSearchParams()
  if (params?.status) searchParams.set('status', params.status)
  if (params?.task_type) searchParams.set('task_type', params.task_type)
  const query = searchParams.toString()
  return request<{ items: AgentTask[]; total: number }>(`/agents/tasks${query ? `?${query}` : ''}`)
}

export async function getTask(id: number) {
  return request<AgentTask>(`/agents/tasks/${id}`)
}

export async function cancelTask(id: number) {
  return request<AgentTask>(`/agents/tasks/${id}/cancel`, { method: 'POST' })
}

export async function listApprovals(entityType?: string) {
  const query = entityType ? `?entity_type=${entityType}` : ''
  return request<{ items: ApprovalRequest[]; total: number }>(`/agents/approvals${query}`)
}

export async function processApproval(id: number, approved: boolean, notes?: string, selectedOption?: number) {
  return request<ApprovalRequest>(`/agents/approvals/${id}`, {
    method: 'POST',
    body: JSON.stringify({ approved, notes, selected_option: selectedOption }),
  })
}
