import { useState } from 'react'
import { Upload, Loader2, AlertCircle, CheckCircle, FileText, Maximize2, Settings, Download } from 'lucide-react'
import { analyzePDF, detectObjectsInFloorPlan, getFloorPlanImageUrl, exportAnalysisJSON, exportFloorPlanJSON, type PDFAnalysisResult, type FloorPlanInfo, type FloorPlanDetectionResult } from '@/services/api'

type ProcessingState = 'idle' | 'uploading' | 'analyzing' | 'selecting' | 'detecting' | 'completed' | 'error'

export default function FloorPlanAnalysisPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [state, setState] = useState<ProcessingState>('idle')
  const [error, setError] = useState<string | null>(null)

  // Analysis results
  const [analysisResult, setAnalysisResult] = useState<PDFAnalysisResult | null>(null)
  const [selectedFloorPlan, setSelectedFloorPlan] = useState<number | null>(null)
  const [detectionResult, setDetectionResult] = useState<FloorPlanDetectionResult | null>(null)

  // User-adjustable parameters
  const [confidence, setConfidence] = useState<number>(0.05)
  const [manualScale, setManualScale] = useState<string>('')
  const [pageNumber, setPageNumber] = useState<number>(1)

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0])
      setError(null)
      setAnalysisResult(null)
      setSelectedFloorPlan(null)
      setDetectionResult(null)
      setState('idle')
    }
  }

  const handleAnalyzePDF = async () => {
    if (!selectedFile) return

    try {
      setState('analyzing')
      setError(null)

      console.log('Analyzing PDF:', selectedFile.name, 'Page:', pageNumber)
      const result = await analyzePDF(selectedFile, pageNumber)

      console.log('Analysis complete:', result)
      setAnalysisResult(result)

      if (result.num_floor_plans === 0) {
        setError('No floor plans detected in the PDF. Try a different page or file.')
        setState('error')
      } else {
        setState('selecting')
      }
    } catch (err: any) {
      console.error('Error analyzing PDF:', err)
      console.error('Error details:', {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status,
        stack: err.stack
      })

      let errorMessage = 'Failed to analyze PDF'

      if (err.response) {
        // Server responded with error
        errorMessage = err.response.data?.detail || err.response.data?.message || `Server error: ${err.response.status}`
      } else if (err.request) {
        // Request made but no response
        errorMessage = 'No response from server. Is the backend running at http://localhost:8000?'
      } else {
        // Something else went wrong
        errorMessage = err.message || 'Unknown error occurred'
      }

      setError(errorMessage)
      setState('error')
    }
  }

  const handleSelectFloorPlan = (floorPlanId: number) => {
    setSelectedFloorPlan(floorPlanId)
    setDetectionResult(null)
  }

  const handleDetectObjects = async () => {
    if (!analysisResult || selectedFloorPlan === null) return

    try {
      setState('detecting')
      setError(null)

      console.log('Detecting objects in floor plan:', selectedFloorPlan, {
        confidence,
        manual_scale: manualScale || 'auto'
      })

      const result = await detectObjectsInFloorPlan({
        analysis_id: analysisResult.analysis_id,
        floor_plan_id: selectedFloorPlan,
        confidence: confidence,
        manual_scale: manualScale || undefined
      })

      console.log('Detection complete:', result)
      setDetectionResult(result)
      setState('completed')
    } catch (err: any) {
      console.error('Error detecting objects:', err)
      console.error('Error details:', {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status
      })

      let errorMessage = 'Failed to detect objects'

      if (err.response) {
        errorMessage = err.response.data?.detail || err.response.data?.message || `Server error: ${err.response.status}`
      } else if (err.request) {
        errorMessage = 'No response from server. Is the backend running?'
      } else {
        errorMessage = err.message || 'Unknown error occurred'
      }

      setError(errorMessage)
      setState('error')
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setAnalysisResult(null)
    setSelectedFloorPlan(null)
    setDetectionResult(null)
    setError(null)
    setState('idle')
  }

  const handleExportJSON = () => {
    if (!analysisResult || selectedFloorPlan === null) return
    
    // Download the JSON file
    const url = exportFloorPlanJSON(analysisResult.analysis_id, selectedFloorPlan)
    const link = document.createElement('a')
    link.href = url
    link.download = `floor_plan_${selectedFloorPlan}_analysis.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const getStatusMessage = () => {
    switch (state) {
      case 'analyzing':
        return 'Analyzing PDF and detecting floor plans...'
      case 'detecting':
        return 'Detecting objects in floor plan...'
      default:
        return ''
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <div className="flex items-center gap-4 mb-4">
            <Maximize2 className="h-10 w-10 text-primary-600" />
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Floor Plan Analysis</h1>
              <p className="text-gray-600 mt-1">
                Upload a PDF, detect floor plans, extract scale, and identify objects
              </p>
            </div>
          </div>

          {/* Workflow Steps */}
          <div className="mt-6 flex items-center justify-between text-sm">
            <div className={`flex items-center gap-2 ${state !== 'idle' ? 'text-green-600' : 'text-gray-400'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${state !== 'idle' ? 'bg-green-100' : 'bg-gray-100'}`}>
                {state !== 'idle' ? <CheckCircle className="h-5 w-5" /> : '1'}
              </div>
              <span className="font-medium">Upload PDF</span>
            </div>
            <div className="flex-1 h-1 mx-4 bg-gray-200">
              <div className={`h-full ${state !== 'idle' ? 'bg-green-500' : 'bg-gray-200'}`} />
            </div>

            <div className={`flex items-center gap-2 ${state === 'selecting' || state === 'detecting' || state === 'completed' ? 'text-green-600' : 'text-gray-400'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${state === 'selecting' || state === 'detecting' || state === 'completed' ? 'bg-green-100' : 'bg-gray-100'}`}>
                {state === 'selecting' || state === 'detecting' || state === 'completed' ? <CheckCircle className="h-5 w-5" /> : '2'}
              </div>
              <span className="font-medium">Select Floor Plan</span>
            </div>
            <div className="flex-1 h-1 mx-4 bg-gray-200">
              <div className={`h-full ${state === 'detecting' || state === 'completed' ? 'bg-green-500' : 'bg-gray-200'}`} />
            </div>

            <div className={`flex items-center gap-2 ${state === 'completed' ? 'text-green-600' : 'text-gray-400'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${state === 'completed' ? 'bg-green-100' : 'bg-gray-100'}`}>
                {state === 'completed' ? <CheckCircle className="h-5 w-5" /> : '3'}
              </div>
              <span className="font-medium">View Results</span>
            </div>
          </div>
        </div>

        {/* Step 1: Upload PDF */}
        {(state === 'idle' || state === 'analyzing') && (
          <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">Step 1: Upload PDF</h2>

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
                    accept=".pdf"
                    onChange={handleFileSelect}
                    disabled={state === 'analyzing'}
                  />
                </label>
              </div>
              <p className="text-xs text-gray-500 mt-2">PDF files only, up to 100MB</p>

              {selectedFile && (
                <div className="mt-4 flex items-center justify-center gap-2 text-green-600">
                  <CheckCircle className="h-5 w-5" />
                  <span className="font-medium">{selectedFile.name}</span>
                </div>
              )}
            </div>

            {/* Configuration */}
            {selectedFile && state === 'idle' && (
              <div className="mt-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Page Number
                  </label>
                  <input
                    type="number"
                    value={pageNumber}
                    onChange={(e) => setPageNumber(Math.max(1, parseInt(e.target.value) || 1))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
                    min="1"
                  />
                  <p className="text-xs text-gray-500 mt-1">Which page of the PDF to analyze</p>
                </div>

                <button
                  onClick={handleAnalyzePDF}
                  className="w-full bg-primary-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-primary-700 transition-colors"
                >
                  Analyze PDF
                </button>
              </div>
            )}

            {/* Processing Status */}
            {state === 'analyzing' && (
              <div className="mt-6 flex items-center justify-center gap-3 text-primary-600">
                <Loader2 className="h-6 w-6 animate-spin" />
                <span className="font-medium">{getStatusMessage()}</span>
              </div>
            )}
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-8 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-red-800">Error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
              <button
                onClick={handleReset}
                className="mt-3 text-sm text-red-600 hover:text-red-700 font-medium"
              >
                Try Again
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Select Floor Plan */}
        {analysisResult && (state === 'selecting' || state === 'detecting' || state === 'completed') && (
          <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">Step 2: Select Floor Plan</h2>

            {/* Document Info */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-gray-700 font-medium">Paper Size:</span>
                  <span className="ml-2 font-semibold text-gray-900">{analysisResult.paper_size.name}</span>
                </div>
                <div>
                  <span className="text-gray-700 font-medium">Dimensions:</span>
                  <span className="ml-2 font-semibold text-gray-900">
                    {analysisResult.paper_size.width_inches.toFixed(1)}" × {analysisResult.paper_size.height_inches.toFixed(1)}"
                  </span>
                </div>
                <div>
                  <span className="text-gray-700 font-medium">Floor Plans:</span>
                  <span className="ml-2 font-semibold text-gray-900">{analysisResult.num_floor_plans}</span>
                </div>
                <div>
                  <span className="text-gray-700 font-medium">Scale Detected:</span>
                  <span className={`ml-2 font-semibold ${analysisResult.full_page_scale?.found ? 'text-green-700' : 'text-red-700'}`}>
                    {analysisResult.full_page_scale?.found ? analysisResult.full_page_scale.notation : 'Not found'}
                  </span>
                </div>
              </div>
            </div>

            {/* Floor Plans Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {analysisResult.floor_plans.map((floorPlan) => (
                <div
                  key={floorPlan.id}
                  onClick={() => handleSelectFloorPlan(floorPlan.id)}
                  className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${
                    selectedFloorPlan === floorPlan.id
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-primary-300'
                  }`}
                >
                  <div className="aspect-video bg-gray-100 rounded mb-3 overflow-hidden">
                    <img
                      src={getFloorPlanImageUrl(analysisResult.analysis_id, `page${analysisResult.page_number}_floorplan${floorPlan.id}.png`)}
                      alt={`Floor Plan ${floorPlan.id}`}
                      className="w-full h-full object-contain"
                    />
                  </div>
                  <h3 className="font-bold text-gray-900 text-lg mb-2">Floor Plan {floorPlan.id}</h3>
                  <div className="text-sm space-y-1">
                    <div className="text-gray-800 font-medium">
                      Size: {floorPlan.width_pixels} × {floorPlan.height_pixels} px
                    </div>
                    {floorPlan.scale?.found && (
                      <div className="text-green-700 font-semibold bg-green-50 px-2 py-1 rounded">
                        Scale: {floorPlan.scale.notation}
                      </div>
                    )}
                  </div>
                  {selectedFloorPlan === floorPlan.id && (
                    <div className="mt-3 flex items-center gap-2 text-primary-600">
                      <CheckCircle className="h-4 w-4" />
                      <span className="text-sm font-medium">Selected</span>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Detection Parameters */}
            {selectedFloorPlan !== null && state === 'selecting' && (
              <div className="mt-8 border-t pt-6">
                <div className="flex items-center gap-2 mb-4">
                  <Settings className="h-5 w-5 text-gray-600" />
                  <h3 className="text-lg font-semibold text-gray-900">Detection Parameters</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Confidence Threshold: {confidence.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="0.01"
                      max="1"
                      step="0.01"
                      value={confidence}
                      onChange={(e) => setConfidence(parseFloat(e.target.value))}
                      className="w-full"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Lower = more detections (may include false positives)
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Manual Scale Override (optional)
                    </label>
                    <input
                      type="text"
                      value={manualScale}
                      onChange={(e) => setManualScale(e.target.value)}
                      placeholder='e.g., 1/4"=1&apos;-0"'
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Override auto-detected scale
                    </p>
                  </div>
                </div>

                <button
                  onClick={handleDetectObjects}
                  className="w-full bg-primary-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-primary-700 transition-colors"
                >
                  Detect Objects
                </button>
              </div>
            )}

            {/* Detecting Status */}
            {state === 'detecting' && (
              <div className="mt-6 flex items-center justify-center gap-3 text-primary-600">
                <Loader2 className="h-6 w-6 animate-spin" />
                <span className="font-medium">{getStatusMessage()}</span>
              </div>
            )}
          </div>
        )}

        {/* Step 3: View Results */}
        {detectionResult && state === 'completed' && analysisResult && selectedFloorPlan !== null && (
          <div className="bg-white rounded-lg shadow-lg p-8">
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">
              Floor Plan {selectedFloorPlan} - Real-World Measurements
            </h2>

            {/* Document Information */}
            <div className="bg-gray-800 text-gray-100 rounded-lg p-6 mb-6 font-mono text-sm">
              <h3 className="text-lg font-bold text-white mb-4">Document Information:</h3>
              <div className="space-y-1">
                <div>  Paper Size: <span className="text-yellow-300">{analysisResult.paper_size.name}</span></div>
                <div>  Paper Dimensions: <span className="text-yellow-300">
                  {analysisResult.paper_size.width_inches.toFixed(2)}" x {analysisResult.paper_size.height_inches.toFixed(2)}"
                </span></div>
                <div>  Page Resolution: <span className="text-yellow-300">
                  {(() => {
                    const fp = analysisResult.floor_plans.find(f => f.id === selectedFloorPlan);
                    if (!fp) return 'N/A';
                    // Estimate page dimensions from floor plan and paper size
                    const ppi = 300; // DPI
                    return `${Math.round(analysisResult.paper_size.width_inches * ppi)} x ${Math.round(analysisResult.paper_size.height_inches * ppi)} pixels`;
                  })()}
                </span></div>
                <div>  DPI: <span className="text-yellow-300">300</span></div>
                <div>  Pixels per Inch: <span className="text-yellow-300">300.00 x 300.00</span></div>
              </div>
            </div>

            {/* Scale Information */}
            {detectionResult.scale_used.found && (
              <div className="bg-gray-800 text-gray-100 rounded-lg p-6 mb-6 font-mono text-sm">
                <h3 className="text-lg font-bold text-white mb-4">Scale Information:</h3>
                <div className="space-y-1">
                  <div>  Scale Notation: <span className="text-green-300">{detectionResult.scale_used.notation}</span></div>
                  {detectionResult.scale_used.scale_ratio && (
                    <>
                      <div>  Scale Ratio: <span className="text-green-300">1:{detectionResult.scale_used.scale_ratio.toFixed(2)} (real/drawing)</span></div>
                      <div>  Meaning: <span className="text-green-300">1 inch on paper = {detectionResult.scale_used.scale_ratio.toFixed(2)} inches in reality</span></div>
                      <div>           <span className="text-green-300">1 inch on paper = {(detectionResult.scale_used.scale_ratio / 12).toFixed(2)} feet in reality</span></div>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Floor Plan Dimensions */}
            {(() => {
              const fp = analysisResult.floor_plans.find(f => f.id === selectedFloorPlan);
              if (!fp) return null;
              return (
                <div className="bg-gray-800 text-gray-100 rounded-lg p-6 mb-6 font-mono text-sm">
                  <h3 className="text-lg font-bold text-white mb-4">Floor Plan Dimensions:</h3>
                  <div className="space-y-1">
                    <div>  Pixels: <span className="text-cyan-300">{fp.width_pixels} x {fp.height_pixels} px</span></div>
                    <div>  On Paper: <span className="text-cyan-300">
                      {fp.width_inches?.toFixed(3)}" x {fp.height_inches?.toFixed(3)}"
                    </span></div>
                    {fp.real_width && fp.real_height && (
                      <>
                        <div>  Real World: <span className="text-cyan-300">{fp.real_width} x {fp.real_height}</span></div>
                        {fp.real_area_sqft && (
                          <div>  Real World Area: <span className="text-cyan-300">{fp.real_area_sqft.toFixed(2)} sq ft</span></div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })()}

            {/* Object Counts Summary */}
            <div className="bg-gray-800 text-gray-100 rounded-lg p-6 mb-6 font-mono text-sm">
              <h3 className="text-lg font-bold text-white mb-4">
                Detected Objects: {detectionResult.detected_objects.length}
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(detectionResult.object_counts).map(([className, count]) => (
                  <div key={className} className="bg-gray-700 rounded p-3 text-center">
                    <div className="text-3xl font-bold text-yellow-300">{count}</div>
                    <div className="text-sm text-gray-300 capitalize mt-1">{className}</div>
                  </div>
                ))}
              </div>
              <div className="mt-4 text-xs text-gray-400">
                NOTE: Object numbers correspond to labels in the numbered annotation image
              </div>
            </div>

            {/* Annotated Images */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              <div>
                <h3 className="font-semibold text-gray-900 mb-3">Numbered Annotations</h3>
                <div className="border rounded-lg overflow-hidden bg-gray-100">
                  <img
                    src={getFloorPlanImageUrl(analysisResult.analysis_id, `page${analysisResult.page_number}_floorplan${selectedFloorPlan}_numbered.png`)}
                    alt="Numbered Annotations"
                    className="w-full"
                  />
                </div>
                <p className="text-sm text-gray-600 mt-2">
                  Objects are numbered by class (e.g., Wall #1, Door #1)
                </p>
              </div>

              <div>
                <h3 className="font-semibold text-gray-900 mb-3">Standard Annotations</h3>
                <div className="border rounded-lg overflow-hidden bg-gray-100">
                  <img
                    src={getFloorPlanImageUrl(analysisResult.analysis_id, `page${analysisResult.page_number}_floorplan${selectedFloorPlan}_annotated.png`)}
                    alt="Standard Annotations"
                    className="w-full"
                  />
                </div>
                <p className="text-sm text-gray-600 mt-2">
                  Standard YOLO detection visualization
                </p>
              </div>
            </div>

            {/* Detailed Object Measurements */}
            <div className="bg-gray-800 text-gray-100 rounded-lg p-6 mb-6 font-mono text-xs overflow-x-auto">
              <h3 className="text-lg font-bold text-white mb-4">Detailed Measurements by Object Class</h3>

              {Object.entries(detectionResult.object_counts).map(([className, count]) => {
                const objectsOfClass = detectionResult.detected_objects
                  .filter(obj => obj.class_name === className)
                  .sort((a, b) => a.id - b.id);

                return (
                  <div key={className} className="mb-8">
                    <div className="border-b border-gray-600 pb-2 mb-4">
                      <h4 className="text-md font-bold text-yellow-300 uppercase">
                        {className} ({count} detected)
                      </h4>
                    </div>

                    {objectsOfClass.map((obj) => {
                      const width_px = obj.bbox.x2 - obj.bbox.x1;
                      const height_px = obj.bbox.y2 - obj.bbox.y1;
                      const dims = obj.real_dimensions;

                      return (
                        <div key={`${obj.class_name}-${obj.id}`} className="mb-6 pl-4 border-l-2 border-gray-600">
                          <div className="text-cyan-300 font-bold mb-2">
                            {obj.class_name} #{obj.id}:
                          </div>
                          <div className="space-y-1 pl-4">
                            <div>Confidence: <span className="text-white">{obj.confidence.toFixed(3)}</span></div>
                            <div>Pixels: <span className="text-white">{width_px.toFixed(1)} x {height_px.toFixed(1)} px</span></div>

                            {dims && dims.bbox_inches_on_paper && (
                              <div>On Paper: <span className="text-white">
                                {dims.bbox_inches_on_paper[0].toFixed(3)}" x {dims.bbox_inches_on_paper[1].toFixed(3)}"
                              </span></div>
                            )}

                            {dims && dims.real_feet_inches && (
                              <>
                                <div>Real Size: <span className="text-green-300">
                                  {(() => {
                                    const [wFt, wIn] = dims.real_feet_inches[0];
                                    const [hFt, hIn] = dims.real_feet_inches[1];
                                    const formatDim = (ft: number, inch: number) =>
                                      ft === 0 ? `${inch.toFixed(2)}"` : `${ft}'-${inch.toFixed(2)}"`;
                                    return `${formatDim(wFt, wIn)} x ${formatDim(hFt, hIn)}`;
                                  })()}
                                </span></div>
                                <div>Real Size (inches): <span className="text-green-300">
                                  {dims.real_inches[0].toFixed(2)}" x {dims.real_inches[1].toFixed(2)}"
                                </span></div>
                                {className.toLowerCase() === 'door' && (
                                  <>
                                    <div>Door Width: <span className="text-green-300">
                                      {dims.real_inches[0].toFixed(2)}" ({(dims.real_inches[0] / 12).toFixed(2)}')
                                    </span></div>
                                    <div>Door Height: <span className="text-green-300">
                                      {dims.real_inches[1].toFixed(2)}" ({(dims.real_inches[1] / 12).toFixed(2)}')
                                    </span></div>
                                  </>
                                )}
                                {className.toLowerCase() === 'wall' && (
                                  <>
                                    <div>Wall Length: <span className="text-green-300">
                                      {Math.max(dims.real_feet_decimal[0], dims.real_feet_decimal[1]).toFixed(2)}'
                                    </span></div>
                                    <div>Wall Thickness: <span className="text-green-300">
                                      {Math.min(dims.real_inches[0], dims.real_inches[1]).toFixed(2)}"
                                    </span></div>
                                  </>
                                )}
                                {className.toLowerCase() === 'window' && (
                                  <>
                                    <div>Window Width: <span className="text-green-300">
                                      {dims.real_inches[0].toFixed(2)}" ({(dims.real_inches[0] / 12).toFixed(2)}')
                                    </span></div>
                                    <div>Window Height: <span className="text-green-300">
                                      {dims.real_inches[1].toFixed(2)}" ({(dims.real_inches[1] / 12).toFixed(2)}')
                                    </span></div>
                                  </>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>

            {/* Summary Statistics */}
            {detectionResult.scale_used.found && (
              <div className="bg-gray-800 text-gray-100 rounded-lg p-6 mb-6 font-mono text-sm">
                <h3 className="text-lg font-bold text-white mb-4">Summary Statistics</h3>

                {Object.entries(detectionResult.object_counts).map(([className, count]) => {
                  const objectsOfClass = detectionResult.detected_objects.filter(obj => obj.class_name === className);

                  // Calculate statistics
                  const widths = objectsOfClass
                    .map(obj => obj.real_dimensions?.real_inches?.[0])
                    .filter((w): w is number => w !== undefined);
                  const heights = objectsOfClass
                    .map(obj => obj.real_dimensions?.real_inches?.[1])
                    .filter((h): h is number => h !== undefined);

                  if (widths.length === 0 || heights.length === 0) return null;

                  const avgWidth = widths.reduce((a, b) => a + b, 0) / widths.length;
                  const avgHeight = heights.reduce((a, b) => a + b, 0) / heights.length;
                  const minWidth = Math.min(...widths);
                  const maxWidth = Math.max(...widths);
                  const minHeight = Math.min(...heights);
                  const maxHeight = Math.max(...heights);

                  // For walls, calculate total length
                  let totalLength = 0;
                  if (className.toLowerCase() === 'wall') {
                    totalLength = objectsOfClass.reduce((sum, obj) => {
                      if (obj.real_dimensions?.real_feet_decimal) {
                        return sum + Math.max(obj.real_dimensions.real_feet_decimal[0], obj.real_dimensions.real_feet_decimal[1]);
                      }
                      return sum;
                    }, 0);
                  }

                  return (
                    <div key={className} className="mb-6 border-b border-gray-600 pb-4">
                      <h4 className="text-yellow-300 font-bold uppercase mb-2">{className}:</h4>
                      <div className="space-y-1 pl-4">
                        <div>Count: <span className="text-white">{count}</span></div>
                        <div>Average Size: <span className="text-white">
                          {avgWidth.toFixed(2)}" x {avgHeight.toFixed(2)}" ({(avgWidth/12).toFixed(2)}' x {(avgHeight/12).toFixed(2)}')
                        </span></div>
                        <div>Width Range: <span className="text-white">{minWidth.toFixed(2)}" - {maxWidth.toFixed(2)}"</span></div>
                        <div>Height Range: <span className="text-white">{minHeight.toFixed(2)}" - {maxHeight.toFixed(2)}"</span></div>
                        {className.toLowerCase() === 'wall' && totalLength > 0 && (
                          <div>Total Wall Length: <span className="text-green-300">{totalLength.toFixed(2)}' ({totalLength.toFixed(10)} linear feet)</span></div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Actions */}
            <div className="mt-8 flex gap-4">
              <button
                onClick={handleExportJSON}
                className="flex items-center gap-2 bg-green-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-green-700 transition-colors"
              >
                <Download className="h-5 w-5" />
                Export as JSON
              </button>
              <button
                onClick={() => {
                  setSelectedFloorPlan(null)
                  setDetectionResult(null)
                  setState('selecting')
                }}
                className="flex-1 bg-gray-200 text-gray-700 py-3 px-6 rounded-lg font-semibold hover:bg-gray-300 transition-colors"
              >
                Select Different Floor Plan
              </button>
              <button
                onClick={handleReset}
                className="flex-1 bg-primary-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-primary-700 transition-colors"
              >
                Analyze New PDF
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

