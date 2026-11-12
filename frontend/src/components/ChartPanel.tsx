"use client";

import { useState } from "react";
import {
  Chart,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar, Line, Pie, Scatter } from "react-chartjs-2";
import type { ChartRequest, ChartSpec, ChartType } from "../types/analytics";

Chart.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

interface ChartPanelProps {
  columns: string[];
  onGenerate: (request: ChartRequest) => void;
  chartSpec?: ChartSpec | null;
  loading?: boolean;
  error?: string | null;
}

const CHART_TYPES: ChartType[] = ["bar", "line", "pie", "scatter", "histogram"];

const COLORS = [
  "rgba(54, 162, 235, 0.7)",
  "rgba(255, 99, 132, 0.7)",
  "rgba(75, 192, 192, 0.7)",
  "rgba(255, 206, 86, 0.7)",
  "rgba(153, 102, 255, 0.7)",
  "rgba(255, 159, 64, 0.7)",
  "rgba(99, 255, 132, 0.7)",
  "rgba(201, 203, 207, 0.7)",
  "rgba(255, 99, 255, 0.7)",
  "rgba(0, 204, 150, 0.7)",
  "rgba(255, 140, 0, 0.7)",
  "rgba(100, 149, 237, 0.7)",
];

export default function ChartPanel({
  columns,
  onGenerate,
  chartSpec,
  loading = false,
  error = null,
}: ChartPanelProps) {
  const [chartType, setChartType] = useState<ChartType>("bar");
  const [xColumn, setXColumn] = useState<string>(columns[0] ?? "");
  const [yColumn, setYColumn] = useState<string>(columns[1] ?? "");
  const [groupBy, setGroupBy] = useState<string>("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const request: ChartRequest = {
      chart_type: chartType,
      x_column: xColumn,
    };
    if (chartType !== "histogram" && yColumn) {
      request.y_column = yColumn;
    }
    if (groupBy) {
      request.group_by = groupBy;
    }
    onGenerate(request);
  }

  function renderChart() {
    if (!chartSpec) return null;

    const isPie = chartSpec.chart_type === "pie";

    const datasets = chartSpec.datasets.map((ds, index) => ({
      label: ds.label,
      data: ds.data,
      backgroundColor: isPie
        ? ds.data.map((_, i) => COLORS[i % COLORS.length])
        : COLORS[index % COLORS.length],
      borderColor: isPie
        ? ds.data.map((_, i) => COLORS[i % COLORS.length].replace("0.7", "1"))
        : COLORS[index % COLORS.length].replace("0.7", "1"),
      borderWidth: 1,
    }));

    const data = {
      labels: chartSpec.labels,
      datasets,
    };

    const options = {
      responsive: true,
      plugins: {
        legend: { position: "top" as const },
        title: {
          display: true,
          text: `${chartSpec.x_axis_label} vs ${chartSpec.y_axis_label}`,
        },
      },
      scales:
        chartSpec.chart_type !== "pie"
          ? {
              x: { title: { display: true, text: chartSpec.x_axis_label } },
              y: { title: { display: true, text: chartSpec.y_axis_label } },
            }
          : undefined,
    };

    switch (chartSpec.chart_type) {
      case "bar":
      case "histogram":
        return <Bar data={data} options={options} />;
      case "line":
        return <Line data={data} options={options} />;
      case "pie":
        return <Pie data={data} options={{ responsive: true, plugins: { legend: { position: "top" as const } } }} />;
      case "scatter": {
        const scatterDatasets = chartSpec.datasets.map((ds, index) => ({
          label: ds.label,
          data: chartSpec.labels.map((label, i) => ({
            x: Number(label),
            y: ds.data[i] ?? 0,
          })),
          backgroundColor: COLORS[index % COLORS.length],
          borderColor: COLORS[index % COLORS.length].replace("0.7", "1"),
        }));
        return (
          <Scatter
            data={{ datasets: scatterDatasets }}
            options={options}
          />
        );
      }
      default:
        return <Bar data={data} options={options} />;
    }
  }

  return (
    <div style={{ border: "1px solid #ddd", borderRadius: "6px", padding: "1rem" }}>
      <h3 style={{ margin: "0 0 1rem 0" }}>Chart Panel</h3>

      <form onSubmit={handleSubmit} style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", alignItems: "flex-end" }}>
          {/* Chart Type Selector */}
          <div style={{ display: "flex", flexDirection: "column" }}>
            <label htmlFor="chart-type" style={{ fontSize: "0.8rem", marginBottom: "0.25rem", color: "#555" }}>
              Chart Type
            </label>
            <select
              id="chart-type"
              value={chartType}
              onChange={(e) => setChartType(e.target.value as ChartType)}
              style={{ padding: "0.4rem", border: "1px solid #ccc", borderRadius: "4px" }}
            >
              {CHART_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {/* X-Axis Column */}
          <div style={{ display: "flex", flexDirection: "column" }}>
            <label htmlFor="x-column" style={{ fontSize: "0.8rem", marginBottom: "0.25rem", color: "#555" }}>
              X-Axis Column
            </label>
            <select
              id="x-column"
              value={xColumn}
              onChange={(e) => setXColumn(e.target.value)}
              style={{ padding: "0.4rem", border: "1px solid #ccc", borderRadius: "4px" }}
            >
              {columns.map((col) => (
                <option key={col} value={col}>
                  {col}
                </option>
              ))}
            </select>
          </div>

          {/* Y-Axis Column (not required for histogram) */}
          {chartType !== "histogram" && (
            <div style={{ display: "flex", flexDirection: "column" }}>
              <label htmlFor="y-column" style={{ fontSize: "0.8rem", marginBottom: "0.25rem", color: "#555" }}>
                Y-Axis Column
              </label>
              <select
                id="y-column"
                value={yColumn}
                onChange={(e) => setYColumn(e.target.value)}
                style={{ padding: "0.4rem", border: "1px solid #ccc", borderRadius: "4px" }}
              >
                {columns.map((col) => (
                  <option key={col} value={col}>
                    {col}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Group By (optional) */}
          <div style={{ display: "flex", flexDirection: "column" }}>
            <label htmlFor="group-by" style={{ fontSize: "0.8rem", marginBottom: "0.25rem", color: "#555" }}>
              Group By (optional)
            </label>
            <select
              id="group-by"
              value={groupBy}
              onChange={(e) => setGroupBy(e.target.value)}
              style={{ padding: "0.4rem", border: "1px solid #ccc", borderRadius: "4px" }}
            >
              <option value="">None</option>
              {columns.map((col) => (
                <option key={col} value={col}>
                  {col}
                </option>
              ))}
            </select>
          </div>

          {/* Generate Button */}
          <button
            type="submit"
            disabled={loading}
            style={{
              padding: "0.4rem 1rem",
              backgroundColor: loading ? "#999" : "#0070f3",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: loading ? "not-allowed" : "pointer",
              fontWeight: "500",
            }}
          >
            {loading ? "Generating..." : "Generate Chart"}
          </button>
        </div>
      </form>

      {/* Error Message */}
      {error && (
        <div style={{ color: "red", marginBottom: "1rem", fontSize: "0.875rem" }}>
          {error}
        </div>
      )}

      {/* Loading Indicator */}
      {loading && (
        <div style={{ textAlign: "center", padding: "2rem", color: "#555" }}>
          <div
            style={{
              display: "inline-block",
              width: "24px",
              height: "24px",
              border: "3px solid #ddd",
              borderTop: "3px solid #0070f3",
              borderRadius: "50%",
              animation: "freeTierSpin 1s linear infinite",
            }}
          />
          <p style={{ marginTop: "0.5rem" }}>Generating chart...</p>
          <p style={{ color: "#9ca3af", fontSize: "0.75rem" }}>
            This project uses free-tier services, so it may take a moment. Please wait.
          </p>
          <style>{`@keyframes freeTierSpin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Chart Rendering */}
      {!loading && chartSpec && (
        <div style={{ maxWidth: "700px", margin: "0 auto" }}>
          {renderChart()}
        </div>
      )}
    </div>
  );
}
