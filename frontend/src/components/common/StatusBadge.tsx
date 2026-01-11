import { clsx } from 'clsx'

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info' | 'processing'

interface StatusBadgeProps {
  status: string
  variant?: BadgeVariant
  size?: 'sm' | 'md'
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-gray-100 text-gray-700',
  success: 'bg-green-100 text-green-700',
  warning: 'bg-amber-100 text-amber-700',
  error: 'bg-red-100 text-red-700',
  info: 'bg-blue-100 text-blue-700',
  processing: 'bg-purple-100 text-purple-700',
}

const statusToVariant: Record<string, BadgeVariant> = {
  // BOM statuses
  draft: 'default',
  active: 'success',
  archived: 'default',
  // Processing statuses
  pending: 'default',
  parsing: 'processing',
  matching: 'processing',
  optimizing: 'processing',
  generating_pos: 'processing',
  awaiting_review: 'warning',
  completed: 'success',
  failed: 'error',
  // PO statuses
  pending_approval: 'warning',
  approved: 'success',
  rejected: 'error',
  sent: 'info',
  acknowledged: 'info',
  shipped: 'info',
  received: 'success',
  cancelled: 'default',
  // BOM item statuses
  matched: 'success',
  confirmed: 'success',
  needs_review: 'warning',
  ordered: 'info',
  // General
  running: 'processing',
  paused: 'warning',
}

export default function StatusBadge({ status, variant, size = 'sm' }: StatusBadgeProps) {
  const computedVariant = variant || statusToVariant[status] || 'default'
  const displayText = status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())

  return (
    <span
      className={clsx(
        'inline-flex items-center font-medium rounded-full',
        variantStyles[computedVariant],
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
      )}
    >
      {computedVariant === 'processing' && (
        <span className="w-1.5 h-1.5 bg-current rounded-full mr-1.5 animate-pulse" />
      )}
      {displayText}
    </span>
  )
}
