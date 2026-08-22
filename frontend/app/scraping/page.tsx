'use client';

import { useState } from 'react';
import { RAW_LEADS, MOCK_SHEETS } from '../lib/data';
import { ScrapeControls } from '../components/ScrapeControls';
import { RawLeadsWorkspaceModal } from '../components/RawLeadsWorkspaceModal';
import { ProgressCard } from '../components/ProgressCard';

export default function OperationsPage() {
  const [isSegregating, setIsSegregating] = useState(false);
  const [showRawLeads, setShowRawLeads] = useState(false);

  const handleSegregate = () => {
    setIsSegregating(true);
    setTimeout(() => setIsSegregating(false), 3000);
  };

  const totalRaw = RAW_LEADS.length;
  const qualified = RAW_LEADS.filter(l => l.status === 'qualified').length;
  const rejected = RAW_LEADS.filter(l => l.status === 'rejected').length;
  const pending = RAW_LEADS.filter(l => l.status === 'pending').length;

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>Operations</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
          Manage scraping runs, review raw leads, and control segregation
        </p>
      </div>

      {/* Scrape Controls Panel */}
      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-xl)',
        padding: '20px 24px',
        marginBottom: '16px',
      }}>
        <div style={{
          fontSize: '12px', fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '14px',
        }}>
          Scrape Controls
        </div>
        <ScrapeControls onSegregate={handleSegregate} isSegregating={isSegregating} />
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        {[
          { label: 'Total Raw', value: totalRaw, color: 'var(--text-primary)' },
          { label: 'Qualified', value: qualified, color: 'var(--green)' },
          { label: 'Pending', value: pending, color: 'var(--amber)' },
          { label: 'Rejected', value: rejected, color: 'var(--red)' },
        ].map(stat => (
          <div key={stat.label} style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '16px 20px',
          }}>
            <div style={{ fontSize: '24px', fontWeight: 700, color: stat.color, marginBottom: '4px' }}>{stat.value}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Progress + Raw Leads */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <ProgressCard />

        {/* Raw Leads panel */}
        <div style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-xl)',
          padding: '20px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}>
          <div style={{
            fontSize: '12px', fontWeight: 600, textTransform: 'uppercase',
            letterSpacing: '0.08em', color: 'var(--text-muted)',
          }}>
            Raw Lead Queue
          </div>

          {RAW_LEADS.slice(0, 5).map((lead, i) => (
            <div key={lead.id} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 0',
              borderBottom: i < 4 ? '1px solid var(--border-subtle)' : 'none',
            }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '2px' }}>
                  {lead.businessName}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  {lead.location} · {lead.source}
                </div>
              </div>
              <span style={{
                fontSize: '10px', fontWeight: 600,
                padding: '2px 8px', borderRadius: 'var(--radius-pill)',
                background: lead.status === 'qualified' ? 'rgba(34,197,94,0.1)' : lead.status === 'rejected' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
                color: lead.status === 'qualified' ? '#4ade80' : lead.status === 'rejected' ? '#f87171' : '#fbbf24',
                textTransform: 'capitalize',
              }}>
                {lead.status}
              </span>
            </div>
          ))}

          <button
            onClick={() => setShowRawLeads(true)}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '7px',
              padding: '10px',
              background: 'var(--bg-glass)',
              border: '1px solid var(--border-glass)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-secondary)',
              fontSize: '13px', fontWeight: 500,
              cursor: 'pointer',
              marginTop: '4px',
              transition: 'background var(--transition), color var(--transition)',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'var(--bg-glass-hover)'; (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'var(--bg-glass)'; (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)'; }}
          >
            View All {totalRaw} Raw Leads
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="9,18 15,12 9,6"/>
            </svg>
          </button>
        </div>
      </div>

      {showRawLeads && <RawLeadsWorkspaceModal onClose={() => setShowRawLeads(false)} />}
    </div>
  );
}
