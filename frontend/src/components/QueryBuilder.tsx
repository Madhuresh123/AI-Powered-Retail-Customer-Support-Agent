"use client";

import { useState } from "react";
import type {
  FilterExpression,
  FilterOperator,
  SortSpec,
  QueryRequest,
} from "@/types/analytics";

interface QueryBuilderProps {
  columns: string[];
  onSubmit: (request: QueryRequest) => void;
  loading?: boolean;
}

const FILTER_OPERATORS: { value: FilterOperator; label: string }[] = [
  { value: "eq", label: "Equals" },
  { value: "neq", label: "Not Equals" },
  { value: "gt", label: "Greater Than" },
  { value: "gte", label: "Greater Than or Equal" },
  { value: "lt", label: "Less Than" },
  { value: "lte", label: "Less Than or Equal" },
  { value: "between", label: "Between" },
  { value: "contains", label: "Contains" },
  { value: "starts_with", label: "Starts With" },
  { value: "ends_with", label: "Ends With" },
  { value: "in", label: "In" },
];

interface FilterRow {
  column: string;
  operator: FilterOperator;
  value: string;
}

export default function QueryBuilder({
  columns,
  onSubmit,
  loading = false,
}: QueryBuilderProps) {
  const [filters, setFilters] = useState<FilterRow[]>([]);
  const [search, setSearch] = useState("");
  const [sortColumn, setSortColumn] = useState("");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  function addFilter() {
    setFilters([
      ...filters,
      { column: columns[0] ?? "", operator: "eq", value: "" },
    ]);
  }

  function removeFilter(index: number) {
    setFilters(filters.filter((_, i) => i !== index));
  }

  function updateFilter(index: number, field: keyof FilterRow, value: string) {
    const updated = [...filters];
    updated[index] = { ...updated[index], [field]: value };
    setFilters(updated);
  }

  function parseFilterValue(
    operator: FilterOperator,
    raw: string
  ): unknown {
    const trimmed = raw.trim();
    if (operator === "between") {
      const parts = trimmed.split(",").map((p) => p.trim());
      return parts.map((p) => (isNaN(Number(p)) ? p : Number(p)));
    }
    if (operator === "in") {
      return trimmed.split(",").map((p) => p.trim());
    }
    if (trimmed === "") return "";
    const num = Number(trimmed);
    return isNaN(num) ? trimmed : num;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const request: QueryRequest = {};

    // Build filters
    if (filters.length > 0) {
      request.filters = filters.map(
        (f): FilterExpression => ({
          column: f.column,
          operator: f.operator,
          value: parseFilterValue(f.operator, f.value),
        })
      );
    }

    // Build search
    if (search.trim()) {
      request.search = search.trim();
    }

    // Build sort
    if (sortColumn) {
      request.sort = [
        { column: sortColumn, direction: sortDirection } as SortSpec,
      ];
    }

    onSubmit(request);
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        border: "1px solid #ddd",
        borderRadius: "6px",
        padding: "1rem",
        marginBottom: "1rem",
        fontFamily: "sans-serif",
        fontSize: "0.875rem",
      }}
    >
      {/* Filters Section */}
      <fieldset
        style={{ border: "none", padding: 0, margin: "0 0 1rem 0" }}
      >
        <legend style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
          Filters
        </legend>
        {filters.map((filter, index) => (
          <div
            key={index}
            style={{
              display: "flex",
              gap: "0.5rem",
              alignItems: "center",
              marginBottom: "0.5rem",
              flexWrap: "wrap",
            }}
          >
            <select
              value={filter.column}
              onChange={(e) => updateFilter(index, "column", e.target.value)}
              aria-label={`Filter ${index + 1} column`}
              style={{ padding: "0.25rem 0.5rem" }}
            >
              {columns.map((col) => (
                <option key={col} value={col}>
                  {col}
                </option>
              ))}
            </select>
            <select
              value={filter.operator}
              onChange={(e) => updateFilter(index, "operator", e.target.value)}
              aria-label={`Filter ${index + 1} operator`}
              style={{ padding: "0.25rem 0.5rem" }}
            >
              {FILTER_OPERATORS.map((op) => (
                <option key={op.value} value={op.value}>
                  {op.label}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={filter.value}
              onChange={(e) => updateFilter(index, "value", e.target.value)}
              placeholder={
                filter.operator === "between"
                  ? "min, max"
                  : filter.operator === "in"
                    ? "val1, val2, ..."
                    : "Value"
              }
              aria-label={`Filter ${index + 1} value`}
              style={{ padding: "0.25rem 0.5rem", minWidth: "120px" }}
            />
            <button
              type="button"
              onClick={() => removeFilter(index)}
              aria-label={`Remove filter ${index + 1}`}
              style={{
                backgroundColor: "#dc3545",
                color: "white",
                border: "none",
                padding: "0.25rem 0.5rem",
                borderRadius: "4px",
                cursor: "pointer",
              }}
            >
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={addFilter}
          style={{
            backgroundColor: "#28a745",
            color: "white",
            border: "none",
            padding: "0.4rem 0.75rem",
            borderRadius: "4px",
            cursor: "pointer",
          }}
        >
          Add Filter
        </button>
      </fieldset>

      {/* Search Section */}
      <fieldset
        style={{ border: "none", padding: 0, margin: "0 0 1rem 0" }}
      >
        <legend style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
          Search
        </legend>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search term..."
          aria-label="Search term"
          style={{ padding: "0.35rem 0.5rem", width: "100%", maxWidth: "300px" }}
        />
      </fieldset>

      {/* Sort Section */}
      <fieldset
        style={{ border: "none", padding: 0, margin: "0 0 1rem 0" }}
      >
        <legend style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
          Sort
        </legend>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <select
            value={sortColumn}
            onChange={(e) => setSortColumn(e.target.value)}
            aria-label="Sort column"
            style={{ padding: "0.25rem 0.5rem" }}
          >
            <option value="">-- No Sort --</option>
            {columns.map((col) => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
          <select
            value={sortDirection}
            onChange={(e) =>
              setSortDirection(e.target.value as "asc" | "desc")
            }
            aria-label="Sort direction"
            style={{ padding: "0.25rem 0.5rem" }}
          >
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </div>
      </fieldset>

      {/* Execute Button */}
      <button
        type="submit"
        disabled={loading}
        style={{
          backgroundColor: loading ? "#6c757d" : "#0070f3",
          color: "white",
          border: "none",
          padding: "0.5rem 1.25rem",
          borderRadius: "4px",
          cursor: loading ? "not-allowed" : "pointer",
          fontSize: "0.9rem",
          fontWeight: "bold",
        }}
      >
        {loading ? "Executing..." : "Execute"}
      </button>
    </form>
  );
}
