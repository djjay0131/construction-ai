/**
 * API Service for Construction AI
 * Handles all API communication with the backend
 */

import axios from 'axios'
import type { MaterialTakeoff } from '@/types/api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types for API responses
export interface UploadResponse {
  success: boolean
  drawing_id: number
  project_id: number
  filename: string
  file_size: number
  file_format: string
  message: string
}

export interface DrawingInfo {
  id: number
  project_id: number
  filename: string
  file_format: string
  file_size: number
  uploaded_at: string
  metadata?: any
}

export interface TakeoffStatusResponse {
  status: string
  started_at?: string
  completed_at?: string
  processing_time_seconds?: number
  total_items?: number
  error_message?: string
}

// API Methods

/**
 * Upload an architectural drawing file
 */
export async function uploadDrawing(
  file: File,
  projectName: string = 'Default Project'
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('project_name', projectName)

  const response = await api.post<UploadResponse>('/api/upload/drawing', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data
}

/**
 * Get information about an uploaded drawing
 */
export async function getDrawing(drawingId: number): Promise<DrawingInfo> {
  const response = await api.get<DrawingInfo>(`/api/upload/drawing/${drawingId}`)
  return response.data
}

/**
 * Delete an uploaded drawing
 */
export async function deleteDrawing(drawingId: number): Promise<void> {
  await api.delete(`/api/upload/drawing/${drawingId}`)
}

/**
 * Process a drawing and create material takeoff
 */
export async function processTakeoff(
  drawingId: number,
  options?: {
    wallHeight?: number
    studSpacing?: number
  }
): Promise<MaterialTakeoff> {
  const params = new URLSearchParams()

  if (options?.wallHeight) {
    params.append('wall_height', options.wallHeight.toString())
  }
  if (options?.studSpacing) {
    params.append('stud_spacing', options.studSpacing.toString())
  }

  const response = await api.post<MaterialTakeoff>(
    `/api/takeoff/process/${drawingId}?${params.toString()}`
  )

  return response.data
}

/**
 * Get the takeoff result for a drawing
 */
export async function getTakeoffResult(drawingId: number): Promise<MaterialTakeoff> {
  const response = await api.get<MaterialTakeoff>(`/api/takeoff/result/${drawingId}`)
  return response.data
}

/**
 * Get the processing status of a takeoff
 */
export async function getTakeoffStatus(drawingId: number): Promise<TakeoffStatusResponse> {
  const response = await api.get<TakeoffStatusResponse>(`/api/takeoff/status/${drawingId}`)
  return response.data
}

/**
 * Health check
 */
export async function healthCheck(): Promise<{ status: string; service: string; version: string }> {
  const response = await api.get('/api/health')
  return response.data
}

// ==========================================
// Object Detection API Methods
// ==========================================

import type { DetectionResult, CalibrationRequest, CalibrationResult } from '@/types/api'

/**
 * Detect objects in a floor plan image
 */
export async function detectObjects(
  file: File,
  options?: {
    confidence?: number
    selectedLabels?: string[]
  }
): Promise<DetectionResult> {
  const formData = new FormData()
  formData.append('file', file)

  if (options?.confidence !== undefined) {
    formData.append('confidence', options.confidence.toString())
  }

  if (options?.selectedLabels && options.selectedLabels.length > 0) {
    formData.append('selected_labels', options.selectedLabels.join(','))
  }

  const response = await api.post<DetectionResult>('/api/detection/detect', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data
}

/**
 * Get annotated image for a detection result
 */
export function getAnnotatedImageUrl(detectionId: string): string {
  return `${API_BASE_URL}/api/detection/image/${detectionId}`
}

/**
 * Get a cached detection result
 */
export async function getDetectionResult(detectionId: string): Promise<DetectionResult> {
  const response = await api.get<DetectionResult>(`/api/detection/result/${detectionId}`)
  return response.data
}

/**
 * Calibrate measurements using a reference object
 */
export async function calibrateMeasurements(
  calibration: CalibrationRequest
): Promise<CalibrationResult> {
  const response = await api.post<CalibrationResult>('/api/detection/calibrate', calibration)
  return response.data
}

/**
 * Delete a detection result
 */
export async function deleteDetectionResult(detectionId: string): Promise<void> {
  await api.delete(`/api/detection/result/${detectionId}`)
}

export default api
