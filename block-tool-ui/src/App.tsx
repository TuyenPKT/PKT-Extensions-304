import { useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import Titlebar from './components/Titlebar';
import LeftPanel from './components/LeftPanel';
import SearchPanel, { type Profile } from './components/SearchPanel';
import ProfilePanel from './components/ProfilePanel';
import RealTimeLog, { type LogEntry } from './components/RealTimeLog';
import CooldownBar from './components/CooldownBar';
import SettingsPanel, { DEFAULT_SETTINGS, type Settings } from './components/SettingsPanel';
import './index.css';

type Tab = 'search' | 'settings';

function now() {
  return new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function App() {
  const [tab, setTab]             = useState<Tab>('search');
  const [running, setRunning]     = useState(false);
  const [paused, setPaused]       = useState(false);
  const [keywords, setKeywords]   = useState<string[]>([]);
  const [kwFile, setKwFile]       = useState('');
  const [currentKi, setCurrentKi] = useState(0);
  const [totalKw, setTotalKw]     = useState(0);
  const [currentKw, setCurrentKw] = useState('');
  const [blocked, setBlocked]     = useState(0);
  const [skipped, setSkipped]     = useState(0);
  const [results, setResults]     = useState<Profile[]>([]);
  const [selected, setSelected]   = useState<Profile | null>(null);
  const [logs, setLogs]           = useState<LogEntry[]>([]);
  const [settings, setSettings]   = useState<Settings>(DEFAULT_SETTINGS);
  const [cooldown, setCooldown]   = useState<{ total: number; remaining: number; until: string } | null>(null);

  const pushLog = useCallback((entry: LogEntry) => {
    setLogs(prev => [...prev.slice(-300), entry]);
  }, []);

  // ── Tauri events ─────────────────────────────────────────────────────────
  useEffect(() => {
    const subs = [
      listen<LogEntry>('log-entry', e => pushLog(e.payload)),

      listen<{ current: number; total: number; blocked: number; skipped: number; current_kw: string }>(
        'progress', e => {
          setCurrentKi(e.payload.current);
          setTotalKw(e.payload.total);
          setBlocked(e.payload.blocked);
          setSkipped(e.payload.skipped);
          setCurrentKw(e.payload.current_kw);
          setRunning(true);
        }
      ),

      listen<{ filter: string; name: string; id: string; url: string; card: string; reason: string; signals: string[] }>(
        'profile-found', e => {
          const p = e.payload;
          const profile: Profile = {
            name: p.name,
            id: p.id || p.url,
            filter: p.filter as 'F1' | 'F2' | 'SKIP',
            score: p.filter === 'F1' ? 90 : p.filter === 'F2' ? 60 : 15,
            bio: p.card,
            signals: p.signals ?? [],
          };
          setResults(prev => [profile, ...prev].slice(0, 50));
          if (p.filter !== 'SKIP') setSelected(profile);
        }
      ),

      listen<{ total: number; remaining: number; until: string }>('cooldown-start', e => {
        setCooldown(e.payload);
        pushLog({ time: now(), filter: 'SKIP', name: `Nghỉ ${Math.floor(e.payload.total / 60)} phút`, reason: `đến ${e.payload.until}` });
      }),

      listen<{ remaining: number }>('cooldown-tick', e => {
        setCooldown(prev => prev ? { ...prev, remaining: e.payload.remaining } : null);
        if (e.payload.remaining <= 0) setCooldown(null);
      }),

      listen<{ blocked: number; skipped: number }>('session-ended', e => {
        setRunning(false);
        setPaused(false);
        setCooldown(null);
        setBlocked(e.payload.blocked);
        setSkipped(e.payload.skipped);
        pushLog({ time: now(), filter: 'SKIP', name: 'Session ended', reason: `Block: ${e.payload.blocked} | Skip: ${e.payload.skipped}` });
      }),
    ];
    return () => { subs.forEach(p => p.then(f => f())); };
  }, [pushLog]);

  // ── Auto-start khi app bật ───────────────────────────────────────────────
  useEffect(() => {
    handleStart();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Actions ───────────────────────────────────────────────────────────────
  async function handleLoadFile() {
    try {
      const path = settings.kwFile;
      const kws = await invoke<string[]>('load_keyword_file', { path });
      setKeywords(kws);
      setKwFile(path);
      setTotalKw(kws.length);
      setCurrentKi(0);
    } catch (e) { console.error(e); }
  }

  async function handleStart() {
    if (!kwFile) await handleLoadFile();
    try {
      await invoke('start_blocking', { kwFile: kwFile || settings.kwFile, mode: settings.mode });
      setRunning(true);
      setResults([]);
      setLogs([]);
      setCooldown(null);
      setTab('search');
    } catch (e: unknown) {
      pushLog({ time: now(), filter: 'SKIP', name: 'Error', reason: String(e) });
    }
  }

  async function handlePause() {
    if (paused) { await invoke('resume_session'); setPaused(false); }
    else { await invoke('pause_session'); setPaused(true); }
  }

  async function handleStop() {
    await invoke('stop_session');
    setRunning(false); setPaused(false); setCooldown(null);
  }

  function handleBlock() {
    if (!selected) return;
    setBlocked(b => b + 1);
    pushLog({ time: now(), filter: 'BLOCK', name: selected.name, reason: '' });
    setResults(r => r.filter(p => p.id !== selected.id));
    setSelected(null);
  }

  // ── Center content ────────────────────────────────────────────────────────
  const centerContent = tab === 'settings'
    ? <SettingsPanel settings={settings} onChange={setSettings} />
    : <>
        <SearchPanel currentKw={currentKw || '—'} results={results} selected={selected} onSelect={setSelected} />
        <ProfilePanel
          profile={selected}
          onBlock={handleBlock}
          onSkipF2={() => {
            setSkipped(s => s + 1);
            if (selected) {
              pushLog({ time: now(), filter: 'SKIP', name: selected.name, reason: 'Manual F2 skip' });
              setResults(r => r.filter(p => p.id !== selected.id));
              setSelected(null);
            }
          }}
          onSkipClean={() => {
            if (selected) { setResults(r => r.filter(p => p.id !== selected.id)); setSelected(null); }
          }}
        />
      </>;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Titlebar running={running} paused={paused} blocked={blocked} skipped={skipped}
        onPause={handlePause} onStop={handleStop} />

      {/* Tab bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 0,
        background: 'var(--surface)', borderBottom: '1px solid var(--border)',
        padding: '0 16px', flexShrink: 0,
      }}>
        {([
          { id: 'search', label: '🔍 Search & Filter' },
          { id: 'settings', label: '⚙ Settings' },
        ] as { id: Tab; label: string }[]).map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: '8px 16px', borderRadius: 0, fontWeight: 600, fontSize: 12,
              background: 'transparent',
              color: tab === t.id ? 'var(--accent)' : 'var(--text-muted)',
              borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Cooldown bar */}
      {cooldown && <CooldownBar total={cooldown.total} remaining={cooldown.remaining} until={cooldown.until} />}

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <LeftPanel kwFile={kwFile} keywords={keywords} currentKw={currentKw}
          currentKi={currentKi} blocked={blocked} skipped={skipped}
          onLoadFile={handleLoadFile} onStart={handleStart} running={running} />

        {centerContent}

        <RealTimeLog entries={logs} />
      </div>

      {/* Status bar */}
      <div style={{
        height: 26, padding: '0 16px', background: 'var(--surface)',
        borderTop: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 20, flexShrink: 0,
      }}>
        {[
          { label: 'Status', value: cooldown ? `Cooldown ${Math.floor(cooldown.remaining / 60)}p${cooldown.remaining % 60}s` : running ? (paused ? 'Paused' : 'Running') : 'Stopped', color: cooldown ? 'var(--yellow)' : running && !paused ? 'var(--green)' : 'var(--text-dim)' },
          { label: 'Block', value: String(blocked), color: 'var(--block-color)' },
          { label: 'Skip', value: String(skipped), color: 'var(--text-dim)' },
          { label: 'Keywords', value: totalKw ? `${currentKi}/${totalKw}` : '—', color: 'var(--text-dim)' },
        ].map(item => (
          <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>{item.label}:</span>
            <span style={{ color: item.color, fontSize: 11, fontWeight: 600 }}>{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
