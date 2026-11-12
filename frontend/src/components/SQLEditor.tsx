"use client";

import { useState } from "react";

interface SQLEditorProps {
  onExecute: (query: string) => void;
  results?: { columns: string[]; rows: Record<string, unknown>[] } | null;
  loading?: boolean;
  error?: string | null;
}

export default function SQLEditor({
  onExecute,
  results,
  loading = false,
  error = null,
}: SQLEditorProps) {
  const [query, setQuery] = useState("");

  function handleExecute() {
    const trimmed = query.trim();
    if (trimmed && !loading) {
      onExecute(trimmed);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Ctrl+Enter or Cmd+Enter to execute
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleExecute();
    }
  }

  const isExecuteDisabled = loading || query.trim().length === 0;

  return (
    <div style={{ fontFamily: "sans-serif" }}>
      {/* SQL Editor Area */}
      <div style={{ marginBottom: "0.75rem" }}>
        <label
          htmlFor="sql-editor-textarea"
          style={{
            display: "block",
            marginBottom: "0.5rem",
            fontWeight: 600,
            fontSize: "0.9rem",
          }}
        >
          SQL Query
        </label>
        <textarea
          id="sql-editor-textarea"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="SELECT * FROM dataset WHERE ..."
          spellCheck={false}
          style={{
            width: "100%",
            minHeight: "160px",
            padding: "0.75rem",
            fontFamily: "'Fira Code', 'Cascadia Code', 'Consolas', monospace",
            fontSize: "0.875rem",
            lineHeight: "1.5",
            backgroundColor: "#1e1e1e",
            color: "#d4d4d4",
            border: "1px solid #3c3c3c",
            borderRadius: "4px",
            resize: "vertical",
            outline: "none",
            boxSizing: "border-box",
          }}
        />
        <p
          style={{
            margin: "0.25rem 0 0 0",
            fontSize: "0.75rem",
            color: "#888",
          }}
        >
          Press Ctrl+Enter to execute
        </p>
      </div>

      {/* Execute Button */}
      <button
        onClick={handleExecute}
        disabled={isExecuteDisabled}
        aria-label="Execute SQL query"
        style={{
          padding: "0.5rem 1.25rem",
          fontSize: "0.875rem",
          fontWeight: 600,
          backgroundColor: isExecuteDisabled ? "#555" : "#0070f3",
          color: "#fff",
          border: "none",
          borderRadius: "4px",
          cursor: isExecuteDisabled ? "not-allowed" : "pointer",
          display: "inline-flex",
          alignItems: "center",
          gap: "0.5rem",
        }}
      >
        {loading && <LoadingSpinner />}
        {loading ? "Executing..." : "Execute"}
      </button>

      {/* Error Display */}
      {error && (
        <div
          role="alert"
          style={{
            marginTop: "1rem",
            padding: "0.75rem 1rem",
            backgroundColor: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "4px",
            color: "#dc2626",
            fontSize: "0.875rem",
          }}
        >
          {error}
        </div>
      )}

      {/* Loading Indicator */}
      {loading && !error && (
        <div
          style={{
            marginTop: "1rem",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "0.5rem",
            color: "#555",
            fontSize: "0.875rem",
            padding: "1rem",
          }}
        >
          <LoadingSpinner />
          <span>Executing query...</span>
          <span style={{ color: "#9ca3af", fontSize: "0.75rem" }}>
            This project uses free-tier services, so it may take a moment. Please wait.
          </span>
        </div>
      )}

      {/* Results Table */}
      {results && !loading && (
        <div style={{ marginTop: "1.5rem" }}>
          <h3
            style={{
              margin: "0 0 0.75rem 0",
              fontSize: "0.9rem",
              fontWeight: 600,
            }}
          >
            Results ({results.rows.length} row
            {results.rows.length !== 1 ? "s" : ""})
          </h3>
          {results.rows.length === 0 ? (
            <p style={{ color: "#666", fontSize: "0.875rem" }}>
              Query returned no results.
              {results.columns.length > 0 &&
                ` Columns: ${results.columns.join(", ")}`}
            </p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table
                style={{
                  borderCollapse: "collapse",
                  width: "100%",
                  fontSize: "0.8rem",
                }}
              >
                <thead>
                  <tr>
                    {results.columns.map((col) => (
                      <th
                        key={col}
                        style={{
                          border: "1px solid #ddd",
                          padding: "0.5rem",
                          backgroundColor: "#f5f5f5",
                          textAlign: "left",
                          whiteSpace: "nowrap",
                          fontWeight: 600,
                        }}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {results.columns.map((col) => (
                        <td
                          key={`${rowIndex}-${col}`}
                          style={{
                            border: "1px solid #ddd",
                            padding: "0.5rem",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {formatCellValue(row[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Format a cell value for display */
function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** Simple CSS spinner component */
function LoadingSpinner() {
  return (
    <span
      role="status"
      aria-label="Loading"
      style={{
        display: "inline-block",
        width: "14px",
        height: "14px",
        border: "2px solid rgba(255, 255, 255, 0.3)",
        borderTopColor: "#fff",
        borderRadius: "50%",
        animation: "sql-editor-spin 0.6s linear infinite",
      }}
    >
      <style>{`
        @keyframes sql-editor-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </span>
  );
}
