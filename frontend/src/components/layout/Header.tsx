import { useState, useRef, useEffect } from 'react'
import { useLocation, Link } from 'react-router-dom'
import { Bell, Search, User, Settings, LogOut, ChevronRight, CheckCircle2, AlertCircle, Clock } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { listApprovals, type ApprovalRequest } from '../../api/client'
import { motion, AnimatePresence } from 'framer-motion'
import { formatDistanceToNow } from 'date-fns'

const pageTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/boms': 'Bill of Materials',
  '/suppliers': 'Suppliers',
  '/pos': 'Purchase Orders',
  '/settings': 'Settings',
}

export default function Header() {
  const location = useLocation()
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const notificationRef = useRef<HTMLDivElement>(null)
  const profileRef = useRef<HTMLDivElement>(null)

  // Get pending approvals count - don't fail if API is down
  const { data: approvals } = useQuery({
    queryKey: ['approvals', 'pending'],
    queryFn: () => listApprovals(),
    refetchInterval: 30000,
    retry: false, // Don't retry on failure
  })

  const pendingApprovals = approvals?.items?.filter(a => a.status === 'pending') || []
  const pendingCount = pendingApprovals.length
  const title = pageTitles[location.pathname] || 'Procura'

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (notificationRef.current && !notificationRef.current.contains(event.target as Node)) {
        setNotificationsOpen(false)
      }
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setProfileOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Close on escape key
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setNotificationsOpen(false)
        setProfileOpen(false)
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [])

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <h1 className="text-xl font-semibold text-gray-900">{title}</h1>

      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search..."
            className="pl-10 pr-4 py-2 w-64 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        </div>

        {/* Notifications */}
        <div className="relative" ref={notificationRef}>
          <button
            onClick={() => {
              setNotificationsOpen(prev => !prev)
              setProfileOpen(false)
            }}
            className="relative p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="Notifications"
          >
            <Bell className="w-5 h-5" />
            {pendingCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-red-500 text-white text-xs font-medium rounded-full flex items-center justify-center">
                {pendingCount > 9 ? '9+' : pendingCount}
              </span>
            )}
          </button>

          {/* Notifications Dropdown */}
          <AnimatePresence>
            {notificationsOpen && (
              <motion.div
                initial={{ opacity: 0, y: -10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.95 }}
                transition={{ duration: 0.15, ease: 'easeOut' }}
                className="absolute right-0 mt-2 w-96 bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden z-50"
              >
                <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                  <h3 className="font-semibold text-gray-900">Notifications</h3>
                  {pendingCount > 0 && (
                    <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs font-medium rounded-full">
                      {pendingCount} pending
                    </span>
                  )}
                </div>

                <div className="max-h-96 overflow-y-auto">
                  {pendingApprovals.length === 0 ? (
                    <div className="px-4 py-8 text-center">
                      <CheckCircle2 className="w-10 h-10 mx-auto text-green-400 mb-2" />
                      <p className="text-gray-500 text-sm">All caught up!</p>
                      <p className="text-gray-400 text-xs mt-1">No pending approvals</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-gray-100">
                      {pendingApprovals.slice(0, 5).map((approval) => (
                        <NotificationItem
                          key={approval.id}
                          approval={approval}
                          onClose={() => setNotificationsOpen(false)}
                        />
                      ))}
                    </div>
                  )}
                </div>

                {pendingApprovals.length > 0 && (
                  <div className="px-4 py-3 border-t border-gray-100 bg-gray-50">
                    <Link
                      to="/pos?tab=approvals"
                      onClick={() => setNotificationsOpen(false)}
                      className="flex items-center justify-center gap-1 text-sm text-primary-600 hover:text-primary-700 font-medium"
                    >
                      View all approvals
                      <ChevronRight className="w-4 h-4" />
                    </Link>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Profile */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => {
              setProfileOpen(prev => !prev)
              setNotificationsOpen(false)
            }}
            className="flex items-center gap-3 p-1 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="User menu"
          >
            <div className="w-8 h-8 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center font-medium text-sm">
              DM
            </div>
          </button>

          {/* Profile Dropdown */}
          <AnimatePresence>
            {profileOpen && (
              <motion.div
                initial={{ opacity: 0, y: -10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.95 }}
                transition={{ duration: 0.15, ease: 'easeOut' }}
                className="absolute right-0 mt-2 w-64 bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden z-50"
              >
                {/* User Info */}
                <div className="px-4 py-3 border-b border-gray-100">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center font-semibold">
                      DM
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">Demo Manager</p>
                      <p className="text-sm text-gray-500">demo@procura.io</p>
                    </div>
                  </div>
                </div>

                {/* Menu Items */}
                <div className="py-2">
                  <button
                    onClick={() => setProfileOpen(false)}
                    className="w-full px-4 py-2 flex items-center gap-3 text-gray-700 hover:bg-gray-50 transition-colors text-left"
                  >
                    <User className="w-4 h-4" />
                    <span className="text-sm">Your Profile</span>
                  </button>
                  <Link
                    to="/settings"
                    onClick={() => setProfileOpen(false)}
                    className="w-full px-4 py-2 flex items-center gap-3 text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    <Settings className="w-4 h-4" />
                    <span className="text-sm">Settings</span>
                  </Link>
                </div>

                {/* Logout */}
                <div className="border-t border-gray-100 py-2">
                  <button
                    onClick={() => setProfileOpen(false)}
                    className="w-full px-4 py-2 flex items-center gap-3 text-red-600 hover:bg-red-50 transition-colors text-left"
                  >
                    <LogOut className="w-4 h-4" />
                    <span className="text-sm">Log out</span>
                  </button>
                </div>

                {/* App Info */}
                <div className="border-t border-gray-100 px-4 py-2 bg-gray-50">
                  <p className="text-xs text-gray-400">Procura v1.0.0 - Demo Mode</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  )
}

interface NotificationItemProps {
  approval: ApprovalRequest
  onClose: () => void
}

function NotificationItem({ approval, onClose }: NotificationItemProps) {
  const getIcon = () => {
    switch (approval.entity_type) {
      case 'purchase_order':
        return <AlertCircle className="w-5 h-5 text-amber-500" />
      case 'supplier_match':
        return <Clock className="w-5 h-5 text-blue-500" />
      default:
        return <Bell className="w-5 h-5 text-gray-400" />
    }
  }

  const getTitle = () => {
    if (approval.title) {
      return approval.title
    }
    switch (approval.entity_type) {
      case 'purchase_order':
        return 'PO Approval Required'
      case 'supplier_match':
        return 'Match Review Needed'
      default:
        return 'Approval Required'
    }
  }

  const getDescription = () => {
    if (approval.description) {
      return approval.description
    }
    const data = approval.details as Record<string, unknown>
    if (approval.entity_type === 'purchase_order' && data?.po_number) {
      return `PO ${data.po_number} requires approval ($${Number(data.total || 0).toLocaleString()})`
    }
    if (approval.entity_type === 'supplier_match' && data?.part_number) {
      return `Review match for ${data.part_number}`
    }
    return 'Action required'
  }

  return (
    <Link
      to={approval.entity_type === 'purchase_order' ? '/pos?tab=approvals' : '/boms'}
      onClick={onClose}
      className="block px-4 py-3 hover:bg-gray-50 transition-colors"
    >
      <div className="flex gap-3">
        <div className="flex-shrink-0 mt-0.5">
          {getIcon()}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900">{getTitle()}</p>
          <p className="text-sm text-gray-500 truncate">{getDescription()}</p>
          <p className="text-xs text-gray-400 mt-1">
            {formatDistanceToNow(new Date(approval.created_at), { addSuffix: true })}
          </p>
        </div>
      </div>
    </Link>
  )
}
