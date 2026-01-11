import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import {
  FileText,
  Search,
  Calculator,
  FileCheck,
  CheckCircle2,
  Loader2,
  Clock
} from 'lucide-react'

export interface AgentStep {
  id: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'error'
  progress?: number
}

interface AgentProgressStepperProps {
  currentStep: string
  progress: number
}

const defaultSteps: AgentStep[] = [
  { id: 'parser', label: 'Parse BOM', status: 'pending' },
  { id: 'matcher', label: 'Match Suppliers', status: 'pending' },
  { id: 'optimizer', label: 'Optimize', status: 'pending' },
  { id: 'generator', label: 'Generate POs', status: 'pending' },
]

const stepIcons: Record<string, typeof FileText> = {
  parser: FileText,
  matcher: Search,
  optimizer: Calculator,
  generator: FileCheck,
}

function getStepsFromProgress(progress: number, _currentStep: string): AgentStep[] {
  const steps = [...defaultSteps]

  // Determine which step is active based on progress
  let activeIndex = -1
  if (progress >= 0 && progress < 25) activeIndex = 0
  else if (progress >= 25 && progress < 60) activeIndex = 1
  else if (progress >= 60 && progress < 70) activeIndex = 2
  else if (progress >= 70 && progress < 100) activeIndex = 3
  else if (progress >= 100) activeIndex = 4

  // Update statuses
  steps.forEach((step, idx) => {
    if (idx < activeIndex) {
      step.status = 'completed'
    } else if (idx === activeIndex) {
      step.status = 'running'
      step.progress = progress
    } else {
      step.status = 'pending'
    }
  })

  return steps
}

export default function AgentProgressStepper({ currentStep, progress }: AgentProgressStepperProps) {
  const steps = getStepsFromProgress(progress, currentStep)

  return (
    <div className="w-full">
      <div className="flex items-center justify-between">
        {steps.map((step, index) => {
          const Icon = stepIcons[step.id] || FileText

          return (
            <div key={step.id} className="flex items-center flex-1">
              {/* Step circle */}
              <div className="flex flex-col items-center">
                <motion.div
                  animate={step.status === 'running' ? { scale: [1, 1.1, 1] } : {}}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                  className={clsx(
                    'w-12 h-12 rounded-full flex items-center justify-center transition-colors',
                    step.status === 'completed' && 'bg-green-100 text-green-600',
                    step.status === 'running' && 'bg-primary-100 text-primary-600 ring-2 ring-primary-400',
                    step.status === 'pending' && 'bg-gray-100 text-gray-400',
                    step.status === 'error' && 'bg-red-100 text-red-600'
                  )}
                >
                  {step.status === 'completed' ? (
                    <CheckCircle2 className="w-6 h-6" />
                  ) : step.status === 'running' ? (
                    <Loader2 className="w-6 h-6 animate-spin" />
                  ) : step.status === 'error' ? (
                    <span className="text-lg font-bold">!</span>
                  ) : (
                    <Icon className="w-5 h-5" />
                  )}
                </motion.div>
                <span
                  className={clsx(
                    'mt-2 text-xs font-medium text-center',
                    step.status === 'completed' && 'text-green-600',
                    step.status === 'running' && 'text-primary-600',
                    step.status === 'pending' && 'text-gray-400',
                    step.status === 'error' && 'text-red-600'
                  )}
                >
                  {step.label}
                </span>
              </div>

              {/* Connector line */}
              {index < steps.length - 1 && (
                <div className="flex-1 mx-2 h-0.5 -mt-6">
                  <div
                    className={clsx(
                      'h-full transition-colors',
                      steps[index + 1].status !== 'pending' ? 'bg-green-400' : 'bg-gray-200'
                    )}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Current step label */}
      {currentStep && (
        <div className="mt-4 text-center">
          <p className="text-sm text-gray-600">
            <Clock className="w-4 h-4 inline mr-1" />
            {currentStep}
          </p>
        </div>
      )}
    </div>
  )
}
