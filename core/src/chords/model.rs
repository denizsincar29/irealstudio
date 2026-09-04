//! Модели гармонии: Chord, TimeSignature, Position, SectionMark, VoltaBracket,
//! ProgressionItem. Перенос `chords.py` (классы и degree-хелперы).

use crate::chords::identify::identify_chord_name;
use crate::chords::notes::{pc_of, root_prefix};

/// Семитоны от корня для простых (мажорных) ступеней.
fn degree_to_st(degree: i32) -> Option<i32> {
    Some(match degree {
        1 => 0,
        2 => 2,
        3 => 4,
        4 => 5,
        5 => 7,
        6 => 9,
        7 => 11,
        _ => return None,
    })
}

/// Аккорд: имя + (опционально) образующие ноты для degree-запросов.
#[derive(Clone)]
pub struct Chord {
    name: String,
    notes: Vec<String>,
    root_pc: i32,
    ivals: Vec<i32>,
    is_sus: bool,
}

impl Chord {
    pub fn new(name: &str) -> Self {
        Self::with_notes(name, &[])
    }

    pub fn with_notes(name: &str, notes: &[String]) -> Self {
        let mut root_pc = -1;
        let mut ivals: Vec<i32> = Vec::new();
        if let Some(first) = notes.first() {
            if let Some(pc) = pc_of(first) {
                root_pc = pc;
                for n in notes {
                    if let Some(p) = pc_of(n) {
                        let st = (p - root_pc).rem_euclid(12);
                        if !ivals.contains(&st) {
                            ivals.push(st);
                        }
                    }
                }
            }
        }
        let notes_vec = notes.to_vec();

        // root_pc из имени, если не получили из нот (O(1) доступ при озвучке).
        if root_pc < 0 {
            root_pc = pc_of(root_prefix(name)).unwrap_or(-1);
        }

        // Кэш sus-качества из имени.
        let tail = &name[root_prefix(name).len()..];
        let is_sus = tail.contains("sus");

        Chord {
            name: name.to_string(),
            notes: notes_vec,
            root_pc,
            ivals,
            is_sus,
        }
    }

    /// Распознать аккорд из набора нот (корень = первая/нижняя).
    pub fn from_notes(notes: &[&str]) -> Option<Chord> {
        identify_chord_name(notes).map(|name| {
            let owned: Vec<String> = notes.iter().map(|s| s.to_string()).collect();
            Self::with_notes(&name, &owned)
        })
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    /// Pitch class корня (0=C…11=B), -1 если неизвестен.
    pub fn root_pc(&self) -> i32 {
        self.root_pc
    }

    pub fn is_sus(&self) -> bool {
        self.is_sus
    }

    fn norm_degree(degree: i32) -> i32 {
        if degree >= 8 {
            degree - 7
        } else {
            degree
        }
    }

    /// Содержит ли аккорд ступень *degree* (1-based).
    pub fn has_degree(&self, degree: i32) -> bool {
        if self.ivals.is_empty() {
            return false;
        }
        match degree_to_st(Self::norm_degree(degree)) {
            Some(st) => self.ivals.contains(&st),
            None => false,
        }
    }

    /// Имя ноты на ступени *degree*, если она есть.
    pub fn get_degree(&self, degree: i32) -> Option<String> {
        if self.root_pc < 0 {
            return None;
        }
        let st = degree_to_st(Self::norm_degree(degree))?;
        for note in &self.notes {
            if let Some(pc) = pc_of(note) {
                if (pc - self.root_pc).rem_euclid(12) == st {
                    return Some(note.clone());
                }
            }
        }
        None
    }
}

// Равенство и хэш — только по имени (как в python).
impl PartialEq for Chord {
    fn eq(&self, other: &Self) -> bool {
        self.name == other.name
    }
}
impl Eq for Chord {}
impl std::hash::Hash for Chord {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.name.hash(state);
    }
}
impl std::fmt::Display for Chord {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.name)
    }
}

/// Размер такта: числитель/знаменатель (4/4 по умолчанию).
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct TimeSignature {
    pub numerator: i32,
    pub denominator: i32,
}

impl TimeSignature {
    pub fn new(numerator: i32, denominator: i32) -> Self {
        TimeSignature {
            numerator,
            denominator,
        }
    }

    pub fn from_string(s: &str) -> TimeSignature {
        let mut it = s.split('/');
        let num: i32 = it.next().and_then(|x| x.trim().parse().ok()).unwrap_or(4);
        let den: i32 = it.next().and_then(|x| x.trim().parse().ok()).unwrap_or(4);
        TimeSignature::new(num, den)
    }
}

impl std::fmt::Display for TimeSignature {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}/{}", self.numerator, self.denominator)
    }
}

/// Позиция: такт : доля (+ размер такта).
#[derive(Clone)]
pub struct Position {
    pub measure: i32,
    pub beat: i32,
    pub time_signature: TimeSignature,
}

impl Position {
    pub fn new(measure: i32, beat: i32, ts: TimeSignature) -> Self {
        Position {
            measure,
            beat,
            time_signature: ts,
        }
    }

    /// Номер доли от начала (1-based глобально).
    pub fn beat_from_start(&self) -> i32 {
        (self.measure - 1) * self.time_signature.numerator + self.beat
    }

    /// Изменить такт/долю по номеру доли от начала (1-based).
    pub fn set_beat_from_start(&mut self, total_beats: i32) {
        self.measure = (total_beats - 1) / self.time_signature.numerator + 1;
        self.beat = (total_beats - 1) % self.time_signature.numerator + 1;
    }

    fn from_beat_from_start(ts: TimeSignature, total_beats: i32) -> Position {
        let measure = (total_beats - 1) / ts.numerator + 1;
        let beat = (total_beats - 1) % ts.numerator + 1;
        Position::new(measure, beat, ts)
    }

    /// +n долей.
    pub fn add_beats(&self, other: i32) -> Position {
        Self::from_beat_from_start(self.time_signature, self.beat_from_start() + other)
    }

    /// -n долей (не ниже 1).
    pub fn sub_beats(&self, other: i32) -> Position {
        let total = self.beat_from_start() - other;
        let total = if total < 1 { 1 } else { total };
        Self::from_beat_from_start(self.time_signature, total)
    }

    /// Сдвинуть на *other* тактов вправо (доля сохраняется).
    pub fn shift_measure_right(&self, other: i32) -> Position {
        Position::new(self.measure + other, self.beat, self.time_signature)
    }

    /// Сдвинуть на *other* тактов влево (не ниже такта 1).
    pub fn shift_measure_left(&self, other: i32) -> Position {
        let m = self.measure - other;
        let m = if m < 1 { 1 } else { m };
        Position::new(m, self.beat, self.time_signature)
    }
}

impl PartialEq for Position {
    fn eq(&self, other: &Self) -> bool {
        self.measure == other.measure
            && self.beat == other.beat
            && self.time_signature == other.time_signature
    }
}
impl Eq for Position {}
impl std::hash::Hash for Position {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.measure.hash(state);
        self.beat.hash(state);
    }
}
// Порядок python: сначала такт, потом доля (размер не участвует).
impl PartialOrd for Position {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for Position {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        (self.measure, self.beat).cmp(&(other.measure, other.beat))
    }
}
impl std::fmt::Display for Position {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}:{}", self.measure, self.beat)
    }
}

/// Репетиционная пометка / знак секции на такте (*A, *B, S, Q, f…).
#[derive(Clone, PartialEq, Eq)]
pub struct SectionMark {
    pub measure: i32,
    pub mark: String,
}

/// Скобка вольты / повтора.
#[derive(Clone, PartialEq, Eq)]
pub struct VoltaBracket {
    pub repeat_start: i32,   // первый такт повторяемой секции ({)
    pub ending1_start: i32,  // первый такт окончания 1 (N1)
    pub ending1_end: i32,    // последний такт окончания 1 (}); 0 = не задан
    pub ending2_start: i32,  // первый такт окончания 2 (N2); 0 = не задан
    pub num_repeats: i32,    // сколько раз играет тело (2–4; только plain-повторы)
}

impl VoltaBracket {
    pub fn is_complete(&self) -> bool {
        self.ending1_end > 0 && self.ending2_start > 0
    }

    /// Plain-повтор (без окончаний N1/N2)? complete и ending1_start == ending1_end + 1.
    pub fn is_repeat_only(&self) -> bool {
        self.is_complete() && self.ending1_start == self.ending1_end + 1
    }

    /// Скрытый диапазон (тело повтора) между окончаниями.
    pub fn hidden_range(&self) -> Option<(i32, i32)> {
        if !self.is_complete() {
            return None;
        }
        let hidden_start = self.ending1_end + 1;
        let hidden_end = self.ending2_start - 1;
        if hidden_start > hidden_end {
            return None;
        }
        Some((hidden_start, hidden_end))
    }

    /// Первый такт после всей структуры повтора.
    pub fn after_repeat_measure(&self) -> i32 {
        if self.is_repeat_only() {
            let body_length = self.ending1_end - self.repeat_start + 1;
            self.ending1_end + 1 + body_length * (self.num_repeats - 1)
        } else {
            let ending_length = self.ending1_end - self.ending1_start + 1;
            self.ending2_start + ending_length
        }
    }

    /// Для plain-повторов — диапазон всех виртуальных копий (навигация вниз).
    pub fn plain_virtual_range(&self) -> Option<(i32, i32)> {
        if !self.is_repeat_only() || self.num_repeats < 2 {
            return None;
        }
        let body_length = self.ending1_end - self.repeat_start + 1;
        let start = self.ending1_end + 1;
        let end = self.ending1_end + body_length * (self.num_repeats - 1);
        Some((start, end))
    }
}

/// Элемент последовательности: аккорд на позиции (+ басовая нота для слэша).
#[derive(Clone)]
pub struct ProgressionItem {
    pub chord: Chord,
    pub position: Position,
    pub bass_note: String,
}

impl ProgressionItem {
    pub fn chord_name(&self) -> String {
        if self.bass_note.is_empty() {
            self.chord.name.clone()
        } else {
            format!("{}/{}", self.chord.name, self.bass_note)
        }
    }

    /// Имя в каноническом формате iReal Pro (см. chords::ireal).
    pub fn ireal_chord_name(&self) -> String {
        let name = crate::chords::ireal::chord_name_to_ireal(&self.chord.name);
        if self.bass_note.is_empty() {
            name
        } else {
            format!("{name}/{}", self.bass_note)
        }
    }
}

impl PartialEq for ProgressionItem {
    fn eq(&self, other: &Self) -> bool {
        self.position == other.position && self.chord.name == other.chord.name
    }
}
impl Eq for ProgressionItem {}
impl PartialOrd for ProgressionItem {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for ProgressionItem {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.position.cmp(&other.position)
    }
}
impl std::hash::Hash for ProgressionItem {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.chord.name.hash(state);
        self.position.hash(state);
    }
}
impl std::fmt::Display for ProgressionItem {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{} at {}", self.chord_name(), self.position)
    }
}
