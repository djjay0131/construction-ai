import { useState } from 'react'
import { Ruler, Download, Loader2 } from 'lucide-react'
import { calibrateMeasurements } from '@/services/api'
import type { DetectionResult, CalibrationResult } from '@/types/api'

interface CalibrationPanelProps {
  detectionResult: DetectionResult
  onCalibrationComplete: (result: CalibrationResult) => void
}

export default function CalibrationPanel({
  detectionResult,
  onCalibrationComplete,
}: CalibrationPanelProps) {
  const [selectedObjectIdx, setSelectedObjectIdx] = useState<number>(0)
  const [realSize, setRealSize] = useState<number>(1.0)
  const [dimension, setDimension] = useState<'width' | 'height'>('width')
  const [unit, setUnit] = useState<string>('meters')
  const [calibrationResult, setCalibrationResult] = useState<CalibrationResult | null>(null)
  const [isCalibrating, setIsCalibrating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (detectionResult.detected_objects.length === 0) {
    return null
  }

  const selectedObject = detectionResult.detected_objects[selectedObjectIdx]

  const handleCalibrate = async () => {
    try {
      setIsCalibrating(true)
      setError(null)

      const result = await calibrateMeasurements({
        detection_id: detectionResult.detection_id,
        reference_object_label: selectedObject.label,
        reference_object_index: selectedObject.index,
        reference_dimension: dimension,
        reference_real_size: realSize,
        unit: unit,
      })

      setCalibrationResult(result)
      onCalibrationComplete(result)
    } catch (err: any) {
      console.error('Calibration error:', err)
      setError(err.response?.data?.detail || err.message || 'Calibration failed')
    } finally {
      setIsCalibrating(false)
    }
  }

  const handleDownloadMeasurementsCSV = () => {
    if (!calibrationResult) return

    // Generate CSV with all measurements
    const csvLines = [
      `Object Type,Object ID,Width (${unit}),Height (${unit}),Diagonal (${unit}),Confidence`,
    ]

    calibrationResult.calibrated_objects.forEach((obj) => {
      csvLines.push(
        `${obj.label},${obj.label} ${obj.index},${obj.width_real?.toFixed(2)},${obj.height_real?.toFixed(2)},${obj.diagonal_real?.toFixed(2)},${(obj.confidence * 100).toFixed(1)}%`
      )
    })

    const csvContent = csvLines.join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `measurements_${unit}_${Date.now()}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  // Group objects by type
  const objectsByType: Record<string, typeof detectionResult.detected_objects> = {}
  detectionResult.detected_objects.forEach((obj) => {
    if (!objectsByType[obj.label]) {
      objectsByType[obj.label] = []
    }
    objectsByType[obj.label].push(obj)
  })

  return (
    <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
      <div className="flex items-center gap-3 mb-6">
        <Ruler className="h-6 w-6 text-primary-600" />
        <h2 className="text-2xl font-semibold text-gray-800">Calibration & Real-World Measurements</h2>
      </div>

      <p className="text-gray-600 mb-6">
        💡 Select a reference object where you know the actual width or height, then enter that
        measurement to calculate real-world dimensions for all objects.
      </p>

      {!calibrationResult ? (
        <div className="space-y-6">
          {/* Reference Object Selection */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Reference Object
              </label>
              <select
                value={selectedObjectIdx}
                onChange={(e) => setSelectedObjectIdx(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
              >
                {detectionResult.detected_objects.map((obj, idx) => (
                  <option key={idx} value={idx}>
                    {obj.label} {obj.index} ({obj.length_pixels.toFixed(0)}px)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Real-World Size
              </label>
              <input
                type="number"
                value={realSize}
                onChange={(e) => setRealSize(Number(e.target.value))}
                min="0.01"
                step="0.1"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Unit</label>
              <select
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
              >
                <option value="meters">Meters</option>
                <option value="feet">Feet</option>
                <option value="inches">Inches</option>
                <option value="cm">Centimeters</option>
              </select>
            </div>
          </div>

          {/* Selected Object Preview */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="font-semibold text-gray-800 mb-3">
              Selected: {selectedObject.label} {selectedObject.index}
            </h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-gray-600">Width (horizontal):</p>
                <p className="font-medium text-gray-900">{selectedObject.width_pixels.toFixed(1)} px</p>
              </div>
              <div>
                <p className="text-gray-600">Height (vertical):</p>
                <p className="font-medium text-gray-900">{selectedObject.height_pixels.toFixed(1)} px</p>
              </div>
            </div>
          </div>

          {/* Dimension Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Which dimension does your measurement represent?
            </label>
            <div className="flex gap-4">
              <label className="flex items-center cursor-pointer">
                <input
                  type="radio"
                  value="width"
                  checked={dimension === 'width'}
                  onChange={(e) => setDimension(e.target.value as 'width' | 'height')}
                  className="mr-2"
                />
                <span className="text-gray-700">Width (horizontal span)</span>
              </label>
              <label className="flex items-center cursor-pointer">
                <input
                  type="radio"
                  value="height"
                  checked={dimension === 'height'}
                  onChange={(e) => setDimension(e.target.value as 'width' | 'height')}
                  className="mr-2"
                />
                <span className="text-gray-700">Height (vertical span)</span>
              </label>
            </div>
          </div>

          {/* Calibrate Button */}
          <button
            onClick={handleCalibrate}
            disabled={isCalibrating || realSize <= 0}
            className="w-full bg-primary-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-primary-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isCalibrating && <Loader2 className="h-5 w-5 animate-spin" />}
            {isCalibrating ? 'Calibrating...' : '🔄 Calculate Real Dimensions'}
          </button>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
              {error}
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-6">
          {/* Calibration Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="font-semibold text-blue-900 mb-2">✅ Calibration Complete!</h3>
            <p className="text-sm text-blue-800">
              <strong>Scale Ratio:</strong> 1 pixel = {calibrationResult.scale_ratio.toFixed(6)}{' '}
              {calibrationResult.unit}
            </p>
            <p className="text-sm text-blue-800">
              <strong>Reference:</strong> {calibrationResult.reference_object}
            </p>
          </div>

          {/* Download Button */}
          <button
            onClick={handleDownloadMeasurementsCSV}
            className="w-full bg-green-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-green-700 transition-colors flex items-center justify-center gap-2"
          >
            <Download className="h-5 w-5" />
            📥 Download All Measurements CSV
          </button>

          {/* Measurements Table */}
          <div>
            <h3 className="text-lg font-semibold text-gray-800 mb-4">
              📐 Real-World Measurements ({calibrationResult.unit})
            </h3>
            <p className="text-xs text-gray-600 mb-4">
              📐 Width = horizontal (left-right), Height = vertical (top-bottom), Diagonal =
              corner-to-corner
            </p>

            {Object.entries(objectsByType).map(([label, objects]) => (
              <div key={label} className="mb-6">
                <h4 className="font-semibold text-gray-700 mb-3">{label}s</h4>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 border">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                          ID
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                          Width ({unit})
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                          Height ({unit})
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                          Diagonal ({unit})
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                          Confidence
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {objects.map((obj, idx) => {
                        const calibratedObj = calibrationResult.calibrated_objects.find(
                          (co) => co.label === obj.label && co.index === obj.index
                        )
                        return (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-4 py-2 text-sm font-medium text-gray-900">
                              {obj.label} {obj.index}
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-700">
                              {calibratedObj?.width_real?.toFixed(2) || '-'}
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-700">
                              {calibratedObj?.height_real?.toFixed(2) || '-'}
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-700">
                              {calibratedObj?.diagonal_real?.toFixed(2) || '-'}
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-700">
                              {(obj.confidence * 100).toFixed(1)}%
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>

          {/* Recalibrate Button */}
          <button
            onClick={() => setCalibrationResult(null)}
            className="w-full bg-gray-600 text-white py-2 px-4 rounded-lg hover:bg-gray-700 transition-colors"
          >
            🔄 Recalibrate
          </button>
        </div>
      )}
    </div>
  )
}
