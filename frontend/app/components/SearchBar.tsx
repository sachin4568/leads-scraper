'use client';

interface SearchBarProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

export function SearchBar({ value, onChange, placeholder = 'Search...' }: SearchBarProps) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      background: 'var(--bg-glass)',
      border: '1px solid var(--border-glass)',
      borderRadius: 'var(--radius-md)',
      padding: '0 14px',
      height: '40px',
      width: '100%',
      transition: 'border-color var(--transition)',
    }}
      onFocusCapture={e => (e.currentTarget.style.borderColor = 'var(--border-pink)')}
      onBlurCapture={e => (e.currentTarget.style.borderColor = 'var(--border-glass)')}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2">
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.35-4.35" />
      </svg>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          flex: 1,
          background: 'transparent',
          border: 'none',
          outline: 'none',
          color: 'var(--text-primary)',
          fontSize: '13px',
        }}
      />
      {value && (
        <button
          onClick={() => onChange('')}
          style={{
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            fontSize: '16px',
            lineHeight: 1,
          }}
        >×</button>
      )}
    </div>
  );
}
