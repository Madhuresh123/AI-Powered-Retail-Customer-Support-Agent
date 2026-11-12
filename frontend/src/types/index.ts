/**
 * Shared TypeScript types matching the backend API response schemas.
 */

/** Source type for a dataset — either uploaded CSV or imported from API. */
export type SourceType = "csv" | "api";

/** Response from POST /api/v1/datasets/upload */
export interface UploadResponse {
  dataset_id: string;
  name: string;
  row_count: number;
}

/** Response from POST /api/v1/datasets/import-api */
export interface ImportResponse {
  dataset_id: string;
  source_url: string;
  row_count: number;
}

/** A single dataset item returned in the list endpoint. */
export interface DatasetListItem {
  dataset_id: string;
  name: string;
  row_count: number;
  created_at: string; // ISO 8601 datetime
}

/** Full dataset detail from GET /api/v1/datasets/{datasetId} */
export interface DatasetDetail {
  dataset_id: string;
  name: string;
  row_count: number;
  column_count: number;
  created_at: string; // ISO 8601 datetime
  source_type: SourceType;
}

/** Response from GET /api/v1/datasets/{datasetId}/preview */
export interface PreviewResponse {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
}

/** A column descriptor from GET /api/v1/datasets/{datasetId}/columns */
export interface ColumnDescriptor {
  name: string;
  dtype: "number" | "string" | "boolean" | "date";
}

/** Response from GET /api/v1/datasets/{datasetId}/summary */
export interface SummaryResponse {
  row_count: number;
  column_count: number;
  missing_value_count: number;
  duplicate_row_count: number;
  memory_usage_bytes: number;
}

/** Standard error response from the API. */
export interface ErrorResponse {
  detail: string;
}
