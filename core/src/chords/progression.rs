//! ChordProgression — модель последовательности тактов: редактирование аккордов,
//! секции, вольты/повторы, виртуальная навигация, транспонирование.
//! Перенос класса `ChordProgression` из `chords.py` (без JSON/экспорта — те
//! живут в слое хранения/экспорта; без локализованных строк — их вернёт ui-слой).

use std::collections::HashSet;

use crate::chords::model::{Chord, Position, ProgressionItem, SectionMark, TimeSignature, VoltaBracket};
use crate::chords::notes::{note_names_for_key, NOTE_NAMES, NOTE_NAMES_SHARP};
use crate::chords::transpose::{transpose_chord_name, transpose_note_name};

/// Построение iReal Pro строки минорной тональности из бемольного корня
/// (некоторые используют диезную запись): C→C-, Db→C#- и т.д.
fn minor_key_str(root: &str) -> String {
    let out = match root {
        "C" => "C-",
        "Db" => "C#-",
        "D" => "D-",
        "Eb" => "Eb-",
        "E" => "E-",
        "F" => "F-",
        "Gb" => "F#-",
        "G" => "G-",
        "Ab" => "G#-",
        "A" => "A-",
        "Bb" => "Bb-",
        "B" => "B-",
        _ => return format!("{root}-"),
    };
    out.to_string()
}

/// Разобрать iReal Pro тональность на (корень, лад). Корень минора — бемольный.
fn key_to_root_mode(key: &str) -> (String, &'static str) {
    if let Some(stripped) = key.strip_suffix('-') {
        let root = if stripped == "C#" || stripped == "F#" || stripped == "G#" {
            // диезные миноры отображаются бемолями
            match stripped {
                "C#" => "Db",
                "F#" => "Gb",
                "G#" => "Ab",
                _ => stripped,
            }
        } else {
            stripped
        };
        (root.to_string(), "minor")
    } else {
        (key.to_string(), "major")
    }
}

/// Последовательность тактов.
pub struct ChordProgression {
    pub title: String,
    pub time_signature: TimeSignature,
    pub key: String,
    pub style: String,
    pub bpm: i32,
    pub composer: String,
    pub items: Vec<ProgressionItem>,
    pub section_marks: Vec<SectionMark>,
    pub volta_brackets: Vec<VoltaBracket>,
    pub total_measures: i32,
    pub no_chord_measures: HashSet<i32>,
}

impl ChordProgression {
    pub fn new(title: &str, ts: TimeSignature, key: &str, style: &str) -> Self {
        ChordProgression {
            title: title.to_string(),
            time_signature: ts,
            key: key.to_string(),
            style: style.to_string(),
            bpm: 120,
            composer: "Unknown".to_string(),
            items: Vec::new(),
            section_marks: Vec::new(),
            volta_brackets: Vec::new(),
            total_measures: 0,
            no_chord_measures: HashSet::new(),
        }
    }

    pub fn len(&self) -> usize {
        self.items.len()
    }

    fn sort_items(&mut self) {
        self.items.sort();
    }

    // -------------------------------------------------------------------
    // Аккорды
    // -------------------------------------------------------------------

    /// Добавить аккорд на позицию (заменяет существующий там же).
    pub fn add_chord_raw(&mut self, chord: Chord, position: Position, bass_note: &str) {
        self.items.retain(|i| i.position != position);
        let measure = position.measure;
        self.items.push(ProgressionItem {
            chord,
            position,
            bass_note: bass_note.to_string(),
        });
        self.sort_items();
        if measure > self.total_measures {
            self.total_measures = measure;
        }
    }

    pub fn add_chord(&mut self, chord: Chord, measure: i32, beat: i32, bass_note: &str) {
        let pos = Position::new(measure, beat, self.time_signature);
        self.add_chord_raw(chord, pos, bass_note);
    }

    pub fn add_chord_by_name(&mut self, chord_name: &str, measure: i32, beat: i32, bass_note: &str) {
        let chord = Chord::new(chord_name);
        self.add_chord(chord, measure, beat, bass_note);
    }

    pub fn add_chord_by_notes(&mut self, notes: &[&str], measure: i32, beat: i32, bass_note: &str) {
        if let Some(chord) = Chord::from_notes(notes) {
            self.add_chord(chord, measure, beat, bass_note);
        }
    }

    pub fn delete_chord_at(&mut self, position: &Position) {
        self.items.retain(|i| i.position != *position);
    }

    /// Удалить аккорды в [start_measure, end_measure]; вернуть число удалённых.
    pub fn delete_chords_in_measure_range(&mut self, start: i32, end: i32) -> usize {
        let before = self.items.len();
        self.items
            .retain(|i| !(start <= i.position.measure && i.position.measure <= end));
        before - self.items.len()
    }

    pub fn find_chords_at_position(&self, position: &Position) -> Vec<&ProgressionItem> {
        self.items.iter().filter(|i| i.position == *position).collect()
    }

    pub fn find_chords_in_measure(&self, measure: i32) -> Vec<&ProgressionItem> {
        self.items
            .iter()
            .filter(|i| i.position.measure == measure)
            .collect()
    }

    pub fn measure_is_empty(&self, measure: i32) -> bool {
        !self.items.iter().any(|i| i.position.measure == measure)
    }

    pub fn find_next_chord_to_right(&self, position: &Position) -> Option<&ProgressionItem> {
        self.items.iter().find(|i| i.position > *position)
    }

    /// Последний сохранённый аккорд строго левее позиции (с учётом виртуальных зон).
    pub fn find_last_chord_to_left(&self, position: &Position) -> Option<&ProgressionItem> {
        if self.is_in_virtual_range(position.measure) {
            let primary_m = self.resolve_virtual_measure(position.measure);
            let primary_pos = Position::new(primary_m, position.beat, position.time_signature);
            let left_primary: Vec<&ProgressionItem> =
                self.items.iter().filter(|i| i.position < primary_pos).collect();
            if let Some(last) = left_primary.last() {
                return Some(last);
            }
            if let Some((vc_start, _)) = self.get_virtual_context(position.measure) {
                let boundary = Position::new(vc_start, 1, position.time_signature);
                let left: Vec<&ProgressionItem> =
                    self.items.iter().filter(|i| i.position < boundary).collect();
                return left.last().copied();
            }
        }
        let left: Vec<&ProgressionItem> =
            self.items.iter().filter(|i| i.position < *position).collect();
        left.last().copied()
    }

    /// Дедупликация по (такт, доля).
    pub fn validate(&mut self) {
        let mut seen: HashSet<(i32, i32)> = HashSet::new();
        let mut unique: Vec<ProgressionItem> = Vec::new();
        for item in self.items.drain(..) {
            let key = (item.position.measure, item.position.beat);
            if seen.insert(key) {
                unique.push(item);
            }
        }
        self.items = unique;
    }

    // -------------------------------------------------------------------
    // Секции
    // -------------------------------------------------------------------

    pub fn add_section_mark(&mut self, measure: i32, mark: &str) {
        self.section_marks.retain(|s| s.measure != measure);
        self.section_marks.push(SectionMark {
            measure,
            mark: mark.to_string(),
        });
        self.section_marks.sort_by_key(|s| s.measure);
    }

    pub fn remove_section_mark(&mut self, measure: i32) {
        self.section_marks.retain(|s| s.measure != measure);
    }

    pub fn get_section_mark(&self, measure: i32) -> Option<&str> {
        self.section_marks
            .iter()
            .find(|s| s.measure == measure)
            .map(|s| s.mark.as_str())
    }

    /// Пометка, управляющая тактом *measure* (последняя на нём или раньше).
    pub fn get_section_at_measure(&self, measure: i32) -> Option<&str> {
        self.section_marks
            .iter()
            .rev()
            .find(|s| s.measure <= measure)
            .map(|s| s.mark.as_str())
    }

    // -------------------------------------------------------------------
    // Вольты / повторы
    // -------------------------------------------------------------------

    fn find_section_start(&self, measure: i32) -> i32 {
        let mut marks_before: Vec<i32> = self
            .section_marks
            .iter()
            .map(|s| s.measure)
            .filter(|&m| m <= measure)
            .collect();
        marks_before.sort();
        marks_before.last().copied().unwrap_or(1)
    }

    fn find_next_section_start(&self, from_measure: i32) -> i32 {
        let mut marks_after: Vec<i32> = self
            .section_marks
            .iter()
            .map(|s| s.measure)
            .filter(|&m| m > from_measure)
            .collect();
        marks_after.sort();
        if let Some(first) = marks_after.first() {
            return *first;
        }
        std::cmp::max(self.total_measures, from_measure) + 1
    }

    /// V на первом такте окончания 1: координаты скобки выводятся из секций.
    pub fn add_volta_start(&mut self, measure: i32) -> String {
        let repeat_start = self.find_section_start(measure);
        let next_section = self.find_next_section_start(measure);
        let body_length = measure - repeat_start;
        let ending_length = std::cmp::max(1, next_section - measure);
        let ending1_end = measure + ending_length - 1;
        let ending2_start = next_section + body_length;

        self.volta_brackets
            .retain(|vb| vb.repeat_start != repeat_start);
        self.volta_brackets.push(VoltaBracket {
            repeat_start,
            ending1_start: measure,
            ending1_end,
            ending2_start,
            num_repeats: 2,
        });

        let hidden = self.volta_brackets
            .iter()
            .find(|vb| vb.repeat_start == repeat_start)
            .and_then(|vb| vb.hidden_range());
        let cleared = if let Some((hs, he)) = hidden {
            self.delete_chords_in_measure_range(hs, he)
        } else {
            0
        };

        let mut msg = format!(
            "Repeat from measure {repeat_start}, ending 1: {measure}–{ending1_end}, ending 2 starts at measure {ending2_start}"
        );
        if cleared > 0 {
            msg.push_str(&format!(" ({cleared} hidden chord(s) removed)"));
        }
        msg
    }

    /// Явные координаты повтора (без вывода из секций).
    pub fn add_volta_bracket(&mut self, repeat_start: i32, repeat_end: i32, volta_start: i32) -> String {
        if !(repeat_start < volta_start && volta_start <= repeat_end) {
            return format!("Invalid volta markers: repeat_start {repeat_start}, volta {volta_start}, repeat_end {repeat_end}");
        }
        let body_length = volta_start - repeat_start;
        let ending1_end = repeat_end;
        let ending2_start = repeat_end + body_length + 1;

        self.volta_brackets
            .retain(|vb| vb.repeat_start != repeat_start);
        self.volta_brackets.push(VoltaBracket {
            repeat_start,
            ending1_start: volta_start,
            ending1_end,
            ending2_start,
            num_repeats: 2,
        });

        let cleared = if let Some((hs, he)) = self
            .volta_brackets
            .iter()
            .find(|vb| vb.repeat_start == repeat_start)
            .and_then(|vb| vb.hidden_range())
        {
            self.delete_chords_in_measure_range(hs, he)
        } else {
            0
        };

        let mut msg = format!(
            "Repeat from measure {repeat_start}, ending 1: {volta_start}–{ending1_end}, ending 2 starts at measure {ending2_start}"
        );
        if cleared > 0 {
            msg.push_str(&format!(" ({cleared} hidden chord(s) removed)"));
        }
        msg
    }

    /// Обычный повтор без окончаний.
    pub fn add_repeat_bracket(&mut self, repeat_start: i32, repeat_end: i32) -> String {
        if repeat_end <= repeat_start {
            return "Repeat end must be after repeat start".to_string();
        }
        self.volta_brackets
            .retain(|vb| vb.repeat_start != repeat_start);
        self.volta_brackets.push(VoltaBracket {
            repeat_start,
            ending1_start: repeat_end + 1,
            ending1_end: repeat_end,
            ending2_start: repeat_start,
            num_repeats: 2,
        });
        format!("Repeat set: {repeat_start}–{repeat_end}")
    }

    /// Скобка, содержащая такт *measure*.
    pub fn get_volta_bracket_for_measure(&self, measure: i32) -> Option<&VoltaBracket> {
        for vb in &self.volta_brackets {
            if vb.repeat_start <= measure {
                if vb.is_complete() && measure <= std::cmp::max(vb.ending1_end, vb.ending2_start) {
                    return Some(vb);
                }
                if !vb.is_complete() && measure >= vb.ending1_start {
                    return Some(vb);
                }
            }
        }
        None
    }

    pub fn is_in_hidden_range(&self, measure: i32) -> bool {
        self.volta_brackets.iter().any(|vb| {
            if let Some((hs, he)) = vb.hidden_range() {
                hs <= measure && measure <= he
            } else {
                false
            }
        })
    }

    // -------------------------------------------------------------------
    // Навигация
    // -------------------------------------------------------------------

    /// Виртуальная территория, содержащая *measure*: (start, end).
    pub fn get_virtual_context(&self, measure: i32) -> Option<(i32, i32)> {
        for vb in &self.volta_brackets {
            if !vb.is_complete() {
                continue;
            }
            let after = vb.after_repeat_measure();
            let virtual_start = vb.ending1_end + 1;
            if virtual_start <= measure && measure < after {
                return Some((virtual_start, after - 1));
            }
        }
        None
    }

    /// Эквивалентный такт в следующем повторе (вниз) или None.
    pub fn navigate_down_from_measure(&self, measure: i32) -> Option<i32> {
        for vb in &self.volta_brackets {
            if !vb.is_complete() {
                continue;
            }
            let after = vb.after_repeat_measure();
            if vb.is_repeat_only() {
                let body_length = vb.ending1_end - vb.repeat_start + 1;
                if vb.repeat_start <= measure && measure < after {
                    let dest = measure + body_length;
                    if dest < after {
                        return Some(dest);
                    }
                }
            } else {
                let total_length = vb.ending1_end - vb.repeat_start + 1;
                if vb.repeat_start <= measure && measure < vb.ending1_start {
                    return Some(measure + total_length);
                }
                if vb.ending1_start <= measure && measure <= vb.ending1_end {
                    return Some(measure - vb.ending1_start + vb.ending2_start);
                }
            }
        }
        None
    }

    /// Эквивалентный такт в предыдущем повторе (вверх) или None.
    pub fn navigate_up_from_measure(&self, measure: i32) -> Option<i32> {
        for vb in &self.volta_brackets {
            if !vb.is_complete() {
                continue;
            }
            if vb.is_repeat_only() {
                let body_length = vb.ending1_end - vb.repeat_start + 1;
                if let Some((vs, ve)) = vb.plain_virtual_range() {
                    if vs <= measure && measure <= ve {
                        return Some(measure - body_length);
                    }
                }
            } else {
                let total_length = vb.ending1_end - vb.repeat_start + 1;
                let hidden_start = vb.ending1_end + 1;
                let hidden_end = vb.ending2_start - 1;
                if hidden_start <= measure && measure <= hidden_end {
                    return Some(measure - total_length);
                }
                let ending2_end = vb.after_repeat_measure() - 1;
                if vb.ending2_start <= measure && measure <= ending2_end {
                    return Some(measure - vb.ending2_start + vb.ending1_start);
                }
            }
        }
        None
    }

    /// Виртуальный/скрытый такт → его реальный (сохранённый) прообраз.
    pub fn resolve_virtual_measure(&self, measure: i32) -> i32 {
        for vb in &self.volta_brackets {
            if !vb.is_complete() {
                continue;
            }
            if vb.is_repeat_only() {
                let body_length = vb.ending1_end - vb.repeat_start + 1;
                if let Some((vs, ve)) = vb.plain_virtual_range() {
                    if vs <= measure && measure <= ve {
                        return vb.repeat_start + (measure - vb.repeat_start) % body_length;
                    }
                }
            } else {
                let total_length = vb.ending1_end - vb.repeat_start + 1;
                let hidden_start = vb.ending1_end + 1;
                let hidden_end = vb.ending2_start - 1;
                if hidden_start <= measure && measure <= hidden_end {
                    return measure - total_length;
                }
            }
        }
        measure
    }

    /// 0-based номер повтора для такта (0 = первичный).
    pub fn get_repeat_num_for_measure(&self, measure: i32) -> i32 {
        for vb in &self.volta_brackets {
            if !vb.is_complete() {
                continue;
            }
            if vb.is_repeat_only() {
                let body_length = vb.ending1_end - vb.repeat_start + 1;
                if vb.repeat_start <= measure && measure <= vb.ending1_end {
                    return 0;
                }
                if let Some((vs, ve)) = vb.plain_virtual_range() {
                    if vs <= measure && measure <= ve {
                        return (measure - vb.repeat_start) / body_length;
                    }
                }
            } else {
                if vb.repeat_start <= measure && measure <= vb.ending1_end {
                    return 0;
                }
                let after = vb.after_repeat_measure();
                if vb.ending1_end + 1 <= measure && measure < after {
                    return 1;
                }
            }
        }
        0
    }

    /// В первичной навигации: если кандидат в виртуальной зоне — перепрыгнуть за неё.
    pub fn primary_skip_past_virtual(&self, cursor_measure: i32, candidate_measure: i32) -> i32 {
        if self.get_virtual_context(cursor_measure).is_some() {
            return candidate_measure; // уже в виртуальной: навигация свободна
        }
        for vb in &self.volta_brackets {
            if !vb.is_complete() {
                continue;
            }
            let after = vb.after_repeat_measure();
            if vb.ending1_end + 1 <= candidate_measure && candidate_measure < after {
                return after;
            }
        }
        candidate_measure
    }

    pub fn is_in_virtual_range(&self, measure: i32) -> bool {
        self.is_in_hidden_range(measure) || self.is_plain_virtual(measure)
    }

    /// Только виртуальные копии plain-повтора (без hidden-зон вольт).
    pub fn is_plain_virtual(&self, measure: i32) -> bool {
        self.volta_brackets.iter().any(|vb| {
            if let Some((vs, ve)) = vb.plain_virtual_range() {
                vs <= measure && measure <= ve
            } else {
                false
            }
        })
    }

    /// Следующий такт (линейно, включая виртуальные зоны).
    pub fn navigate_right_from_measure(&self, measure: i32) -> i32 {
        measure + 1
    }

    /// Предыдущий такт (линейно, не ниже 1).
    pub fn navigate_left_from_measure(&self, measure: i32) -> i32 {
        std::cmp::max(1, measure - 1)
    }

    /// Последний такт с содержимым (аккорды, секции, N.C.).
    pub fn last_measure(&self) -> i32 {
        let mut mx = self
            .items
            .iter()
            .map(|i| i.position.measure)
            .chain(self.section_marks.iter().map(|s| s.measure))
            .chain(self.no_chord_measures.iter().copied())
            .max();
        if let Some(m) = mx.take() {
            m
        } else {
            1
        }
    }

    /// Такты со структурными маркерами (секции + начала скобок), по возрастанию.
    pub fn structural_marker_measures(&self) -> Vec<i32> {
        let mut marks: HashSet<i32> = HashSet::new();
        for sm in &self.section_marks {
            marks.insert(sm.measure);
        }
        for vb in &self.volta_brackets {
            marks.insert(vb.repeat_start);
            if !vb.is_repeat_only() {
                marks.insert(vb.ending1_start);
            }
            if vb.is_complete() && !vb.is_repeat_only() {
                marks.insert(vb.ending2_start);
            }
        }
        let mut v: Vec<i32> = marks.into_iter().collect();
        v.sort();
        v
    }

    pub fn navigate_next_structural(&self, measure: i32) -> i32 {
        for m in self.structural_marker_measures() {
            if m > measure {
                return m;
            }
        }
        measure
    }

    pub fn navigate_prev_structural(&self, measure: i32) -> i32 {
        for m in self.structural_marker_measures().iter().rev() {
            if *m < measure {
                return *m;
            }
        }
        measure
    }

    // -------------------------------------------------------------------
    // No-chord (N.C.)
    // -------------------------------------------------------------------

    pub fn add_no_chord(&mut self, measure: i32) {
        self.no_chord_measures.insert(measure);
        if measure > self.total_measures {
            self.total_measures = measure;
        }
    }

    pub fn remove_no_chord(&mut self, measure: i32) {
        self.no_chord_measures.remove(&measure);
    }

    pub fn is_no_chord(&self, measure: i32) -> bool {
        self.no_chord_measures.contains(&measure)
    }

    // -------------------------------------------------------------------
    // Транспонирование
    // -------------------------------------------------------------------

    /// Транспонировать имя аккорда с записью знаков тональности прогрессии.
    pub fn transpose_chord_name(&self, name: &str, semitones: i32) -> String {
        transpose_chord_name(name, semitones, note_names_for_key(&self.key))
    }

    /// Тональность, транспонированная на *semitones* (минор сохраняется).
    pub fn transpose_key(&self, semitones: i32) -> String {
        let (root, mode) = key_to_root_mode(&self.key);
        let pc = if let Some(idx) = NOTE_NAMES.iter().position(|&n| n == root) {
            idx as i32
        } else {
            NOTE_NAMES_SHARP
                .iter()
                .position(|&n| n == root)
                .unwrap_or(0) as i32
        };
        let new_pc = (pc + semitones).rem_euclid(12);
        let new_root = NOTE_NAMES[new_pc as usize];
        if mode == "minor" {
            minor_key_str(new_root)
        } else {
            new_root.to_string()
        }
    }

    /// Транспонировать аккорды (и тональность, если вся прогрессия).
    pub fn transpose(&mut self, semitones: i32, positions: Option<&[Position]>) {
        let semitones = semitones.rem_euclid(12);
        if semitones == 0 {
            return;
        }
        let note_names = note_names_for_key(&self.key).to_vec();
        let pos_set: Option<HashSet<Position>> = positions.map(|p| p.iter().cloned().collect());
        for item in self.items.iter_mut() {
            let whole = pos_set.is_none();
            let hit = whole || pos_set.as_ref().unwrap().contains(&item.position);
            if hit {
                let orig_name = item.chord.name().to_string();
                let new_name = transpose_chord_name(&orig_name, semitones, &note_names);
                item.chord = Chord::new(&new_name);
                if !item.bass_note.is_empty() {
                    item.bass_note =
                        transpose_note_name(&item.bass_note, semitones, &note_names);
                }
            }
        }
        if pos_set.is_none() {
            self.key = self.transpose_key(semitones);
        }
    }
}

impl std::fmt::Display for ChordProgression {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        writeln!(
            f,
            "{} in {} ({}) @ {} BPM, time: {}",
            self.title, self.key, self.style, self.bpm, self.time_signature
        )?;
        for item in &self.items {
            writeln!(f, "  {item}")?;
        }
        Ok(())
    }
}
