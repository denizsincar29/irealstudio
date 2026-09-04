//! Транспонирование нот и аккордов. Перенос `_transpose_note_name` /
//! `_transpose_chord_name` из `chords.py`.

use crate::chords::notes::{pc_of, root_prefix};

/// Транспонировать ноту на *semitones* семитонов, используя *note_names*
/// для записи знаков (бемоли или диезы). Незнакомые ноты не меняются.
pub fn transpose_note_name(note: &str, semitones: i32, note_names: &[&str]) -> String {
    match pc_of(note) {
        Some(pc) => {
            let new_pc = (pc + semitones).rem_euclid(12);
            note_names[new_pc as usize].to_string()
        }
        None => note.to_string(),
    }
}

/// Транспонировать аккорд, сохранив качество.
///
/// Транспонируется только корень и (если есть) басовая нота слэш-аккорда;
/// строка качества остаётся нетронутой. *note_names* задаёт запись знаков.
pub fn transpose_chord_name(name: &str, semitones: i32, note_names: &[&str]) -> String {
    let semitones = semitones.rem_euclid(12);
    if semitones == 0 {
        return name.to_string();
    }
    let root = root_prefix(name);
    if root.is_empty() {
        return name.to_string(); // незнакомый — без изменений
    }
    let quality_and_bass = &name[root.len()..];
    let new_root = transpose_note_name(root, semitones, note_names);

    // Басовая нота (слэш-аккорд).
    if let Some(slash_idx) = quality_and_bass.find('/') {
        let quality = &quality_and_bass[..slash_idx];
        let bass = &quality_and_bass[slash_idx + 1..];
        let new_bass = transpose_note_name(bass, semitones, note_names);
        return format!("{new_root}{quality}/{new_bass}");
    }
    format!("{new_root}{quality_and_bass}")
}
