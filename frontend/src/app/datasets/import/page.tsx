"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { importFromAPI, ApiError } from "@/lib/api-client";
import type { ImportResponse } from "@/types";

type ImportState = "idle" | "importing" | "success" | "error";

export default function ImportPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [state, setState] = useState<ImportState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResponse | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setState("importing");

    try {
      const response = await importFromAPI(url);
      setResult(response);
      setState("success");
      // Redirect to dataset detail page after a short delay so user sees success
      setTimeout(() => {
        router.push(`/datasets/${response.dataset_id}`);
      }, 1500);
    } catch (err) {
      setState("error");
      if (err instanceof ApiError) {
        setError(err.detail);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred during import.");
      }
    }
  }

  return (
    <main style={{ maxWidth: "600px", margin: "0 auto", padding: "2rem" }}>
      <h1>Import from REST API</h1>
      <p>Enter the URL of a REST API endpoint that returns a JSON array of objects.</p>

      <form onSubmit={handleSubmit} style={{ marginTop: "1.5rem" }}>
        <div style={{ marginBottom: "1rem" }}>
          <label htmlFor="api-url" style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500 }}>
            API URL
          </label>
          <input
            id="api-url"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://api.example.com/data"
            required
            disabled={state === "importing"}
            style={{
              width: "100%",
              padding: "0.5rem 0.75rem",
              fontSize: "1rem",
              border: "1px solid #ccc",
              borderRadius: "4px",
              boxSizing: "border-box",
            }}
            aria-describedby="url-hint"
          />
          <small id="url-hint" style={{ color: "#666", marginTop: "0.25rem", display: "block" }}>
            Must be an HTTP or HTTPS URL returning a JSON array of flat objects.
          </small>
        </div>

        <button
          type="submit"
          disabled={state === "importing" || !url.trim()}
          style={{
            padding: "0.5rem 1.5rem",
            fontSize: "1rem",
            backgroundColor: state === "importing" ? "#999" : "#0070f3",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: state === "importing" ? "not-allowed" : "pointer",
          }}
        >
          {state === "importing" ? "Importing…" : "Import Dataset"}
        </button>
      </form>

      {state === "importing" && (
        <div role="status" aria-live="polite" style={{ marginTop: "1.5rem", color: "#555" }}>
          <p>Importing data from the API… This may take a moment.</p>
        </div>
      )}

      {state === "success" && result && (
        <div
          role="status"
          aria-live="polite"
          style={{
            marginTop: "1.5rem",
            padding: "1rem",
            backgroundColor: "#e6f9e6",
            border: "1px solid #4caf50",
            borderRadius: "4px",
          }}
        >
          <p style={{ margin: 0, fontWeight: 500, color: "#2e7d32" }}>Import successful!</p>
          <ul style={{ marginTop: "0.5rem", paddingLeft: "1.25rem" }}>
            <li>Dataset ID: {result.dataset_id}</li>
            <li>Source URL: {result.source_url}</li>
            <li>Rows imported: {result.row_count}</li>
          </ul>
          <p style={{ marginTop: "0.5rem", color: "#555", fontSize: "0.875rem" }}>
            Redirecting to dataset details…
          </p>
        </div>
      )}

      {state === "error" && error && (
        <div
          role="alert"
          style={{
            marginTop: "1.5rem",
            padding: "1rem",
            backgroundColor: "#fdecea",
            border: "1px solid #f44336",
            borderRadius: "4px",
            color: "#c62828",
          }}
        >
          <p style={{ margin: 0, fontWeight: 500 }}>Import failed</p>
          <p style={{ margin: "0.5rem 0 0" }}>{error}</p>
        </div>
      )}

      <div style={{ marginTop: "2rem" }}>
        <a href="/" style={{ color: "#0070f3", textDecoration: "none" }}>
          ← Back to dashboard
        </a>
      </div>
    </main>
  );
}
