import Link from "next/link";
import { listDatasets } from "@/lib/api-client";
import type { DatasetListItem } from "@/types";

// Disable caching so the dataset list is always fresh
export const dynamic = "force-dynamic";
export const revalidate = 0;

/**
 * Format an ISO 8601 timestamp into a human-readable date/time string.
 */
function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default async function Home() {
  let datasets: DatasetListItem[] = [];
  let error: string | null = null;

  try {
    datasets = await listDatasets();
  } catch (e: unknown) {
    error =
      e instanceof Error
        ? e.message
        : "Failed to load datasets. Please try again later.";
  }

  return (
    <main style={{ maxWidth: "960px", margin: "0 auto", padding: "2rem" }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "2rem",
        }}
      >
        <h1 style={{ margin: 0 }}>Data Insight</h1>
        <nav style={{ display: "flex", gap: "1rem" }}>
          <Link
            href="/datasets/upload"
            style={{
              padding: "0.5rem 1rem",
              backgroundColor: "#0070f3",
              color: "#fff",
              borderRadius: "6px",
              textDecoration: "none",
              fontSize: "0.875rem",
            }}
          >
            Upload CSV
          </Link>
          <Link
            href="/datasets/import"
            style={{
              padding: "0.5rem 1rem",
              backgroundColor: "#10b981",
              color: "#fff",
              borderRadius: "6px",
              textDecoration: "none",
              fontSize: "0.875rem",
            }}
          >
            Import from API
          </Link>
        </nav>
      </header>

      {error && (
        <div
          role="alert"
          style={{
            padding: "1rem",
            backgroundColor: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "6px",
            color: "#991b1b",
            marginBottom: "1.5rem",
          }}
        >
          {error}
        </div>
      )}

      {!error && datasets.length === 0 && (
        <div
          style={{
            textAlign: "center",
            padding: "4rem 2rem",
            backgroundColor: "#f9fafb",
            borderRadius: "8px",
            border: "1px solid #e5e7eb",
          }}
        >
          <h2 style={{ marginBottom: "0.5rem", color: "#374151" }}>
            No datasets yet
          </h2>
          <p style={{ color: "#6b7280", marginBottom: "1.5rem" }}>
            Get started by uploading a CSV file or importing data from an
            external API.
          </p>
          <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
            <Link
              href="/datasets/upload"
              style={{
                padding: "0.5rem 1rem",
                backgroundColor: "#0070f3",
                color: "#fff",
                borderRadius: "6px",
                textDecoration: "none",
              }}
            >
              Upload CSV
            </Link>
            <Link
              href="/datasets/import"
              style={{
                padding: "0.5rem 1rem",
                backgroundColor: "#10b981",
                color: "#fff",
                borderRadius: "6px",
                textDecoration: "none",
              }}
            >
              Import from API
            </Link>
          </div>
        </div>
      )}

      {!error && datasets.length > 0 && (
        <section>
          <h2 style={{ marginBottom: "1rem", color: "#374151" }}>
            Datasets ({datasets.length})
          </h2>
          <div
            style={{
              display: "grid",
              gap: "1rem",
            }}
          >
            {datasets.map((dataset) => (
              <Link
                key={dataset.dataset_id}
                href={`/datasets/${dataset.dataset_id}`}
                style={{
                  display: "block",
                  padding: "1.25rem",
                  border: "1px solid #e5e7eb",
                  borderRadius: "8px",
                  textDecoration: "none",
                  color: "inherit",
                  transition: "border-color 0.15s",
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
                    <h3
                      style={{
                        margin: "0 0 0.25rem 0",
                        fontSize: "1.125rem",
                        color: "#111827",
                      }}
                    >
                      {dataset.name}
                    </h3>
                    <p
                      style={{
                        margin: 0,
                        fontSize: "0.875rem",
                        color: "#6b7280",
                      }}
                    >
                      {dataset.row_count.toLocaleString()} rows
                    </p>
                  </div>
                  <time
                    dateTime={dataset.created_at}
                    style={{
                      fontSize: "0.75rem",
                      color: "#9ca3af",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {formatTimestamp(dataset.created_at)}
                  </time>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
