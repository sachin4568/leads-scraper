'use client';
import { useState, useRef, useEffect, ReactNode } from 'react';

interface MenuItem {
  label: string;
  icon: ReactNode;
  danger?: boolean;
  onClick: () => void;
}

export function ThreeDotMenu({ items }: { items: MenuItem[] }) {
  const [open, setOpen] = useState(false);
  const [openUpward, setOpenUpward] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!open && ref.current) {
      const rect = ref.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      setOpenUpward(spaceBelow < 190);
    }
    setOpen(prev => !prev);
  };

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={handleToggle}
        style={{
          width: '28px', height: '28px', display: 'flex', alignItems: 'center',
          justifyContent: 'center', borderRadius: 'var(--r-md)', color: 'var(--text-3)',
          cursor: 'pointer', transition: 'background var(--ease)',
        }}
        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-hover)'; }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
          <circle cx="12" cy="5" r="1.2" fill="currentColor"/>
          <circle cx="12" cy="12" r="1.2" fill="currentColor"/>
          <circle cx="12" cy="19" r="1.2" fill="currentColor"/>
        </svg>
      </button>

      {open && (
        <div style={{
          position: 'absolute', right: 0,
          ...(openUpward ? { bottom: 'calc(100% + 4px)' } : { top: 'calc(100% + 4px)' }),
          width: '192px', background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)',
          boxShadow: '0 12px 40px rgba(0,0,0,.25)', zIndex: 999,
          overflow: 'hidden', padding: '4px',
        }}>
          {items.map((item, i) => (
            <button
              key={i}
              onClick={e => { 
                e.stopPropagation(); 
                item.onClick(); 
                setOpen(false); 
              }}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '9px',
                padding: '8px 10px', borderRadius: 'var(--r-md)',
                color: item.danger ? 'var(--red)' : 'var(--text-2)',
                fontSize: '12px', fontWeight: 500,
                transition: 'background var(--ease)', textAlign: 'left', cursor: 'pointer',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.background =
                  item.danger ? 'rgba(239,68,68,.08)' : 'var(--bg-hover)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
              }}
            >
              <span style={{ color: item.danger ? 'var(--red)' : 'var(--text-3)', display: 'flex', flexShrink: 0 }}>
                {item.icon}
              </span>
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
