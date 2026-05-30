interface LeftPanelProps {
  kwFile: string;
  keywords: string[];
  currentKw: string;
  currentKi: number;
  blocked: number;
  skipped: number;
  onLoadFile: () => void;
  onStart: () => void;
  running: boolean;
}

function ProgressRing({ pct }: { pct: number }) {
  const r = 44, cx = 54, cy = 54;
  const circ = 2 * Math.PI * r;
  const dash = circ * pct;
  return (
    <svg width={108} height={108} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--surface3)" strokeWidth={7} />
      <circle
        cx={cx} cy={cy} r={r} fill="none"
        stroke="var(--accent)" strokeWidth={7}
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        style={{ transition: 'stroke-dasharray 0.4s ease' }}
      />
      <text
        x={cx} y={cy + 1}
        textAnchor="middle" dominantBaseline="middle"
        fill="var(--text)" fontSize={16} fontWeight={700}
        style={{ transform: 'rotate(90deg)', transformOrigin: `${cx}px ${cy}px` }}
      >
        {Math.round(pct * 100)}%
      </text>
      <text
        x={cx} y={cy + 18}
        textAnchor="middle" dominantBaseline="middle"
        fill="var(--text-dim)" fontSize={9}
        style={{ transform: 'rotate(90deg)', transformOrigin: `${cx}px ${cy}px` }}
      >
        progress
      </text>
    </svg>
  );
}

export default function LeftPanel({
  kwFile, keywords, currentKw, currentKi, blocked, skipped, onLoadFile, onStart, running
}: LeftPanelProps) {
  const total = keywords.length;
  const pct = total > 0 ? currentKi / total : 0;

  return (
    <div style={{
      width: 220, flexShrink: 0,
      background: 'var(--surface)',
      borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* File source */}
      <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid var(--border)' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', marginBottom: 8 }}>
          Keyword Source
        </p>
        <div style={{
          background: 'var(--surface2)', border: '1px solid var(--border)',
          borderRadius: 8, padding: '8px 10px', marginBottom: 8,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 600, fontSize: 12 }}>
              {kwFile ? kwFile.split('/').pop() : 'No file'}
            </span>
            {kwFile && (
              <span style={{ background: 'var(--accent)', color: '#fff', fontSize: 9, padding: '1px 5px', borderRadius: 3 }}>
                Loaded
              </span>
            )}
          </div>
          <p style={{ color: 'var(--text-dim)', fontSize: 10, marginTop: 3 }}>
            {total.toLocaleString()} keywords
          </p>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={onLoadFile}
            style={{ flex: 1, background: 'var(--surface3)', color: 'var(--text-dim)', border: '1px solid var(--border)' }}
          >
            ↺ Reload
          </button>
          <button
            onClick={onStart}
            disabled={running}
            style={{
              flex: 1, fontWeight: 700,
              background: running ? 'var(--surface3)' : 'var(--accent)',
              color: running ? 'var(--text-muted)' : '#fff',
              border: 'none', opacity: running ? 0.5 : 1,
            }}
          >
            {running ? '▶ Running' : '▶ Start'}
          </button>
        </div>
      </div>

      {/* Progress ring */}
      <div style={{ padding: '14px', borderBottom: '1px solid var(--border)', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', marginBottom: 10 }}>
          Progress
        </p>
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <ProgressRing pct={pct} />
        </div>
        <p style={{ color: 'var(--text-dim)', fontSize: 11, marginTop: 8 }}>
          {currentKi.toLocaleString()} / {total.toLocaleString()}
        </p>
        <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: 8 }}>
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: 'var(--block-color)', fontWeight: 700, fontSize: 14 }}>{blocked}</p>
            <p style={{ color: 'var(--text-muted)', fontSize: 10 }}>Blocked</p>
          </div>
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: 'var(--text-dim)', fontWeight: 700, fontSize: 14 }}>{skipped}</p>
            <p style={{ color: 'var(--text-muted)', fontSize: 10 }}>Skipped</p>
          </div>
        </div>
      </div>

      {/* Keyword list */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: '10px 14px 0' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', marginBottom: 8 }}>
          Keywords ({total.toLocaleString()})
        </p>
        <div style={{ overflowY: 'auto', flex: 1 }}>
          {keywords.map((kw, i) => (
            <div
              key={i}
              style={{
                padding: '5px 8px',
                borderRadius: 5,
                marginBottom: 2,
                background: kw === currentKw ? 'var(--accent-dim)' : 'transparent',
                color: kw === currentKw ? 'var(--text)' : 'var(--text-dim)',
                fontSize: 12,
                cursor: 'default',
                transition: 'background 0.15s',
              }}
            >
              {kw}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
