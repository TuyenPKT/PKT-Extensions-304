import type { } from 'react';

export interface Settings {
  mode: 'pages' | 'people';
  delay: number;       // giây giữa các profile
  batchMin: number;
  batchMax: number;
  kwFile: string;
  autoBlock: boolean;
  headless: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  mode: 'pages',
  delay: 3,
  batchMin: 15,
  batchMax: 20,
  kwFile: '/Users/tuyennguyen/GitHub/PKT Extensions 304/Anti.txt',
  autoBlock: true,
  headless: false,
};

interface SettingsPanelProps {
  settings: Settings;
  onChange: (s: Settings) => void;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--surface3)' }}>
      <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>{label}</span>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>{children}</div>
    </div>
  );
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div
      onClick={() => onChange(!value)}
      style={{
        width: 36, height: 20, borderRadius: 10, cursor: 'pointer',
        background: value ? 'var(--accent)' : 'var(--surface3)',
        position: 'relative', transition: 'background 0.2s',
        border: '1px solid var(--border)',
      }}
    >
      <div style={{
        width: 14, height: 14, borderRadius: '50%',
        background: '#fff',
        position: 'absolute',
        top: 2, left: value ? 18 : 2,
        transition: 'left 0.2s',
      }} />
    </div>
  );
}

function NumInput({ value, onChange, min, max }: { value: number; onChange: (v: number) => void; min: number; max: number }) {
  return (
    <input
      type="number" min={min} max={max} value={value}
      onChange={e => onChange(Number(e.target.value))}
      style={{ width: 60, textAlign: 'right', padding: '4px 8px', fontSize: 12 }}
    />
  );
}

export default function SettingsPanel({ settings, onChange }: SettingsPanelProps) {
  const set = (patch: Partial<Settings>) => onChange({ ...settings, ...patch });

  return (
    <div style={{
      flex: 1, background: 'var(--bg)',
      overflowY: 'auto', padding: '20px 24px',
    }}>
      <h3 style={{ color: 'var(--text)', fontSize: 14, fontWeight: 700, marginBottom: 20 }}>
        ⚙ Cài đặt
      </h3>

      {/* File */}
      <section style={{ marginBottom: 24 }}>
        <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', marginBottom: 8 }}>
          Keyword File
        </p>
        <input
          value={settings.kwFile}
          onChange={e => set({ kwFile: e.target.value })}
          style={{ fontSize: 11, color: 'var(--text-dim)' }}
        />
      </section>

      {/* Mode */}
      <section style={{ marginBottom: 24 }}>
        <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', marginBottom: 8 }}>
          Search Mode
        </p>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['pages', 'people'] as const).map(m => (
            <button
              key={m}
              onClick={() => set({ mode: m })}
              style={{
                padding: '6px 14px', fontWeight: 600,
                background: settings.mode === m ? 'var(--accent)' : 'var(--surface3)',
                color: settings.mode === m ? '#fff' : 'var(--text-dim)',
                border: settings.mode === m ? 'none' : '1px solid var(--border)',
              }}
            >
              {m === 'pages' ? '📄 Pages' : '👤 People'}
            </button>
          ))}
        </div>
      </section>

      {/* Timing */}
      <section style={{ marginBottom: 24, background: 'var(--surface)', borderRadius: 10, padding: '4px 14px', border: '1px solid var(--border)' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', padding: '10px 0 6px' }}>
          Timing
        </p>
        <Row label="Delay giữa profiles (giây)">
          <NumInput value={settings.delay} onChange={v => set({ delay: v })} min={1} max={30} />
        </Row>
        <Row label="Batch size tối thiểu">
          <NumInput value={settings.batchMin} onChange={v => set({ batchMin: v })} min={5} max={50} />
        </Row>
        <Row label="Batch size tối đa">
          <NumInput value={settings.batchMax} onChange={v => set({ batchMax: v })} min={10} max={100} />
        </Row>
      </section>

      {/* Options */}
      <section style={{ background: 'var(--surface)', borderRadius: 10, padding: '4px 14px', border: '1px solid var(--border)' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', padding: '10px 0 6px' }}>
          Options
        </p>
        <Row label="Auto block (F1/F2 tự động block)">
          <Toggle value={settings.autoBlock} onChange={v => set({ autoBlock: v })} />
        </Row>
        <Row label="Headless mode (ẩn browser)">
          <Toggle value={settings.headless} onChange={v => set({ headless: v })} />
        </Row>
      </section>
    </div>
  );
}
