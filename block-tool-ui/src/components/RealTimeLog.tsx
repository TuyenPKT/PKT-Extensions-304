import { useEffect, useRef, useState } from 'react';

export interface LogEntry {
  time: string;
  filter: 'F1' | 'F2' | 'SKIP' | 'BLOCK';
  name: string;
  reason: string;
}

interface RealTimeLogProps {
  entries: LogEntry[];
}

type FilterTab = 'All' | 'F1' | 'F2' | 'SKIP' | 'BLOCK';

function Badge({ filter }: { filter: string }) {
  const cls = {
    F1: 'badge-f1', F2: 'badge-f2', SKIP: 'badge-skip', BLOCK: 'badge-block'
  }[filter] ?? 'badge-skip';
  return <span className={`badge ${cls}`}>{filter}</span>;
}

export default function RealTimeLog({ entries }: RealTimeLogProps) {
  const [tab, setTab] = useState<FilterTab>('All');
  const bottomRef = useRef<HTMLDivElement>(null);

  const filtered = tab === 'All' ? entries : entries.filter(e => e.filter === tab);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [filtered.length]);

  const tabs: FilterTab[] = ['All', 'F1', 'F2', 'SKIP', 'BLOCK'];
  const tabColor: Record<string, string> = {
    F1: 'var(--f1)', F2: 'var(--f2)', SKIP: 'var(--text-muted)', BLOCK: 'var(--block-color)', All: 'var(--text)'
  };

  return (
    <div style={{
      width: 300, flexShrink: 0,
      background: 'var(--surface)',
      borderLeft: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ padding: '12px 14px 0', borderBottom: '1px solid var(--border)' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', marginBottom: 10 }}>
          Real-Time Log
        </p>
        <div style={{ display: 'flex', gap: 4, marginBottom: 12 }}>
          {tabs.map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: '3px 8px', fontSize: 10, fontWeight: 700,
                background: tab === t ? (t === 'All' ? 'var(--surface3)' : tabColor[t]) : 'transparent',
                color: tab === t ? (t === 'F2' ? '#000' : t === 'BLOCK' ? '#000' : '#fff') : 'var(--text-muted)',
                border: tab === t ? 'none' : '1px solid var(--border)',
              }}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Entries */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {filtered.map((entry, i) => (
          <div
            key={i}
            style={{
              padding: '6px 14px',
              borderBottom: '1px solid var(--surface3)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
            }}
          >
            <span style={{ color: 'var(--text-muted)', fontSize: 10, minWidth: 48, paddingTop: 1, fontFamily: 'monospace' }}>
              {entry.time}
            </span>
            <Badge filter={entry.filter} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{
                fontSize: 12, fontWeight: 600, color: 'var(--text)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {entry.name}
              </p>
              {entry.filter === 'SKIP' && (
                <p style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>{entry.reason}</p>
              )}
            </div>
            {(entry.filter === 'F1' || entry.filter === 'F2') && (
              <span style={{ color: 'var(--block-color)', fontSize: 11, fontWeight: 600 }}>→ BLOCK</span>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
