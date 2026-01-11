import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  ShoppingCart,
  Building2,
  Calendar,
  DollarSign,
  Check,
  X,
  Send,
  Loader2,
  FileText
} from 'lucide-react'
import { getPurchaseOrder, approvePurchaseOrder, sendPurchaseOrder } from '../api/client'
import StatusBadge from '../components/common/StatusBadge'
import { format } from 'date-fns'
import { toast } from '../stores/toastStore'

export default function PODetail() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const { data: po, isLoading } = useQuery({
    queryKey: ['po', id],
    queryFn: () => getPurchaseOrder(Number(id)),
  })

  const approveMutation = useMutation({
    mutationFn: ({ approved, notes }: { approved: boolean; notes?: string }) =>
      approvePurchaseOrder(Number(id), approved, notes),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['po', id] })
      if (variables.approved) {
        toast.success('Purchase Order Approved', 'The PO is ready to be sent to the supplier.')
      } else {
        toast.info('Purchase Order Rejected', 'The PO has been returned to draft status.')
      }
    },
    onError: (error) => {
      toast.error('Action Failed', error instanceof Error ? error.message : 'Could not process the approval.')
    },
  })

  const sendMutation = useMutation({
    mutationFn: () => sendPurchaseOrder(Number(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['po', id] })
      queryClient.invalidateQueries({ queryKey: ['pos'] })
      toast.success('Purchase Order Sent', `${po?.po_number} has been sent to ${po?.supplier?.name || 'the supplier'}.`)
    },
    onError: (error) => {
      toast.error('Failed to Send', error instanceof Error ? error.message : 'Could not send the purchase order.')
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (!po) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Purchase order not found</p>
        <Link to="/pos" className="text-primary-600 hover:text-primary-700 mt-2 inline-block">
          Back to Purchase Orders
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            to="/pos"
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Purchase Orders
          </Link>
          <h1 className="text-2xl font-semibold text-gray-900 flex items-center gap-3">
            <ShoppingCart className="w-7 h-7 text-gray-400" />
            {po.po_number}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={po.status} size="md" />

          {po.status === 'pending_approval' && (
            <>
              <button
                onClick={() => approveMutation.mutate({ approved: true })}
                disabled={approveMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                {approveMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4" />
                )}
                Approve
              </button>
              <button
                onClick={() => approveMutation.mutate({ approved: false, notes: 'Rejected' })}
                disabled={approveMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                <X className="w-4 h-4" />
                Reject
              </button>
            </>
          )}

          {po.status === 'approved' && (
            <button
              onClick={() => sendMutation.mutate()}
              disabled={sendMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
            >
              {sendMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              Send to Supplier
            </button>
          )}
        </div>
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Building2 className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Supplier</p>
              <p className="font-semibold">{po.supplier?.name || 'Unknown'}</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <DollarSign className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total</p>
              <p className="font-semibold font-mono">${po.total?.toLocaleString() || '0'}</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Line Items</p>
              <p className="font-semibold">{po.items?.length || 0}</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
              <Calendar className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Required Date</p>
              <p className="font-semibold">
                {po.required_date
                  ? format(new Date(po.required_date), 'MMM d, yyyy')
                  : 'Not specified'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Approval Info */}
      {po.approved_at && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center gap-3"
        >
          <Check className="w-5 h-5 text-green-600" />
          <div>
            <p className="font-medium text-green-900">Approved</p>
            <p className="text-sm text-green-700">
              {format(new Date(po.approved_at), 'MMM d, yyyy h:mm a')}
            </p>
          </div>
        </motion.div>
      )}

      {po.rejection_reason && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3"
        >
          <X className="w-5 h-5 text-red-600" />
          <div>
            <p className="font-medium text-red-900">Rejected</p>
            <p className="text-sm text-red-700">{po.rejection_reason}</p>
          </div>
        </motion.div>
      )}

      {/* Line Items */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">Line Items</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">#</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Part Number</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Qty</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Unit Price</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Extended</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {po.items?.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-500">{item.line_number}</td>
                  <td className="px-6 py-4 text-sm font-mono text-gray-900">
                    {item.part_number || '-'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                    {item.description || '-'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900 text-right">
                    {Number(item.quantity).toLocaleString()} {item.unit_of_measure}
                  </td>
                  <td className="px-6 py-4 text-sm font-mono text-gray-900 text-right">
                    ${Number(item.unit_price).toFixed(2)}
                  </td>
                  <td className="px-6 py-4 text-sm font-mono text-gray-900 text-right font-medium">
                    ${Number(item.extended_price || Number(item.quantity) * Number(item.unit_price)).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-gray-50">
              <tr>
                <td colSpan={5} className="px-6 py-3 text-right text-sm font-medium text-gray-700">
                  Subtotal
                </td>
                <td className="px-6 py-3 text-right text-sm font-mono font-medium text-gray-900">
                  ${po.subtotal?.toLocaleString() || '0'}
                </td>
              </tr>
              {po.tax && Number(po.tax) > 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-3 text-right text-sm font-medium text-gray-700">
                    Tax
                  </td>
                  <td className="px-6 py-3 text-right text-sm font-mono font-medium text-gray-900">
                    ${Number(po.tax).toFixed(2)}
                  </td>
                </tr>
              )}
              {po.shipping && Number(po.shipping) > 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-3 text-right text-sm font-medium text-gray-700">
                    Shipping
                  </td>
                  <td className="px-6 py-3 text-right text-sm font-mono font-medium text-gray-900">
                    ${Number(po.shipping).toFixed(2)}
                  </td>
                </tr>
              )}
              <tr className="border-t-2 border-gray-200">
                <td colSpan={5} className="px-6 py-3 text-right text-sm font-semibold text-gray-900">
                  Total
                </td>
                <td className="px-6 py-3 text-right text-lg font-mono font-bold text-gray-900">
                  ${po.total?.toLocaleString() || '0'}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  )
}
