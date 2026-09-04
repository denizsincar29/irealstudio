//! Озвучка имени аккорда на русском — порт `chord_name_to_spoken` (chords.py).
//!
//! В python текст-шаблоны английские, а в рантайме гоняются через gettext-
//! каталог (irealstudio/locales/ru). Порт без gettext вендорит каталог для
//! нужного набора фраз в `spoken_i18n.rs` и переводит через `tr()`; ключа нет —
//! фраза остаётся как есть (поведение gettext с пустым каталогом).
//!
//! Разбор такой же, как в эталоне: корень берётся из `ALL_ROOTS` (порядок
//! важен: сначала диезы/бемоли, потом натуральные), качество ищется точным
//! совпадением в карте, незнакомое качество — longest-prefix + extension-токены,
//! слэш перед заглавной буквой читается как бас-инверсия (`C/E`), перед цифрой —
//! как часть качества (`m6/9`). Явный `bass_note` перекрывает встроенный бас.

use super::notes::root_prefix;
use super::spoken_i18n::RU_PHRASES;

/// Перевод шаблона в русскую строку (из вендоренного ru-каталога).
fn tr(en: &str) -> String {
    for (k, v) in RU_PHRASES {
        if *k == en {
            return v.to_string();
        }
    }
    en.to_string()
}

/// Только цифры (пробелы между ними допускаются)? Такие фразы не переводятся —
/// в любой локали остаются цифровой записью.
fn is_digits(s: &str) -> bool {
    !s.is_empty() && s.chars().all(|c| c == ' ' || c.is_ascii_digit())
}

/// Карта качества: (строка качества, разговорная форма). Сверка — точным
/// равенством, порядок не влияет (дубликаты с общей приставкой различимы).
const QUALITY: &[(&str, &str)] = &[
    ("mM7", "minor major 7"),
    ("mM7(9)", "minor major 9"),
    ("m7b5", "half diminished"),
    ("m7(b5)", "half diminished"),
    ("m7b5(b9)", "half diminished flat 9"),
    ("m7b5(9)", "half diminished 9"),
    ("m7(9)", "minor 9"),
    ("m7(11)", "minor 7 eleven"),
    ("m7(#11)", "minor 7 sharp 11"),
    ("m7(13)", "minor 13"),
    ("m7", "minor 7"),
    ("m6/9", "minor 6 9"),
    ("m6", "minor 6"),
    ("m9", "minor 9"),
    ("m11", "minor 11"),
    ("m13", "minor 13"),
    ("m#5", "minor sharp 5"),
    ("m", "minor"),
    ("maj13", "major 13"),
    ("maj9", "major 9"),
    ("maj7(9#11)", "major 9 sharp 11"),
    ("maj7(9)", "major 9"),
    ("maj7(#11)", "major 7 sharp 11"),
    ("maj7(13)", "major 13"),
    ("maj7", "major 7"),
    ("7(b9#11)", "7 flat 9 sharp 11"),
    ("7(#9#11)", "7 sharp 9 sharp 11"),
    ("7(b9b5)", "7 flat 9 flat 5"),
    ("7(#9b5)", "7 sharp 9 flat 5"),
    ("7(9b5)", "9 flat 5"),
    ("7(b5)", "7 flat 5"),
    ("7(#9#5)", "7 sharp 9 sharp 5"),
    ("7(b9#5)", "7 flat 9 sharp 5"),
    ("7(b9)", "7 flat 9"),
    ("7(#9)", "7 sharp 9"),
    ("7(9)", "9"),
    ("7(#11)", "7 sharp 11"),
    ("7(b13)", "7 flat 13"),
    ("7(b913)", "7 flat 9 13"),
    ("7(#913)", "7 sharp 9 13"),
    ("7(913)", "13"),
    ("7(13)", "13"),
    ("6/9", "6 9"),
    ("dim7", "diminished 7"),
    ("dim", "diminished"),
    ("aug7", "augmented 7"),
    ("augM7", "augmented major 7"),
    ("aug", "augmented"),
    ("7sus4(b913)", "7 sus 4 flat 9 13"),
    ("7sus4(13)", "7 sus 4 13"),
    ("7sus4(b9)", "7 sus 4 flat 9"),
    ("7sus4", "7 sus 4"),
    ("sus4", "sus 4"),
    ("7sus", "7 sus 4"),
    ("sus", "sus 4"),
    ("add9", "add 9"),
    ("13", "13"),
    ("11", "11"),
    ("9", "9"),
    ("7", "7"),
    ("6", "6"),
];

/// Разговорные формы extension-токенов (порядок важен: длинные раньше).
const EXT: &[(&str, &str)] = &[
    ("#11", "sharp 11"),
    ("b13", "flat 13"),
    ("#9", "sharp 9"),
    ("b9", "flat 9"),
    ("#5", "sharp 5"),
    ("b5", "flat 5"),
    ("13", "13"),
    ("11", "11"),
    ("9", "9"),
];

/// Разговорная форма корня: `C#` → «до диез», `Bb` → «си бемоль», `G` → «соль».
fn spoken_root(root: &str) -> String {
    let letter = &root[..1];
    let letter_spoken = tr(letter);
    if root.ends_with('#') {
        return format!("{letter_spoken} {}", tr("sharp"));
    }
    if root.len() == 2 && root.as_bytes()[1] == b'b' {
        return format!("{letter_spoken} {}", tr("flat"));
    }
    letter_spoken
}

/// Разговорная форма качества, отсутствующего в карте: сначала longest-prefix
/// по базовому качеству, затем чтение extension-токенов. Нет совпадений —
/// возвращаем строку качества как есть.
fn spoken_quality_fallback(quality: &str) -> String {
    let mut inner = quality;
    if inner.starts_with('(') && inner.ends_with(')') && inner.len() >= 2 {
        inner = &inner[1..inner.len() - 1];
    }

    // Самая длинная известная приставка базового качества.
    let mut best_base = "";
    let mut best_spoken = "";
    for (src, dst) in QUALITY {
        if inner.starts_with(*src) && src.len() > best_base.len() {
            best_base = src;
            best_spoken = dst;
        }
    }

    let mut remainder = &inner[best_base.len()..];
    if remainder.starts_with('(') && remainder.ends_with(')') && remainder.len() >= 2 {
        remainder = &remainder[1..remainder.len() - 1];
    }

    // Токенизация остатка на известные расширения.
    let mut ext_parts: Vec<String> = Vec::new();
    let mut pos = 0;
    while pos < remainder.len() {
        let rest = &remainder[pos..];
        let mut matched = false;
        for (token, spoken) in EXT {
            if rest.starts_with(*token) {
                ext_parts.push(if is_digits(spoken) {
                    spoken.to_string()
                } else {
                    tr(spoken)
                });
                pos += token.len();
                matched = true;
                break;
            }
        }
        if !matched {
            // Незнакомый фрагмент — не портим: возвращаем строку как есть.
            return quality.to_string();
        }
    }

    let mut combined = if best_spoken.is_empty() {
        String::new()
    } else {
        tr(best_spoken)
    };
    if !ext_parts.is_empty() {
        if !combined.is_empty() {
            combined.push(' ');
        }
        combined.push_str(&ext_parts.join(" "));
    }
    if combined.is_empty() {
        quality.to_string()
    } else {
        combined
    }
}

/// Полное разговорное имя аккорда (порт `chord_name_to_spoken`).
pub fn chord_name_to_spoken(name: &str, bass_note: &str) -> String {
    if name.is_empty() {
        return String::new();
    }

    let root = root_prefix(name);
    let mut quality_and_ext = &name[root.len()..];

    // Слэш-инверсия, встроенная в имя: '/' перед заглавной — бас (`C/E`),
    // перед цифрой — часть качества (`m6/9`). Явный bass_note приоритетнее.
    let mut embedded_bass = "";
    if let Some(pos) = quality_and_ext.rfind('/') {
        let after = &quality_and_ext[pos + 1..];
        if !after.is_empty() && after.as_bytes()[0].is_ascii_uppercase() {
            embedded_bass = after;
            quality_and_ext = &quality_and_ext[..pos];
        }
    }
    let resolved_bass = if bass_note.is_empty() {
        embedded_bass
    } else {
        bass_note
    };

    // Точное совпадение качества в карте; чисто цифровые формы не переводятся.
    let mut quality_spoken = String::new();
    for (src, dst) in QUALITY {
        if quality_and_ext == *src {
            quality_spoken = if is_digits(dst) {
                dst.to_string()
            } else {
                tr(dst)
            };
            break;
        }
    }
    // Незнакомое непустое качество — longest-prefix + extension-токены.
    if quality_spoken.is_empty() && !quality_and_ext.is_empty() {
        quality_spoken = spoken_quality_fallback(quality_and_ext);
    }

    let mut result = spoken_root(root);
    if !quality_spoken.is_empty() {
        result.push(' ');
        result.push_str(&quality_spoken);
    }
    if !resolved_bass.is_empty() {
        result.push(' ');
        result.push_str(&tr("over"));
        result.push(' ');
        result.push_str(&spoken_root(resolved_bass));
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn digits_stay_digits() {
        assert!(is_digits("7"));
        assert!(is_digits("6 9"));
        assert!(!is_digits("minor 7"));
        assert!(!is_digits(""));
    }

    #[test]
    fn roots() {
        assert_eq!(spoken_root("C"), "до");
        assert_eq!(spoken_root("C#"), "до диез");
        assert_eq!(spoken_root("Bb"), "си бемоль");
        assert_eq!(spoken_root("F"), "фа");
    }
}
