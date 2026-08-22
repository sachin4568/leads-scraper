"use client";

interface AnalyticsCardProps {
  totalLeads: number;
  verifiedContacts: number;
  highOpportunities: number;
  systemHealth: string;
  onViewDetailed: () => void;
}

export function AnalyticsCard({
  totalLeads,
  verifiedContacts,
  highOpportunities,
  systemHealth,
  onViewDetailed,
}: AnalyticsCardProps) {
  return (
    <div className="card-container">
      <div>
        <h3 style={{ fontSize: "1.05rem", fontWeight: "700", color: "var(--text-dark)", marginBottom: "4px" }}>
          Analytics Overview
        </h3>
        <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "10px" }}>
          Live scraping & validation metrics
        </p>

        <div className="analytics-grid">
          <div className="metric-stat-box">
            <span className="metric-label">Total Leads</span>
            <span className="metric-value">{totalLeads.toLocaleString()}</span>
          </div>

          <div className="metric-stat-box">
            <span className="metric-label">Verified Contacts</span>
            <span className="metric-value">{verifiedContacts.toLocaleString()}</span>
          </div>

          <div className="metric-stat-box">
            <span className="metric-label">High SMMA Opps</span>
            <span className="metric-value">{highOpportunities.toLocaleString()}</span>
          </div>

          <div className="metric-stat-box" style={{ justifyContent: "center" }}>
            <span className="metric-label">System Health</span>
            <span className="status-badge">{systemHealth}</span>
          </div>
        </div>
      </div>

      <div style={{ textAlign: "right", marginTop: "12px" }}>
        <button
          onClick={onViewDetailed}
          style={{
            background: "none",
            border: "none",
            color: "var(--purple-accent)",
            fontSize: "0.8rem",
            fontWeight: "600",
            cursor: "pointer",
          }}
        >
          View Detailed Analytics
        </button>
      </div>
    </div>
  );
}
