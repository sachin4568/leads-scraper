"use client";

export function SecuritySettings() {
  return (
    <div>
      <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "16px" }}>Security & Integrations</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ background: "#E5E7EB", padding: "14px 16px", borderRadius: "12px", display: "flex", justifyContent: "space-between" }}>
          <span>PostgreSQL Row-Level Security (RLS)</span>
          <strong style={{ color: "#10B981" }}>ACTIVE</strong>
        </div>
        <div style={{ background: "#E5E7EB", padding: "14px 16px", borderRadius: "12px", display: "flex", justifyContent: "space-between" }}>
          <span>SSRF Outbound Guard</span>
          <strong style={{ color: "#10B981" }}>PROTECTED</strong>
        </div>
        <div style={{ background: "#E5E7EB", padding: "14px 16px", borderRadius: "12px", display: "flex", justifyContent: "space-between" }}>
          <span>Webhook HMAC Signature Verification</span>
          <strong style={{ color: "#10B981" }}>ENABLED</strong>
        </div>
        <div style={{ background: "#E5E7EB", padding: "14px 16px", borderRadius: "12px", display: "flex", justifyContent: "space-between" }}>
          <span>Sentry & Structlog PII Sanitizer</span>
          <strong style={{ color: "#10B981" }}>ACTIVE</strong>
        </div>
        <div style={{ background: "#E5E7EB", padding: "14px 16px", borderRadius: "12px", display: "flex", justifyContent: "space-between" }}>
          <span>Prometheus Metrics Endpoint</span>
          <a href="http://localhost:8000/metrics" target="_blank" rel="noreferrer" style={{ color: "#8B5CF6", fontWeight: "600" }}>
            /metrics ↗
          </a>
        </div>
      </div>
    </div>
  );
}
