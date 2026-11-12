"use client";

import { useState, useRef, FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { UploadResponse } from "@/types";

type UploadState = "idle" | "uploading" | "success" | "error";

export default function UploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!selectedFile) {
      setErrorMessage("Please select a CSV file to upload.");
      setUploadState("error");
      return;
    }

    setUploadState("uploading");
    setErrorMessage("");
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch("/api/v1/datasets/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let detail = `Upload failed with status ${response.status}`;
        try {
          const body = await response.json();
          if (body.detail) {
            detail = body.detail;
          }
        } catch {
          // Use default detail if response body is not JSON
        }
        throw new Error(detail);
      }

      const data: UploadResponse = await response.json();
      setUploadResult(data);
      setUploadState("success");

      // Redirect to dataset detail page after a brief delay so user can see success
      setTimeout(() => {
        router.push(`/datasets/${data.dataset_id}`);
      }, 1500);
    } catch (err) {
      setUploadState("error");
      setErrorMessage(
        err instanceof Error ? err.message : "An unexpected error occurred."
      );
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setSelectedFile(file);
    // Reset state when a new file is selected
    if (uploadState === "error" || uploadState === "success") {
      setUploadState("idle");
      setErrorMessage("");
      setUploadResult(null);
    }
  }

  function handleReset() {
    setSelectedFile(null);
    setUploadState("idle");
    setErrorMessage("");
    setUploadResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  return (
    <main style={{ maxWidth: 600, margin: "0 auto", padding: "2rem" }}>
      <h1>Upload CSV Dataset</h1>
      <p>Select a CSV file to upload and create a new dataset.</p>

      <form onSubmit={handleSubmit} style={{ marginTop: "1.5rem" }}>
        <div style={{ marginBottom: "1rem" }}>
          <label htmlFor="csv-file" style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500 }}>
            CSV File
          </label>
          <input
            ref={fileInputRef}
            id="csv-file"
            type="file"
            accept=".csv,text/csv"
            onChange={handleFileChange}
            disabled={uploadState === "uploading"}
            aria-describedby="file-help"
          />
          <p id="file-help" style={{ fontSize: "0.875rem", color: "#666", marginTop: "0.25rem" }}>
            Accepted format: CSV (UTF-8, max 50 MB, max 500 columns)
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.75rem" }}>
          <button
            type="submit"
            disabled={uploadState === "uploading" || !selectedFile}
            style={{
              padding: "0.5rem 1.25rem",
              backgroundColor: uploadState === "uploading" ? "#999" : "#0070f3",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: uploadState === "uploading" || !selectedFile ? "not-allowed" : "pointer",
              fontSize: "1rem",
            }}
          >
            {uploadState === "uploading" ? "Uploading…" : "Upload"}
          </button>

          <button
            type="button"
            onClick={handleReset}
            disabled={uploadState === "uploading"}
            style={{
              padding: "0.5rem 1.25rem",
              backgroundColor: "#eee",
              color: "#333",
              border: "1px solid #ccc",
              borderRadius: "4px",
              cursor: uploadState === "uploading" ? "not-allowed" : "pointer",
              fontSize: "1rem",
            }}
          >
            Reset
          </button>
        </div>
      </form>

      {uploadState === "uploading" && (
        <div role="status" aria-live="polite" style={{ marginTop: "1.5rem", color: "#0070f3" }}>
          <p>Uploading file, please wait…</p>
        </div>
      )}

      {uploadState === "success" && uploadResult && (
        <div role="status" aria-live="polite" style={{ marginTop: "1.5rem", padding: "1rem", backgroundColor: "#e6f9e6", borderRadius: "4px", border: "1px solid #4caf50" }}>
          <h2 style={{ margin: "0 0 0.5rem", color: "#2e7d32" }}>Upload Successful</h2>
          <p><strong>Dataset ID:</strong> {uploadResult.dataset_id}</p>
          <p><strong>Name:</strong> {uploadResult.name}</p>
          <p><strong>Rows:</strong> {uploadResult.row_count}</p>
          <p style={{ fontSize: "0.875rem", color: "#666", marginTop: "0.5rem" }}>
            Redirecting to dataset detail page…
          </p>
        </div>
      )}

      {uploadState === "error" && errorMessage && (
        <div role="alert" aria-live="assertive" style={{ marginTop: "1.5rem", padding: "1rem", backgroundColor: "#fdecea", borderRadius: "4px", border: "1px solid #f44336" }}>
          <h2 style={{ margin: "0 0 0.5rem", color: "#c62828" }}>Upload Failed</h2>
          <p>{errorMessage}</p>
        </div>
      )}

      <div style={{ marginTop: "2rem" }}>
        <a href="/" style={{ color: "#0070f3" }}>← Back to Dashboard</a>
      </div>
    </main>
  );
}
