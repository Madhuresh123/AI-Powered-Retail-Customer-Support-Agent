"use client";

interface ErrorNotificationProps {
  message: string | null;
  onDismiss: () => void;
}

export default function ErrorNotification({
  message,
  onDismiss,
}: ErrorNotificationProps) {
  if (!message) return null;

  return (
    <div
      role="alert"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.75rem 1rem",
        backgroundColor: "#fef2f2",
        border: "1px solid #fecaca",
        borderRadius: "6px",
        marginBottom: "1rem",
        color: "#dc2626",
        fontSize: "0.875rem",
      }}
    >
      <span>{message}</span>
      <button
        onClick={onDismiss}
        aria-label="Dismiss error"
        style={{
          background: "none",
          border: "none",
          color: "#dc2626",
          fontSize: "1.25rem",
          cursor: "pointer",
          padding: "0 0.25rem",
          lineHeight: 1,
        }}
      >
        &times;
      </button>
    </div>
  );
}
