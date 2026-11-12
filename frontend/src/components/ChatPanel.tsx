"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  sendChatMessage,
  getChatHistory,
  clearChatHistory,
  type ChatMessage,
  type ChatResponse,
} from "@/lib/api-client";
import FreeTierSpinner from "@/components/FreeTierSpinner";

interface ChatPanelProps {
  datasetId: string;
}

export default function ChatPanel({ datasetId }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load chat history on mount
  useEffect(() => {
    async function loadHistory() {
      setHistoryLoading(true);
      try {
        const history = await getChatHistory(datasetId);
        setMessages(history);
      } catch (err) {
        // Silently handle — empty chat is fine
      } finally {
        setHistoryLoading(false);
      }
    }
    loadHistory();
  }, [datasetId]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const question = input.trim();
    if (!question || loading) return;

    setInput("");
    setError(null);

    // Add user message optimistically
    const userMsg: ChatMessage = {
      role: "user",
      content: question,
      sql: null,
      data: null,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const response: ChatResponse = await sendChatMessage(datasetId, question);

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: response.answer,
        sql: response.sql,
        data: response.data?.rows ?? null,
        timestamp: response.timestamp,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to get response";
      setError(message);
      // Remove the optimistic user message on error
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  }, [input, loading, datasetId]);

  const handleClear = useCallback(async () => {
    try {
      await clearChatHistory(datasetId);
      setMessages([]);
      setError(null);
    } catch (err) {
      setError("Failed to clear chat history");
    }
  }, [datasetId]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "500px" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "0.5rem 0",
          borderBottom: "1px solid #e5e7eb",
          marginBottom: "0.5rem",
        }}
      >
        <span style={{ fontSize: "0.85rem", color: "#6b7280" }}>
          Ask questions about your data in natural language
        </span>
        <button
          onClick={handleClear}
          disabled={messages.length === 0}
          style={{
            fontSize: "0.8rem",
            padding: "0.25rem 0.5rem",
            border: "1px solid #d1d5db",
            borderRadius: "4px",
            backgroundColor: messages.length === 0 ? "#f3f4f6" : "#fff",
            color: messages.length === 0 ? "#9ca3af" : "#374151",
            cursor: messages.length === 0 ? "not-allowed" : "pointer",
          }}
        >
          Clear History
        </button>
      </div>

      {/* Messages Area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "0.5rem",
          border: "1px solid #e5e7eb",
          borderRadius: "8px",
          backgroundColor: "#fafafa",
        }}
      >
        {historyLoading && (
          <FreeTierSpinner message="Loading conversation..." />
        )}

        {!historyLoading && messages.length === 0 && (
          <div style={{ textAlign: "center", padding: "3rem 1rem", color: "#9ca3af" }}>
            <p style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>💬 Start a conversation</p>
            <p style={{ fontSize: "0.85rem" }}>
              Ask questions like &quot;What is the average sales by region?&quot; or
              &quot;Show me the top 10 products&quot;
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <MessageBubble key={idx} message={msg} />
        ))}

        {loading && (
          <div style={{ display: "flex", padding: "0.75rem", gap: "0.5rem", alignItems: "center" }}>
            <div
              style={{
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                backgroundColor: "#6366f1",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                fontSize: "0.7rem",
                fontWeight: "bold",
                flexShrink: 0,
              }}
            >
              AI
            </div>
            <div style={{ padding: "0.5rem 0.75rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <div style={{
                  width: "16px",
                  height: "16px",
                  border: "2px solid #e5e7eb",
                  borderTopColor: "#6366f1",
                  borderRadius: "50%",
                  animation: "freeTierSpin 1s linear infinite",
                }} />
                <span style={{ color: "#6b7280", fontStyle: "italic", fontSize: "0.85rem" }}>
                  Thinking...
                </span>
              </div>
              <p style={{ color: "#9ca3af", fontSize: "0.75rem", margin: "0.25rem 0 0 0" }}>
                This project uses free-tier AI, so responses may take a moment. Please wait.
              </p>
              <style>{`@keyframes freeTierSpin { to { transform: rotate(360deg); } }`}</style>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error */}
      {error && (
        <div
          style={{
            marginTop: "0.5rem",
            padding: "0.5rem 0.75rem",
            backgroundColor: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "6px",
            color: "#dc2626",
            fontSize: "0.85rem",
          }}
        >
          {error}
        </div>
      )}

      {/* Input Area */}
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your data..."
          disabled={loading}
          rows={2}
          style={{
            flex: 1,
            padding: "0.6rem 0.75rem",
            border: "1px solid #d1d5db",
            borderRadius: "8px",
            fontSize: "0.9rem",
            resize: "none",
            outline: "none",
            fontFamily: "inherit",
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          style={{
            padding: "0.6rem 1.2rem",
            backgroundColor: loading || !input.trim() ? "#93c5fd" : "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: "8px",
            cursor: loading || !input.trim() ? "not-allowed" : "pointer",
            fontWeight: "500",
            fontSize: "0.9rem",
            alignSelf: "flex-end",
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

// --- Message Bubble Component ---
function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const [showSQL, setShowSQL] = useState(false);
  const [showData, setShowData] = useState(false);

  return (
    <div
      style={{
        display: "flex",
        padding: "0.75rem",
        gap: "0.5rem",
        flexDirection: isUser ? "row-reverse" : "row",
      }}
    >
      {/* Avatar */}
      <div
        style={{
          width: "28px",
          height: "28px",
          borderRadius: "50%",
          backgroundColor: isUser ? "#2563eb" : "#6366f1",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#fff",
          fontSize: "0.7rem",
          fontWeight: "bold",
          flexShrink: 0,
        }}
      >
        {isUser ? "U" : "AI"}
      </div>

      {/* Content */}
      <div
        style={{
          maxWidth: "75%",
          backgroundColor: isUser ? "#dbeafe" : "#fff",
          border: isUser ? "none" : "1px solid #e5e7eb",
          borderRadius: "12px",
          padding: "0.6rem 0.85rem",
        }}
      >
        <p style={{ margin: 0, fontSize: "0.9rem", lineHeight: "1.5", whiteSpace: "pre-wrap" }}>
          {message.content}
        </p>

        {/* SQL toggle */}
        {message.sql && (
          <div style={{ marginTop: "0.5rem" }}>
            <button
              onClick={() => setShowSQL(!showSQL)}
              style={{
                fontSize: "0.75rem",
                color: "#6366f1",
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 0,
                textDecoration: "underline",
              }}
            >
              {showSQL ? "Hide SQL" : "Show SQL"}
            </button>
            {showSQL && (
              <pre
                style={{
                  marginTop: "0.25rem",
                  padding: "0.5rem",
                  backgroundColor: "#f3f4f6",
                  borderRadius: "4px",
                  fontSize: "0.75rem",
                  overflowX: "auto",
                  whiteSpace: "pre-wrap",
                }}
              >
                {message.sql}
              </pre>
            )}
          </div>
        )}

        {/* Data toggle */}
        {message.data && message.data.length > 0 && (
          <div style={{ marginTop: "0.4rem" }}>
            <button
              onClick={() => setShowData(!showData)}
              style={{
                fontSize: "0.75rem",
                color: "#6366f1",
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 0,
                textDecoration: "underline",
              }}
            >
              {showData ? "Hide Data" : `Show Data (${message.data.length} rows)`}
            </button>
            {showData && (
              <div style={{ marginTop: "0.25rem", overflowX: "auto" }}>
                <table
                  style={{
                    borderCollapse: "collapse",
                    fontSize: "0.7rem",
                    width: "100%",
                  }}
                >
                  <thead>
                    <tr>
                      {Object.keys(message.data[0]).map((col) => (
                        <th
                          key={col}
                          style={{
                            border: "1px solid #e5e7eb",
                            padding: "0.25rem 0.4rem",
                            backgroundColor: "#f9fafb",
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
                    {message.data.slice(0, 20).map((row, i) => (
                      <tr key={i}>
                        {Object.values(row).map((val, j) => (
                          <td
                            key={j}
                            style={{
                              border: "1px solid #e5e7eb",
                              padding: "0.25rem 0.4rem",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {String(val ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {message.data.length > 20 && (
                  <p style={{ fontSize: "0.7rem", color: "#9ca3af", marginTop: "0.25rem" }}>
                    Showing 20 of {message.data.length} rows
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
