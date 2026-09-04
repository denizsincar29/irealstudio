//! Ноты и тональности: имена, pitch-class маппинг, выбор бемолей/диезов.
//! Прямой перенос шапки `chords.py`.

/// Ноты с бемолями (аккорды без предпочтения диезов).
pub const NOTE_NAMES: [&str; 12] =
    ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"];

/// Ноты с диезами (когда тональность предпочитает диезы).
pub const NOTE_NAMES_SHARP: [&str; 12] =
    ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

/// Тональности, предпочитающие диезы (мажор + их относительные миноры,
/// только те, что есть в pyrealpro.KEY_SIGNATURES).
const SHARP_KEYS: [&str; 12] =
    ["C", "G", "D", "A", "E", "B", "A-", "E-", "B-", "F#-", "C#-", "G#-"];

/// Pitch-class (0=C … 11=B): единый маппинг, принимающий и бемоли, и диезы.
/// Единственный источник правды для распознавания аккордов.
pub fn pc_of(note: &str) -> Option<i32> {
    Some(match note {
        "C" => 0,
        "C#" | "Db" => 1,
        "D" => 2,
        "D#" | "Eb" => 3,
        "E" => 4,
        "F" => 5,
        "F#" | "Gb" => 6,
        "G" => 7,
        "G#" | "Ab" => 8,
        "A" => 9,
        "A#" | "Bb" => 10,
        "B" => 11,
        _ => return None,
    })
}

/// Имена нот (бемольные или диезные) для тональности *key*.
pub fn note_names_for_key(key: &str) -> &'static [&'static str] {
    if SHARP_KEYS.contains(&key) {
        &NOTE_NAMES_SHARP
    } else {
        &NOTE_NAMES
    }
}

/// Все валидные корни (обе записи), длинные первыми, чтобы префиксный скан
/// всегда пробовал двухбуквенный корень раньше однобуквенного.
pub const ALL_ROOTS: [&str; 17] = [
    "C#", "Db", "D#", "Eb", "F#", "Gb", "G#", "Ab", "A#", "Bb", "C", "D", "E", "F", "G", "A", "B",
];

/// Найти корень аккорда в начале имени (самый длинный подходящий из ALL_ROOTS).
pub fn root_prefix(name: &str) -> &str {
    for r in ALL_ROOTS {
        if name.starts_with(r) {
            return r;
        }
    }
    ""
}

/// Pitch-class корня имени аккорда, или -1 если корень не распознан.
pub fn root_pc_of_name(name: &str) -> i32 {
    let r = root_prefix(name);
    pc_of(r).unwrap_or(-1)
}
