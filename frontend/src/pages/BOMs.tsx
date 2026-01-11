import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useDropzone } from 'react-dropzone'
import {
  Upload,
  FileSpreadsheet,
  MoreVertical,
  Trash2,
  Eye,
  X,
  Loader2,
  Sparkles,
  Cpu,
  Thermometer,
  Zap,
  Server
} from 'lucide-react'
import { listBOMs, uploadBOM, deleteBOM, type BOM } from '../api/client'
import StatusBadge from '../components/common/StatusBadge'
import ProgressBar from '../components/common/ProgressBar'
import { formatDistanceToNow } from 'date-fns'

// Demo BOM templates for quick testing
const DEMO_BOMS = [
  {
    id: 'iot_sensor_board',
    name: 'IoT Sensor Board',
    description: 'WiFi-enabled environmental monitoring with STM32 + ESP32',
    icon: Cpu,
    items: 14,
    file: 'iot_sensor_board.csv',
  },
  {
    id: 'motor_controller',
    name: 'Motor Controller',
    description: 'High-power BLDC motor controller for robotics',
    icon: Zap,
    items: 15,
    file: 'motor_controller.csv',
  },
  {
    id: 'smart_thermostat',
    name: 'Smart Thermostat',
    description: 'WiFi thermostat with display and voice control',
    icon: Thermometer,
    items: 18,
    file: 'smart_thermostat.csv',
  },
  {
    id: 'industrial_plc',
    name: 'Industrial PLC Module',
    description: 'Industrial PLC with Ethernet and fieldbus support',
    icon: Server,
    items: 20,
    file: 'industrial_plc_module.csv',
  },
]

export default function BOMs() {
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [bomName, setBomName] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadMode, setUploadMode] = useState<'upload' | 'demo'>('demo')
  const [selectedDemo, setSelectedDemo] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: boms, isLoading } = useQuery({
    queryKey: ['boms'],
    queryFn: () => listBOMs(),
    refetchInterval: 5000, // Refresh to see processing updates
  })

  const uploadMutation = useMutation({
    mutationFn: ({ file, name }: { file: File; name: string }) => uploadBOM(file, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['boms'] })
      setUploadModalOpen(false)
      setBomName('')
      setSelectedFile(null)
      setSelectedDemo(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteBOM,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['boms'] })
    },
  })

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setSelectedFile(acceptedFiles[0])
      if (!bomName) {
        setBomName(acceptedFiles[0].name.replace(/\.[^/.]+$/, ''))
      }
    }
  }, [bomName])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/csv': ['.csv'],
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg'],
    },
    maxFiles: 1,
  })

  const handleUpload = async () => {
    if (uploadMode === 'demo' && selectedDemo) {
      const demo = DEMO_BOMS.find(d => d.id === selectedDemo)
      if (demo) {
        // Fetch the demo file and upload it
        try {
          const response = await fetch(`/data/demo_boms/${demo.file}`)
          const blob = await response.blob()
          const file = new File([blob], demo.file, { type: 'text/csv' })
          uploadMutation.mutate({ file, name: bomName || demo.name })
        } catch (error) {
          console.error('Failed to load demo BOM:', error)
        }
      }
    } else if (selectedFile && bomName) {
      uploadMutation.mutate({ file: selectedFile, name: bomName })
    }
  }

  const handleDemoSelect = (demoId: string) => {
    setSelectedDemo(demoId)
    const demo = DEMO_BOMS.find(d => d.id === demoId)
    if (demo) {
      setBomName(demo.name)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Bill of Materials</h1>
          <p className="text-sm text-gray-500 mt-1">Upload and process BOMs with AI-powered supplier matching</p>
        </div>
        <button
          onClick={() => setUploadModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <Upload className="w-4 h-4" />
          Upload BOM
        </button>
      </div>

      {/* BOM List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : boms?.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <FileSpreadsheet className="w-12 h-12 mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No BOMs yet</h3>
          <p className="text-gray-500 mb-4">Upload your first Bill of Materials to get started</p>
          <button
            onClick={() => setUploadModalOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Upload className="w-4 h-4" />
            Upload BOM
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Items
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Matched
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Total Cost
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {boms?.map((bom) => (
                <BOMRow key={bom.id} bom={bom} onDelete={() => deleteMutation.mutate(bom.id)} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Upload Modal */}
      <AnimatePresence>
        {uploadModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/50"
              onClick={() => setUploadModalOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 p-6 max-h-[90vh] overflow-y-auto"
            >
              <button
                onClick={() => setUploadModalOpen(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>

              <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload BOM</h2>

              {/* Mode Toggle */}
              <div className="flex bg-gray-100 rounded-lg p-1 mb-6">
                <button
                  onClick={() => setUploadMode('demo')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                    uploadMode === 'demo'
                      ? 'bg-white text-gray-900 shadow'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  <Sparkles className="w-4 h-4" />
                  Demo Templates
                </button>
                <button
                  onClick={() => setUploadMode('upload')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                    uploadMode === 'upload'
                      ? 'bg-white text-gray-900 shadow'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  <Upload className="w-4 h-4" />
                  Upload File
                </button>
              </div>

              {uploadMode === 'demo' ? (
                <>
                  {/* Demo BOM Selection */}
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    {DEMO_BOMS.map((demo) => {
                      const Icon = demo.icon
                      return (
                        <div
                          key={demo.id}
                          onClick={() => handleDemoSelect(demo.id)}
                          className={`p-4 rounded-lg border-2 text-left transition-all cursor-pointer ${
                            selectedDemo === demo.id
                              ? 'border-primary-500 bg-primary-50'
                              : 'border-gray-200 hover:border-gray-300'
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            <div className={`p-2 rounded-lg ${
                              selectedDemo === demo.id ? 'bg-primary-100' : 'bg-gray-100'
                            }`}>
                              <Icon className={`w-5 h-5 ${
                                selectedDemo === demo.id ? 'text-primary-600' : 'text-gray-500'
                              }`} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-gray-900">{demo.name}</p>
                              <p className="text-sm text-gray-500 mt-0.5">{demo.description}</p>
                              <div className="flex items-center justify-between mt-1">
                                <p className="text-xs text-gray-400">{demo.items} items</p>
                                <a
                                  href={`/data/demo_boms/${demo.file}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1"
                                >
                                  <Eye className="w-3 h-3" />
                                  Preview CSV
                                </a>
                              </div>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </>
              ) : (
                <>
                  {/* Dropzone */}
                  <div
                    {...getRootProps()}
                    className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                      isDragActive
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    <input {...getInputProps()} />
                    {selectedFile ? (
                      <div className="flex items-center justify-center gap-3">
                        <FileSpreadsheet className="w-8 h-8 text-primary-600" />
                        <div className="text-left">
                          <p className="font-medium text-gray-900">{selectedFile.name}</p>
                          <p className="text-sm text-gray-500">
                            {(selectedFile.size / 1024).toFixed(1)} KB
                          </p>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedFile(null)
                          }}
                          className="p-1 hover:bg-gray-100 rounded"
                        >
                          <X className="w-4 h-4 text-gray-400" />
                        </button>
                      </div>
                    ) : (
                      <>
                        <Upload className="w-10 h-10 mx-auto text-gray-400 mb-3" />
                        <p className="text-gray-600">
                          Drag and drop your BOM file here, or click to browse
                        </p>
                        <p className="text-sm text-gray-400 mt-1">
                          Supports Excel, CSV, PDF, and images
                        </p>
                      </>
                    )}
                  </div>
                </>
              )}

              {/* BOM Name */}
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  BOM Name
                </label>
                <input
                  type="text"
                  value={bomName}
                  onChange={(e) => setBomName(e.target.value)}
                  placeholder="Enter a name for this BOM"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>

              {/* Actions */}
              <div className="mt-6 flex justify-end gap-3">
                <button
                  onClick={() => setUploadModalOpen(false)}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleUpload}
                  disabled={
                    (uploadMode === 'upload' && (!selectedFile || !bomName)) ||
                    (uploadMode === 'demo' && !selectedDemo) ||
                    uploadMutation.isPending
                  }
                  className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {uploadMutation.isPending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      Upload & Process
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}

function BOMRow({ bom, onDelete }: { bom: BOM; onDelete: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const isProcessing = ['parsing', 'matching', 'optimizing', 'generating_pos'].includes(bom.processing_status)

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4">
        <Link to={`/boms/${bom.id}`} className="flex items-center gap-3">
          <FileSpreadsheet className="w-5 h-5 text-gray-400" />
          <div>
            <p className="font-medium text-gray-900 hover:text-primary-600">{bom.name}</p>
            <p className="text-sm text-gray-500">{bom.source_file_name}</p>
          </div>
        </Link>
      </td>
      <td className="px-6 py-4 text-sm text-gray-900">{bom.total_items}</td>
      <td className="px-6 py-4 text-sm">
        <span className="text-gray-900">{bom.matched_items}</span>
        <span className="text-gray-400">/{bom.total_items}</span>
      </td>
      <td className="px-6 py-4">
        <div className="space-y-1">
          <StatusBadge status={bom.processing_status} />
          {isProcessing && (
            <div className="w-24">
              <ProgressBar progress={bom.processing_progress} size="sm" />
            </div>
          )}
        </div>
      </td>
      <td className="px-6 py-4 text-sm font-mono text-gray-900">
        {bom.total_cost ? `$${bom.total_cost.toLocaleString()}` : '-'}
      </td>
      <td className="px-6 py-4 text-sm text-gray-500">
        {formatDistanceToNow(new Date(bom.created_at), { addSuffix: true })}
      </td>
      <td className="px-6 py-4 text-right">
        <div className="relative">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <MoreVertical className="w-5 h-5 text-gray-400" />
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 mt-1 w-36 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20">
                <Link
                  to={`/boms/${bom.id}`}
                  className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  <Eye className="w-4 h-4" />
                  View Details
                </Link>
                <button
                  onClick={() => {
                    setMenuOpen(false)
                    onDelete()
                  }}
                  className="flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 w-full"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete
                </button>
              </div>
            </>
          )}
        </div>
      </td>
    </tr>
  )
}
