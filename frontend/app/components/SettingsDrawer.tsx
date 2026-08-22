"use client";

import { useEffect, useState } from "react";
import { AddSecondarySheetModal, SecondarySheetData } from "./AddSecondarySheetModal";

interface SettingsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  token: string;
  onOpenRawLeadsWorkspace?: () => void;
  initialSection?: "api" | "google" | "secondary" | "raw" | "history" | "rejected" | "export";
}

export function SettingsDrawer({
  isOpen,
  onClose,
  token,
  onOpenRawLeadsWorkspace,
  initialSection = "api",
}: SettingsDrawerProps) {
  const [activeSection, setActiveSection] = useState<
    "api" | "google" | "secondary" | "raw" | "history" | "rejected" | "export"
  >(initialSection);

  useEffect(() => {
    if (initialSection) {
      setActiveSection(initialSection);
    }
  }, [initialSection, isOpen]);

  const [masterSheetUrl, setMasterSheetUrl] = useState(
    "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"
  );
  const [googleMapsKey, setGoogleMapsKey] = useState("AIzaSyB-DemoMapsKey-2026");
  const [yelpApiKey, setYelpApiKey] = useState("yelp_live_api_token_smma");
  const [autoSyncEnabled, setAutoSyncEnabled] = useState(true);

  // Secondary Sheets State
  const [secondarySheets, setSecondarySheets] = useState<SecondarySheetData[]>([
    {
      id: "sec-1",
      name: "High Priority SMMA Leads Sheet",
      url: "https://docs.google.com/spreadsheets/d/1HighPrioritySMMADestination2026/edit",
      ownerName: "Sarah Connor",
      dateCreated: "2026-08-01",
      type: "Google Sheet",
      count: 1450,
    },
    {
      id: "sec-2",
      name: "Verified Contacts Destination Sheet",
      url: "https://docs.google.com/spreadsheets/d/1VerifiedEmailsDestination2026/edit",
      ownerName: "Alex Vance",
      dateCreated: "2026-08-05",
      type: "Excel (XLSX)",
      count: 2890,
    },
  ]);

  // Export & Raw Leads History State
  const [exportHistory] = useState([
    {
      id: "exp-1",
      sheetName: "Dental Clinics NY Master",
      format: "CSV",
      date: "2026-08-11 14:30",
      link: "http://localhost:8000/api/leads/export.csv",
      fileSize: "2.4 MB",
      recordCount: 1000,
    },
    {
      id: "exp-2",
      sheetName: "Yelp Local Services LA",
      format: "Excel (XLSX)",
      date: "2026-08-10 11:15",
      link: "https://docs.google.com/spreadsheets/d/102_Yelp_Destination/edit",
      fileSize: "2.8 MB",
      recordCount: 1200,
    },
    {
      id: "exp-3",
      sheetName: "Apollo B2B SaaS Leads",
      format: "Google Sheet",
      date: "2026-08-09 18:45",
      link: "https://docs.google.com/spreadsheets/d/110_Apollo_Destination/edit",
      fileSize: "6.8 MB",
      recordCount: 3100,
    },
  ]);

  const [rawHistory] = useState([
    { id: "raw-1", jobName: "Google Maps Scraping (NY)", date: "2026-08-11 10:00", rawCount: 1850, status: "Raw Preserved" },
    { id: "raw-2", jobName: "Yelp Local Services (LA)", date: "2026-08-10 09:30", rawCount: 1200, status: "Raw Preserved" },
    { id: "raw-3", jobName: "LinkedIn B2B Outreach", date: "2026-08-09 16:20", rawCount: 412, status: "Raw Preserved" },
  ]);

  // Rejected Leads Training Data State
  const [rejectedLeads, setRejectedLeads] = useState<any[]>([]);

  useEffect(() => {
    fetch("http://localhost:8000/api/leads/rejected")
      .then((res) => res.json())
      .then((data) => setRejectedLeads(data.records || []))
      .catch((err) => console.error("Failed to load rejected leads:", err));
  }, []);

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [activeMenuSheetId, setActiveMenuSheetId] = useState<string | null>(null);

  const handleSave = () => {
    onClose();
  };

  const handleAddSecondarySheet = (newSheet: SecondarySheetData) => {
    setSecondarySheets((prev) => [...prev, newSheet]);
  };

  const handleEditSecondarySheet = (id: string) => {
    setActiveMenuSheetId(null);
    const sheet = secondarySheets.find((s) => s.id === id);
    if (!sheet) return;
    const newName = prompt("Edit Sheet Name:", sheet.name);
    if (!newName || !newName.trim()) return;
    const newUrl = prompt("Edit Sheet Link / URL:", sheet.url);
    if (!newUrl || !newUrl.trim()) return;

    setSecondarySheets((prev) =>
      prev.map((s) => (s.id === id ? { ...s, name: newName.trim(), url: newUrl.trim() } : s))
    );
  };

  const handleExportSecondarySheet = (id: string, format: string) => {
    setActiveMenuSheetId(null);
    const sheet = secondarySheets.find((s) => s.id === id);
    alert(`Exporting secondary sheet "${sheet?.name || id}" as ${format}...`);
    window.location.href = "http://localhost:8000/api/leads/export.csv";
  };

  const handleDeleteSecondarySheet = (id: string) => {
    setActiveMenuSheetId(null);
    const sheet = secondarySheets.find((s) => s.id === id);
    if (confirm(`Are you sure you want to delete secondary sheet "${sheet?.name || id}"?`)) {
      setSecondarySheets((prev) => prev.filter((s) => s.id !== id));
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose}>
        <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
          <div className="drawer-header">
            <h2 style={{ fontSize: "1.05rem", fontWeight: "700" }}>System Settings</h2>
            <button
              onClick={onClose}
              style={{
                background: "none",
                border: "none",
                color: "var(--text-header)",
                fontSize: "1.2rem",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </div>

          <div className="drawer-body">
            {/* Minimalist Navigation List */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <div
                className="settings-list-item"
                onClick={() => setActiveSection("api")}
                style={{
                  borderLeft: activeSection === "api" ? "3px solid var(--purple-accent)" : "none",
                  fontWeight: activeSection === "api" ? "700" : "500",
                }}
              >
                <span>API Management</span>
              </div>

              <div
                className="settings-list-item"
                onClick={() => setActiveSection("google")}
                style={{
                  borderLeft: activeSection === "google" ? "3px solid var(--purple-accent)" : "none",
                  fontWeight: activeSection === "google" ? "700" : "500",
                }}
              >
                <span>Google Sheet Management</span>
              </div>

              <div
                className="settings-list-item"
                onClick={() => setActiveSection("secondary")}
                style={{
                  borderLeft: activeSection === "secondary" ? "3px solid var(--purple-accent)" : "none",
                  fontWeight: activeSection === "secondary" ? "700" : "500",
                }}
              >
                <span>Secondary Sheets</span>
              </div>

              <div
                className="settings-list-item"
                onClick={() => setActiveSection("raw")}
                style={{
                  borderLeft: activeSection === "raw" ? "3px solid var(--purple-accent)" : "none",
                  fontWeight: activeSection === "raw" ? "700" : "500",
                }}
              >
                <span>Raw Leads Repository</span>
              </div>

              <div
                className="settings-list-item"
                onClick={() => setActiveSection("history")}
                style={{
                  borderLeft: activeSection === "history" ? "3px solid var(--purple-accent)" : "none",
                  fontWeight: activeSection === "history" ? "700" : "500",
                }}
              >
                <span>History</span>
              </div>

              <div
                className="settings-list-item"
                onClick={() => setActiveSection("rejected")}
                style={{
                  borderLeft: activeSection === "rejected" ? "3px solid var(--purple-accent)" : "none",
                  fontWeight: activeSection === "rejected" ? "700" : "500",
                }}
              >
                <span>AI Training (Rejected Leads)</span>
              </div>

              <div
                className="settings-list-item"
                onClick={() => setActiveSection("export")}
                style={{
                  borderLeft: activeSection === "export" ? "3px solid var(--purple-accent)" : "none",
                  fontWeight: activeSection === "export" ? "700" : "500",
                }}
              >
                <span>Export Leads</span>
              </div>
            </div>

            <hr style={{ borderColor: "var(--border-color)", margin: "4px 0" }} />

            {/* Section 1: API Management */}
            {activeSection === "api" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: "700", color: "var(--text-dark)" }}>
                  API Keys & Connectors
                </h3>
                <div>
                  <label style={{ fontSize: "0.8rem", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                    Google Maps Places API Key
                  </label>
                  <input
                    type="password"
                    value={googleMapsKey}
                    onChange={(e) => setGoogleMapsKey(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: "8px",
                      border: "1px solid var(--border-color)",
                      backgroundColor: "var(--bg-row)",
                      color: "var(--text-dark)",
                      fontSize: "0.85rem",
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: "0.8rem", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                    Yelp Fusion API Key
                  </label>
                  <input
                    type="password"
                    value={yelpApiKey}
                    onChange={(e) => setYelpApiKey(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: "8px",
                      border: "1px solid var(--border-color)",
                      backgroundColor: "var(--bg-row)",
                      color: "var(--text-dark)",
                      fontSize: "0.85rem",
                    }}
                  />
                </div>
              </div>
            )}

            {/* Section 2: Google Sheet Management */}
            {activeSection === "google" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: "700", color: "var(--text-dark)" }}>
                  Master Google Sheet Management
                </h3>
                <div>
                  <label style={{ fontSize: "0.8rem", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                    Master Sheet Link
                  </label>
                  <input
                    type="text"
                    value={masterSheetUrl}
                    onChange={(e) => setMasterSheetUrl(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: "8px",
                      border: "1px solid var(--border-color)",
                      backgroundColor: "var(--bg-row)",
                      color: "var(--text-dark)",
                      fontSize: "0.85rem",
                    }}
                  />
                </div>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "4px" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: "500" }}>Auto-Sync Scraped Leads</span>
                  <input
                    type="checkbox"
                    checked={autoSyncEnabled}
                    onChange={(e) => setAutoSyncEnabled(e.target.checked)}
                    style={{ width: "16px", height: "16px", accentColor: "var(--purple-accent)" }}
                  />
                </div>
              </div>
            )}

            {/* Section 3: Secondary Sheets */}
            {activeSection === "secondary" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 style={{ fontSize: "0.95rem", fontWeight: "700", color: "var(--text-dark)" }}>
                    Secondary Sheets
                  </h3>
                  <button
                    className="pill-btn"
                    onClick={() => setIsAddModalOpen(true)}
                    style={{ padding: "4px 12px", fontSize: "0.85rem", background: "var(--purple-accent)" }}
                    title="Add Secondary Sheet Form"
                  >
                    + Add Sheet
                  </button>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "4px" }}>
                  {secondarySheets.map((sheet) => (
                    <div
                      key={sheet.id}
                      style={{
                        backgroundColor: "var(--bg-card)",
                        borderRadius: "10px",
                        padding: "10px 14px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "4px",
                        border: "1px solid var(--border-color)",
                        position: "relative",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontWeight: "600", fontSize: "0.85rem", color: "var(--text-dark)" }}>
                          {sheet.name}
                        </span>

                        <button
                          className="three-dots-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveMenuSheetId(activeMenuSheetId === sheet.id ? null : sheet.id);
                          }}
                          title="Actions"
                        >
                          ⋮
                        </button>
                      </div>

                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", wordBreak: "break-all" }}>
                        {sheet.url}
                      </div>

                      <div style={{ display: "flex", gap: "12px", fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>
                        <span>Owner: {sheet.ownerName}</span>
                        <span>Type: {sheet.type}</span>
                        <span>Created: {sheet.dateCreated}</span>
                      </div>

                      {activeMenuSheetId === sheet.id && (
                        <div className="action-menu" style={{ right: "12px", top: "34px" }}>
                          <button className="action-menu-item" onClick={() => handleEditSecondarySheet(sheet.id)}>
                            Edit sheet
                          </button>

                          <button className="action-menu-item" onClick={() => handleExportSecondarySheet(sheet.id, "CSV")}>
                            Export as...
                          </button>

                          <button className="action-menu-item danger" onClick={() => handleDeleteSecondarySheet(sheet.id)}>
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Section 4: Raw Leads Repository */}
            {activeSection === "raw" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: "700", color: "var(--text-dark)" }}>
                  Raw Leads Repository
                </h3>
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Full raw leads workspace containing unsegregated scraped lead sheets before AI filtering.
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  <div className="metric-stat-box">
                    <span className="metric-label">Raw Scraped Collections</span>
                    <span className="metric-value">10 Active Collections</span>
                  </div>
                  <div className="metric-stat-box">
                    <span className="metric-label">Total Raw Records</span>
                    <span className="metric-value">13,563 Leads</span>
                  </div>
                </div>

                <button
                  className="pill-btn"
                  onClick={() => {
                    onClose();
                    if (onOpenRawLeadsWorkspace) onOpenRawLeadsWorkspace();
                  }}
                  style={{ width: "100%", padding: "10px", background: "var(--purple-accent)", marginTop: "6px" }}
                >
                  Open Full Raw Leads Repository Page
                </button>
              </div>
            )}

            {/* Section 5: History */}
            {activeSection === "history" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: "700", color: "var(--text-dark)" }}>
                  System History Logs
                </h3>

                {/* Export History */}
                <div>
                  <h4 style={{ fontSize: "0.85rem", fontWeight: "600", color: "var(--purple-accent)", marginBottom: "6px" }}>
                    Export History
                  </h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    {exportHistory.map((item) => (
                      <div
                        key={item.id}
                        style={{
                          backgroundColor: "var(--bg-card)",
                          borderRadius: "8px",
                          padding: "8px 12px",
                          border: "1px solid var(--border-color)",
                          fontSize: "0.78rem",
                        }}
                      >
                        <div style={{ fontWeight: "600", color: "var(--text-dark)" }}>
                          {item.sheetName} ({item.format})
                        </div>
                        <div style={{ color: "var(--text-muted)", marginTop: "2px" }}>
                          Date: {item.date} • Size: {item.fileSize} • Records: {item.recordCount}
                        </div>
                        <a
                          href={item.link}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: "var(--purple-accent)", fontSize: "0.75rem", wordBreak: "break-all" }}
                        >
                          {item.link}
                        </a>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Raw Leads History */}
                <div>
                  <h4 style={{ fontSize: "0.85rem", fontWeight: "600", color: "var(--purple-accent)", marginBottom: "6px" }}>
                    Raw Leads Scrape History
                  </h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    {rawHistory.map((item) => (
                      <div
                        key={item.id}
                        style={{
                          backgroundColor: "var(--bg-card)",
                          borderRadius: "8px",
                          padding: "8px 12px",
                          border: "1px solid var(--border-color)",
                          fontSize: "0.78rem",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: "600", color: "var(--text-dark)" }}>{item.jobName}</div>
                          <div style={{ color: "var(--text-muted)" }}>Date: {item.date}</div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <span style={{ fontWeight: "700", color: "var(--purple-accent)" }}>{item.rawCount} Raw</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Section 6: AI Training (Rejected Leads Dataset) - Save button removed */}
            {activeSection === "rejected" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: "700", color: "var(--text-dark)" }}>
                  AI Model Training (Rejected Leads)
                </h3>
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Contains all rejected leads removed during AI segregation (`rejected_leads.csv`). Used to continuously train the AI model for higher precision.
                </p>

                <div className="metric-stat-box">
                  <span className="metric-label">Dataset File</span>
                  <span style={{ fontSize: "0.85rem", fontWeight: "600", color: "var(--purple-accent)" }}>
                    training_data/rejected_leads.csv
                  </span>
                </div>

                <div className="metric-stat-box">
                  <span className="metric-label">Total Rejected Records Stored</span>
                  <span className="metric-value">{rejectedLeads.length || 4} Records</span>
                </div>

                <button
                  className="pill-btn"
                  onClick={() => alert("Downloading training dataset: rejected_leads.csv")}
                  style={{ width: "100%", padding: "8px", fontSize: "0.85rem" }}
                >
                  Download Training Dataset
                </button>
              </div>
            )}

            {/* Section 7: Export Leads - Save button removed */}
            {activeSection === "export" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: "700", color: "var(--text-dark)" }}>
                  Export Leads
                </h3>
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Download the complete lead database in CSV format.
                </p>
                <button
                  className="pill-btn"
                  onClick={() => (window.location.href = "http://localhost:8000/api/leads/export.csv")}
                  style={{ width: "100%", padding: "10px", background: "var(--purple-accent)" }}
                >
                  Download Master CSV Database
                </button>
              </div>
            )}

            {/* Save Button is strictly restricted to input/configurable settings (API, Google Sheet, Secondary Sheets) */}
            {["api", "google", "secondary"].includes(activeSection) && (
              <div style={{ marginTop: "auto", paddingTop: "16px" }}>
                <button className="pill-btn" onClick={handleSave} style={{ width: "100%", background: "var(--purple-accent)" }}>
                  Save
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <AddSecondarySheetModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAdd={handleAddSecondarySheet}
      />
    </>
  );
}
