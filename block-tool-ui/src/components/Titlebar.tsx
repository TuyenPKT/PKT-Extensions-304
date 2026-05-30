interface TitlebarProps {
  running: boolean;
  paused: boolean;
  blocked: number;
  skipped: number;
  onPause: () => void;
  onStop: () => void;
}

export default function Titlebar({ running, paused, blocked, skipped, onPause, onStop }: TitlebarProps) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      height: 44, padding: '0 16px',
      background: 'var(--surface)',
      borderBottom: '1px solid var(--border)',
      flexShrink: 0,
    }}>
      {/* Left */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)' }}>
          🛡 Block Tool
        </span>
        <span style={{
          fontSize: 10, fontWeight: 600, color: 'var(--text-dim)',
          background: 'var(--surface3)', padding: '2px 6px', borderRadius: 4,
        }}>v1.5</span>
      </div>

      {/* Center — status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className={`dot dot-${running && !paused ? 'green' : paused ? 'yellow' : 'red'}`} />
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          {running && !paused ? 'Running' : paused ? 'Paused' : 'Stopped'}
        </span>
        <span style={{ color: 'var(--border)', margin: '0 4px' }}>·</span>
        <span style={{ color: 'var(--block-color)', fontSize: 12 }}>⬥ {blocked} blocked</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>· {skipped} skipped</span>
      </div>

      {/* Right — controls */}
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={onPause}
          style={{
            background: paused ? 'var(--accent)' : 'var(--surface3)',
            color: paused ? '#fff' : 'var(--text-dim)',
            border: '1px solid var(--border)',
          }}
        >
          {paused ? '▶ Resume' : '⏸ Pause'}
        </button>
        <button
          onClick={onStop}
          style={{ background: '#3a1515', color: 'var(--red)', border: '1px solid #5a2020' }}
        >
          ⏹ Stop
        </button>
      </div>
    </div>
  );
}
