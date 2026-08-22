"use client";

import { useEffect, useState } from "react";
import { LeadSheet } from "../lib/data";

interface EditLeadSheetModalProps {
  sheet: any;
  isOpen: boolean;
  onClose: () => void;
  onSave: (updatedSheet: any) => void;
}

export function EditLeadSheetModal({ sheet, isOpen, onClose, onSave }: EditLeadSheetModalProps) {
  const [name, setName] = useState("");
  const [shortId, setShortId] = useState("");
  const [date, setDate] = useState("");
  const [leadsCount, setLeadsCount] = useState(1000);
  const [sheetUrl, setSheetUrl] = useState("");

  useEffect(() => {
    if (sheet) {
      setName(sheet.name || "");
      setShortId(sheet.shortId || sheet.sheetId || sheet.id || "");
      setDate(sheet.date || sheet.createdAt || "");
      setLeadsCount(sheet.leadsCount || sheet.leads?.length || 100);
      setSheetUrl(sheet.sheetUrl || sheet.googleSheetsUrl || `https://docs.google.com/spreadsheets/d/${sheet.id}_destination/edit`);
    }
  }, [sheet]);

  if (!isOpen || !sheet) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    onSave({
      ...sheet,
      name: name.trim(),
      shortId: shortId.trim() || sheet.shortId || sheet.id,
      date: date.trim() || sheet.date || sheet.createdAt,
      leadsCount: Number(leadsCount) || sheet.leadsCount || 100,
      sheetUrl: sheetUrl.trim(),
      googleSheetsUrl: sheetUrl.trim(),
    });
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="excel-modal" style={{ width: "500px" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "700", color: "var(--text-dark)" }}>
            Edit Sheet Details: {sheet.shortId}
          </h2>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", fontSize: "1.2rem", cursor: "pointer", color: "var(--text-dark)" }}
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px", marginTop: "10px" }}>
          <div>
            <label style={{ fontSize: "0.85rem", fontWeight: "600", display: "block", marginBottom: "4px" }}>
              Sheet Name
            </label>
            <input
              type="text"
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

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <div>
              <label style={{ fontSize: "0.85rem", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Lead Short ID
              </label>
              <input
                type="text"
                value={shortId}
                onChange={(e) => setShortId(e.target.value)}
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
                type="text"
                value={date}
                onChange={(e) => setDate(e.target.value)}
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
              Leads Count
            </label>
            <input
              type="number"
              value={leadsCount}
              onChange={(e) => setLeadsCount(Number(e.target.value))}
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
              Saved Sheet Link / URL
            </label>
            <input
              type="text"
              value={sheetUrl}
              onChange={(e) => setSheetUrl(e.target.value)}
              placeholder="https://docs.google.com/spreadsheets/d/..."
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

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "12px" }}>
            <button type="button" className="pill-btn" onClick={onClose} style={{ background: "transparent", color: "var(--text-dark)" }}>
              Cancel
            </button>
            <button type="submit" className="pill-btn" style={{ background: "var(--purple-accent)", color: "#FFF" }}>
              Save Changes
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
