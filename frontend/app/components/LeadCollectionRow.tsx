'use client';

import { LeadSheet } from '../lib/data';

interface Props {
  sheet: LeadSheet;
  onClick: () => void;
}

const sourceColors: Record<string, string> = {
  google_maps: '#34a853',
  yelp:        '#d32323',
  linkedin:    '#0077b5',
};

const statusColors: Record<string, string> = {
  new:       'rgba(148,163,184,0.15)',
  assigned:  'rgba(59,130,246,0.15)',
  called:    'rgba(245,158,11,0.15)',
  warm:      'rgba(236,72,153,0.18)',
  converted: 'rgba(34,197,94,0.18)',
};

const statusText: Record<string, string> = {
  new:       '#94a3b8',
  assigned:  '#60a5fa',
  called:    '#fbbf24',
  warm:      '#f472b6',
  converted: '#4ade80',
};

export function LeadCollectionRow({ sheet, onClick }: Props) {
  const total = sheet.leads.length;
  const warm = sheet.leads.filter(l => l.status === 'warm' || l.status === 'converted').length;
  const avgScore = Math.round(sheet.leads.reduce((a, l) => a + l.priorityScore, 0) / total);
  const sources = [...new Set(sheet.leads.map(l => l.source))];

  return (
    <tr
      onClick={onClick}
      style={{ cursor: 'pointer' }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.background = 'var(--bg-glass-hover)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.background = 'transparent';
      }}
    >
      {/* Sheet Name */}
      <td style={{ padding: '14px 18px', verticalAlign: 'middle' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: 'var(--pink-primary)',
            flexShrink: 0,
          }} />
          <div>
            <div style={{ fontWeight: 500, color: 'var(--text-primary)', marginBottom: '2px' }}>
              {sheet.name}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              {(sheet as any).description || `${sheet.service} lead sheet`}
            </div>
          </div>
        </div>
      </td>

      {/* Lead Count */}
      <td style={{ padding: '14px 18px', verticalAlign: 'middle' }}>
        <span style={{
          background: 'var(--pink-dim)',
          color: 'var(--pink-bright)',
          fontSize: '12px',
          fontWeight: 600,
          padding: '3px 10px',
          borderRadius: 'var(--radius-pill)',
        }}>
          {total} leads
        </span>
      </td>

      {/* Sources */}
      <td style={{ padding: '14px 18px', verticalAlign: 'middle' }}>
        <div style={{ display: 'flex', gap: '5px' }}>
          {sources.map(s => (
            <span key={s} style={{
              fontSize: '10px',
              fontWeight: 600,
              color: sourceColors[s] || '#94a3b8',
              background: `${sourceColors[s]}18` || 'transparent',
              padding: '2px 7px',
              borderRadius: 'var(--radius-pill)',
              border: `1px solid ${sourceColors[s]}30`,
              textTransform: 'capitalize',
            }}>
              {s.replace('_', ' ')}
            </span>
          ))}
        </div>
      </td>

      {/* Warm Rate */}
      <td style={{ padding: '14px 18px', verticalAlign: 'middle' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '60px',
            height: '4px',
            borderRadius: '4px',
            background: 'var(--bg-glass)',
            overflow: 'hidden',
          }}>
            <div style={{
              width: `${(warm / total) * 100}%`,
              height: '100%',
              background: 'var(--pink-primary)',
              borderRadius: '4px',
            }} />
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            {warm}/{total}
          </span>
        </div>
      </td>

      {/* Avg Score */}
      <td style={{ padding: '14px 18px', verticalAlign: 'middle' }}>
        <span style={{
          fontSize: '13px',
          fontWeight: 600,
          color: avgScore >= 80 ? 'var(--green)' : avgScore >= 60 ? 'var(--amber)' : 'var(--text-secondary)',
        }}>
          {avgScore}
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>/100</span>
      </td>

      {/* Caller */}
      <td style={{ padding: '14px 18px', verticalAlign: 'middle' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
          {sheet.callerName || '—'}
        </span>
      </td>

      {/* Date */}
      <td style={{ padding: '14px 18px', verticalAlign: 'middle' }}>
        <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
          {new Date(sheet.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        </span>
      </td>

      {/* Arrow */}
      <td style={{ padding: '14px 18px', verticalAlign: 'middle' }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2">
          <polyline points="9,18 15,12 9,6" />
        </svg>
      </td>
    </tr>
  );
}

export default LeadCollectionRow;
