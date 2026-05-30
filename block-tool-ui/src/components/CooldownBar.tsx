interface CooldownBarProps {
  total: number;      // giây
  remaining: number;  // giây
  until: string;      // "HH:MM:SS"
}

export default function CooldownBar({ total, remaining, until }: CooldownBarProps) {
  if (remaining <= 0) return null;

  const pct = total > 0 ? (remaining / total) * 100 : 0;
  const m = Math.floor(remaining / 60);
  const s = remaining % 60;

  return (
    <div style={{
      padding: '8px 16px',
      background: '#1a1510',
      borderBottom: '1px solid #3a2a10',
      display: 'flex', alignItems: 'center', gap: 12,
      flexShrink: 0,
    }}>
      <span style={{ fontSize: 14 }}>⏱</span>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ color: '#f59e0b', fontSize: 11, fontWeight: 600 }}>
            Nghỉ batch — còn {m}p{String(s).padStart(2, '0')}s
          </span>
          <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>đến {until}</span>
        </div>
        <div style={{ background: 'var(--surface3)', borderRadius: 3, height: 4, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 3,
            background: 'var(--yellow)',
            width: `${pct}%`,
            transition: 'width 1s linear',
          }} />
        </div>
      </div>
    </div>
  );
}
