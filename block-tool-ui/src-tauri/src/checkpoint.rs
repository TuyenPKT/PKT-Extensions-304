#![allow(dead_code)]
use std::path::{Path, PathBuf};
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Checkpoint {
    pub file: String,
    pub ki: usize,
    pub blocked: u32,
    pub skipped: u32,
}

pub fn ckpt_path(data_dir: &Path) -> PathBuf {
    data_dir.join("progress.json")
}

pub fn save(path: &Path, ckpt: &Checkpoint) -> anyhow::Result<()> {
    let json = serde_json::to_string_pretty(ckpt)?;
    std::fs::write(path, json)?;
    Ok(())
}

pub fn load(path: &Path, kw_file: &str) -> Option<Checkpoint> {
    let data = std::fs::read_to_string(path).ok()?;
    let ckpt: Checkpoint = serde_json::from_str(&data).ok()?;
    if ckpt.file == kw_file {
        Some(ckpt)
    } else {
        None
    }
}

pub fn clear(path: &Path) {
    let _ = std::fs::remove_file(path);
}
