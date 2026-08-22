'use client';

import { RAW_LEADS, RawLead } from '../lib/data';

interface Props {
  onClose: () => void;
}

const statusColors: Record<string, { bg: string; text: string; dot: string }> = {
  pending:    { bg: 'rgba(148,163,184,0.1)', text: '#94a3b8', dot: '#94a3b8' },
  processing: { bg: 'rgba(245,158,11,0.1)',  text: '#fbbf24', dot: '#f59e0b' },
  qualified:  { bg: 'rgba(34,197,94,0.1)',   text: '#4ade80', dot: '#22c55e' },
  rejected:   { bg: 'rgba(239,68,68,0.1)',   text: '#f87171', dot: '#ef4444' },
};

export function RawLeadsWorkspaceModal({ onClose }: Props) {
  return (
    <>
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
        zIndex: 100,
      }} />
      <div style={{
        position: 'fixed',
        top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        width: 'min(92vw, 900px)',
        maxHeight: '80vh',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border-glass)',
        borderRadius: 'var(--radius-xl)',
        zIndex: 101,
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
        boxShadow: '0 32px 80px rgba(0,0,0,0.6)',
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>Raw Leads</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Unprocessed scrape output · {RAW_LEADS.length} records
            </div>
          </div>
          <button onClick={onClose} style={{
            width: '30px', height: '30px', display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 'var(--radius-md)', color: 'var(--text-muted)',
          }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-glass-hover)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* Table */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', position: 'sticky', top: 0, background: 'var(--bg-elevated)' }}>
                {['Business', 'Location', 'Niche', 'Phone', 'Website', 'Source', 'Scraped', 'Status'].map(col => (
                  <th key={col} style={{
                    padding: '10px 16px', fontSize: '11px', fontWeight: 600,
                    color: 'var(--text-muted)', textTransform: 'uppercase',
                    letterSpacing: '0.06em', textAlign: 'left', whiteSpace: 'nowrap',
                  }}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {RAW_LEADS.map((lead, i) => (
                <tr key={lead.id} style={{ borderBottom: i < RAW_LEADS.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-glass-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <td style={{ padding: '12px 16px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>{lead.businessName}</td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{lead.location}</td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>{lead.niche}</td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontSize: '12px' }}>{lead.phone || '—'}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{ color: lead.website ? 'var(--green)' : 'var(--text-muted)', fontSize: '12px', fontWeight: 500 }}>
                      {lead.website ? 'Yes' : 'No'}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: '12px' }}>{lead.source}</td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: '11px', whiteSpace: 'nowrap' }}>{lead.scrapedAt}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{
                        width: '6px', height: '6px', borderRadius: '50%',
                        background: statusColors[lead.status].dot, flexShrink: 0,
                      }} />
                      <span style={{
                        fontSize: '11px', fontWeight: 500,
                        padding: '2px 8px', borderRadius: 'var(--radius-pill)',
                        background: statusColors[lead.status].bg,
                        color: statusColors[lead.status].text,
                        textTransform: 'capitalize',
                      }}>
                        {lead.status}
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
