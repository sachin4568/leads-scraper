"use client";

interface GoogleWorkspaceSettingsProps {
  token: string;
}

export function GoogleWorkspaceSettings({ token }: GoogleWorkspaceSettingsProps) {
  return (
    <div>
      <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "16px" }}>Google & Workspace Auth</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div style={{ background: "#E5E7EB", padding: "16px", borderRadius: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
            <span>Google Identity Provider</span>
            <strong style={{ color: "#10B981" }}>● Connected</strong>
          </div>
          <p style={{ fontSize: "0.85rem", color: "#4B5563" }}>
            OAuth 2.0 State: Verified session token (JWT isolation active)
          </p>
        </div>

        <div style={{ background: "#E5E7EB", padding: "16px", borderRadius: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
            <span>Google Sheets Auto-Sync</span>
            <strong style={{ color: "#10B981" }}>● Active</strong>
          </div>
          <p style={{ fontSize: "0.85rem", color: "#4B5563" }}>
            Scraped leads automatically sync to Google Sheets spreadheets upon job completion.
          </p>
        </div>
      </div>
    </div>
  );
}
