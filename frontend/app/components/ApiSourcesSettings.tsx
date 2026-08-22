"use client";

import { useEffect, useState } from "react";
import { sourcesApi } from "../lib/sources";

interface ApiSourcesSettingsProps {
  token: string;
}

export function ApiSourcesSettings({ token }: ApiSourcesSettingsProps) {
  const [sources, setSources] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    sourcesApi
      .getHealth(token)
      .then((data: any) => setSources(Array.isArray(data) ? data : (data?.sources || [])))
      .catch((err) => console.error("Failed to load source health:", err))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div>
      <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "16px" }}>API Sources & Credentials</h3>
      <p style={{ fontSize: "0.85rem", color: "#4B5563", marginBottom: "20px" }}>
        Configure source connector credentials. Safe state indicators reflect real API health.
      </p>

      {loading ? (
        <p>Loading source health...</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {sources.map((s) => (
            <div
              key={s.source}
              style={{
                background: "#E5E7EB",
                padding: "12px 16px",
                borderRadius: "12px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <strong style={{ textTransform: "capitalize" }}>{s.source.replace("_", " ")}</strong>
              </div>
              <span
                style={{
                  padding: "4px 12px",
                  borderRadius: "9999px",
                  fontSize: "0.75rem",
                  fontWeight: "700",
                  background: s.state === "CONNECTED" ? "#D1FAE5" : "#FEE2E2",
                  color: s.state === "CONNECTED" ? "#065F46" : "#991B1B",
                }}
              >
                {s.state}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
