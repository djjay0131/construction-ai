import { MaterialTakeoff, LumberMaterialItem, MaterialItem } from '@/types/api'
import { Package, FileText, CheckCircle2, AlertCircle } from 'lucide-react'

interface TakeoffResultsProps {
  takeoff: MaterialTakeoff
}

export default function TakeoffResults({ takeoff }: TakeoffResultsProps) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Material Takeoff Results</h2>
            <p className="text-sm text-gray-600 mt-1">
              {takeoff.drawing_filename}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Processed: {new Date(takeoff.processed_at).toLocaleString()}
            </p>
          </div>
          {takeoff.confidence_score && (
            <div className="text-right">
              <div className="text-sm text-gray-600">Confidence</div>
              <div className="text-2xl font-bold text-green-600">
                {(takeoff.confidence_score * 100).toFixed(0)}%
              </div>
            </div>
          )}
        </div>

        {/* Summary Stats */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="flex items-center gap-2">
              <Package className="h-5 w-5 text-blue-600" />
              <div className="text-sm text-gray-600">Total Items</div>
            </div>
            <div className="text-2xl font-bold text-blue-900 mt-2">
              {takeoff.total_items}
            </div>
          </div>

          <div className="bg-green-50 rounded-lg p-4">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-green-600" />
              <div className="text-sm text-gray-600">Lumber Items</div>
            </div>
            <div className="text-2xl font-bold text-green-900 mt-2">
              {takeoff.lumber.length}
            </div>
          </div>

          {takeoff.total_waste_percentage !== undefined && (
            <div className="bg-yellow-50 rounded-lg p-4">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-yellow-600" />
                <div className="text-sm text-gray-600">Waste %</div>
              </div>
              <div className="text-2xl font-bold text-yellow-900 mt-2">
                {takeoff.total_waste_percentage.toFixed(1)}%
              </div>
            </div>
          )}
        </div>

        {/* Notes */}
        {takeoff.notes && takeoff.notes.length > 0 && (
          <div className="mt-4 border-t pt-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Processing Notes:</h3>
            <ul className="space-y-1">
              {takeoff.notes.map((note, index) => (
                <li key={index} className="text-sm text-gray-600 flex items-start gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                  {note}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Warnings */}
        {takeoff.warnings && takeoff.warnings.length > 0 && (
          <div className="mt-4 border-t pt-4">
            <h3 className="text-sm font-semibold text-yellow-700 mb-2">Warnings:</h3>
            <ul className="space-y-1">
              {takeoff.warnings.map((warning, index) => (
                <li key={index} className="text-sm text-yellow-700 flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                  {warning}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Lumber Materials */}
      {takeoff.lumber.length > 0 && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b">
            <h3 className="text-lg font-semibold text-gray-900">Lumber Materials</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Material
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Size
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Quantity
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Unit
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total LF
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Description
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {takeoff.lumber.map((item: LumberMaterialItem) => (
                  <tr key={item.material_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{item.name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-600">
                        {item.specification.nominal_width}x{item.specification.nominal_height}
                      </div>
                      <div className="text-xs text-gray-400">
                        (Actual: {item.specification.actual_width}x{item.specification.actual_height}")
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <div className="text-sm font-semibold text-gray-900">{item.quantity}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-600">{item.unit}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <div className="text-sm text-gray-900">{item.total_linear_feet.toFixed(2)}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-600">{item.description}</div>
                      {item.metadata && (
                        <div className="text-xs text-gray-400 mt-1">
                          {item.metadata.spacing && `Spacing: ${item.metadata.spacing}" O.C.`}
                          {item.metadata.height_inches && ` | Height: ${item.metadata.height_inches}"`}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Other Materials (Concrete, Drywall, etc.) */}
      {[
        { title: 'Concrete', items: takeoff.concrete },
        { title: 'Drywall', items: takeoff.drywall },
        { title: 'Fasteners', items: takeoff.fasteners },
        { title: 'Tie-downs', items: takeoff.tiedowns },
        { title: 'Other', items: takeoff.other },
      ].map(({ title, items }) => (
        items.length > 0 && (
          <div key={title} className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b">
              <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Material
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Quantity
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Unit
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Description
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {items.map((item: MaterialItem) => (
                    <tr key={item.material_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{item.name}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <div className="text-sm font-semibold text-gray-900">{item.quantity}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-600">{item.unit}</div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-600">{item.description}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      ))}
    </div>
  )
}
