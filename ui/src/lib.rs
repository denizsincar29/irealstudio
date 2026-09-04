//! irealwx_ui — логика документа поверх core + презентация для слоя wx.
//!
//! Чистая (без wxDragon) часть этапа 2: документ = `ChordProgression` из core
//! плюс курсор по тактам, тексты для озвучки и ячейки сетки для отрисовки.
//! GUI-оболочка живёт в `main.rs` (Windows, wxDragon) и только вызывает эти
//! функции — здесь всё тестируется в контейнере.
//!
//! Озвучка такта строится из слов `chord_name_to_spoken` (ru-каталог) — это
//! ровно то, что слышит пользователь. Сетка отдаёт на каждый такт короткую
//! строку символов аккордов (для отрисовки панели тактов в `on_paint`).

use irealwx_core::{chord_name_to_spoken, ChordProgression, TimeSignature};

/// Текущая цифровка + курсор по тактам.
pub struct Doc {
    pub cp: ChordProgression,
    /// Номер текущего такта (1-based), в пределах документа.
    pub cursor: i32,
}

/// Один аккорд такта — что рисуем и что озвучиваем.
pub struct ChordCell {
    /// Доля в такте (1-based).
    pub beat: i32,
    /// Символьная запись для сетки: `G7` или `G/B` (слэш-бас).
    pub symbol: String,
    /// Слова для озвучки (ru-каталог, с басом).
    pub spoken: String,
}

/// Содержимое такта для отрисовки/озвучки.
pub struct MeasureView {
    pub number: i32,
    /// Репетиционная пометка (напр. "*A"); показывается над тактом.
    pub section: Option<String>,
    pub no_chord: bool,
    pub chords: Vec<ChordCell>,
}

impl Doc {
    /// Демо-цифровка: 12 тактов, две секции (*A / *B), N.C. в конце.
    /// Строится API core — как будет строиться документ из файла позже.
    pub fn new_demo() -> Self {
        let ts = TimeSignature::new(4, 4);
        let mut cp = ChordProgression::new("Rhythm Changes (демо)", ts, "B-", "Swing");
        cp.bpm = 160;
        cp.composer = "Gershwin / Ragas".to_string();

        // Секция A: такты 1–8.
        cp.add_section_mark(1, "*A");
        for (m, names) in [
            (1, vec!["B-7", "E-7"]),
            (2, vec!["A-7", "D7"]),
            (3, vec!["G-7", "C7"]),
            (4, vec!["F7", "F7b5"]),
            (5, vec!["B-7", "E-7"]),
            (6, vec!["A-7", "D7"]),
            (7, vec!["G-7", "C7"]),
            (8, vec!["F7", "B-7"]),
        ] {
            let mut beat = 1;
            for name in names {
                cp.add_chord_by_name(name, m, beat, "");
                beat += 2; // аккорды на 1 и 3 долях
            }
        }
        // Один слэш-аккорд, чтобы проверить озвучку баса.
        cp.add_chord_by_name("D7", 4, 4, "A");

        // Секция B: такты 9–12; 12-й без аккордов (N.C.).
        cp.add_section_mark(9, "*B");
        for (m, names) in [(9, vec!["F7", "F7"]), (10, vec!["E7", "E-7"])] {
            let mut beat = 1;
            for name in names {
                cp.add_chord_by_name(name, m, beat, "");
                beat += 2;
            }
        }
        cp.add_section_mark(11, "*A");
        cp.add_chord_by_name("B-7", 11, 1, "");
        cp.add_no_chord(12);

        let last = cp.last_measure();
        Doc { cp, cursor: 1.min(last.max(1)) }
    }

    /// Последний такт документа (не ниже 1).
    pub fn last_measure(&self) -> i32 {
        self.cp.last_measure().max(1)
    }

    /// Курсор вправо (не дальше конца документа).
    pub fn go_right(&mut self) {
        let n = self.cursor + 1;
        if n <= self.last_measure() {
            self.cursor = n;
        }
    }

    /// Курсор влево (не ниже 1).
    pub fn go_left(&mut self) {
        if self.cursor > 1 {
            self.cursor -= 1;
        }
    }

    /// К следующей структурной метке (секция/вольта) после курсора.
    pub fn go_next_structural(&mut self) {
        let m = self.cp.navigate_next_structural(self.cursor);
        if m > self.cursor {
            self.cursor = m;
        }
    }

    /// К предыдущей структурной метке до курсора.
    pub fn go_prev_structural(&mut self) {
        let m = self.cp.navigate_prev_structural(self.cursor);
        if m < self.cursor {
            self.cursor = m;
        }
    }

    /// Содержимое такта *measure*.
    pub fn measure_view(&self, measure: i32) -> MeasureView {
        let section = self.cp.get_section_mark(measure).map(|s| s.to_string());
        let no_chord = self.cp.is_no_chord(measure);
        let chords = self
            .cp
            .find_chords_in_measure(measure)
            .into_iter()
            .map(|it| {
                let name = it.chord.name();
                let symbol = if it.bass_note.is_empty() {
                    name.to_string()
                } else {
                    format!("{}/{}", name, it.bass_note)
                };
                let spoken = chord_name_to_spoken(name, &it.bass_note);
                ChordCell { beat: it.position.beat, symbol, spoken }
            })
            .collect();
        MeasureView { number: measure, section, no_chord, chords }
    }

    /// Строка для ячейки сетки (рисуется в on_paint): напр. `1  B-7 E-7`.
    pub fn grid_cell_text(&self, measure: i32) -> String {
        let v = self.measure_view(measure);
        if v.no_chord {
            return "N.C.".to_string();
        }
        let mut out = String::new();
        if let Some(sec) = &v.section {
            out.push_str(&format!("{sec} "));
        }
        for (i, c) in v.chords.iter().enumerate() {
            if i > 0 {
                out.push(' ');
            }
            out.push_str(&c.symbol);
        }
        if out.trim().is_empty() {
            out.push_str("—"); // пустой такт
        }
        out
    }

    /// Все строки сетки, по одной на такт, для отрисовки панели.
    pub fn grid_cells(&self) -> Vec<String> {
        (1..=self.last_measure()).map(|m| self.grid_cell_text(m)).collect()
    }

    /// Речевая фраза секции (напр. "*A" → "секция А").
    fn section_spoken(section: &str) -> String {
        if let Some(rest) = section.strip_prefix('*') {
            format!("секция {}", rest.trim())
        } else {
            section.to_string()
        }
    }

    /// Озвучка такта целиком — то, что произносится при навигации.
    pub fn announce_measure(&self, measure: i32) -> String {
        let v = self.measure_view(measure);
        let mut parts: Vec<String> = Vec::new();
        if let Some(sec) = &v.section {
            parts.push(Self::section_spoken(sec));
        }
        if v.no_chord {
            parts.push("без аккорда".to_string());
        } else if !v.chords.is_empty() {
            for c in &v.chords {
                let spoken = c.spoken.trim();
                if !spoken.is_empty() {
                    parts.push(spoken.to_string());
                }
            }
        } else {
            parts.push("пустой такт".to_string());
        }
        format!("такт {}. {}", measure, parts.join(", "))
    }

    /// Озвучка текущего такта (навигация/меню).
    pub fn announce_current(&self) -> String {
        self.announce_measure(self.cursor)
    }

    /// Озвучка всей песни: по такту на строку.
    pub fn announce_song(&self) -> String {
        let mut lines: Vec<String> = Vec::new();
        let title = format!(
            "{}, {}, {}", self.cp.title, self.cp.key, self.cp.style
        );
        lines.push(title);
        for m in 1..=self.last_measure() {
            lines.push(self.announce_measure(m));
        }
        lines.join("\n")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn demo_has_twelve_measures_and_sections() {
        let d = Doc::new_demo();
        assert_eq!(d.last_measure(), 12, "демо должно быть на 12 тактов");
        assert_eq!(d.cp.get_section_mark(1), Some("*A"));
        assert_eq!(d.cp.get_section_mark(9), Some("*B"));
        assert_eq!(d.cp.get_section_mark(11), Some("*A"));
    }

    #[test]
    fn cursor_stays_in_document() {
        let mut d = Doc::new_demo();
        assert_eq!(d.cursor, 1);
        for _ in 0..50 {
            d.go_right();
        }
        assert_eq!(d.cursor, 12, "вправо не должен выходить за документ");
        for _ in 0..50 {
            d.go_left();
        }
        assert_eq!(d.cursor, 1, "влево не должен выходить ниже первого такта");
    }

    #[test]
    fn structural_navigation_jumps_sections() {
        let mut d = Doc::new_demo();
        d.go_next_structural(); // из 1 → следующая метка
        assert_eq!(d.cursor, 9, "*B на такте 9");
        d.go_next_structural();
        assert_eq!(d.cursor, 11, "*A на такте 11");
        // дальше меток нет — курсор стоит.
        d.go_next_structural();
        assert_eq!(d.cursor, 11);
        d.go_prev_structural();
        assert_eq!(d.cursor, 9);
    }

    #[test]
    fn no_chord_and_slash_cell_text() {
        let d = Doc::new_demo();
        assert_eq!(d.grid_cell_text(12), "N.C.");
        let m4 = d.grid_cell_text(4);
        assert!(m4.contains("D7/A"), "слэш-аккорд в символьной записи: {m4}");
    }

    #[test]
    fn announce_contains_measure_and_not_empty() {
        let d = Doc::new_demo();
        let a1 = d.announce_measure(1);
        assert!(a1.starts_with("такт 1."), "заголовок такта: {a1}");
        assert!(a1.len() > 6, "не пустая озвучка: {a1}");
        let a12 = d.announce_measure(12);
        assert!(a12.contains("без аккорда"), "{a12}");
        // Вся песня — по строке на такт.
        let song = d.announce_song();
        assert_eq!(song.lines().count(), 13, "заголовок + 12 тактов");
    }

    #[test]
    fn chord_spoken_words_are_used() {
        // Озвучка такта должна брать слова из core (ru-каталог): для B-7 —
        // не символы, а фраза вида «си-бемоль минор септ».
        let d = Doc::new_demo();
        let a1 = d.announce_measure(1);
        assert!(
            !a1.contains("B-7"),
            "озвучка не должна содержать сырые символы аккордов: {a1}"
        );
    }
}
