'use client';

interface PipelineStage {
  label: string;
  count: number;
  total: number;
  color: string;
}

const stages: PipelineStage[] = [
  { label: 'Scraped',    count: 8,  total: 8,  color: '#60a5fa' },
  { label: 'Filtered',   count: 6,  total: 8,  color: '#a78bfa' },
  { label: 'Enriched',   count: 5,  total: 6,  color: '#f472b6' },
  { label: 'Scored',     count: 4,  total: 5,  color: '#fb923c' },
  { label: 'Qualified',  count: 3,  total: 4,  color: '#4ade80' },
];

export function ProgressCard() {
  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--radius-xl)',
      padding: '20px 24px',
    }}>
      <div style={{
        fontSize: '12px', fontWeight: 600, textTransform: 'uppercase',
        letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '18px',
      }}>
        Pipeline Progress
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {stages.map(stage => (
          <div key={stage.label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{stage.label}</span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                <span style={{ color: stage.color, fontWeight: 600 }}>{stage.count}</span>/{stage.total}
              </span>
            </div>
            <div style={{
              height: '4px', borderRadius: '4px',
              background: 'var(--bg-glass)', overflow: 'hidden',
            }}>
              <div style={{
                width: `${(stage.count / stage.total) * 100}%`,
                height: '100%',
                background: stage.color,
                borderRadius: '4px',
                transition: 'width 0.5s ease',
              }} />
            </div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: '18px',
        padding: '12px',
        background: 'var(--bg-glass)',
        border: '1px solid var(--border-glass)',
        borderRadius: 'var(--radius-md)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Qualification rate</span>
        <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--green)' }}>37.5%</span>
      </div>
    </div>
  );
}
