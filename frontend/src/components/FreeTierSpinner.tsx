"use client";

interface FreeTierSpinnerProps {
  message?: string;
}

/**
 * Reusable loading spinner with free-tier disclaimer.
 * Shows a revolving circle + loading message + disclaimer about free-tier latency.
 */
export default function FreeTierSpinner({ message = "Loading..." }: FreeTierSpinnerProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "2rem" }}>
      <div style={{
        width: "28px",
        height: "28px",
        border: "3px solid #e5e7eb",
        borderTopColor: "#2563eb",
        borderRadius: "50%",
        animation: "freeTierSpin 1s linear infinite",
        marginBottom: "0.75rem",
      }} />
      <p style={{ color: "#374151", fontSize: "0.9rem", margin: "0 0 0.25rem 0" }}>{message}</p>
      <p style={{ color: "#9ca3af", fontSize: "0.75rem", margin: 0, textAlign: "center" }}>
        This project uses free-tier services, so it may take a moment. Please wait.
      </p>
      <style>{`@keyframes freeTierSpin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
