"use client";

import { useState } from "react";

export interface SecondarySheetData {
  id: string;
  name: string;
  url: string;
  ownerName: string;
  dateCreated: string;
  type: string;
  count: number;
}

interface AddSecondarySheetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (sheet: SecondarySheetData) => void;
}

export function AddSecondarySheetModal({ isOpen, onClose, onAdd }: AddSecondarySheetModalProps) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [dateCreated, setDateCreated] = useState(new Date().toISOString().split("T")[0]);
  const [type, setType] = useState("Google Sheet");

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !url.trim()) {
      alert("Please provide Sheet Name and Sheet Link.");
      return;
    }

    onAdd({
      id: `sec-${Date.now()}`,
      name: name.trim(),
      url: url.trim(),
      ownerName: ownerName.trim() || "Admin",
      dateCreated,
      type,
      count: 0,
    });

    // Reset form
    setName("");
    setUrl("");
    setOwnerName("");
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="excel-modal" style={{ width: "520px" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "700", color: "var(--text-dark)" }}>
            Add Secondary Sheet
          </h2>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              fontSize: "1.2rem",
              color: "var(--text-dark)",
              cursor: "pointer",
            }}
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div>
            <label style={{ fontSize: "0.85rem", fontWeight: "600", display: "block", marginBottom: "4px" }}>
              Sheet Name
            </label>
            <input
              type="text"
              placeholder="e.g. Qualified Dental Leads Sheet"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: "10px",
                border: "1px solid var(--border-color)",
                backgroundColor: "var(--bg-row)",
                color: "var(--text-dark)",
                fontSize: "0.85rem",
              }}
              required
            />
          </div>

          <div>
            <label style={{ fontSize: "0.85rem", fontWeight: "600", display: "block", marginBottom: "4px" }}>
              Sheet Link / URL
            </label>
            <input
              type="text"
              placeholder="https://docs.google.com/spreadsheets/d/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: "10px",
                border: "1px solid var(--border-color)",
                backgroundColor: "var(--bg-row)",
                color: "var(--text-dark)",
                fontSize: "0.85rem",
              }}
              required
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <div>
              <label style={{ fontSize: "0.85rem", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Owner Name
              </label>
              <input
                type="text"
                placeholder="e.g. John Doe / Team Lead"
                value={ownerName}
                onChange={(e) => setOwnerName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: "10px",
                  border: "1px solid var(--border-color)",
                  backgroundColor: "var(--bg-row)",
                  color: "var(--text-dark)",
                  fontSize: "0.85rem",
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: "0.85rem", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Date Created
              </label>
              <input
                type="date"
                value={dateCreated}
                onChange={(e) => setDateCreated(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: "10px",
                  border: "1px solid var(--border-color)",
                  backgroundColor: "var(--bg-row)",
                  color: "var(--text-dark)",
                  fontSize: "0.85rem",
                }}
              />
            </div>
          </div>

          <div>
            <label style={{ fontSize: "0.85rem", fontWeight: "600", display: "block", marginBottom: "4px" }}>
              Type
            </label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="pill-select"
              style={{ padding: "10px 14px" }}
            >
              <option value="Google Sheet">Google Sheet</option>
              <option value="Excel (XLSX)">Excel (XLSX)</option>
              <option value="CSV">CSV</option>
              <option value="S3 Bucket">S3 Bucket</option>
            </select>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
            <button type="button" className="pill-btn" onClick={onClose} style={{ background: "transparent", color: "var(--text-dark)" }}>
              Cancel
            </button>
            <button type="submit" className="pill-btn" style={{ background: "var(--purple-accent)", color: "#FFF" }}>
              Add Sheet
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
