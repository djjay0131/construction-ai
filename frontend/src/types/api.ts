/**
 * TypeScript types for Construction AI API
 * Mirrors the backend Pydantic schemas
 */

export enum MaterialType {
  LUMBER = 'lumber',
  CONCRETE = 'concrete',
  DRYWALL = 'drywall',
  FASTENER = 'fastener',
  TIEDOWN = 'tiedown',
  OTHER = 'other',
}

export enum LumberGrade {
  STUD = 'stud',
  NO2 = 'no2',
  NO1 = 'no1',
  SELECT = 'select',
}

export interface LumberSpecification {
  nominal_width: number
  nominal_height: number
  actual_width: number
  actual_height: number
  grade?: LumberGrade
}

export interface CutPiece {
  piece_id: string
  length_inches: number
  label?: string
  description?: string
}

export interface CutList {
  stock_length_inches: number
  pieces: CutPiece[]
  waste_inches: number
  waste_percentage: number
  quantity_needed: number
}

export interface MaterialItem {
  material_id: string
  material_type: MaterialType
  name: string
  description?: string
  unit: string
  quantity: number
  metadata?: Record<string, any>
}

export interface LumberMaterialItem extends MaterialItem {
  material_type: MaterialType.LUMBER
  specification: LumberSpecification
  total_linear_feet: number
  cut_lists?: CutList[]
}

export interface MaterialTakeoff {
  project_id?: string
  drawing_filename: string
  processed_at: string

  lumber: LumberMaterialItem[]
  concrete: MaterialItem[]
  drywall: MaterialItem[]
  fasteners: MaterialItem[]
  tiedowns: MaterialItem[]
  other: MaterialItem[]

  total_items: number
  total_waste_percentage?: number

  confidence_score?: number
  warnings: string[]
  notes: string[]
}

export enum TakeoffStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export interface TakeoffJob {
  job_id: string
  status: TakeoffStatus
  created_at: string
  updated_at: string
  progress_percentage?: number
  message?: string
  result?: MaterialTakeoff
  error?: string
}

export interface ApiError {
  error: string
  detail?: string
}

export interface HealthCheckResponse {
  status: string
  service: string
  version: string
}
