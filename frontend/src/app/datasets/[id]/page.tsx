"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import type {
  DatasetDetail,
  PreviewResponse,
  ColumnDescriptor,
  SummaryResponse,
} from "@/types";
import type {
  QueryRequest,
  QueryResponse,
  ChartRequest,
  ChartSpec,
  SQLResponse,
} from "@/types/analytics";
import {
  getDatasetDetail,
  getDatasetPreview,
  getDatasetColumns,
  getDatasetSummary,
  deleteDataset,
  queryDataset,
  sqlQuery,
  generateChart,
} from "@/lib/api-client";
import QueryBuilder from "@/components/QueryBuilder";
import ResultsTable from "@/components/ResultsTable";
import PaginationControls from "@/components/PaginationControls";
import SQLEditor from "@/components/SQLEditor";
import ChartPanel from "@/components/ChartPanel";
import ChatPanel from "@/components/ChatPanel";
import FreeTierSpinner from "@/components/FreeTierSpinner";
import ErrorNotification from "@/components/ErrorNotification";

type TabName = "preview" | "columns" | "summary" | "query" | "sql" | "chart" | "chat";

export default function DatasetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const datasetId = params.id as string;

  // --- Existing state ---
  const [detail, setDetail] = useState<DatasetDetail | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [columns, setColumns] = useState<ColumnDescriptor[] | null>(null);
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [activeTab, setActiveTab] = useState<TabName>("preview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // --- Analytics state ---
  const [columnNames, setColumnNames] = useState<string[]>([]);

  // Query state
  const [queryResults, setQueryResults] = useState<QueryResponse | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [currentSort, setCurrentSort] = useState<{ column: string; direction: "asc" | "desc" } | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  // SQL state
  const [sqlResults, setSqlResults] = useState<SQLResponse | null>(null);
  const [sqlLoading, setSqlLoading] = useState(false);
  const [sqlError, setSqlError] = useState<string | null>(null);

  // Chart state
  const [chartSpec, setChartSpec] = useState<ChartSpec | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);

  // Keep track of the last query request for sort/pagination rebuilds
  const lastQueryRef = useRef<QueryRequest>({});

  // --- Data fetching on mount ---
  useEffect(() => {
    if (!datasetId) return;

    async function fetchWithRetry<T>(fn: () => Promise<T>, retries = 2): Promise<T> {
      for (let i = 0; i <= retries; i++) {
        try {
          return await fn();
        } catch (err) {
          if (i === retries) throw err;
          await new Promise((r) => setTimeout(r, 1000));
        }
      }
      throw new Error("Failed after retries");
    }

    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        // Load detail first (fast), then rest in parallel with retry
        const detailData = await fetchWithRetry(() => getDatasetDetail(datasetId));
        setDetail(detailData);

        const [previewData, columnsData, summaryData] = await Promise.all([
          fetchWithRetry(() => getDatasetPreview(datasetId)),
          fetchWithRetry(() => getDatasetColumns(datasetId)),
          fetchWithRetry(() => getDatasetSummary(datasetId)),
        ]);
        setPreview(previewData);
        setColumns(columnsData);
        setSummary(summaryData);
        setColumnNames(columnsData.map((c) => c.name));
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to load dataset";
        setError(message);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [datasetId]);

  // --- Query Handlers ---
  const handleQuerySubmit = useCallback(
    async (request: QueryRequest) => {
      setQueryLoading(true);
      setQueryError(null);
      try {
        // Apply current pagination
        const fullRequest: QueryRequest = {
          ...request,
          page: 1,
          page_size: pageSize,
        };
        lastQueryRef.current = fullRequest;
        const result = await queryDataset(datasetId, fullRequest);
        setQueryResults(result);
        setCurrentPage(1);
        // Update sort state from the request
        if (request.sort && request.sort.length > 0) {
          setCurrentSort({
            column: request.sort[0].column,
            direction: request.sort[0].direction,
          });
        } else {
          setCurrentSort(null);
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Query failed";
        setQueryError(message);
      } finally {
        setQueryLoading(false);
      }
    },
    [datasetId, pageSize]
  );

  const handleSort = useCallback(
    async (column: string, direction: "asc" | "desc") => {
      setQueryLoading(true);
      setQueryError(null);
      try {
        const updatedRequest: QueryRequest = {
          ...lastQueryRef.current,
          sort: [{ column, direction }],
          page: 1,
          page_size: pageSize,
        };
        lastQueryRef.current = updatedRequest;
        const result = await queryDataset(datasetId, updatedRequest);
        setQueryResults(result);
        setCurrentSort({ column, direction });
        setCurrentPage(1);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Sort failed";
        setQueryError(message);
      } finally {
        setQueryLoading(false);
      }
    },
    [datasetId, pageSize]
  );

  const handlePageChange = useCallback(
    async (page: number) => {
      setQueryLoading(true);
      setQueryError(null);
      try {
        const updatedRequest: QueryRequest = {
          ...lastQueryRef.current,
          page,
          page_size: pageSize,
        };
        lastQueryRef.current = updatedRequest;
        const result = await queryDataset(datasetId, updatedRequest);
        setQueryResults(result);
        setCurrentPage(page);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Pagination failed";
        setQueryError(message);
      } finally {
        setQueryLoading(false);
      }
    },
    [datasetId, pageSize]
  );

  const handlePageSizeChange = useCallback(
    async (newPageSize: number) => {
      setPageSize(newPageSize);
      setQueryLoading(true);
      setQueryError(null);
      try {
        const updatedRequest: QueryRequest = {
          ...lastQueryRef.current,
          page: 1,
          page_size: newPageSize,
        };
        lastQueryRef.current = updatedRequest;
        const result = await queryDataset(datasetId, updatedRequest);
        setQueryResults(result);
        setCurrentPage(1);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Page size change failed";
        setQueryError(message);
      } finally {
        setQueryLoading(false);
      }
    },
    [datasetId]
  );

  // --- SQL Handler ---
  const handleSQLExecute = useCallback(
    async (query: string) => {
      setSqlLoading(true);
      setSqlError(null);
      try {
        const result = await sqlQuery(datasetId, query);
        setSqlResults(result);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "SQL query failed";
        setSqlError(message);
      } finally {
        setSqlLoading(false);
      }
    },
    [datasetId]
  );

  // --- Chart Handler ---
  const handleChartGenerate = useCallback(
    async (request: ChartRequest) => {
      setChartLoading(true);
      setChartError(null);
      try {
        const result = await generateChart(datasetId, request);
        setChartSpec(result);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Chart generation failed";
        setChartError(message);
      } finally {
        setChartLoading(false);
      }
    },
    [datasetId]
  );

  // --- Delete handler ---
  async function handleDelete() {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${detail?.name ?? "this dataset"}"? This action cannot be undone.`
    );
    if (!confirmed) return;

    setDeleting(true);
    try {
      await deleteDataset(datasetId);
      router.push("/");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to delete dataset";
      setError(message);
      setDeleting(false);
    }
  }

  // --- Dismiss error ---
  function dismissError() {
    setQueryError(null);
    setSqlError(null);
    setChartError(null);
  }

  // Combined error for the global ErrorNotification
  const activeError = queryError || sqlError || chartError;

  // --- Render loading/error/not-found states ---
  if (loading) {
    return (
      <main style={{ padding: "2rem", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
        <FreeTierSpinner message="Loading dataset..." />
      </main>
    );
  }

  if (error) {
    return (
      <main style={{ padding: "2rem" }}>
        <h1>Error</h1>
        <p style={{ color: "red" }}>{error}</p>
        <button onClick={() => router.push("/")}>Back to Home</button>
      </main>
    );
  }

  if (!detail) {
    return (
      <main style={{ padding: "2rem" }}>
        <p>Dataset not found.</p>
        <button onClick={() => router.push("/")}>Back to Home</button>
      </main>
    );
  }

  return (
    <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      {/* Error Notification */}
      <ErrorNotification message={activeError} onDismiss={dismissError} />

      {/* Dataset Metadata Header */}
      <header
        style={{
          marginBottom: "1.5rem",
          borderBottom: "1px solid #ddd",
          paddingBottom: "1rem",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
          }}
        >
          <div>
            <h1 style={{ margin: "0 0 0.5rem 0" }}>{detail.name}</h1>
            <p style={{ margin: "0.25rem 0", color: "#555" }}>
              <strong>ID:</strong> {detail.dataset_id}
            </p>
            <p style={{ margin: "0.25rem 0", color: "#555" }}>
              <strong>Rows:</strong> {detail.row_count} |{" "}
              <strong>Columns:</strong> {detail.column_count}
            </p>
            <p style={{ margin: "0.25rem 0", color: "#555" }}>
              <strong>Source:</strong> {detail.source_type} |{" "}
              <strong>Created:</strong>{" "}
              {new Date(detail.created_at).toLocaleString()}
            </p>
          </div>
          <button
            onClick={handleDelete}
            disabled={deleting}
            style={{
              backgroundColor: "#dc3545",
              color: "white",
              border: "none",
              padding: "0.5rem 1rem",
              borderRadius: "4px",
              cursor: deleting ? "not-allowed" : "pointer",
              fontSize: "0.9rem",
            }}
          >
            {deleting ? "Deleting..." : "Delete Dataset"}
          </button>
        </div>
      </header>

      {/* Tabs */}
      <nav style={{ marginBottom: "1rem" }}>
        {(["preview", "columns", "summary", "query", "sql", "chart", "chat"] as TabName[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "0.5rem 1rem",
              marginRight: "0.5rem",
              border: "1px solid #ccc",
              borderBottom: activeTab === tab ? "2px solid #0070f3" : "1px solid #ccc",
              backgroundColor: activeTab === tab ? "#f0f8ff" : "#fff",
              cursor: "pointer",
              fontWeight: activeTab === tab ? "bold" : "normal",
              borderRadius: "4px 4px 0 0",
            }}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </nav>

      {/* Tab Content */}
      <section>
        {activeTab === "preview" && <PreviewTab data={preview} />}
        {activeTab === "columns" && <ColumnsTab data={columns} />}
        {activeTab === "summary" && <SummaryTab data={summary} />}
        {activeTab === "query" && (
          <QueryTab
            columnNames={columnNames}
            queryResults={queryResults}
            queryLoading={queryLoading}
            currentSort={currentSort}
            currentPage={currentPage}
            pageSize={pageSize}
            onQuerySubmit={handleQuerySubmit}
            onSort={handleSort}
            onPageChange={handlePageChange}
            onPageSizeChange={handlePageSizeChange}
          />
        )}
        {activeTab === "sql" && (
          <SQLTab
            sqlResults={sqlResults}
            sqlLoading={sqlLoading}
            sqlError={sqlError}
            onExecute={handleSQLExecute}
          />
        )}
        {activeTab === "chart" && (
          <ChartTab
            columnNames={columnNames}
            chartSpec={chartSpec}
            chartLoading={chartLoading}
            chartError={chartError}
            onGenerate={handleChartGenerate}
          />
        )}
        {activeTab === "chat" && (
          <ChatPanel datasetId={datasetId} />
        )}
      </section>
    </main>
  );
}

// --- Query Tab ---
interface QueryTabProps {
  columnNames: string[];
  queryResults: QueryResponse | null;
  queryLoading: boolean;
  currentSort: { column: string; direction: "asc" | "desc" } | null;
  currentPage: number;
  pageSize: number;
  onQuerySubmit: (request: QueryRequest) => void;
  onSort: (column: string, direction: "asc" | "desc") => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

function QueryTab({
  columnNames,
  queryResults,
  queryLoading,
  currentSort,
  currentPage,
  pageSize,
  onQuerySubmit,
  onSort,
  onPageChange,
  onPageSizeChange,
}: QueryTabProps) {
  return (
    <div>
      <QueryBuilder
        columns={columnNames}
        onSubmit={onQuerySubmit}
        loading={queryLoading}
      />

      {queryResults && (
        <>
          <ResultsTable
            columns={queryResults.columns}
            rows={queryResults.rows}
            loading={queryLoading}
            currentSort={currentSort}
            onSort={onSort}
          />
          <PaginationControls
            currentPage={currentPage}
            totalPages={queryResults.pagination.total_pages}
            totalRows={queryResults.pagination.total_rows}
            pageSize={pageSize}
            onPageChange={onPageChange}
            onPageSizeChange={onPageSizeChange}
          />
        </>
      )}

      {!queryResults && !queryLoading && (
        <p style={{ color: "#555", padding: "1rem 0" }}>
          Configure your query above and click Execute to see results.
        </p>
      )}
    </div>
  );
}

// --- SQL Tab ---
interface SQLTabProps {
  sqlResults: SQLResponse | null;
  sqlLoading: boolean;
  sqlError: string | null;
  onExecute: (query: string) => void;
}

function SQLTab({ sqlResults, sqlLoading, sqlError, onExecute }: SQLTabProps) {
  return (
    <div>
      <SQLEditor
        onExecute={onExecute}
        results={sqlResults}
        loading={sqlLoading}
        error={sqlError}
      />
    </div>
  );
}

// --- Chart Tab ---
interface ChartTabProps {
  columnNames: string[];
  chartSpec: ChartSpec | null;
  chartLoading: boolean;
  chartError: string | null;
  onGenerate: (request: ChartRequest) => void;
}

function ChartTab({
  columnNames,
  chartSpec,
  chartLoading,
  chartError,
  onGenerate,
}: ChartTabProps) {
  return (
    <div>
      <ChartPanel
        columns={columnNames}
        onGenerate={onGenerate}
        chartSpec={chartSpec}
        loading={chartLoading}
        error={chartError}
      />
    </div>
  );
}

// --- Preview Tab ---
function PreviewTab({ data }: { data: PreviewResponse | null }) {
  if (!data) return <p>No preview data available.</p>;

  if (data.rows.length === 0) {
    return <p>No data rows to display. Columns: {data.columns.join(", ")}</p>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <p style={{ marginBottom: "0.5rem", color: "#555" }}>
        Showing {data.rows.length} of {data.row_count} rows
      </p>
      <table
        style={{
          borderCollapse: "collapse",
          width: "100%",
          fontSize: "0.875rem",
        }}
      >
        <thead>
          <tr>
            {data.columns.map((col) => (
              <th
                key={col}
                style={{
                  border: "1px solid #ddd",
                  padding: "0.5rem",
                  backgroundColor: "#f5f5f5",
                  textAlign: "left",
                  whiteSpace: "nowrap",
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {data.columns.map((col) => (
                <td
                  key={`${rowIndex}-${col}`}
                  style={{
                    border: "1px solid #ddd",
                    padding: "0.5rem",
                    whiteSpace: "nowrap",
                  }}
                >
                  {String(row[col] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Columns Tab ---
function ColumnsTab({ data }: { data: ColumnDescriptor[] | null }) {
  if (!data || data.length === 0) {
    return <p>No column information available.</p>;
  }

  return (
    <table
      style={{
        borderCollapse: "collapse",
        width: "100%",
        maxWidth: "500px",
        fontSize: "0.875rem",
      }}
    >
      <thead>
        <tr>
          <th
            style={{
              border: "1px solid #ddd",
              padding: "0.5rem",
              backgroundColor: "#f5f5f5",
              textAlign: "left",
            }}
          >
            Column Name
          </th>
          <th
            style={{
              border: "1px solid #ddd",
              padding: "0.5rem",
              backgroundColor: "#f5f5f5",
              textAlign: "left",
            }}
          >
            Inferred Type
          </th>
        </tr>
      </thead>
      <tbody>
        {data.map((col, index) => (
          <tr key={index}>
            <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>
              {col.name}
            </td>
            <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>
              {col.dtype}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// --- Summary Tab ---
function SummaryTab({ data }: { data: SummaryResponse | null }) {
  if (!data) return <p>No summary data available.</p>;

  function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  const stats = [
    { label: "Row Count", value: data.row_count.toLocaleString() },
    { label: "Column Count", value: data.column_count.toLocaleString() },
    {
      label: "Missing Values",
      value: data.missing_value_count.toLocaleString(),
    },
    {
      label: "Duplicate Rows",
      value: data.duplicate_row_count.toLocaleString(),
    },
    { label: "Memory Usage", value: formatBytes(data.memory_usage_bytes) },
  ];

  return (
    <table
      style={{
        borderCollapse: "collapse",
        width: "100%",
        maxWidth: "400px",
        fontSize: "0.875rem",
      }}
    >
      <thead>
        <tr>
          <th
            style={{
              border: "1px solid #ddd",
              padding: "0.5rem",
              backgroundColor: "#f5f5f5",
              textAlign: "left",
            }}
          >
            Metric
          </th>
          <th
            style={{
              border: "1px solid #ddd",
              padding: "0.5rem",
              backgroundColor: "#f5f5f5",
              textAlign: "left",
            }}
          >
            Value
          </th>
        </tr>
      </thead>
      <tbody>
        {stats.map((stat) => (
          <tr key={stat.label}>
            <td
              style={{
                border: "1px solid #ddd",
                padding: "0.5rem",
                fontWeight: "500",
              }}
            >
              {stat.label}
            </td>
            <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>
              {stat.value}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
