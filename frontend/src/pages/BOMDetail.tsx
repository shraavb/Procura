import { useState, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft,
  RefreshCw,
  FileSpreadsheet,
  Building2,
  DollarSign,
  AlertTriangle,
  ChevronDown,
  Loader2,
  Search,
  X,
  Check,
  CheckCircle2,
  FileText,
  ExternalLink
} from 'lucide-react'
import { getBOM, processBOM, updateBOMItem, listSuppliers, searchSuppliersSemantic, listPurchaseOrders, type BOMItem } from '../api/client'
import StatusBadge from '../components/common/StatusBadge'
import ProgressBar from '../components/common/ProgressBar'
import AgentProgressStepper from '../components/agent/AgentProgressStepper'
import { clsx } from 'clsx'
import { toast } from '../stores/toastStore'

type FilterTab = 'all' | 'needs_review' | 'matched'

export default function BOMDetail() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all')
  const [supplierSearchOpen, setSupplierSearchOpen] = useState(false)
  const [selectedItemForSearch, setSelectedItemForSearch] = useState<BOMItem | null>(null)

  const { data: bom, isLoading } = useQuery({
    queryKey: ['bom', id],
    queryFn: () => getBOM(Number(id)),
    refetchInterval: (query) => {
      // Refresh more frequently while processing
      const status = query.state.data?.processing_status
      if (status && ['parsing', 'matching', 'optimizing', 'generating_pos'].includes(status)) {
        return 2000
      }
      return false
    },
  })

  const processMutation = useMutation({
    mutationFn: () => processBOM(Number(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bom', id] })
    },
  })

  // Fetch related POs
  const { data: relatedPOs } = useQuery({
    queryKey: ['pos', 'bom', id],
    queryFn: () => listPurchaseOrders({ bom_id: Number(id) }),
    enabled: !!id,
  })

  // Filter items based on active tab - must be before early returns (React hooks rule)
  const filteredItems = useMemo(() => {
    if (!bom?.items) return []
    switch (activeFilter) {
      case 'needs_review':
        return bom.items.filter(item => item.status === 'needs_review')
      case 'matched':
        return bom.items.filter(item => item.status === 'matched' || item.status === 'confirmed')
      default:
        return bom.items
    }
  }, [bom?.items, activeFilter])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (!bom) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">BOM not found</p>
        <Link to="/boms" className="text-primary-600 hover:text-primary-700 mt-2 inline-block">
          Back to BOMs
        </Link>
      </div>
    )
  }

  const isProcessing = ['parsing', 'matching', 'optimizing', 'generating_pos'].includes(bom.processing_status)
  const needsReviewCount = bom.items?.filter(item => item.status === 'needs_review').length || 0
  const matchedCount = bom.items?.filter(item => item.status === 'matched' || item.status === 'confirmed').length || 0

  const handleOpenSupplierSearch = (item: BOMItem) => {
    setSelectedItemForSearch(item)
    setSupplierSearchOpen(true)
  }

  const handleCloseSupplierSearch = () => {
    setSupplierSearchOpen(false)
    setSelectedItemForSearch(null)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            to="/boms"
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to BOMs
          </Link>
          <h1 className="text-2xl font-semibold text-gray-900 flex items-center gap-3">
            <FileSpreadsheet className="w-7 h-7 text-gray-400" />
            {bom.name}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Version {bom.version} &middot; {bom.source_file_name}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={bom.processing_status} size="md" />
          {!isProcessing && bom.processing_status !== 'completed' && (
            <button
              onClick={() => processMutation.mutate()}
              disabled={processMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
            >
              {processMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              Process BOM
            </button>
          )}
        </div>
      </div>

      {/* Processing Progress */}
      {isProcessing && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-xl border border-gray-200 p-6"
        >
          <AgentProgressStepper
            currentStep={bom.processing_step || ''}
            progress={bom.processing_progress}
          />
        </motion.div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <FileSpreadsheet className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Items</p>
              <p className="text-xl font-semibold">{bom.total_items}</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <Building2 className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Matched</p>
              <p className="text-xl font-semibold">
                {bom.matched_items}
                <span className="text-sm text-gray-400 font-normal">/{bom.total_items}</span>
              </p>
            </div>
          </div>
          <ProgressBar
            progress={(bom.matched_items / Math.max(bom.total_items, 1)) * 100}
            size="sm"
            variant="success"
          />
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Needs Review</p>
              <p className="text-xl font-semibold">{needsReviewCount}</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <DollarSign className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Cost</p>
              <p className="text-xl font-semibold font-mono">
                ${bom.total_cost?.toLocaleString() || '0'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Items Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Line Items</h2>

          {/* Filter Tabs */}
          <div className="flex items-center gap-1 p-1 bg-gray-100 rounded-lg">
            <button
              onClick={() => setActiveFilter('all')}
              className={clsx(
                'px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
                activeFilter === 'all'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              )}
            >
              All ({bom.total_items})
            </button>
            <button
              onClick={() => setActiveFilter('needs_review')}
              className={clsx(
                'px-3 py-1.5 text-sm font-medium rounded-md transition-colors flex items-center gap-1.5',
                activeFilter === 'needs_review'
                  ? 'bg-amber-100 text-amber-800 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              )}
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              Needs Review ({needsReviewCount})
            </button>
            <button
              onClick={() => setActiveFilter('matched')}
              className={clsx(
                'px-3 py-1.5 text-sm font-medium rounded-md transition-colors flex items-center gap-1.5',
                activeFilter === 'matched'
                  ? 'bg-green-100 text-green-800 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              )}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Matched ({matchedCount})
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-12">#</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Part Number</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase max-w-xs">Description</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-20">Qty</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Supplier</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-20">Unit Cost</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-20">Extended</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-24">Status</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-28">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredItems.map((item) => (
                <BOMItemRow
                  key={item.id}
                  item={item}
                  bomId={bom.id}
                  onSearchSupplier={() => handleOpenSupplierSearch(item)}
                />
              ))}
              {filteredItems.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-6 py-8 text-center text-gray-500">
                    {activeFilter === 'needs_review'
                      ? 'No items need review'
                      : activeFilter === 'matched'
                        ? 'No matched items yet'
                        : 'No items found'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Related Purchase Orders */}
      {relatedPOs?.items && relatedPOs.items.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-gray-400" />
              <h2 className="font-semibold text-gray-900">Related Purchase Orders</h2>
              <span className="text-sm text-gray-500">({relatedPOs.items.length})</span>
            </div>
            <Link
              to="/pos"
              className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
            >
              View all POs
              <ExternalLink className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="divide-y divide-gray-200">
            {relatedPOs.items.map((po) => (
              <Link
                key={po.id}
                to={`/pos/${po.id}`}
                className="flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                    <FileText className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">{po.po_number}</p>
                    <p className="text-sm text-gray-500">
                      {po.supplier?.name || 'Unknown Supplier'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="font-mono font-medium text-gray-900">
                      ${Number(po.total || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </p>
                    <p className="text-xs text-gray-500">
                      {new Date(po.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <StatusBadge status={po.status} />
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Supplier Search Modal */}
      <SupplierSearchModal
        isOpen={supplierSearchOpen}
        onClose={handleCloseSupplierSearch}
        item={selectedItemForSearch}
        bomId={bom.id}
      />
    </div>
  )
}

interface BOMItemRowProps {
  item: BOMItem
  bomId: number
  onSearchSupplier: () => void
}

function BOMItemRow({ item, bomId, onSearchSupplier }: BOMItemRowProps) {
  const [expanded, setExpanded] = useState(false)
  const [isEditingPrice, setIsEditingPrice] = useState(false)
  const [priceInput, setPriceInput] = useState(item.unit_cost?.toString() || '')
  const queryClient = useQueryClient()

  const updateMutation = useMutation({
    mutationFn: (data: Partial<BOMItem>) => updateBOMItem(bomId, item.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bom', String(bomId)] })
      setIsEditingPrice(false)
    },
  })

  const handlePriceSubmit = () => {
    const price = parseFloat(priceInput)
    if (!isNaN(price) && price >= 0) {
      updateMutation.mutate({
        unit_cost: price,
        status: item.matched_supplier ? 'confirmed' : item.status
      })
    } else {
      setIsEditingPrice(false)
      setPriceInput(item.unit_cost?.toString() || '')
    }
  }

  const handlePriceKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handlePriceSubmit()
    } else if (e.key === 'Escape') {
      setIsEditingPrice(false)
      setPriceInput(item.unit_cost?.toString() || '')
    }
  }

  const hasAlternatives = item.alternative_matches && item.alternative_matches.length > 0
  const needsReview = item.status === 'needs_review'
  const isConfirmed = item.status === 'confirmed'

  return (
    <>
      <tr className={clsx(
        'hover:bg-gray-50 transition-colors',
        needsReview && 'bg-amber-50 hover:bg-amber-100',
        isConfirmed && 'bg-green-50'
      )}>
        <td className="px-3 py-3 text-sm text-gray-500">{item.line_number}</td>
        <td className="px-3 py-3 text-sm font-mono text-gray-900">
          {item.part_number_raw || '-'}
        </td>
        <td className="px-3 py-3 text-sm text-gray-900 max-w-xs truncate" title={item.description_raw || ''}>
          {item.description_raw || '-'}
        </td>
        <td className="px-3 py-3 text-sm text-gray-900 whitespace-nowrap">
          {item.quantity} {item.unit_of_measure}
        </td>
        <td className="px-3 py-3 text-sm">
          {item.matched_supplier ? (
            <div className="flex items-center gap-1">
              <span className="text-gray-900">{item.matched_supplier.name}</span>
              {item.match_confidence && (
                <span className="text-xs text-gray-400">
                  ({Math.round(Number(item.match_confidence) * 100)}%)
                </span>
              )}
            </div>
          ) : (
            <span className="text-gray-400 italic">Not matched</span>
          )}
        </td>
        <td className="px-3 py-3 text-sm font-mono text-gray-900 whitespace-nowrap">
          {isEditingPrice ? (
            <div className="flex items-center gap-1">
              <span className="text-gray-400">$</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={priceInput}
                onChange={(e) => setPriceInput(e.target.value)}
                onBlur={handlePriceSubmit}
                onKeyDown={handlePriceKeyDown}
                className="w-16 px-1 py-0.5 text-sm font-mono border border-primary-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                autoFocus
              />
            </div>
          ) : (
            <button
              onClick={() => {
                setPriceInput(item.unit_cost?.toString() || '')
                setIsEditingPrice(true)
              }}
              className={clsx(
                "hover:bg-gray-100 px-1 py-0.5 rounded transition-colors",
                !item.unit_cost && item.matched_supplier && "text-amber-600 bg-amber-50 hover:bg-amber-100"
              )}
              title="Click to edit price"
            >
              {item.unit_cost ? `$${Number(item.unit_cost).toFixed(2)}` : (item.matched_supplier ? 'Add price' : '-')}
            </button>
          )}
        </td>
        <td className="px-3 py-3 text-sm font-mono text-gray-900 whitespace-nowrap">
          {item.extended_cost ? `$${Number(item.extended_cost).toFixed(2)}` : '-'}
        </td>
        <td className="px-3 py-3">
          <div className="flex items-center gap-1">
            <StatusBadge status={item.status} />
            {hasAlternatives && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="p-1 hover:bg-gray-200 rounded transition-colors"
                title="View alternatives"
              >
                <ChevronDown
                  className={clsx('w-4 h-4 text-gray-400 transition-transform', expanded && 'rotate-180')}
                />
              </button>
            )}
          </div>
        </td>
        <td className="px-3 py-3">
          <div className="flex items-center gap-2">
            {needsReview && hasAlternatives && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="px-2 py-1 text-xs bg-amber-100 text-amber-800 rounded hover:bg-amber-200 transition-colors"
              >
                Review Options
              </button>
            )}
            <button
              onClick={onSearchSupplier}
              className={clsx(
                "px-2 py-1 text-xs rounded transition-colors flex items-center gap-1",
                needsReview
                  ? "bg-primary-100 text-primary-700 hover:bg-primary-200"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
              )}
              title={item.matched_supplier ? "Change supplier" : "Find supplier"}
            >
              <Search className="w-3 h-3" />
              {item.matched_supplier ? 'Change' : 'Find Supplier'}
            </button>
          </div>
        </td>
      </tr>

      {/* Alternatives Row */}
      <AnimatePresence>
        {expanded && hasAlternatives && (
          <motion.tr
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            <td colSpan={9} className="bg-gray-50 px-6 py-4">
              <div className="text-sm">
                <div className="flex items-center justify-between mb-3">
                  <p className="font-medium text-gray-700">Alternative Suppliers:</p>
                  <button
                    onClick={onSearchSupplier}
                    className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1"
                  >
                    <Search className="w-3 h-3" />
                    Search for more
                  </button>
                </div>
                <div className="space-y-2">
                  {item.alternative_matches?.map((alt, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200 hover:border-primary-300 transition-colors"
                    >
                      <div className="flex items-center gap-4">
                        <div>
                          <span className="font-medium text-gray-900">{alt.supplier_name}</span>
                          <div className="text-xs text-gray-500 mt-0.5">
                            {Math.round(alt.confidence * 100)}% match confidence
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="font-mono text-gray-900">
                          ${alt.unit_price?.toFixed(2) || 'N/A'}
                        </span>
                        <button
                          onClick={() => {
                            updateMutation.mutate({
                              matched_supplier_id: alt.supplier_id,
                              status: 'confirmed',
                            })
                            setExpanded(false)
                          }}
                          disabled={updateMutation.isPending}
                          className="px-3 py-1.5 text-xs bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50 flex items-center gap-1 transition-colors"
                        >
                          {updateMutation.isPending ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Check className="w-3 h-3" />
                          )}
                          Select
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </td>
          </motion.tr>
        )}
      </AnimatePresence>
    </>
  )
}

// Supplier Search Modal Component
interface SupplierSearchModalProps {
  isOpen: boolean
  onClose: () => void
  item: BOMItem | null
  bomId: number
}

function SupplierSearchModal({ isOpen, onClose, item, bomId }: SupplierSearchModalProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchType, setSearchType] = useState<'text' | 'semantic'>('text')
  const queryClient = useQueryClient()

  // Text search for suppliers
  const { data: textResults, isLoading: isTextLoading } = useQuery({
    queryKey: ['suppliers', 'search', searchQuery],
    queryFn: () => listSuppliers({ search: searchQuery }),
    enabled: isOpen && searchType === 'text' && searchQuery.length >= 2,
  })

  // Semantic search for suppliers
  const semanticMutation = useMutation({
    mutationFn: (query: string) => searchSuppliersSemantic(query, 10, 0.3),
  })

  const updateMutation = useMutation({
    mutationFn: (data: { supplierId: number; supplierName?: string }) =>
      updateBOMItem(bomId, item?.id || 0, {
        matched_supplier_id: data.supplierId,
        status: 'confirmed',
      }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['bom', String(bomId)] })
      toast.success('Supplier Selected', `${item?.part_number_raw || 'Item'} matched to ${variables.supplierName || 'supplier'}.`)
      onClose()
    },
    onError: (error) => {
      toast.error('Selection Failed', error instanceof Error ? error.message : 'Could not select the supplier.')
    },
  })

  const handleSearch = () => {
    if (searchType === 'semantic' && searchQuery.trim()) {
      semanticMutation.mutate(searchQuery)
    }
  }

  const handleSelectSupplier = (supplierId: number, supplierName?: string) => {
    updateMutation.mutate({ supplierId, supplierName })
  }

  // Reset state when modal closes
  const handleClose = () => {
    setSearchQuery('')
    setSearchType('text')
    semanticMutation.reset()
    onClose()
  }

  if (!isOpen || !item) return null

  const suppliers = searchType === 'text'
    ? textResults?.items || []
    : semanticMutation.data?.map(r => ({ ...r.supplier, confidence: r.confidence })) || []

  const isLoading = searchType === 'text' ? isTextLoading : semanticMutation.isPending

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        {/* Backdrop */}
        <div className="fixed inset-0 bg-black/50" onClick={handleClose} />

        {/* Modal */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="relative bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden"
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Find Supplier</h3>
              <p className="text-sm text-gray-500 mt-0.5">
                {item.part_number_raw || item.description_raw}
              </p>
            </div>
            <button
              onClick={handleClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>

          {/* Search */}
          <div className="px-6 py-4 border-b border-gray-200 space-y-3">
            {/* Search Type Toggle */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSearchType('text')}
                className={clsx(
                  'px-3 py-1.5 text-sm rounded-md transition-colors',
                  searchType === 'text'
                    ? 'bg-primary-100 text-primary-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                Text Search
              </button>
              <button
                onClick={() => setSearchType('semantic')}
                className={clsx(
                  'px-3 py-1.5 text-sm rounded-md transition-colors',
                  searchType === 'semantic'
                    ? 'bg-primary-100 text-primary-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                Semantic Search (AI)
              </button>
            </div>

            {/* Search Input */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder={searchType === 'text' ? 'Search by name or code...' : 'Describe what you need...'}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>
              {searchType === 'semantic' && (
                <button
                  onClick={handleSearch}
                  disabled={!searchQuery.trim() || semanticMutation.isPending}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                >
                  {semanticMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    'Search'
                  )}
                </button>
              )}
            </div>

            {searchType === 'semantic' && (
              <p className="text-xs text-gray-500">
                Tip: Describe the part type, specifications, or capabilities needed
              </p>
            )}
          </div>

          {/* Results */}
          <div className="px-6 py-4 overflow-y-auto max-h-[400px]">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
              </div>
            ) : suppliers.length > 0 ? (
              <div className="space-y-2">
                {suppliers.map((supplier) => (
                  <div
                    key={supplier.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    <div>
                      <div className="font-medium text-gray-900">{supplier.name}</div>
                      {supplier.code && (
                        <div className="text-xs text-gray-500">Code: {supplier.code}</div>
                      )}
                      {'confidence' in supplier && (
                        <div className="text-xs text-primary-600 mt-0.5">
                          {Math.round((supplier as { confidence: number }).confidence * 100)}% match
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => handleSelectSupplier(supplier.id, supplier.name)}
                      disabled={updateMutation.isPending}
                      className="px-3 py-1.5 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50 flex items-center gap-1 transition-colors"
                    >
                      {updateMutation.isPending ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Check className="w-3 h-3" />
                      )}
                      Select
                    </button>
                  </div>
                ))}
              </div>
            ) : searchQuery.length >= 2 || semanticMutation.isSuccess ? (
              <div className="text-center py-8 text-gray-500">
                No suppliers found. Try a different search.
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                {searchType === 'text'
                  ? 'Type at least 2 characters to search'
                  : 'Enter a description and click Search'}
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  )
}
