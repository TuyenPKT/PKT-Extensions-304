use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use serde_json::Value;
use tauri::{AppHandle, Emitter};

use crate::commands::{LogEntry, ProgressPayload, SharedState};

// ── Session ────────────────────────────────────────────────────────────────

pub struct Session {
    pub child: Child,
}

impl Drop for Session {
    fn drop(&mut self) {
        let _ = self.child.kill();
    }
}

pub type SharedSession = Arc<Mutex<Option<Session>>>;

// ── Helpers ────────────────────────────────────────────────────────────────

fn find_python() -> &'static str {
    if Command::new("python3").arg("--version")
        .output().map(|o| o.status.success()).unwrap_or(false)
    { "python3" } else { "python" }
}

fn dirs_home() -> PathBuf {
    std::env::var("HOME").map(PathBuf::from).unwrap_or_else(|_| PathBuf::from("/tmp"))
}

fn find_block_tool_script() -> Result<PathBuf, String> {
    let candidates = [
        dirs_home().join("GitHub/PKT Extensions 304/facebook-block-tool/block_tool.py"),
        PathBuf::from("../facebook-block-tool/block_tool.py"),
        PathBuf::from("facebook-block-tool/block_tool.py"),
    ];
    for p in &candidates {
        if p.exists() { return Ok(p.clone()); }
    }
    Err("Không tìm thấy block_tool.py".to_string())
}

fn chrono_time() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
    format!("{:02}:{:02}:{:02}", (secs % 86400) / 3600, (secs % 3600) / 60, secs % 60)
}

// ── Main: spawn Python + stream stdout ────────────────────────────────────

pub fn spawn_and_stream(
    app: AppHandle,
    kw_file: PathBuf,
    mode: String,
    state: SharedState,
    session_holder: SharedSession,
) -> Result<(), String> {
    let script = find_block_tool_script()?;
    let python = find_python();

    let mut child = Command::new(python)
        .arg(&script)
        .arg(kw_file.to_str().unwrap_or(""))
        .arg(&mode)
        .arg("--json")
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|e| format!("Không thể spawn Python: {e}"))?;

    let stdout = child.stdout.take().ok_or("Không lấy được stdout")?;

    {
        let mut s = state.lock().unwrap();
        s.running = true;
        s.paused = false;
        s.kw_file = kw_file.to_string_lossy().into_owned();
    }

    {
        let mut lock = session_holder.lock().unwrap();
        *lock = Some(Session { child });
    }

    let app2 = app.clone();
    let state2 = state.clone();
    let session2 = session_holder.clone();

    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            let Ok(line) = line else { break };
            if line.trim().is_empty() { continue; }

            if let Ok(val) = serde_json::from_str::<Value>(&line) {
                handle_json_line(&app2, &state2, val);
            } else {
                let _ = app2.emit("raw-log", &line);
            }
        }

        // Process exited
        let (blocked, skipped) = {
            let mut s = state2.lock().unwrap();
            s.running = false;
            (s.blocked, s.skipped)
        };
        let _ = app2.emit("session-ended", serde_json::json!({
            "blocked": blocked, "skipped": skipped,
        }));
        *session2.lock().unwrap() = None;
    });

    Ok(())
}

// ── Parse JSON events từ Python ────────────────────────────────────────────

fn handle_json_line(app: &AppHandle, state: &SharedState, val: Value) {
    let event = val["event"].as_str().unwrap_or("");

    match event {
        "profile" => {
            let filter = val["filter"].as_str().unwrap_or("SKIP");
            let name   = val["name"].as_str().unwrap_or("").to_string();
            let reason = val["reason"].as_str().unwrap_or("").to_string();

            let _ = app.emit("log-entry", LogEntry {
                time: chrono_time(),
                filter: filter.to_string(),
                name,
                reason,
            });
            let _ = app.emit("profile-found", &val);
        }

        "blocked" => {
            let blocked = val["blocked"].as_u64().unwrap_or(0) as u32;
            let skipped = val["skipped"].as_u64().unwrap_or(0) as u32;
            {
                let mut s = state.lock().unwrap();
                s.blocked = blocked;
                s.skipped = skipped;
            }
            let _ = app.emit("log-entry", LogEntry {
                time: chrono_time(),
                filter: "BLOCK".into(),
                name: val["url"].as_str().unwrap_or("").to_string(),
                reason: String::new(),
            });
        }

        "block_skip" => {
            let skipped = val["skipped"].as_u64().unwrap_or(0) as u32;
            state.lock().unwrap().skipped = skipped;
        }

        "progress" => {
            let ki         = val["ki"].as_u64().unwrap_or(0) as usize;
            let total      = val["total"].as_u64().unwrap_or(0) as usize;
            let current_kw = val["current_kw"].as_str().unwrap_or("").to_string();
            let blocked    = val["blocked"].as_u64().unwrap_or(0) as u32;
            let skipped    = val["skipped"].as_u64().unwrap_or(0) as u32;

            {
                let mut s = state.lock().unwrap();
                s.current_ki = ki;
                s.current_kw = current_kw.clone();
                s.blocked    = blocked;
                s.skipped    = skipped;
            }
            let _ = app.emit("progress", ProgressPayload { current: ki, total, blocked, skipped, current_kw });
        }

        "cooldown" => {
            let total = val["total_seconds"].as_u64().unwrap_or(0);
            let until = val["until"].as_str().unwrap_or("").to_string();
            let _ = app.emit("cooldown-start", serde_json::json!({
                "total": total, "remaining": total, "until": until
            }));
        }

        "cooldown_tick" => {
            let remaining = val["remaining"].as_u64().unwrap_or(0);
            let _ = app.emit("cooldown-tick", serde_json::json!({ "remaining": remaining }));
        }

        "log" => {
            let text = val["text"].as_str().unwrap_or("").to_string();
            let kind = val["kind"].as_str().unwrap_or("info").to_string();
            let _ = app.emit("raw-log", serde_json::json!({ "kind": kind, "text": text }));
        }

        _ => {}
    }
}

// ── Pause / Resume / Stop ─────────────────────────────────────────────────

pub fn send_pause(session: &SharedSession) {
    #[cfg(unix)]
    if let Some(sess) = session.lock().unwrap().as_ref() {
        unsafe { libc::kill(sess.child.id() as i32, libc::SIGSTOP); }
    }
}

pub fn send_resume(session: &SharedSession) {
    #[cfg(unix)]
    if let Some(sess) = session.lock().unwrap().as_ref() {
        unsafe { libc::kill(sess.child.id() as i32, libc::SIGCONT); }
    }
}

pub fn send_stop(session: &SharedSession) {
    let mut lock = session.lock().unwrap();
    if let Some(sess) = lock.as_mut() {
        let _ = sess.child.kill();
    }
    *lock = None;
}
