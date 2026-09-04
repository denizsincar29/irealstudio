//! Перевод канонического имени аккорда в нотацию iReal Pro.
//! Перенос `_IREAL_QUALITY_MAP` / `_chord_name_to_ireal` из `chords.py`.
//!
//! Длинные/специфичные паттерны идут ПЕРЕД короткими (например "mM7" перед "m").

use crate::chords::notes::root_prefix;

/// (наше качество, качество iReal Pro). Порядок критичен.
const IREAL_QUALITY_MAP: &[(&str, &str)] = &[
    // Minor-major 7th / минорные расширенные
    ("mM7", "-^7"),
    ("mM7(9)", "-^9"),
    ("m7b5", "h7"),
    ("m7(b5)", "h7"),
    ("m7b5(b9)", "h9"),
    ("m7b5(9)", "h9"),
    ("m7(9)", "-9"),
    ("m7(11)", "-11"),
    ("m7(#11)", "-11"),
    ("m7(13)", "min13"),
    ("m7", "-7"),
    ("m6/9", "-69"),
    ("m6", "-6"),
    ("m9", "-9"),
    ("m11", "-11"),
    ("m13", "min13"),
    ("m#5", "-#5"),
    ("m", "-"),
    // Мажорные 7-е — скобочные расширения раскрываются
    ("maj13", "^13"),
    ("maj9", "^9"),
    ("maj7(9#11)", "^9#11"),
    ("maj7(9)", "^9"),
    ("maj7(#11)", "^7#11"),
    ("maj7(13)", "^13"),
    ("maj7", "^7"),
    // Доминанта с расширениями в скобках → раскрыть
    ("7(b9#11)", "7b9#11"),
    ("7(#9#11)", "7#9#11"),
    ("7(b9b5)", "7b9b5"),
    ("7(#9b5)", "7#9b5"),
    ("7(9b5)", "9b5"),
    ("7(b5)", "7b5"),
    ("7(#9#5)", "7#9#5"),
    ("7(b9#5)", "7b9#5"),
    ("7(b913)", "13b9"),
    ("7(#913)", "13#9"),
    ("7(913)", "13"),
    ("7(b9)", "7b9"),
    ("7(#9)", "7#9"),
    ("7(9)", "9"),
    ("7(#11)", "7#11"),
    ("7(b13)", "7b13"),
    ("7(13)", "13"),
    ("6/9", "69"),
    ("dim7", "o7"),
    ("dim", "o"),
    ("aug7", "7#5"),
    ("augM7", "^7#5"),
    ("aug", "+"),
    ("7sus4(b913)", "7b9sus"),
    ("7sus4(13)", "13sus"),
    ("7sus4(b9)", "7b9sus"),
    ("7sus4", "7sus"),
    ("sus4", "sus"),
];

/// Каноническое имя → нотация iReal Pro (или без изменений, если незнакомо).
pub fn chord_name_to_ireal(name: &str) -> String {
    let root = root_prefix(name);
    let quality = &name[root.len()..];

    // 1. Точное совпадение качества в карте.
    for &(src, dst) in IREAL_QUALITY_MAP {
        if quality == src {
            return format!("{root}{dst}");
        }
    }

    // 2. У качества может быть «хвост» из маркеров iReal Pro (C=coda, Q=coda-alt,
    //    f=fine, S=segno, Y=vert-space). Срезаем только если хвост состоит
    //    исключительно из этих символов.
    let stripped = quality.trim_end_matches(|c| matches!(c, 'C' | 'Q' | 'f' | 'S' | 'Y'));
    if stripped != quality && !stripped.is_empty() {
        for &(src, dst) in IREAL_QUALITY_MAP {
            if stripped == src {
                return format!("{root}{dst}");
            }
        }
        return format!("{root}{stripped}");
    }

    name.to_string()
}
