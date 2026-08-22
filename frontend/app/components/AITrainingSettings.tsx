"use client";

import { useEffect, useState } from "react";
import { modelsApi } from "../lib/models";

interface AITrainingSettingsProps {
  token: string;
}

export function AITrainingSettings({ token }: AITrainingSettingsProps) {
  const [versions, setVersions] = useState<any[]>([]);
  const [training, setTraining] = useState(false);

  const loadVersions = () => {
    modelsApi
      .listVersions(token)
      .then((data: any) => setVersions(Array.isArray(data) ? data : (data?.versions || [])))
      .catch((err) => console.error("Failed to load model versions:", err));
  };

  useEffect(() => {
    loadVersions();
  }, [token]);

  const handleTrain3Phase = async () => {
    setTraining(true);
    try {
      await modelsApi.train3Phase(token);
      alert("3-Phase AI Model Training Complete! Version placed in STAGING.");
      loadVersions();
    } catch (err) {
      console.error("Training failed:", err);
    } finally {
      setTraining(false);
    }
  };

  const handlePromote = async (version: string) => {
    try {
      await modelsApi.promote(version, token);
      alert(`Model ${version} promoted to PRODUCTION!`);
      loadVersions();
    } catch (err) {
      console.error("Promotion failed:", err);
    }
  };

  return (
    <div>
      <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "16px" }}>AI Training & Model Governance</h3>
      <p style={{ fontSize: "0.85rem", color: "#4B5563", marginBottom: "16px" }}>
        Train CatBoost & LightGBM ensemble models across 40,000+ synthetic permutations & raw data noise.
      </p>

      <button className="pill-btn" onClick={handleTrain3Phase} disabled={training} style={{ marginBottom: "20px" }}>
        {training ? "Training 40,000+ Permutations..." : "⚡ Execute 3-Phase AI Model Training"}
      </button>

      <h4 style={{ fontSize: "0.95rem", fontWeight: "700", marginBottom: "12px" }}>Registered Model Versions</h4>
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {versions.map((v) => (
          <div
            key={v.version}
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
              <strong>{v.version}</strong>
              <span
                style={{
                  marginLeft: "10px",
                  fontSize: "0.75rem",
                  padding: "2px 8px",
                  borderRadius: "9999px",
                  background: v.status === "PRODUCTION" ? "#D1FAE5" : "#FEF3C7",
                  color: v.status === "PRODUCTION" ? "#065F46" : "#92400E",
                  fontWeight: "700",
                }}
              >
                {v.status}
              </span>
            </div>
            {v.status !== "PRODUCTION" && (
              <button
                className="pill-btn"
                style={{ padding: "6px 16px", fontSize: "0.8rem" }}
                onClick={() => handlePromote(v.version)}
              >
                Promote to Production
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
