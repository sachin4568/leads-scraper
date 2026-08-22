'use client';

import { Lead } from '../lib/data';

interface Props {
  lead: Lead | null;
  isOpen?: boolean;
  onClose: () => void;
}

export function LeadIntelligenceDrawer({ lead, isOpen = true, onClose }: Props) {
  if (!lead || isOpen === false) return null;
  return (
    <>
      {/* Overlay */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          zIndex: 200,
        }}
      />

      {/* Drawer */}
      <div style={{
        position: 'fixed',
        top: 0, right: 0, bottom: 0,
        width: 'min(460px, 90vw)',
        background: 'var(--bg-elevated)',
        borderLeft: '1px solid var(--border-glass)',
        zIndex: 201,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        boxShadow: '-24px 0 60px rgba(0,0,0,0.5)',
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div>
            <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
              {lead.businessName}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              {(lead as any).ownerName ? `${(lead as any).ownerName} · ` : ''}{lead.location}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: '30px', height: '30px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-muted)',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-glass-hover)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>

          {/* Contact Block */}
          <Section title="Contact Information">
            <Row label="Direct Phone" value={(lead as any).directPhone || lead.contactPhone || (lead as any).contact || 'N/A'} highlight />
            {((lead as any).email || lead.contactEmail) && <Row label="Email" value={(lead as any).email || lead.contactEmail} />}
            <Row label="Business" value={lead.businessName} />
            <Row label="Location" value={lead.location} />
            <Row label="Niche" value={(lead as any).niche || 'General'} />
            <Row label="Website" value={(lead as any).hasWebsite ? 'Yes' : (lead.websiteUrl ? 'Yes' : 'No')} />
            <Row label="Source" value={(lead.source || 'google_maps').replace('_', ' ')} />
          </Section>

          {/* Score Block */}
          <Section title="Lead Quality">
            <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
              <ScoreCard label="Genuineness" value={`${lead.genuineness}%`} color="var(--pink-primary)" />
              <ScoreCard label="Priority Score" value={`${lead.priorityScore}`} color={lead.priorityScore >= 80 ? 'var(--green)' : lead.priorityScore >= 60 ? 'var(--amber)' : 'var(--text-secondary)'} />
            </div>
            <StatusBadge status={lead.status} />
          </Section>

          {/* Pain Points */}
          {(lead as any).painPoints && (lead as any).painPoints.length > 0 && (
            <Section title="Pain Points">
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '7px' }}>
                {(lead as any).painPoints.map((p: any, i: number) => (
                  <li key={i} style={{
                    display: 'flex', alignItems: 'flex-start', gap: '8px',
                    fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5,
                  }}>
                    <span style={{
                      width: '5px', height: '5px', borderRadius: '50%',
                      background: 'var(--pink-primary)', flexShrink: 0, marginTop: '5px',
                    }} />
                    {p}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* Call Script */}
          {(lead as any).callScript && (
            <Section title="AI Call Script">
              <div style={{
                background: 'var(--bg-glass)',
                border: '1px solid var(--border-glass)',
                borderRadius: 'var(--radius-md)',
                padding: '14px',
                fontSize: '12px',
                color: 'var(--text-secondary)',
                lineHeight: 1.7,
                fontStyle: 'italic',
              }}>
                "{(lead as any).callScript}"
              </div>
            </Section>
          )}

          {/* Notes */}
          <Section title="Notes">
            <textarea
              placeholder="Add call notes here..."
              defaultValue={lead.notes || ''}
              style={{
                width: '100%',
                background: 'var(--bg-glass)',
                border: '1px solid var(--border-glass)',
                borderRadius: 'var(--radius-md)',
                padding: '12px',
                fontSize: '12px',
                color: 'var(--text-secondary)',
                resize: 'vertical',
                minHeight: '90px',
                lineHeight: 1.6,
                outline: 'none',
              }}
              onFocus={e => (e.currentTarget.style.borderColor = 'var(--border-pink)')}
              onBlur={e => (e.currentTarget.style.borderColor = 'var(--border-glass)')}
            />
          </Section>
        </div>

        {/* Footer actions */}
        <div style={{
          padding: '16px 24px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          gap: '10px',
          flexShrink: 0,
        }}>
          <button style={{
            flex: 1,
            background: 'var(--pink-primary)',
            color: '#fff',
            fontWeight: 600,
            fontSize: '13px',
            padding: '10px',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            cursor: 'pointer',
            transition: 'opacity var(--transition)',
          }}
            onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
            onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
          >
            Mark as Called
          </button>
          <button style={{
            flex: 1,
            background: 'var(--bg-glass)',
            border: '1px solid var(--border-glass)',
            color: 'var(--text-secondary)',
            fontWeight: 500,
            fontSize: '13px',
            padding: '10px',
            borderRadius: 'var(--radius-md)',
            cursor: 'pointer',
            transition: 'background var(--transition), color var(--transition)',
          }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'var(--bg-glass-hover)';
              e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'var(--bg-glass)';
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
          >
            Mark as Warm
          </button>
        </div>
      </div>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '22px' }}>
      <div style={{
        fontSize: '10px', fontWeight: 600, textTransform: 'uppercase',
        letterSpacing: '0.08em', color: 'var(--text-muted)',
        marginBottom: '10px',
      }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between',
      padding: '8px 0',
      borderBottom: '1px solid var(--border-subtle)',
      gap: '16px',
    }}>
      <span style={{ fontSize: '12px', color: 'var(--text-muted)', flexShrink: 0 }}>{label}</span>
      <span style={{
        fontSize: '12px',
        color: highlight ? 'var(--text-primary)' : 'var(--text-secondary)',
        fontWeight: highlight ? 600 : 400,
        textAlign: 'right',
      }}>{value}</span>
    </div>
  );
}

function ScoreCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{
      flex: 1,
      background: 'var(--bg-glass)',
      border: '1px solid var(--border-glass)',
      borderRadius: 'var(--radius-md)',
      padding: '12px',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: '20px', fontWeight: 700, color, marginBottom: '3px' }}>{value}</div>
      <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    new:       { bg: 'rgba(148,163,184,0.12)', text: '#94a3b8' },
    assigned:  { bg: 'rgba(59,130,246,0.12)',  text: '#60a5fa' },
    called:    { bg: 'rgba(245,158,11,0.12)',  text: '#fbbf24' },
    warm:      { bg: 'rgba(236,72,153,0.15)',  text: '#f472b6' },
    converted: { bg: 'rgba(34,197,94,0.12)',   text: '#4ade80' },
  };
  const c = colors[status] || colors.new;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Status</span>
      <span style={{
        fontSize: '11px', fontWeight: 600,
        padding: '3px 10px', borderRadius: 'var(--radius-pill)',
        background: c.bg, color: c.text, textTransform: 'capitalize',
      }}>{status}</span>
    </div>
  );
}

export default LeadIntelligenceDrawer;
