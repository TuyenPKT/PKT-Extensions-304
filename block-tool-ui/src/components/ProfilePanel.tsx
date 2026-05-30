import type { Profile } from './SearchPanel';

interface ProfilePanelProps {
  profile: Profile | null;
  onBlock: () => void;
  onSkipF2: () => void;
  onSkipClean: () => void;
}

function SignalTag({ label, matched }: { label: string; matched: boolean }) {
  return (
    <span style={{
      padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
      background: matched ? 'rgba(108,99,255,0.2)' : 'var(--surface3)',
      color: matched ? 'var(--accent)' : 'var(--text-muted)',
      border: `1px solid ${matched ? 'var(--accent-dim)' : 'var(--border)'}`,
    }}>
      {label}
    </span>
  );
}

function Step({ n, label, done }: { n: number; label: string; done: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
      <div style={{
        width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
        background: done ? 'var(--block-color)' : 'var(--surface3)',
        color: done ? '#000' : 'var(--text-muted)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 700,
      }}>
        {done ? '✓' : n}
      </div>
      <span style={{ fontSize: 12, color: done ? 'var(--text)' : 'var(--text-dim)' }}>{label}</span>
    </div>
  );
}

export default function ProfilePanel({ profile, onBlock, onSkipF2, onSkipClean }: ProfilePanelProps) {
  if (!profile) {
    return (
      <div style={{
        flex: 1, background: 'var(--bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Select a profile to analyze</p>
      </div>
    );
  }

  const isBlock = profile.filter === 'F1' || profile.filter === 'F2';
  const confidence = profile.score;

  return (
    <div style={{
      flex: 1, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Profile header */}
      <div style={{
        padding: '16px 20px', background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <div style={{
          width: 56, height: 56, borderRadius: '50%',
          background: `hsl(${(profile.name.charCodeAt(0) * 37) % 360},40%,30%)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 22, fontWeight: 700, color: '#fff', flexShrink: 0,
        }}>
          {profile.name[0]}
        </div>
        <div>
          <h2 style={{ fontWeight: 700, fontSize: 16, color: 'var(--text)' }}>{profile.name}</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 2 }}>{profile.id}</p>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* Bio */}
        <div style={{ background: 'var(--surface)', borderRadius: 10, padding: '12px 14px', border: '1px solid var(--border)' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', marginBottom: 8 }}>Bio</p>
          <p style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6 }}>
            {profile.bio || profile.card || 'No bio available'}
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {/* Signal match */}
          <div style={{ background: 'var(--surface)', borderRadius: 10, padding: '12px 14px', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <p style={{ color: 'var(--red)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase' }}>
                Signal Match ({profile.filter})
              </p>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(profile.signals ?? []).map((sig, i) => (
                <SignalTag key={i} label={sig} matched={true} />
              ))}
              {(!profile.signals || profile.signals.length === 0) && (
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>No signals matched</span>
              )}
            </div>
            {profile.signals && profile.signals.length > 0 && (
              <>
                <div style={{ height: 1, background: 'var(--border)', margin: '10px 0' }} />
                {/* Confidence bar */}
                <div style={{ background: 'var(--surface3)', borderRadius: 3, height: 5, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', borderRadius: 3,
                    background: confidence > 70 ? 'var(--red)' : confidence > 40 ? 'var(--yellow)' : 'var(--green)',
                    width: `${confidence}%`,
                    transition: 'width 0.4s ease',
                  }} />
                </div>
                <p style={{ color: 'var(--text-dim)', fontSize: 10, marginTop: 4 }}>
                  Confidence: {confidence}%
                </p>
              </>
            )}
          </div>

          {/* Decision */}
          <div style={{ background: 'var(--surface)', borderRadius: 10, padding: '12px 14px', border: '1px solid var(--border)' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', marginBottom: 10 }}>
              Decision Engine
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 11, width: 60 }}>Category</span>
                <span style={{
                  fontSize: 11, fontWeight: 700,
                  color: isBlock ? 'var(--red)' : 'var(--text-dim)',
                }}>
                  {profile.filter} – {isBlock ? 'High Risk' : 'Low Risk'}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 11, width: 60 }}>Action</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: isBlock ? 'var(--block-color)' : 'var(--text-dim)' }}>
                  {isBlock ? 'BLOCK' : 'SKIP'}
                </span>
              </div>
            </div>

            <div style={{ height: 1, background: 'var(--border)', margin: '10px 0' }} />

            <p style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', marginBottom: 8 }}>
              Next Action
            </p>
            <Step n={1} label='Open profile menu' done={isBlock} />
            <Step n={2} label='Click "Chặn"' done={isBlock} />
            <Step n={3} label='Confirm block' done={isBlock} />
            <Step n={4} label='Verify result' done={false} />
          </div>
        </div>
      </div>

      {/* Action buttons */}
      <div style={{
        padding: '12px 20px', background: 'var(--surface)',
        borderTop: '1px solid var(--border)',
        display: 'flex', gap: 10,
      }}>
        <button
          onClick={onBlock}
          style={{
            flex: 1, padding: '10px', fontWeight: 700, fontSize: 13,
            background: 'var(--red)', color: '#fff',
          }}
        >
          🚫 Block Now
        </button>
        <button
          onClick={onSkipF2}
          style={{
            padding: '10px 14px', fontWeight: 600, fontSize: 12,
            background: 'var(--surface3)', color: 'var(--text-dim)',
            border: '1px solid var(--border)',
          }}
        >
          Skip (F2)
        </button>
        <button
          onClick={onSkipClean}
          style={{
            padding: '10px 14px', fontWeight: 600, fontSize: 12,
            background: 'var(--surface3)', color: 'var(--block-color)',
            border: '1px solid var(--border)',
          }}
        >
          ✓ Skip (Clean)
        </button>
      </div>
    </div>
  );
}
