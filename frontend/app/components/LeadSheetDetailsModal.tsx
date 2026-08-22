"use client";

interface LeadSheetDetailsModalProps {
  sheet: any;
  isOpen: boolean;
  onClose: () => void;
}

export function LeadSheetDetailsModal({ sheet, isOpen, onClose }: LeadSheetDetailsModalProps) {
  if (!isOpen || !sheet) return null;

  const rawCount = sheet.rawLeadsCount || sheet.leadsCount || sheet.leads?.length || 100;
  const segregatedCount = sheet.segregatedLeadsCount || Math.round(rawCount * 0.74);
  const fileSize = sheet.fileSize || `${(rawCount * 0.0024).toFixed(1)} MB`;
  const sheetUrl = sheet.sheetUrl || sheet.googleSheetsUrl || `https://docs.google.com/spreadsheets/d/${sheet.id}_destination/edit`;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="excel-modal" style={{ width: "560px" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ fontSize: "1.15rem", fontWeight: "700", color: "var(--text-dark)" }}>
              Sheet Details: {sheet.name}
            </h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Lead Collection Metadata & Sources
            </p>
          </div>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", fontSize: "1.2rem", cursor: "pointer", color: "var(--text-dark)" }}
          >
            ✕
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "12px" }}>
          <div className="metric-stat-box" style={{ padding: "14px" }}>
            <span className="metric-label">Saved Sheet Link</span>
            <a
              href={sheetUrl}
              target="_blank"
              rel="noreferrer"
              style={{ color: "var(--purple-accent)", fontSize: "0.85rem", wordBreak: "break-all", fontWeight: "600" }}
            >
              {sheetUrl}
            </a>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            <div className="metric-stat-box">
              <span className="metric-label">Date Created</span>
              <span className="metric-value" style={{ fontSize: "1rem" }}>{sheet.date}</span>
            </div>

            <div className="metric-stat-box">
              <span className="metric-label">File Size</span>
              <span className="metric-value" style={{ fontSize: "1rem" }}>{fileSize}</span>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" }}>
            <div className="metric-stat-box">
              <span className="metric-label">Raw Leads</span>
              <span className="metric-value" style={{ fontSize: "1.1rem" }}>{rawCount}</span>
            </div>

            <div className="metric-stat-box">
              <span className="metric-label">Segregated</span>
              <span className="metric-value" style={{ fontSize: "1.1rem", color: "#10B981" }}>
                {segregatedCount}
              </span>
            </div>

            <div className="metric-stat-box">
              <span className="metric-label">Total Count</span>
              <span className="metric-value" style={{ fontSize: "1.1rem" }}>{sheet.leadsCount}</span>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            <div className="metric-stat-box">
              <span className="metric-label">Sources</span>
              <span style={{ fontSize: "0.85rem", fontWeight: "600", color: "var(--text-dark)" }}>
                Google Maps, Yelp, Web Scraping
              </span>
            </div>

            <div className="metric-stat-box">
              <span className="metric-label">Outreach Channels</span>
              <span style={{ fontSize: "0.85rem", fontWeight: "600", color: "var(--text-dark)" }}>
                Email, Phone, WhatsApp, CRM
              </span>
            </div>
          </div>

          <div style={{ textAlign: "right", marginTop: "10px" }}>
            <button className="pill-btn" onClick={onClose} style={{ padding: "8px 20px" }}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
