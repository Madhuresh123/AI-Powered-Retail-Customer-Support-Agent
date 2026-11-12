/**
 * TypeScript types for the Analytics Engine.
 * Covers query/filter, charting, and SQL interfaces.
 */

export type FilterOperator =
  | "eq" | "neq" | "gt" | "gte" | "lt" | "lte"
  | "between" | "contains" | "starts_with" | "ends_with" | "in";

export interface FilterExpression {
  column: string;
  operator: FilterOperator;
  value: unknown;
}

export interface AggregationOp {
  function: "count" | "sum" | "avg" | "min" | "max" | "median" | "std" | "distinct_count";
  column: string;
}

export interface SortSpec {
  column: string;
  direction: "asc" | "desc";
}

export interface QueryRequest {
  filters?: FilterExpression[];
  search?: string;
  search_columns?: string[];
  aggregations?: AggregationOp[];
  group_by?: string[];
  sort?: SortSpec[];
  page?: number;
  page_size?: number;
}

export interface PaginationMeta {
  total_rows: number;
  total_pages: number;
  current_page: number;
  page_size: number;
}

export interface QueryResponse {
  columns: string[];
  rows: Record<string, unknown>[];
  pagination: PaginationMeta;
}

export type ChartType = "bar" | "line" | "pie" | "scatter" | "histogram";

export interface ChartRequest {
  chart_type: ChartType;
  x_column: string;
  y_column?: string;
  group_by?: string;
  filters?: FilterExpression[];
  bins?: number;
}

export interface ChartDataset {
  label: string;
  data: (number | null)[];
}

export interface ChartSpec {
  chart_type: string;
  labels: string[];
  datasets: ChartDataset[];
  x_axis_label: string;
  y_axis_label: string;
}

export interface SQLRequest {
  query: string;
}

export interface SQLResponse {
  columns: string[];
  rows: Record<string, unknown>[];
}
