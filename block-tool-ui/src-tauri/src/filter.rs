use once_cell::sync::Lazy;
use regex::Regex;
use crate::normalize::{compact, to_searchable};
use crate::keyword::ParsedKeyword;

// ── Gambling blacklist ─────────────────────────────────────────────────────
static GAMBLING_BLACKLIST: &[&str] = &[
    "new88","bet88","thabet","kubet","okvip","rikvip","789bet","jun88",
    "hi88","shbet","188bet","m88","w88","fun88","fb88","bk88","v9bet",
    "fi88","f8bet","st666","loto188","lode88","vnloto",
    "ea88","kuwin","sh88","88sh",
    "b52","v8","8us","vb777","choangclub","xhuclub","zclub","sunvn","6623",
    "68gb","68kb","bigboss","bigboos",
];

static BLACKLIST_REGEXES: Lazy<Vec<Regex>> = Lazy::new(|| {
    vec![
        Regex::new(r"\d+bet").unwrap(),
        Regex::new(r"[a-z]\d{2,}[a-z]").unwrap(),
        Regex::new(r"\b[a-z]{1,4}\d{2,3}\b").unwrap(),  // b52, v8, sh88
        Regex::new(r"\b\d{2,3}[a-z]{1,4}\b").unwrap(),  // 68gb, 99ok
    ]
});

// ── Helpers ────────────────────────────────────────────────────────────────

#[allow(dead_code)]
/// Word-boundary substring match: "5" khớp "5.0", không khớp "500"
pub fn term_in(term: &str, text: &str) -> bool {
    if term.is_empty() { return false; }
    // Escape regex metacharacters
    let escaped = regex::escape(term);
    let pattern = format!(r"(?i)(?:^|[^a-z0-9àáảãạăắặẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]){escaped}(?:[^a-z0-9àáảãạăắặẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]|$)");
    Regex::new(&pattern).map(|re| re.is_match(text)).unwrap_or(false)
}

/// Simple contains check (dùng khi term_in regex phức tạp)
pub fn term_in_simple(term: &str, text: &str) -> bool {
    let text_l = text.to_lowercase();
    let term_l = term.to_lowercase();
    // Check as substring with simple boundary: space/punct before+after
    if text_l.contains(&term_l) {
        // Check boundaries: char before and after
        if let Some(pos) = text_l.find(&term_l) {
            let before_ok = pos == 0 || !text_l.chars().nth(pos - 1).map(|c| c.is_alphanumeric()).unwrap_or(false);
            let after_ok = pos + term_l.len() >= text_l.len()
                || !text_l.chars().nth(pos + term_l.len()).map(|c| c.is_alphanumeric()).unwrap_or(false);
            return before_ok && after_ok;
        }
    }
    false
}

pub fn slug_has(url: &str, keyword: &str) -> bool {
    let url_l = url.to_lowercase();
    let kw_l = compact(keyword);
    url_l.contains(&kw_l)
}

/// Check gambling blacklist
pub fn is_gambling(name: &str) -> bool {
    let normalized = to_searchable(name);
    let compacted = compact(name);
    for &item in GAMBLING_BLACKLIST {
        if normalized.contains(item) || compacted.contains(item) {
            return true;
        }
    }
    for re in BLACKLIST_REGEXES.iter() {
        if re.is_match(&normalized) || re.is_match(&compacted) {
            return true;
        }
    }
    false
}

// ── F1: Name match ─────────────────────────────────────────────────────────

pub enum F1Result {
    Pass,
    Fail { reason: String },
}

/// F1 filter: check name (và card cho optional)
pub fn name_matches(name: &str, card: &str, kw: &ParsedKeyword) -> F1Result {
    let name_s = to_searchable(name);
    let card_s = to_searchable(card);
    let name_c = compact(name);

    // Gambling shortcut
    if is_gambling(name) {
        return F1Result::Pass;
    }

    // URL slug check (nếu có url trong card)
    // (browser layer sẽ pass url riêng nếu cần)

    let required = &kw.required;
    let optional = &kw.optional;
    let fallback: Vec<String> = {
        // Nếu không có required/optional → fallback = words từ search_kw
        if required.is_empty() && optional.is_empty() {
            kw.search_kw.split_whitespace()
                .filter(|w| w.chars().filter(|c| c.is_alphabetic()).count() >= 2)
                .map(|w| to_searchable(w))
                .collect()
        } else {
            vec![]
        }
    };

    if !fallback.is_empty() {
        // Fallback mode: tất cả words phải match
        let missing: Vec<&String> = fallback.iter()
            .filter(|w| !term_in_simple(w, &name_s) && !term_in_simple(w, &name_c))
            .collect();
        if missing.is_empty() {
            F1Result::Pass
        } else {
            F1Result::Fail {
                reason: format!("fallback miss: {:?}", missing),
            }
        }
    } else {
        // Required: tất cả phải có trong name
        let req_missing: Vec<&String> = required.iter()
            .filter(|w| !term_in_simple(w, &name_s) && !term_in_simple(w, &name_c))
            .collect();
        if !req_missing.is_empty() {
            return F1Result::Fail {
                reason: format!("required miss: {:?}", req_missing),
            };
        }

        // Optional: ít nhất 1 phải có trong name HOẶC card
        if !optional.is_empty() {
            let any_opt = optional.iter().any(|opt| {
                let opt_s = to_searchable(opt);
                term_in_simple(&opt_s, &name_s)
                    || term_in_simple(&opt_s, &card_s)
                    || term_in_simple(&opt_s, &name_c)
            });
            if !any_opt {
                return F1Result::Fail {
                    reason: format!("optional miss: all of {:?}", optional),
                };
            }
        }

        F1Result::Pass
    }
}

// ── F2: Bio signals ────────────────────────────────────────────────────────

pub struct F2Result {
    pub pass: bool,
    pub matched: usize,
    pub total: usize,
}

/// F2 filter: check bio signals trong card
pub fn bio_match(card: &str, signals: &[String], threshold: usize) -> F2Result {
    let card_s = to_searchable(card);
    let mut matched = 0usize;
    for sig in signals {
        let sig_s = to_searchable(sig);
        // Multi-word signal (has space): 1 match là đủ
        let is_multiword = sig.contains(' ');
        if term_in_simple(&sig_s, &card_s) {
            if is_multiword {
                return F2Result { pass: true, matched: 1, total: signals.len() };
            }
            matched += 1;
        }
    }
    F2Result {
        pass: matched >= threshold,
        matched,
        total: signals.len(),
    }
}

// ── Decision ───────────────────────────────────────────────────────────────

pub struct BlockDecision {
    pub should_block: bool,
    pub filter: &'static str,  // "F1", "F2", "SKIP"
    pub reason: String,
}

pub fn decide(name: &str, card: &str, url: &str, kw: &ParsedKeyword, global_signals: &[String]) -> BlockDecision {
    // F1
    match name_matches(name, card, kw) {
        F1Result::Pass => {
            return BlockDecision {
                should_block: true,
                filter: "F1",
                reason: "name match".to_string(),
            };
        }
        F1Result::Fail { reason: f1_reason } => {
            // URL slug check
            if slug_has(url, &kw.search_kw) {
                return BlockDecision {
                    should_block: true,
                    filter: "F1",
                    reason: "url slug match".to_string(),
                };
            }

            // F2: bio signals
            let signals = if kw.bio_signals.is_empty() {
                global_signals
            } else {
                &kw.bio_signals
            };
            let f2 = bio_match(card, signals, 2);
            if f2.pass {
                BlockDecision {
                    should_block: true,
                    filter: "F2",
                    reason: format!("bio {}/{} signals", f2.matched, f2.total),
                }
            } else {
                BlockDecision {
                    should_block: false,
                    filter: "SKIP",
                    reason: format!(
                        "F1: {} | F2: bio {}/{} signals",
                        f1_reason, f2.matched, f2.total
                    ),
                }
            }
        }
    }
}
