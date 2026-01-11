import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  FileSpreadsheet,
  ShoppingCart,
  Building2,
  AlertCircle,
  ArrowRight,
  TrendingUp,
  Clock
} from 'lucide-react'
import { listBOMs, listPurchaseOrders, listSuppliers, listApprovals } from '../api/client'
import StatusBadge from '../components/common/StatusBadge'
import ProgressBar from '../components/common/ProgressBar'

export default function Dashboard() {
  const { data: boms } = useQuery({
    queryKey: ['boms'],
    queryFn: () => listBOMs(),
  })

  const { data: pos } = useQuery({
    queryKey: ['pos'],
    queryFn: () => listPurchaseOrders(),
  })

  const { data: suppliers } = useQuery({
    queryKey: ['suppliers'],
    queryFn: () => listSuppliers(),
  })

  const { data: approvals } = useQuery({
    queryKey: ['approvals'],
    queryFn: () => listApprovals(),
  })

  // Calculate stats
  const totalBOMs = boms?.length || 0
  const processingBOMs = boms?.filter(b => ['parsing', 'matching', 'optimizing', 'generating_pos'].includes(b.processing_status)).length || 0
  const pendingApprovals = approvals?.items.filter(a => a.status === 'pending').length || 0
  const totalPOs = pos?.total || 0
  const pendingPOs = pos?.items.filter(p => p.status === 'pending_approval').length || 0
  const totalSuppliers = suppliers?.total || 0

  // Get recent activity
  const recentBOMs = boms?.slice(0, 5) || []
  const recentPOs = pos?.items.slice(0, 5) || []

  return (
    <div className="space-y-6">
      {/* Action Required Banner */}
      {pendingApprovals > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-amber-50 border border-amber-200 rounded-xl p-4"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-amber-900">Action Required</h3>
              <p className="text-sm text-amber-700 mt-1">
                You have {pendingApprovals} item{pendingApprovals > 1 ? 's' : ''} pending review. Some supplier matches need verification before POs can be generated.
              </p>
              <Link
                to="/boms"
                className="inline-flex items-center gap-1 mt-2 text-sm font-medium text-amber-700 hover:text-amber-800"
              >
                Review items <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </motion.div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-xl p-6 shadow-sm border border-gray-100"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total BOMs</p>
              <p className="text-2xl font-semibold mt-1">{totalBOMs}</p>
            </div>
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <FileSpreadsheet className="w-6 h-6 text-blue-600" />
            </div>
          </div>
          {processingBOMs > 0 && (
            <p className="mt-3 text-sm text-blue-600">
              <Clock className="w-3 h-3 inline mr-1" />
              {processingBOMs} processing
            </p>
          )}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white rounded-xl p-6 shadow-sm border border-gray-100"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Purchase Orders</p>
              <p className="text-2xl font-semibold mt-1">{totalPOs}</p>
            </div>
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <ShoppingCart className="w-6 h-6 text-green-600" />
            </div>
          </div>
          {pendingPOs > 0 && (
            <p className="mt-3 text-sm text-amber-600">
              <AlertCircle className="w-3 h-3 inline mr-1" />
              {pendingPOs} awaiting approval
            </p>
          )}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-xl p-6 shadow-sm border border-gray-100"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Suppliers</p>
              <p className="text-2xl font-semibold mt-1">{totalSuppliers}</p>
            </div>
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <Building2 className="w-6 h-6 text-purple-600" />
            </div>
          </div>
          <p className="mt-3 text-sm text-gray-500">
            <TrendingUp className="w-3 h-3 inline mr-1" />
            Active suppliers
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-xl p-6 shadow-sm border border-gray-100"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Pending Reviews</p>
              <p className="text-2xl font-semibold mt-1">{pendingApprovals}</p>
            </div>
            <div className="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center">
              <AlertCircle className="w-6 h-6 text-amber-600" />
            </div>
          </div>
          {pendingApprovals > 0 && (
            <Link to="/boms" className="mt-3 text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1">
              Review now <ArrowRight className="w-3 h-3" />
            </Link>
          )}
        </motion.div>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent BOMs */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-white rounded-xl shadow-sm border border-gray-100"
        >
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Recent BOMs</h2>
            <Link to="/boms" className="text-sm text-primary-600 hover:text-primary-700">
              View all
            </Link>
          </div>
          <div className="divide-y divide-gray-100">
            {recentBOMs.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <FileSpreadsheet className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>No BOMs yet</p>
                <Link to="/boms" className="text-sm text-primary-600 hover:text-primary-700 mt-2 inline-block">
                  Upload your first BOM
                </Link>
              </div>
            ) : (
              recentBOMs.map((bom) => (
                <Link
                  key={bom.id}
                  to={`/boms/${bom.id}`}
                  className="p-4 hover:bg-gray-50 transition-colors flex items-center justify-between"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate">{bom.name}</p>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {bom.total_items} items &middot; {bom.matched_items} matched
                    </p>
                    {['parsing', 'matching', 'optimizing', 'generating_pos'].includes(bom.processing_status) && (
                      <div className="mt-2 w-32">
                        <ProgressBar progress={bom.processing_progress} size="sm" />
                      </div>
                    )}
                  </div>
                  <StatusBadge status={bom.processing_status} />
                </Link>
              ))
            )}
          </div>
        </motion.div>

        {/* Recent POs */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="bg-white rounded-xl shadow-sm border border-gray-100"
        >
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Recent Purchase Orders</h2>
            <Link to="/pos" className="text-sm text-primary-600 hover:text-primary-700">
              View all
            </Link>
          </div>
          <div className="divide-y divide-gray-100">
            {recentPOs.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <ShoppingCart className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>No purchase orders yet</p>
                <p className="text-sm mt-1">Process a BOM to generate POs</p>
              </div>
            ) : (
              recentPOs.map((po) => (
                <Link
                  key={po.id}
                  to={`/pos/${po.id}`}
                  className="p-4 hover:bg-gray-50 transition-colors flex items-center justify-between"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900">{po.po_number}</p>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {po.supplier?.name || 'Unknown supplier'} &middot; ${po.total?.toLocaleString() || '0'}
                    </p>
                  </div>
                  <StatusBadge status={po.status} />
                </Link>
              ))
            )}
          </div>
        </motion.div>
      </div>

    </div>
  )
}
