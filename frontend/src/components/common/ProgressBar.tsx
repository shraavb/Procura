import { motion } from 'framer-motion'
import { clsx } from 'clsx'

interface ProgressBarProps {
  progress: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  label?: string
  variant?: 'default' | 'success' | 'warning' | 'error'
}

const sizeStyles = {
  sm: 'h-1.5',
  md: 'h-2',
  lg: 'h-3',
}

const variantStyles = {
  default: 'bg-primary-500',
  success: 'bg-green-500',
  warning: 'bg-amber-500',
  error: 'bg-red-500',
}

export default function ProgressBar({
  progress,
  size = 'md',
  showLabel = false,
  label,
  variant = 'default',
}: ProgressBarProps) {
  const clampedProgress = Math.min(100, Math.max(0, progress))

  return (
    <div className="w-full">
      {showLabel && (
        <div className="flex justify-between items-center mb-1">
          <span className="text-sm text-gray-600">{label}</span>
          <span className="text-sm font-medium text-gray-900">{Math.round(clampedProgress)}%</span>
        </div>
      )}
      <div className={clsx('w-full bg-gray-100 rounded-full overflow-hidden', sizeStyles[size])}>
        <motion.div
          className={clsx('h-full rounded-full', variantStyles[variant])}
          initial={{ width: 0 }}
          animate={{ width: `${clampedProgress}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}
