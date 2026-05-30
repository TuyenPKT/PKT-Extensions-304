use unicode_normalization::UnicodeNormalization;

/// Map lookalike → ASCII (Cyrillic, Latin small caps, Greek, Canadian Syllabics, Fullwidth)
fn lookalike_replace(c: char) -> Option<char> {
    match c {
        // Cyrillic → Latin
        'А' => Some('A'), 'В' => Some('B'), 'С' => Some('C'), 'Е' => Some('E'),
        'Н' => Some('H'), 'І' => Some('I'), 'К' => Some('K'), 'М' => Some('M'),
        'О' => Some('O'), 'Р' => Some('P'), 'Ѕ' => Some('S'), 'Т' => Some('T'),
        'Х' => Some('X'), 'Ү' => Some('Y'), 'Ѡ' => Some('W'),
        'а' => Some('a'), 'с' => Some('c'), 'е' => Some('e'), 'о' => Some('o'),
        'р' => Some('p'), 'х' => Some('x'), 'і' => Some('i'),
        'Ԁ' => Some('D'), 'ԁ' => Some('d'), 'п' => Some('n'), 'н' => Some('h'),
        'һ' => Some('h'), 'ʜ' => Some('H'),
        // Latin small capitals / IPA
        'ᴀ' => Some('a'), 'ʙ' => Some('b'), 'ᴄ' => Some('c'), 'ᴅ' => Some('d'),
        'ᴇ' => Some('e'), 'ꜰ' => Some('f'), 'ɢ' => Some('g'), 'ɪ' => Some('i'),
        'ᴊ' => Some('j'), 'ᴋ' => Some('k'), 'ʟ' => Some('l'), 'ᴍ' => Some('m'),
        'ɴ' => Some('n'), 'ᴏ' => Some('o'), 'ᴘ' => Some('p'), 'ʀ' => Some('r'),
        'ꜱ' => Some('s'), 'ᴛ' => Some('t'), 'ᴜ' => Some('u'), 'ᴠ' => Some('v'),
        'ᴡ' => Some('w'), 'ʏ' => Some('y'), 'ᴢ' => Some('z'),
        // Greek
        'α' => Some('a'), 'β' => Some('b'), 'ε' => Some('e'), 'ι' => Some('i'),
        'κ' => Some('k'), 'ο' => Some('o'), 'ρ' => Some('p'), 'τ' => Some('t'),
        'υ' => Some('u'), 'χ' => Some('x'), 'ω' => Some('w'),
        // Canadian Syllabics
        'ᗰ' => Some('M'),
        // Fullwidth digits
        '０' => Some('0'), '１' => Some('1'), '２' => Some('2'), '３' => Some('3'),
        '４' => Some('4'), '５' => Some('5'), '６' => Some('6'), '７' => Some('7'),
        '８' => Some('8'), '９' => Some('9'),
        _ => None,
    }
}

/// Mathematical Bold/Italic/... U+1D400–U+1D7FF → ASCII
fn math_alpha_replace(c: char) -> Option<char> {
    let cp = c as u32;
    if !(0x1D400..=0x1D7FF).contains(&cp) {
        return None;
    }
    // Rough mapping: each block of 26 letters repeating A-Z / a-z
    let offsets_upper: &[(u32, u32)] = &[
        (0x1D400, 0), (0x1D434, 0), (0x1D468, 0), (0x1D49C, 0), (0x1D4D0, 0),
        (0x1D504, 0), (0x1D538, 0), (0x1D56C, 0), (0x1D5A0, 0), (0x1D5D4, 0),
        (0x1D608, 0), (0x1D63C, 0), (0x1D670, 0),
    ];
    let offsets_lower: &[(u32, u32)] = &[
        (0x1D41A, 0), (0x1D44E, 0), (0x1D482, 0), (0x1D4BB, 0), (0x1D4EF, 0),
        (0x1D51E, 0), (0x1D552, 0), (0x1D586, 0), (0x1D5BA, 0), (0x1D5EE, 0),
        (0x1D622, 0), (0x1D656, 0), (0x1D68A, 0),
    ];
    for (base, _) in offsets_upper {
        if cp >= *base && cp < base + 26 {
            return char::from_u32(b'A' as u32 + (cp - base)).map(|ch| ch);
        }
    }
    for (base, _) in offsets_lower {
        if cp >= *base && cp < base + 26 {
            return char::from_u32(b'a' as u32 + (cp - base)).map(|ch| ch);
        }
    }
    // Digits blocks
    let digit_bases: &[u32] = &[0x1D7CE, 0x1D7D8, 0x1D7E2, 0x1D7EC, 0x1D7F6];
    for &base in digit_bases {
        if cp >= base && cp < base + 10 {
            return char::from_u32(b'0' as u32 + (cp - base));
        }
    }
    None
}

/// Apply lookalike + math-alpha substitution
fn apply_subs(s: &str) -> String {
    s.chars().map(|c| {
        lookalike_replace(c)
            .or_else(|| math_alpha_replace(c))
            .unwrap_or(c)
    }).collect()
}

/// Strip diacritics (NFD → keep only ASCII) + remove non-alphanum + lowercase
pub fn compact(s: &str) -> String {
    s.nfd()
        .filter(|c| c.is_ascii_alphanumeric())
        .map(|c| c.to_ascii_lowercase())
        .collect()
}

/// lookalike + math-alpha → NFC → lowercase (dùng cho detect/match)
pub fn to_searchable(s: &str) -> String {
    let replaced = apply_subs(s);
    replaced.nfc().collect::<String>().to_lowercase()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cyrillic() {
        assert_eq!(to_searchable("Мinh"), "minh");
    }

    #[test]
    fn test_canadian_syllabics() {
        assert_eq!(to_searchable("ᗰᗰO"), "mmo");
    }

    #[test]
    fn test_compact() {
        assert_eq!(compact("ok-vip"), "okvip");
        assert_eq!(compact("Ôkê"), "oke");
    }
}
