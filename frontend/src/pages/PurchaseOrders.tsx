import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  ShoppingCart,
  Filter,
  Check,
  X,
  Send,
  Eye,
  Loader2,
  ArrowRight
} from 'lucide-react'
import { listPurchaseOrders, approvePurchaseOrder, sendPurchaseOrder, submitPurchaseOrder, type PurchaseOrder } from '../api/client'
import StatusBadge from '../components/common/StatusBadge'
import { formatDistanceToNow } from 'date-fns'
import { clsx } from 'clsx'

const statusFilters = [
  { value: '', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'pending_approval', label: 'Pending Approval' },
  { value: 'approved', label: 'Approved' },
  { value: 'sent', label: 'Sent' },
  { value: 'received', label: 'Received' },
]

export default function PurchaseOrders() {
  const [statusFilter, setStatusFilter] = useState('')
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['pos', statusFilter],
    queryFn: () => listPurchaseOrders({ status: statusFilter || undefined }),
  })

  const approveMutation = useMutation({
    mutationFn: ({ id, approved, notes }: { id: number; approved: boolean; notes?: string }) =>
      approvePurchaseOrder(id, approved, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pos'] })
    },
  })

  const sendMutation = useMutation({
    mutationFn: sendPurchaseOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pos'] })
    },
  })

  const submitMutation = useMutation({
    mutationFn: submitPurchaseOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pos'] })
    },
  })

  const pos = data?.items || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Purchase Orders</h1>
          <p className="text-sm text-gray-500 mt-1">Manage and track purchase orders to suppliers</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <Filter className="w-4 h-4 text-gray-400" />
        <span className="text-sm text-gray-500">Status:</span>
        <div className="flex gap-1">
          {statusFilters.map((filter) => (
            <button
              key={filter.value}
              onClick={() => setStatusFilter(filter.value)}
              className={clsx(
                'px-3 py-1 text-sm rounded-full transition-colors',
                statusFilter === filter.value
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {/* PO List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : pos.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <ShoppingCart className="w-12 h-12 mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No purchase orders</h3>
          <p className="text-gray-500">
            {statusFilter
              ? `No ${statusFilter.replace('_', ' ')} purchase orders found`
              : 'Process a BOM to automatically generate purchase orders'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  PO Number
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Supplier
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Total
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Created
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {pos.map((po) => (
                <PORow
                  key={po.id}
                  po={po}
                  onApprove={(approved, notes) =>
                    approveMutation.mutate({ id: po.id, approved, notes })
                  }
                  onSend={() => sendMutation.mutate(po.id)}
                  onSubmit={() => submitMutation.mutate(po.id)}
                  isApproving={approveMutation.isPending}
                  isSending={sendMutation.isPending}
                  isSubmitting={submitMutation.isPending}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function PORow({
  po,
  onApprove,
  onSend,
  onSubmit,
  isApproving,
  isSending,
  isSubmitting,
}: {
  po: PurchaseOrder
  onApprove: (approved: boolean, notes?: string) => void
  onSend: () => void
  onSubmit: () => void
  isApproving: boolean
  isSending: boolean
  isSubmitting: boolean
}) {
  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4">
        <Link
          to={`/pos/${po.id}`}
          className="font-medium text-gray-900 hover:text-primary-600"
        >
          {po.po_number}
        </Link>
      </td>
      <td className="px-6 py-4 text-sm text-gray-900">
        {po.supplier?.name || 'Unknown'}
      </td>
      <td className="px-6 py-4 text-sm font-mono text-gray-900">
        ${Number(po.total || 0).toLocaleString()}
      </td>
      <td className="px-6 py-4">
        <StatusBadge status={po.status} />
      </td>
      <td className="px-6 py-4 text-sm text-gray-500">
        {formatDistanceToNow(new Date(po.created_at), { addSuffix: true })}
      </td>
      <td className="px-6 py-4 text-right">
        <div className="flex items-center justify-end gap-2">
          <Link
            to={`/pos/${po.id}`}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
            title="View Details"
          >
            <Eye className="w-4 h-4" />
          </Link>

          {po.status === 'pending_approval' && (
            <>
              <button
                onClick={() => onApprove(true)}
                disabled={isApproving}
                className="p-1.5 text-green-600 hover:bg-green-50 rounded"
                title="Approve"
              >
                <Check className="w-4 h-4" />
              </button>
              <button
                onClick={() => onApprove(false, 'Rejected')}
                disabled={isApproving}
                className="p-1.5 text-red-600 hover:bg-red-50 rounded"
                title="Reject"
              >
                <X className="w-4 h-4" />
              </button>
            </>
          )}

          {po.status === 'approved' && (
            <button
              onClick={onSend}
              disabled={isSending}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
              title="Send to Supplier"
            >
              {isSending ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Send className="w-3 h-3" />
              )}
              Send
            </button>
          )}

          {po.status === 'draft' && (
            <button
              onClick={onSubmit}
              disabled={isSubmitting}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
              title="Submit for Approval"
            >
              {isSubmitting ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <ArrowRight className="w-3 h-3" />
              )}
              Submit
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}
