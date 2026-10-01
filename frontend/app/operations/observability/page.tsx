'use client';

import React, { useEffect, useState } from 'react';
import { api, HealthAPI, JobDiagnosticsAPI, ObservabilityDashboardAPI } from '../../lib/api';

export default function ObservabilityPage() {
  const [dashboard, setDashboard] = useState<ObservabilityDashboardAPI | null>(null);
  const [health, setHealth] = useState<HealthAPI | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [recoveringJobId, setRecoveringJobId] = useState<string | null>(null);
  const [selectedJobDiagnostics, setSelectedJobDiagnostics] = useState<JobDiagnosticsAPI | null>(null);
  const [loadingDiag, setLoadingDiag] = useState<boolean>(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api.getObservabilityDashboard().catch(() => null),
      api.getHealth().catch(() => null),
    ]).then(([dashData, healthData]) => {
      setDashboard(dashData);
      setHealth(healthData);
      setLoading(false);
    });
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // 10s live polling
    return () => clearInterval(interval);
  }, []);

  const handleRecoverJob = (jobId: string) => {
    setRecoveringJobId(jobId);
    setFeedbackMsg(null);
    api.recoverJob(jobId)
      .then((res) => {
        setRecoveringJobId(null);
        setFeedbackMsg({ type: 'success', text: `Job ${jobId} successfully recovered: ${res.message}` });
        loadData();
      })
      .catch((err) => {
        setRecoveringJobId(null);
        setFeedbackMsg({ type: 'error', text: `Failed to recover job: ${err.message}` });
      });
  };

  const handleInspectDiagnostics = (jobId: string) => {
    setLoadingDiag(true);
    api.getJobDiagnostics(jobId)
      .then((diag) => {
        setSelectedJobDiagnostics(diag);
        setLoadingDiag(false);
      })
      .catch((err) => {
        console.error('Failed to load diagnostics:', err);
        setLoadingDiag(false);
      });
  };

  return (
    <div style={{ padding: '24px 32px', backgroundColor: '#F8FAFC', minHeight: '100vh', fontFamily: 'Inter, system-ui, sans-serif' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: '700', color: '#0F172A', margin: 0 }}>Production Observability & Recovery</h1>
          <p style={{ fontSize: '14px', color: '#64748B', margin: '4px 0 0 0' }}>
            Real-time infrastructure health, worker telemetry, stuck-job detection, and idempotent recovery
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={loadData}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              backgroundColor: '#FFFFFF',
              border: '1px solid #CBD5E1',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: '600',
              color: '#334155',
              cursor: 'pointer',
            }}
          >
            ↻ Refresh Telemetry
          </button>
          <span style={{ fontSize: '12px', color: '#94A3B8' }}>Auto-refresh: 10s</span>
        </div>
      </div>

      {feedbackMsg && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: '8px',
            marginBottom: '20px',
            backgroundColor: feedbackMsg.type === 'success' ? '#F0FDF4' : '#FEF2F2',
            border: `1px solid ${feedbackMsg.type === 'success' ? '#BBF7D0' : '#FECACA'}`,
            color: feedbackMsg.type === 'success' ? '#15803D' : '#B91C1C',
            fontSize: '13px',
            fontWeight: '500',
          }}
        >
          {feedbackMsg.text}
        </div>
      )}

      {/* 1. Top Level Health & Infrastructure Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
        {/* Core System Status */}
        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            System Status
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: health?.status === 'healthy' ? '#10B981' : '#EF4444' }} />
            <span style={{ fontSize: '20px', fontWeight: '700', color: '#0F172A', textTransform: 'capitalize' }}>
              {health?.status || (loading ? 'Checking...' : 'Unknown')}
            </span>
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            Uptime: {health ? `${Math.floor(health.uptime_seconds / 60)}m ${Math.floor(health.uptime_seconds % 60)}s` : '0m 0s'}
          </div>
        </div>

        {/* Database Health */}
        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            Database Connectivity
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: health?.database?.connected ? '#10B981' : '#EF4444' }} />
            <span style={{ fontSize: '20px', fontWeight: '700', color: '#0F172A' }}>
              {health?.database?.connected ? 'CONNECTED' : 'DISCONNECTED'}
            </span>
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            Ping Latency: {health?.database?.latency_ms ?? 0} ms
          </div>
        </div>

        {/* Active Worker Nodes */}
        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            Worker Telemetry
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '20px', fontWeight: '700', color: '#0F172A' }}>
              {dashboard?.workers?.total_count ?? 0} Active Node(s)
            </span>
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            Status: <strong style={{ color: health?.workers?.status === 'HEALTHY' ? '#10B981' : '#F59E0B' }}>{health?.workers?.status || 'HEALTHY'}</strong>
          </div>
        </div>

        {/* Stuck Jobs Alert */}
        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            Stuck / Suspicious Jobs
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '20px', fontWeight: '700', color: (dashboard?.job_health?.stuck_count ?? 0) > 0 ? '#DC2626' : '#10B981' }}>
              {dashboard?.job_health?.stuck_count ?? 0} Stuck
            </span>
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            Running: {dashboard?.job_health?.running ?? 0} | Failed: {dashboard?.job_health?.failed ?? 0}
          </div>
        </div>
      </div>

      {/* 2. Stuck Jobs Actionable Alert Table */}
      {dashboard?.job_health?.stuck_jobs && dashboard.job_health.stuck_jobs.length > 0 && (
        <div style={{ backgroundColor: '#FEF2F2', border: '1px solid #F87171', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <span style={{ color: '#DC2626', fontSize: '18px' }}>⚠️</span>
            <h2 style={{ fontSize: '16px', fontWeight: '700', color: '#991B1B', margin: 0 }}>
              Stuck Job Intervention Required ({dashboard.job_health.stuck_jobs.length})
            </h2>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #FECACA', textAlign: 'left', color: '#7F1D1D' }}>
                <th style={{ padding: '8px' }}>Job ID</th>
                <th style={{ padding: '8px' }}>Niche / Region</th>
                <th style={{ padding: '8px' }}>Status</th>
                <th style={{ padding: '8px' }}>Progress</th>
                <th style={{ padding: '8px' }}>Reason</th>
                <th style={{ padding: '8px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.job_health.stuck_jobs.map((sj) => (
                <tr key={sj.job_id} style={{ borderBottom: '1px solid #FEE2E2' }}>
                  <td style={{ padding: '8px', fontFamily: 'monospace', fontWeight: '600' }}>{sj.job_id.slice(0, 8)}...</td>
                  <td style={{ padding: '8px' }}>{sj.niche} ({sj.state})</td>
                  <td style={{ padding: '8px' }}><span style={{ backgroundColor: '#FEE2E2', color: '#991B1B', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '700' }}>{sj.status}</span></td>
                  <td style={{ padding: '8px' }}>{sj.progress_percent.toFixed(1)}%</td>
                  <td style={{ padding: '8px', color: '#B91C1C' }}>{sj.reason}</td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>
                    <button
                      disabled={recoveringJobId === sj.job_id}
                      onClick={() => handleRecoverJob(sj.job_id)}
                      style={{
                        padding: '6px 12px',
                        backgroundColor: '#DC2626',
                        color: '#FFFFFF',
                        border: 'none',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: '600',
                        cursor: 'pointer',
                        marginRight: '6px',
                      }}
                    >
                      {recoveringJobId === sj.job_id ? 'Recovering...' : 'Safe Recover'}
                    </button>
                    <button
                      onClick={() => handleInspectDiagnostics(sj.job_id)}
                      style={{
                        padding: '6px 12px',
                        backgroundColor: '#FFFFFF',
                        color: '#475569',
                        border: '1px solid #CBD5E1',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: '600',
                        cursor: 'pointer',
                      }}
                    >
                      Diagnostics
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 3. Provider Telemetry & Workers Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
        {/* External Provider Metrics */}
        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <h2 style={{ fontSize: '16px', fontWeight: '700', color: '#0F172A', marginBottom: '16px' }}>External Provider Health</h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div style={{ padding: '12px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '13px', fontWeight: '700', color: '#0F172A', marginBottom: '6px' }}>OSM / Overpass API</div>
              <div style={{ fontSize: '12px', color: '#64748B', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>Total Requests: <strong>{dashboard?.provider_telemetry?.osm_overpass?.requests_total ?? 0}</strong></div>
                <div>Successes: <strong style={{ color: '#10B981' }}>{dashboard?.provider_telemetry?.osm_overpass?.success_total ?? 0}</strong></div>
                <div>Timeouts: <strong style={{ color: '#F59E0B' }}>{dashboard?.provider_telemetry?.osm_overpass?.timeouts ?? 0}</strong></div>
                <div>Rate Limits (429): <strong style={{ color: '#EF4444' }}>{dashboard?.provider_telemetry?.osm_overpass?.rate_limits_429 ?? 0}</strong></div>
                <div>Avg Latency: <strong>{dashboard?.provider_telemetry?.osm_overpass?.avg_latency_ms ?? 0} ms</strong></div>
              </div>
            </div>

            <div style={{ padding: '12px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '13px', fontWeight: '700', color: '#0F172A', marginBottom: '6px' }}>Website Enrichment Engine</div>
              <div style={{ fontSize: '12px', color: '#64748B', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>Domains Attempted: <strong>{dashboard?.provider_telemetry?.website_enrichment?.domains_attempted ?? 0}</strong></div>
                <div>Successes: <strong style={{ color: '#10B981' }}>{dashboard?.provider_telemetry?.website_enrichment?.success_total ?? 0}</strong></div>
                <div>HTTP / DNS / SSL Errors: <strong style={{ color: '#EF4444' }}>{(dashboard?.provider_telemetry?.website_enrichment?.http_errors ?? 0) + (dashboard?.provider_telemetry?.website_enrichment?.dns_errors ?? 0) + (dashboard?.provider_telemetry?.website_enrichment?.ssl_errors ?? 0)}</strong></div>
                <div>Pages Fetched: <strong>{dashboard?.provider_telemetry?.website_enrichment?.pages_fetched ?? 0}</strong></div>
                <div>Avg Latency: <strong>{dashboard?.provider_telemetry?.website_enrichment?.avg_latency_ms ?? 0} ms</strong></div>
              </div>
            </div>
          </div>
        </div>

        {/* Worker Node Health */}
        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <h2 style={{ fontSize: '16px', fontWeight: '700', color: '#0F172A', marginBottom: '16px' }}>Worker Nodes</h2>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #E2E8F0', textAlign: 'left', color: '#64748B' }}>
                  <th style={{ padding: '8px' }}>Worker ID</th>
                  <th style={{ padding: '8px' }}>Status</th>
                  <th style={{ padding: '8px' }}>Processed / Failed</th>
                  <th style={{ padding: '8px' }}>Last Heartbeat</th>
                </tr>
              </thead>
              <tbody>
                {dashboard?.workers?.workers && dashboard.workers.workers.length > 0 ? (
                  dashboard.workers.workers.map((w) => (
                    <tr key={w.worker_id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                      <td style={{ padding: '8px', fontWeight: '600', color: '#0F172A' }}>{w.worker_id}</td>
                      <td style={{ padding: '8px' }}>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: '700',
                            backgroundColor: w.status === 'HEALTHY' ? '#DCFCE7' : (w.status === 'BUSY' ? '#EFF6FF' : '#FEF3C7'),
                            color: w.status === 'HEALTHY' ? '#15803D' : (w.status === 'BUSY' ? '#1D4ED8' : '#B45309'),
                          }}
                        >
                          {w.status}
                        </span>
                      </td>
                      <td style={{ padding: '8px' }}>{w.jobs_processed} / {w.jobs_failed}</td>
                      <td style={{ padding: '8px', color: '#64748B' }}>{new Date(w.last_heartbeat).toLocaleTimeString()}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} style={{ padding: '16px', textAlign: 'center', color: '#94A3B8' }}>
                      No active workers registered yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 4. Recent Failure Logs */}
      <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
        <h2 style={{ fontSize: '16px', fontWeight: '700', color: '#0F172A', marginBottom: '16px' }}>Recent Failure Audit Log</h2>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #E2E8F0', textAlign: 'left', color: '#64748B' }}>
                <th style={{ padding: '8px' }}>Timestamp</th>
                <th style={{ padding: '8px' }}>Job ID</th>
                <th style={{ padding: '8px' }}>Pipeline Stage</th>
                <th style={{ padding: '8px' }}>Failure Category</th>
                <th style={{ padding: '8px' }}>Diagnostic Detail</th>
              </tr>
            </thead>
            <tbody>
              {dashboard?.recent_failures && dashboard.recent_failures.length > 0 ? (
                dashboard.recent_failures.map((f) => (
                  <tr key={f.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                    <td style={{ padding: '8px', color: '#64748B' }}>{new Date(f.started_at).toLocaleTimeString()}</td>
                    <td style={{ padding: '8px', fontFamily: 'monospace' }}>{f.job_id.slice(0, 8)}...</td>
                    <td style={{ padding: '8px', fontWeight: '600' }}>{f.stage}</td>
                    <td style={{ padding: '8px' }}>
                      <span style={{ backgroundColor: '#FEE2E2', color: '#991B1B', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '700' }}>
                        {f.error_category}
                      </span>
                    </td>
                    <td style={{ padding: '8px', color: '#475569' }}>{f.error_detail || 'None'}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} style={{ padding: '16px', textAlign: 'center', color: '#10B981' }}>
                    ✓ No recent failure events detected
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. Job Diagnostics Modal */}
      {selectedJobDiagnostics && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div style={{ backgroundColor: '#FFFFFF', padding: '24px', borderRadius: '12px', maxWidth: '600px', width: '100%', maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '18px', fontWeight: '700', margin: 0 }}>Job Diagnostics: {selectedJobDiagnostics.job_id.slice(0, 8)}...</h3>
              <button onClick={() => setSelectedJobDiagnostics(null)} style={{ border: 'none', background: 'none', fontSize: '18px', cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ fontSize: '13px', color: '#475569', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
              <div>Status: <strong>{selectedJobDiagnostics.status}</strong></div>
              <div>Leads Scraped: <strong>{selectedJobDiagnostics.leads_scraped}</strong> (Discovered: {selectedJobDiagnostics.discovered_count})</div>
              <div>Persisted in DB: <strong>{selectedJobDiagnostics.persisted_leads_in_db}</strong></div>
              {selectedJobDiagnostics.is_stuck && (
                <div style={{ color: '#DC2626' }}>Stuck Reason: <strong>{selectedJobDiagnostics.stuck_reason}</strong></div>
              )}
            </div>
            <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px' }}>Pipeline Stages Execution</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {selectedJobDiagnostics.stages.map((st) => (
                <div key={st.id} style={{ padding: '8px 12px', backgroundColor: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', fontSize: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <strong>{st.stage}</strong>
                    <span style={{ color: st.status === 'SUCCESS' ? '#10B981' : '#DC2626' }}>{st.status}</span>
                  </div>
                  <div style={{ color: '#64748B', marginTop: '4px' }}>Duration: {st.duration_ms}ms {st.error_category && `| Error: ${st.error_category}`}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
