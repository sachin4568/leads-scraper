"use client";

import { useState } from "react";

interface HistoryWorkspaceModalProps {
  isOpen: boolean;
  onClose: () => void;
  exportHistory: Array<{
    id: string;
    sheetName: string;
    format: string;
    date: string;
    link: string;
    fileSize: string;
    recordCount: number;
  }>;
  rawHistory: Array<{
    id: string;
    jobName: string;
    date: string;
    rawCount: number;
    status: string;
  }>;
}

export function HistoryWorkspaceModal({
  isOpen,
  onClose,
  exportHistory,
  rawHistory,
}: HistoryWorkspaceModalProps) {
  const [searchQuery, setSearchQuery] = useState("");

  if (!isOpen) return null;

  const filteredExport = exportHistory.filter(
    (item) =>
      item.sheetName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.format.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.date.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredRaw = rawHistory.filter(
    (item) =>
      item.jobName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.date.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.status.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        zIndex: 2000,
        backgroundColor: "var(--bg-page)",
        display: "flex",
        flexDirection: "column",
        padding: "20px 32px",
        overflow: "hidden",
      }}
    >
      {/* Top Header Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          paddingBottom: "16px",
          borderBottom: "1px solid var(--border-color)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <button
            onClick={onClose}
            className="modal-action-btn"
            style={{ padding: "6px 14px", fontSize: "0.82rem" }}
          >
            ← Back to Home
          </button>
          <div>
            <h1 style={{ fontSize: "1.5rem", fontWeight: "700", color: "var(--text-dark)", margin: 0 }}>
              History
            </h1>
          </div>
        </div>

        <div style={{ width: "320px" }}>
          <input
            type="text"
            className="search-input"
            style={{ width: "100%", padding: "8px 16px", fontSize: "0.85rem" }}
            placeholder="Search history logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Main Content Area: Export History & Raw Leads History */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          marginTop: "20px",
          display: "flex",
          flexDirection: "column",
          gap: "24px",
        }}
      >
        {/* Export History Table */}
        <div className="card-container" style={{ padding: "20px" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "700", color: "var(--text-dark)", marginBottom: "12px" }}>
            Export History
          </h2>

          <table className="excel-table">
            <thead>
              <tr>
                <th>Sheet Name</th>
                <th>Format</th>
                <th>Date & Time</th>
                <th>File Size</th>
                <th>Records</th>
                <th>Destination Link</th>
              </tr>
            </thead>
            <tbody>
              {filteredExport.map((item) => (
                <tr key={item.id}>
                  <td style={{ fontWeight: "600" }}>{item.sheetName}</td>
                  <td>
                    <span style={{ fontWeight: "600", color: "var(--purple-accent)" }}>{item.format}</span>
                  </td>
                  <td>{item.date}</td>
                  <td>{item.fileSize}</td>
                  <td>{item.recordCount}</td>
                  <td>
                    <a
                      href={item.link}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: "var(--purple-accent)", textDecoration: "none" }}
                    >
                      View Link
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Raw Leads Scrape History Table */}
        <div className="card-container" style={{ padding: "20px" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "700", color: "var(--text-dark)", marginBottom: "12px" }}>
            Raw Leads Scrape History
          </h2>

          <table className="excel-table">
            <thead>
              <tr>
                <th>Job Name</th>
                <th>Date & Time</th>
                <th>Raw Leads Scraped</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredRaw.map((item) => (
                <tr key={item.id}>
                  <td style={{ fontWeight: "600" }}>{item.jobName}</td>
                  <td>{item.date}</td>
                  <td style={{ fontWeight: "700", color: "var(--purple-accent)" }}>{item.rawCount}</td>
                  <td>{item.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
