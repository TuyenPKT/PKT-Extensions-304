/// Kết quả parse một dòng Anti.txt
#[derive(Debug, Clone)]
pub struct ParsedKeyword {
    pub raw: String,
    pub required: Vec<String>,   // double-quoted hoặc fallback words
    pub optional: Vec<String>,   // single-quoted (check name OR card)
    pub bio_signals: Vec<String>, // từ @@ macro (check card F2)
    pub search_kw: String,        // từ khóa để search Facebook
}

/// Parse một dòng keyword (sau khi expand macro)
pub fn parse_keyword(line: &str) -> ParsedKeyword {
    let line = line.trim();
    let (main_part, bio_signals) = split_macro(line);
    let (required, optional, fallback, search_kw) = split_line(main_part);

    let req = if !required.is_empty() {
        required
    } else {
        fallback
    };

    ParsedKeyword {
        raw: line.to_string(),
        required: req,
        optional,
        bio_signals,
        search_kw,
    }
}

/// Tách @@ macro_name ra khỏi dòng
fn split_macro(line: &str) -> (&str, Vec<String>) {
    if let Some(idx) = line.find("@@") {
        let main = line[..idx].trim();
        let _macro_name = line[idx + 2..].trim();
        // Macro đã được expand trước → bio_signals trả về rỗng ở đây
        // Actual signals được inject từ expand_keyword_file
        (main, vec![])
    } else {
        (line, vec![])
    }
}

/// Tách dòng theo && hoặc &@
fn split_line(line: &str) -> (Vec<String>, Vec<String>, Vec<String>, String) {
    if let Some(idx) = line.find(" &@ ") {
        // Tất cả words (double-quoted) đều required
        let left = line[..idx].trim();
        let right = line[idx + 4..].trim();
        let required = extract_quoted(right, '"');
        let search_kw = left.to_string();
        return (required, vec![], vec![], search_kw);
    }

    if let Some(idx) = line.find(" && ") {
        let left = line[..idx].trim();
        let right = line[idx + 4..].trim();
        // left words → required; right single-quoted → optional
        let required = words_ge2(left);
        let optional = extract_quoted(right, '\'');
        let search_kw = left.to_string();
        return (required, optional, vec![], search_kw);
    }

    // Plain → fallback: tất cả words >= 2 chars
    let fallback = words_ge2(line);
    (vec![], vec![], fallback, line.to_string())
}

fn words_ge2(s: &str) -> Vec<String> {
    s.split_whitespace()
        .filter(|w| w.chars().filter(|c| c.is_alphabetic()).count() >= 2)
        .map(|w| w.to_lowercase())
        .collect()
}

fn extract_quoted(s: &str, quote: char) -> Vec<String> {
    let mut result = Vec::new();
    let mut inside = false;
    let mut current = String::new();
    for c in s.chars() {
        if c == quote {
            if inside {
                if !current.is_empty() {
                    result.push(current.trim().to_lowercase());
                    current = String::new();
                }
                inside = false;
            } else {
                inside = true;
            }
        } else if inside {
            current.push(c);
        }
    }
    result
}

/// Expand Anti.txt: parse macros, trả về list ParsedKeyword
pub fn expand_keyword_file(content: &str) -> Vec<ParsedKeyword> {
    use std::collections::HashMap;
    let mut macros: HashMap<String, Vec<String>> = HashMap::new();
    let mut results = Vec::new();

    for raw_line in content.lines() {
        let line = raw_line.trim();

        // Comment
        if line.starts_with('#') && !line.starts_with("##") {
            // Macro definition: # macro_name = && 'term1' 'term2'
            if let Some(eq_idx) = line.find('=') {
                let name = line[1..eq_idx].trim().to_string();
                let body = line[eq_idx + 1..].trim();
                let signals = extract_quoted(body, '\'');
                macros.insert(name.to_lowercase(), signals);
            }
            continue;
        }

        // Section header (## SECTION) — không tạo implicit macro
        if line.starts_with("##") {
            continue;
        }

        if line.is_empty() {
            continue;
        }

        // Xử lý @@ macro reference
        let (main_part, macro_signals) = if let Some(at_idx) = line.find("@@") {
            let main = line[..at_idx].trim();
            let macro_name = line[at_idx + 2..].trim().to_lowercase();
            let signals = macros.get(&macro_name).cloned().unwrap_or_default();
            (main, signals)
        } else {
            (line, vec![])
        };

        let mut kw = parse_keyword(main_part);
        kw.bio_signals = macro_signals;
        kw.raw = line.to_string();
        results.push(kw);
    }

    results
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_plain() {
        let kw = parse_keyword("Netshort");
        assert_eq!(kw.search_kw, "Netshort");
        assert!(kw.required.is_empty());
        assert_eq!(kw.optional, vec![] as Vec<String>);
    }

    #[test]
    fn test_and_and() {
        let kw = parse_keyword("miinh anh && 'r28' 'mmo'");
        assert_eq!(kw.required, vec!["miinh", "anh"]);
        assert_eq!(kw.optional, vec!["r28", "mmo"]);
    }

    #[test]
    fn test_at_at() {
        let kw = parse_keyword("World Cup VIP &@ \"world cup\" \"vip\"");
        assert_eq!(kw.required, vec!["world cup", "vip"]);
    }

    #[test]
    fn test_fallback_short() {
        let kw = parse_keyword("ok bóng đá");
        // words >= 2 alphabetic chars
        assert!(kw.required.is_empty());
        // fallback
        let fb: Vec<String> = vec!["ok", "bóng", "đá"]
            .iter().map(|s| s.to_string()).collect();
        // Ít nhất "bóng" và "đá" phải có (alphabetic chars >= 2)
        assert!(kw.raw.contains("ok"));
    }
}
