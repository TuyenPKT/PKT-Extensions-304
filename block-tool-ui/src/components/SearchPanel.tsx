export interface Profile {
  name: string;
  id: string;
  filter: 'F1' | 'F2' | 'SKIP';
  score: number;
  bio?: string;
  signals?: string[];
  card?: string;
}

interface SearchPanelProps {
  currentKw: string;
  results: Profile[];
  selected: Profile | null;
  onSelect: (p: Profile) => void;
}

function FilterBadge({ filter, score }: { filter: string; score: number }) {
  const colors: Record<string, string> = {
    F1: 'var(--f1)', F2: 'var(--f2)', SKIP: 'var(--surface3)'
  };
  const textColors: Record<string, string> = {
    F1: '#fff', F2: '#000', SKIP: 'var(--text-dim)'
  };
  return (
    <div style={{ textAlign: 'right' }}>
      <span className="badge" style={{ background: colors[filter], color: textColors[filter] }}>
        {filter}
      </span>
      <p style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
        Score: {score}
      </p>
    </div>
  );
}

export default function SearchPanel({ currentKw, results, selected, onSelect }: SearchPanelProps) {
  return (
    <div style={{
      width: 260, flexShrink: 0,
      background: 'var(--surface)',
      borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase' }}>
            Search Results ({results.length})
          </p>
          <span style={{ fontSize: 16, cursor: 'pointer', color: 'var(--text-dim)' }}>↻</span>
        </div>
        <div style={{
          background: 'var(--surface2)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '6px 10px', fontSize: 12,
          color: currentKw ? 'var(--text)' : 'var(--text-muted)',
        }}>
          {currentKw || 'Waiting…'}
        </div>
      </div>

      {/* Results list */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {results.map((p, i) => (
          <div
            key={i}
            onClick={() => onSelect(p)}
            style={{
              padding: '10px 14px',
              borderBottom: '1px solid var(--surface3)',
              display: 'flex', alignItems: 'center', gap: 10,
              cursor: 'pointer',
              background: selected?.id === p.id ? 'var(--surface2)' : 'transparent',
              transition: 'background 0.1s',
            }}
          >
            {/* Avatar placeholder */}
            <div style={{
              width: 36, height: 36, borderRadius: '50%',
              background: `hsl(${(p.name.charCodeAt(0) * 37) % 360},40%,30%)`,
              flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 14, fontWeight: 700, color: '#fff',
            }}>
              {p.name[0]}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{
                fontWeight: 600, fontSize: 12, color: 'var(--text)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {p.name}
              </p>
              <p style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{p.id}</p>
            </div>
            <FilterBadge filter={p.filter} score={p.score} />
          </div>
        ))}
        {results.length === 0 && (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
            No results
          </div>
        )}
      </div>
    </div>
  );
}
