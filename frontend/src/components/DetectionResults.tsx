import { Download } from 'lucide-react'
import { getAnnotatedImageUrl } from '@/services/api'
import type { DetectionResult } from '@/types/api'

interface DetectionResultsProps {
  detectionResult: DetectionResult
}

export default function DetectionResults({ detectionResult }: DetectionResultsProps) {
  const handleDownloadCSV = () => {
    // Generate CSV data
    const csvLines = ['Object Type,Count']
    Object.entries(detectionResult.object_counts).forEach(([label, count]) => {
      csvLines.push(`${label},${count}`)
    })
    const csvContent = csvLines.join('\n')

    // Create download link
    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `object_counts_${Date.now()}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-semibold text-gray-800">Detection Results</h2>
        <button
          onClick={handleDownloadCSV}
          className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
        >
          <Download className="h-4 w-4" />
          Download CSV
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Annotated Image */}
        <div>
          <h3 className="text-lg font-semibold text-gray-800 mb-3">
            Annotated Image with Object Numbers
          </h3>
          <div className="border rounded-lg overflow-hidden">
            <img
              src={getAnnotatedImageUrl(detectionResult.detection_id)}
              alt="Annotated floor plan"
              className="w-full h-auto"
            />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Detected {detectionResult.detected_objects.length} objects with{' '}
            {(detectionResult.confidence_threshold * 100).toFixed(0)}% confidence threshold
          </p>
        </div>

        {/* Object Counts */}
        <div>
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Object Counts</h3>
          <div className="space-y-3">
            {Object.entries(detectionResult.object_counts).map(([label, count]) => (
              <div
                key={label}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
              >
                <span className="font-medium text-gray-700">{label}</span>
                <span className="text-2xl font-bold text-primary-600">{count}</span>
              </div>
            ))}
          </div>

          {Object.keys(detectionResult.object_counts).length === 0 && (
            <p className="text-gray-500 text-center py-8">
              No objects detected. Try adjusting the confidence threshold or selected labels.
            </p>
          )}
        </div>
      </div>

      {/* Detailed Object List */}
      <div className="mt-8">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Detailed Object Information</h3>
        <div className="space-y-4">
          {detectionResult.detected_objects.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {detectionResult.detected_objects.map((obj, idx) => (
                <div key={idx} className="border rounded-lg p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-gray-800">
                      {obj.label} {obj.index}
                    </h4>
                    <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                      {(obj.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-sm text-gray-600 space-y-1">
                    <p>
                      <span className="font-medium">Position:</span> ({obj.x1.toFixed(0)},{' '}
                      {obj.y1.toFixed(0)})
                    </p>
                    <p>
                      <span className="font-medium">Width:</span> {obj.width_pixels.toFixed(1)} px
                    </p>
                    <p>
                      <span className="font-medium">Height:</span> {obj.height_pixels.toFixed(1)}{' '}
                      px
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No objects detected.</p>
          )}
        </div>
      </div>
    </div>
  )
}
