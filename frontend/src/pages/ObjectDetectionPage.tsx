import { useState } from 'react'
import { Upload, Loader2, AlertCircle, CheckCircle, Eye } from 'lucide-react'
import { detectObjects } from '@/services/api'
import DetectionResults from '@/components/DetectionResults'
import CalibrationPanel from '@/components/CalibrationPanel'
import type { DetectionResult, CalibrationResult } from '@/types/api'

type ProcessingState = 'idle' | 'detecting' | 'detected' | 'error'

const AVAILABLE_LABELS = [
  'Column',
  'Curtain Wall',
  'Dimension',
  'Door',
  'Railing',
  'Sliding Door',
  'Stair Case',
  'Wall',
  'Window',
]

export default function ObjectDetectionPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [state, setState] = useState<ProcessingState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [detectionResult, setDetectionResult] = useState<DetectionResult | null>(null)
  const [calibrationResult, setCalibrationResult] = useState<CalibrationResult | null>(null)
  
  // Configuration
  const [confidence, setConfidence] = useState<number>(0.25)
  const [selectedLabels, setSelectedLabels] = useState<string[]>(AVAILABLE_LABELS)

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      const file = event.target.files[0]
      setSelectedFile(file)
      setError(null)
      setDetectionResult(null)
      setCalibrationResult(null)
      setState('idle')

      // Create preview URL
      const url = URL.createObjectURL(file)
      setPreviewUrl(url)
    }
  }

  const handleLabelToggle = (label: string) => {
    setSelectedLabels((prev) =>
      prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]
    )
  }

  const handleDetect = async () => {
    if (!selectedFile) return

    try {
      setState('detecting')
      setError(null)

      const result = await detectObjects(selectedFile, {
        confidence,
        selectedLabels: selectedLabels.length > 0 ? selectedLabels : undefined,
      })

      console.log('Detection result:', result)
      setDetectionResult(result)
      setState('detected')
    } catch (err: any) {
      console.error('Error detecting objects:', err)
      setError(err.response?.data?.detail || err.message || 'Detection failed')
      setState('error')
    }
  }

  const handleCalibrationComplete = (result: CalibrationResult) => {
    setCalibrationResult(result)
  }

  const getStatusMessage = () => {
    switch (state) {
      case 'detecting':
        return 'Detecting objects...'
      case 'detected':
        return 'Detection completed!'
      case 'error':
        return 'Error occurred'
      default:
        return ''
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Floor Plan Object Detection</h1>
              <p className="text-sm text-gray-600 mt-1">
                Upload a floor plan image to detect and measure objects using YOLOv8
              </p>
            </div>
            <Eye className="h-10 w-10 text-primary-600" />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Upload Section */}
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <h2 className="text-2xl font-semibold text-gray-800 mb-6">Upload Floor Plan Image</h2>

          {/* File Upload Area */}
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-primary-500 transition-colors">
            <Upload className="mx-auto h-12 w-12 text-gray-400" />
            <div className="mt-4">
              <label htmlFor="file-upload" className="cursor-pointer">
                <span className="text-primary-600 hover:text-primary-500 font-medium">
                  Click to upload
                </span>
                <span className="text-gray-600"> or drag and drop</span>
                <input
                  id="file-upload"
                  name="file-upload"
                  type="file"
                  className="sr-only"
                  accept=".png,.jpg,.jpeg"
                  onChange={handleFileSelect}
                />
              </label>
            </div>
            <p className="text-xs text-gray-500 mt-2">PNG or JPG up to 100MB</p>

            {selectedFile && (
              <div className="mt-4 flex items-center justify-center gap-2 text-green-600">
                <CheckCircle className="h-5 w-5" />
                <span className="font-medium">{selectedFile.name}</span>
              </div>
            )}
          </div>

          {/* Configuration */}
          {selectedFile && state === 'idle' && (
            <div className="mt-6 space-y-6">
              {/* Preview */}
              {previewUrl && (
                <div className="border rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Image Preview</h3>
                  <img
                    src={previewUrl}
                    alt="Preview"
                    className="max-h-64 mx-auto object-contain"
                  />
                </div>
              )}

              {/* Confidence Slider */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Confidence Threshold: {(confidence * 100).toFixed(0)}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={confidence}
                  onChange={(e) => setConfidence(Number(e.target.value))}
                  className="w-full"
                />
              </div>

              {/* Label Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Objects to Detect
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {AVAILABLE_LABELS.map((label) => (
                    <button
                      key={label}
                      onClick={() => handleLabelToggle(label)}
                      className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                        selectedLabels.includes(label)
                          ? 'bg-primary-600 text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setSelectedLabels(AVAILABLE_LABELS)}
                  className="mt-2 text-sm text-primary-600 hover:text-primary-700"
                >
                  Select All
                </button>
                {' | '}
                <button
                  onClick={() => setSelectedLabels([])}
                  className="text-sm text-primary-600 hover:text-primary-700"
                >
                  Clear All
                </button>
              </div>

              <button
                onClick={handleDetect}
                disabled={selectedLabels.length === 0}
                className="w-full bg-primary-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-primary-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                Detect Objects
              </button>
            </div>
          )}

          {/* Processing Status */}
          {state === 'detecting' && (
            <div className="mt-6 flex items-center justify-center gap-3 text-primary-600">
              <Loader2 className="h-6 w-6 animate-spin" />
              <span className="font-medium">{getStatusMessage()}</span>
            </div>
          )}

          {/* Error Message */}
          {state === 'error' && error && (
            <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-semibold text-red-800">Error</h3>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          )}
        </div>

        {/* Detection Results */}
        {detectionResult && state === 'detected' && (
          <>
            <DetectionResults detectionResult={detectionResult} />
            <CalibrationPanel
              detectionResult={detectionResult}
              onCalibrationComplete={handleCalibrationComplete}
            />
          </>
        )}

        {/* Info Cards */}
        {!detectionResult && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-3xl mb-3">🎯</div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">AI-Powered Detection</h3>
              <p className="text-gray-600 text-sm">
                Uses YOLOv8 to automatically identify columns, walls, doors, windows, and more
              </p>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-3xl mb-3">📏</div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Real-World Measurements</h3>
              <p className="text-gray-600 text-sm">
                Calibrate with a known dimension to get accurate real-world sizes
              </p>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-3xl mb-3">📊</div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Export Results</h3>
              <p className="text-gray-600 text-sm">
                Download object counts and measurements as CSV for further analysis
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
