import { useState } from 'react'
import { Upload, FileText, CheckCircle, Loader2, AlertCircle } from 'lucide-react'
import { uploadDrawing, processTakeoff } from '@/services/api'
import TakeoffResults from '@/components/TakeoffResults'
import type { MaterialTakeoff } from '@/types/api'

type ProcessingState = 'idle' | 'uploading' | 'processing' | 'completed' | 'error'

export default function HomePage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [state, setState] = useState<ProcessingState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [takeoffResult, setTakeoffResult] = useState<MaterialTakeoff | null>(null)
  const [studSpacing, setStudSpacing] = useState<number>(16)
  const [wallHeight, setWallHeight] = useState<number>(96)

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0])
      setError(null)
      setTakeoffResult(null)
      setState('idle')
    }
  }

  const handleProcess = async () => {
    if (!selectedFile) return

    try {
      setState('uploading')
      setError(null)

      // Upload the file
      const uploadResponse = await uploadDrawing(selectedFile)
      console.log('Upload response:', uploadResponse)

      // Process the takeoff
      setState('processing')
      const result = await processTakeoff(uploadResponse.drawing_id, {
        wallHeight,
        studSpacing,
      })

      console.log('Takeoff result:', result)
      setTakeoffResult(result)
      setState('completed')
    } catch (err: any) {
      console.error('Error processing drawing:', err)
      setError(err.response?.data?.detail || err.message || 'An error occurred')
      setState('error')
    }
  }

  const getStatusMessage = () => {
    switch (state) {
      case 'uploading':
        return 'Uploading drawing...'
      case 'processing':
        return 'Processing takeoff...'
      case 'completed':
        return 'Processing complete!'
      default:
        return ''
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-primary-600 to-primary-700 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2">Construction AI</h1>
              <p className="text-primary-100 text-lg">
                Automated Material Take-off from Architectural Drawings
              </p>
            </div>
            <div className="text-sm text-gray-500">v0.1.0</div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Upload Section */}
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <h2 className="text-2xl font-semibold text-gray-800 mb-6">Upload Architectural Drawing</h2>

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
                  accept=".dwg,.dxf,.pdf,.png,.jpg,.jpeg"
                  onChange={handleFileSelect}
                />
              </label>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              DWG, DXF, PDF, PNG, JPG up to 100MB
            </p>

            {selectedFile && (
              <div className="mt-4 flex items-center justify-center gap-2 text-green-600">
                <CheckCircle className="h-5 w-5" />
                <span className="font-medium">{selectedFile.name}</span>
              </div>
            )}
          </div>

          {selectedFile && state === 'idle' && (
            <div className="mt-6 space-y-4">
              {/* Configuration Options */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Wall Height (inches)
                  </label>
                  <input
                    type="number"
                    value={wallHeight}
                    onChange={(e) => setWallHeight(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
                    min="48"
                    max="240"
                    step="12"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Stud Spacing (inches O.C.)
                  </label>
                  <select
                    value={studSpacing}
                    onChange={(e) => setStudSpacing(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value={12}>12" O.C.</option>
                    <option value={16}>16" O.C.</option>
                    <option value={24}>24" O.C.</option>
                  </select>
                </div>
              </div>

              <button
                onClick={handleProcess}
                className="w-full bg-primary-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-primary-700 transition-colors"
              >
                Process Drawing
              </button>
            </div>
          )}

          {/* Processing Status */}
          {(state === 'uploading' || state === 'processing') && (
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

        {/* Results Section */}
        {takeoffResult && state === 'completed' && (
          <TakeoffResults takeoff={takeoffResult} />
        )}

        {/* Features Section */}
        {!takeoffResult && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <FileText className="h-8 w-8 text-primary-600 mb-3" />
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Multi-Format Support</h3>
              <p className="text-gray-600 text-sm">
                Upload DWG, DXF, PDF, or image files of your architectural plans
              </p>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <CheckCircle className="h-8 w-8 text-primary-600 mb-3" />
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Accurate Calculations</h3>
              <p className="text-gray-600 text-sm">
                AI-powered material detection and quantity calculation
              </p>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <Loader2 className="h-8 w-8 text-primary-600 mb-3" />
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Fast Processing</h3>
              <p className="text-gray-600 text-sm">
                Get your material takeoff results in minutes, not hours
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
