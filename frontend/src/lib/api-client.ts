/**
 * API client utility for communicating with the Data Insight backend.
 *
 * The base URL is configured via the API_URL environment variable,
 * defaulting to http://api:8000 for Docker Compose networking.
 */

import type {
  UploadResponse,
  ImportResponse,
  DatasetListItem,
  DatasetDetail,
  PreviewResponse,
  ColumnDescriptor,
  SummaryResponse,
} from "@/types";

import type {
  QueryRequest,
  QueryResponse,
  SQLResponse,
  ChartRequest,
  ChartSpec,
} from "../types/analytics";

/** Chat API types */
export interface ChatRequest {
  dataset_id: string;
  question: string;
}

export interface ChatDataResponse {
  columns: string[];
  rows: Record<string, unknown>[];
}

export interface ChatResponse {
  answer: string;
  sql: string | null;
  data: ChatDataResponse | null;
  timestamp: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sql: string | null;
  data: Record<string, unknown>[] | null;
  timestamp: string;
}

/**
 * On the server side, use the API_URL env var (for Docker networking).
 * On the client side (browser), use relative URLs — Next.js rewrites
 * will proxy /api/* requests to the backend.
 */
const API_BASE_URL =
  typeof window === "undefined"
    ? process.env.API_URL || "http://localhost:8000"
    : "";

/** Custom error class for API response errors. */
export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Make a fetch request to the backend API, handling errors consistently.
 */
async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const response = await fetch(url, options);

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) {
        detail = body.detail;
      }
    } catch {
      // Use default detail if response body is not JSON
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content — return undefined
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

/**
 * Upload a CSV file.
 */
export async function uploadCSV(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return apiFetch<UploadResponse>("/api/v1/datasets/upload", {
    method: "POST",
    body: formData,
  });
}

/**
 * Import a dataset from an external REST API URL.
 */
export async function importFromAPI(url: string): Promise<ImportResponse> {
  return apiFetch<ImportResponse>("/api/v1/datasets/import-api", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

/**
 * List all datasets.
 */
export async function listDatasets(): Promise<DatasetListItem[]> {
  return apiFetch<DatasetListItem[]>("/api/v1/datasets");
}

/**
 * Get detailed information about a specific dataset.
 */
export async function getDatasetDetail(
  datasetId: string
): Promise<DatasetDetail> {
  return apiFetch<DatasetDetail>(`/api/v1/datasets/${datasetId}`);
}

/**
 * Delete a dataset.
 */
export async function deleteDataset(datasetId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/datasets/${datasetId}`, {
    method: "DELETE",
  });
}

/**
 * Get a preview of the first 20 rows of a dataset.
 */
export async function getDatasetPreview(
  datasetId: string
): Promise<PreviewResponse> {
  return apiFetch<PreviewResponse>(
    `/api/v1/datasets/${datasetId}/preview`
  );
}

/**
 * Get column descriptors (name and inferred type) for a dataset.
 */
export async function getDatasetColumns(
  datasetId: string
): Promise<ColumnDescriptor[]> {
  return apiFetch<ColumnDescriptor[]>(
    `/api/v1/datasets/${datasetId}/columns`
  );
}

/**
 * Get statistical summary for a dataset.
 */
export async function getDatasetSummary(
  datasetId: string
): Promise<SummaryResponse> {
  return apiFetch<SummaryResponse>(
    `/api/v1/datasets/${datasetId}/summary`
  );
}

/**
 * Query a dataset with filters, aggregations, sorting, search, and pagination.
 */
export async function queryDataset(
  datasetId: string,
  request: QueryRequest
): Promise<QueryResponse> {
  return apiFetch<QueryResponse>(`/api/v1/datasets/${datasetId}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

/**
 * Execute a SQL SELECT query against a dataset.
 */
export async function sqlQuery(
  datasetId: string,
  query: string
): Promise<SQLResponse> {
  return apiFetch<SQLResponse>(`/api/v1/datasets/${datasetId}/sql`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}

/**
 * Generate a chart specification from a dataset.
 */
export async function generateChart(
  datasetId: string,
  request: ChartRequest
): Promise<ChartSpec> {
  return apiFetch<ChartSpec>(`/api/v1/datasets/${datasetId}/chart`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

/**
 * Send a chat question about a dataset.
 */
export async function sendChatMessage(
  datasetId: string,
  question: string
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/api/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, question }),
  });
}

/**
 * Get chat history for a dataset.
 */
export async function getChatHistory(
  datasetId: string
): Promise<ChatMessage[]> {
  return apiFetch<ChatMessage[]>(
    `/api/v1/chat/history?dataset_id=${encodeURIComponent(datasetId)}`
  );
}

/**
 * Clear chat history for a dataset.
 */
export async function clearChatHistory(
  datasetId: string
): Promise<void> {
  return apiFetch<void>(
    `/api/v1/chat/history?dataset_id=${encodeURIComponent(datasetId)}`,
    { method: "DELETE" }
  );
}
