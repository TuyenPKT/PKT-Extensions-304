use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, State};

use crate::browser::{SharedSession, spawn_and_stream, send_pause, send_resume, send_stop};
use crate::keyword::expand_keyword_file;
use crate::filter::decide;

// ── State ──────────────────────────────────────────────────────────────────

#[derive(Default)]
pub struct AppState {
    pub running: bool,
    pub paused: bool,
    pub blocked: u32,
    pub skipped: u32,
    pub current_ki: usize,
    pub current_kw: String,
    pub kw_file: String,
}

pub type SharedState = Arc<Mutex<AppState>>;

// ── Event payloads ─────────────────────────────────────────────────────────

#[derive(Serialize, Clone)]
pub struct LogEntry {
    pub time: String,
    pub filter: String,
    pub name: String,
    pub reason: String,
}

#[derive(Serialize, Clone)]
pub struct ProgressPayload {
    pub current: usize,
    pub total: usize,
    pub blocked: u32,
    pub skipped: u32,
    pub current_kw: String,
}

// ── Commands ───────────────────────────────────────────────────────────────

#[tauri::command]
pub fn load_keyword_file(path: String) -> Result<Vec<String>, String> {
    let content = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let keywords = expand_keyword_file(&content)
        .into_iter()
        .map(|k| k.raw)
        .collect();
    Ok(keywords)
}

#[tauri::command]
pub fn get_state(state: State<SharedState>) -> serde_json::Value {
    let s = state.lock().unwrap();
    serde_json::json!({
        "running": s.running,
        "paused": s.paused,
        "blocked": s.blocked,
        "skipped": s.skipped,
        "current_ki": s.current_ki,
        "current_kw": s.current_kw,
        "kw_file": s.kw_file,
    })
}

#[tauri::command]
pub fn start_blocking(
    app: AppHandle,
    kw_file: String,
    mode: String,
    state: State<SharedState>,
    session: State<SharedSession>,
) -> Result<(), String> {
    spawn_and_stream(
        app,
        PathBuf::from(&kw_file),
        mode,
        state.inner().clone(),
        session.inner().clone(),
    )
}

#[tauri::command]
pub fn pause_session(state: State<SharedState>, session: State<SharedSession>) {
    send_pause(session.inner());
    state.lock().unwrap().paused = true;
}

#[tauri::command]
pub fn resume_session(state: State<SharedState>, session: State<SharedSession>) {
    send_resume(session.inner());
    state.lock().unwrap().paused = false;
}

#[tauri::command]
pub fn stop_session(state: State<SharedState>, session: State<SharedSession>) {
    send_stop(session.inner());
    let mut s = state.lock().unwrap();
    s.running = false;
    s.paused = false;
}

/// Test filter decision
#[derive(Deserialize)]
pub struct FilterTestInput {
    pub name: String,
    pub card: String,
    pub url: String,
    pub keyword_line: String,
}

#[derive(Serialize)]
pub struct FilterTestOutput {
    pub filter: String,
    pub reason: String,
    pub should_block: bool,
}

#[tauri::command]
pub fn test_filter(input: FilterTestInput) -> FilterTestOutput {
    use crate::keyword::parse_keyword;
    let kw = parse_keyword(&input.keyword_line);
    let decision = decide(&input.name, &input.card, &input.url, &kw, &[]);
    FilterTestOutput {
        filter: decision.filter.to_string(),
        reason: decision.reason,
        should_block: decision.should_block,
    }
}

