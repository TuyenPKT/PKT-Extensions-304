mod normalize;
mod keyword;
mod filter;
mod checkpoint;
mod browser;
mod commands;

use std::sync::{Arc, Mutex};
use commands::AppState;
use browser::SharedSession;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let state: commands::SharedState = Arc::new(Mutex::new(AppState::default()));
    let session: SharedSession = Arc::new(Mutex::new(None));

    tauri::Builder::default()
        .plugin(tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build())
        .plugin(tauri_plugin_shell::init())
        .manage(state)
        .manage(session)
        .invoke_handler(tauri::generate_handler![
            commands::load_keyword_file,
            commands::get_state,
            commands::start_blocking,
            commands::pause_session,
            commands::resume_session,
            commands::stop_session,
            commands::test_filter,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
