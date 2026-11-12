"use client";

import { useCallback } from "react";

interface ResultsTableProps {
  columns: string[];
  rows: Record<string, unknown>[];
  loading?: boolean;
  currentSort?: { column: string; direction: "asc" | "desc" } | null;
  onSort?: (column: string, direction: "asc" | "desc") => void;
}

export default function ResultsTable({
  columns,
  rows,
  loading = false,
  currentSort = null,
  onSort,
}: ResultsTableProps) {
  const handleHeaderClick = useCallback(
    (column: string) => {
      if (!onSort) return;

      let direction: "asc" | "desc" = "asc";
      if (currentSort && currentSort.column === column) {
        direction = currentSort.direction === "asc" ? "desc" : "asc";
      }

      onSort(column, direction);
    },
    [currentSort, onSort]
  );

  function getSortIndicator(column: string): string {
    if (!currentSort || currentSort.column !== column) return "";
    return currentSort.direction === "asc" ? " ▲" : " ▼";
  }

  return (
    <div style={{ position: "relative", overflowX: "auto" }}>
      {loading && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundColor: "rgba(255, 255, 255, 0.85)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10,
          }}
          aria-label="Loading results"
        >
          <div style={{
            width: "24px",
            height: "24px",
            border: "3px solid #e5e7eb",
            borderTopColor: "#2563eb",
            borderRadius: "50%",
            animation: "freeTierSpin 1s linear infinite",
            marginBottom: "0.5rem",
          }} />
          <span style={{ fontSize: "0.85rem", color: "#555", fontWeight: 500 }}>Loading...</span>
          <span style={{ fontSize: "0.7rem", color: "#9ca3af", marginTop: "0.25rem" }}>
            Free-tier services may be slow. Please wait.
          </span>
          <style>{`@keyframes freeTierSpin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {columns.length === 0 ? (
        <p style={{ color: "#555", padding: "1rem 0" }}>No results</p>
      ) : rows.length === 0 ? (
        <p style={{ color: "#555", padding: "1rem 0" }}>No results</p>
      ) : (
        <table
          style={{
            borderCollapse: "collapse",
            width: "100%",
            fontSize: "0.875rem",
          }}
        >
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  onClick={() => handleHeaderClick(col)}
                  style={{
                    border: "1px solid #ddd",
                    padding: "0.5rem",
                    backgroundColor: "#f5f5f5",
                    textAlign: "left",
                    whiteSpace: "nowrap",
                    cursor: onSort ? "pointer" : "default",
                    userSelect: "none",
                  }}
                  aria-sort={
                    currentSort?.column === col
                      ? currentSort.direction === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  {col}
                  {getSortIndicator(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((col) => (
                  <td
                    key={`${rowIndex}-${col}`}
                    style={{
                      border: "1px solid #ddd",
                      padding: "0.5rem",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {row[col] === null || row[col] === undefined
                      ? ""
                      : String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
