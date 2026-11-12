"use client";

interface PaginationControlsProps {
  currentPage: number;
  totalPages: number;
  totalRows: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

export default function PaginationControls({
  currentPage,
  totalPages,
  totalRows,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: PaginationControlsProps) {
  const isPreviousDisabled = currentPage <= 1;
  const isNextDisabled = currentPage >= totalPages || totalPages === 0;

  function handlePrevious() {
    if (!isPreviousDisabled) {
      onPageChange(currentPage - 1);
    }
  }

  function handleNext() {
    if (!isNextDisabled) {
      onPageChange(currentPage + 1);
    }
  }

  function handlePageSizeChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const newPageSize = Number(e.target.value);
    onPageSizeChange(newPageSize);
    onPageChange(1);
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.75rem 0",
        fontSize: "0.875rem",
        gap: "1rem",
        flexWrap: "wrap",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <button
          onClick={handlePrevious}
          disabled={isPreviousDisabled}
          aria-label="Previous page"
          style={{
            padding: "0.4rem 0.75rem",
            border: "1px solid #ccc",
            borderRadius: "4px",
            backgroundColor: isPreviousDisabled ? "#f5f5f5" : "#fff",
            color: isPreviousDisabled ? "#999" : "#333",
            cursor: isPreviousDisabled ? "not-allowed" : "pointer",
          }}
        >
          Previous
        </button>
        <button
          onClick={handleNext}
          disabled={isNextDisabled}
          aria-label="Next page"
          style={{
            padding: "0.4rem 0.75rem",
            border: "1px solid #ccc",
            borderRadius: "4px",
            backgroundColor: isNextDisabled ? "#f5f5f5" : "#fff",
            color: isNextDisabled ? "#999" : "#333",
            cursor: isNextDisabled ? "not-allowed" : "pointer",
          }}
        >
          Next
        </button>
      </div>

      <span style={{ color: "#555" }}>
        Page {currentPage} of {totalPages} ({totalRows} total rows)
      </span>

      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <label htmlFor="page-size-select" style={{ color: "#555" }}>
          Rows per page:
        </label>
        <select
          id="page-size-select"
          value={pageSize}
          onChange={handlePageSizeChange}
          style={{
            padding: "0.3rem 0.5rem",
            border: "1px solid #ccc",
            borderRadius: "4px",
            fontSize: "0.875rem",
          }}
        >
          {PAGE_SIZE_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
