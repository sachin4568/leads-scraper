'use client';

import { useState } from 'react';

interface Props {
  onSegregate: () => void;
  isSegregating: boolean;
}

export function ScrapeControls({ onSegregate, isSegregating }: Props) {
  const [niche, setNiche] = useState('');
  const [city, setCity] = useState('');

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      flexWrap: 'wrap',
    }}>
      {/* Niche input */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        background: 'var(--bg-glass)',
        border: '1px solid var(--border-glass)',
        borderRadius: 'var(--radius-md)',
        padding: '0 14px', height: '38px',
        flex: '1', minWidth: '140px',
      }}>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        <input
          type="text"
          placeholder="Niche (e.g. Restaurants)"
          value={niche}
          onChange={e => setNiche(e.target.value)}
          style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: 'var(--text-primary)', fontSize: '13px' }}
        />
      </div>

      {/* City input */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        background: 'var(--bg-glass)',
        border: '1px solid var(--border-glass)',
        borderRadius: 'var(--radius-md)',
        padding: '0 14px', height: '38px',
        flex: '1', minWidth: '140px',
      }}>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
          <circle cx="12" cy="10" r="3"/>
        </svg>
        <input
          type="text"
          placeholder="City / Region"
          value={city}
          onChange={e => setCity(e.target.value)}
          style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: 'var(--text-primary)', fontSize: '13px' }}
        />
      </div>

      {/* Scrape button */}
      <button style={{
        display: 'flex', alignItems: 'center', gap: '7px',
        padding: '0 18px', height: '38px',
        background: 'var(--bg-glass)',
        border: '1px solid var(--border-glass)',
        borderRadius: 'var(--radius-md)',
        color: 'var(--text-secondary)',
        fontSize: '13px', fontWeight: 500,
        cursor: 'pointer',
        whiteSpace: 'nowrap',
        transition: 'background var(--transition), color var(--transition)',
      }}
        onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'var(--bg-glass-hover)'; (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)'; }}
        onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'var(--bg-glass)'; (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)'; }}
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="16"/>
          <line x1="8" y1="12" x2="16" y2="12"/>
        </svg>
        Start Scrape
      </button>

      {/* Segregate button — pink accent */}
      <button
        onClick={onSegregate}
        disabled={isSegregating}
        style={{
          display: 'flex', alignItems: 'center', gap: '7px',
          padding: '0 18px', height: '38px',
          background: isSegregating ? 'rgba(236,72,153,0.3)' : 'var(--pink-primary)',
          border: '1px solid transparent',
          borderRadius: 'var(--radius-md)',
          color: '#fff',
          fontSize: '13px', fontWeight: 600,
          cursor: isSegregating ? 'not-allowed' : 'pointer',
          whiteSpace: 'nowrap',
          transition: 'opacity var(--transition)',
          opacity: isSegregating ? 0.7 : 1,
        }}
        onMouseEnter={e => { if (!isSegregating) (e.currentTarget as HTMLElement).style.opacity = '0.85'; }}
        onMouseLeave={e => { if (!isSegregating) (e.currentTarget as HTMLElement).style.opacity = '1'; }}
      >
        {isSegregating ? (
          <>
            <span style={{
              width: '12px', height: '12px',
              border: '2px solid rgba(255,255,255,0.4)',
              borderTopColor: '#fff',
              borderRadius: '50%',
              display: 'inline-block',
              animation: 'spin 0.7s linear infinite',
            }} />
            Segregating...
          </>
        ) : (
          <>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M16 16v2a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
              <rect x="8" y="2" width="14" height="14" rx="2"/>
              <line x1="11" y1="8" x2="19" y2="8"/>
              <line x1="11" y1="12" x2="19" y2="12"/>
              <line x1="11" y1="16" x2="15" y2="16"/>
            </svg>
            Segregate
          </>
        )}
      </button>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
