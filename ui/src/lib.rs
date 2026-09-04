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

/// Диапазон допустимого BPM новой цифровки — как в python
/// (`dialogs.py`: BPM_MIN/BPM_MAX); вне диапазона остаётся дефолт 120.
pub const BPM_MIN: i32 = 40;
pub const BPM_MAX: i32 = 240;

/// Параметры новой цифровки из диалога «Новая цифровка» (Ctrl+N).
/// Поля повторяют python-эталон `new_project_dialog` (dialogs.py:99) и
/// `new_project` (app_io.py:340). `template` — имя шаблона как в python:
/// `""` (без шаблона), `"Blues"`, либо AABA-семейство
/// `"AABA"/"ABAC"/"ABAB"/"ABCD"`.
#[derive(Debug, Clone, PartialEq)]
pub struct NewChart {
    /// Название цифровки (python-дефолт "My Progression").
    pub title: String,
    /// Композитор (python-дефолт "" — пусто, пока не введено).
    pub composer: String,
    /// Тональность (дефолт "C").
    pub key: String,
    /// Стиль (дефолт "Medium Swing").
    pub style: String,
    /// Темп (дефолт 120; вне [BPM_MIN, BPM_MAX] не применяется).
    pub bpm: i32,
    /// Имя шаблона: "" / "Blues" / "AABA" / "ABAC" / "ABAB" / "ABCD".
    pub template: String,
    /// Тактов блюза — только 12/16/24; иное значение трактуется как 12.
    pub blues_bars: i32,
    /// Тактов на секции форм (дефолт 8 на каждую букву).
    pub bars_a: i32,
    pub bars_b: i32,
    pub bars_c: i32,
    pub bars_d: i32,
    /// Вступление: метка `*i` + intro_bars тактов перед телом шаблона.
    pub intro: bool,
    pub intro_bars: i32,
    /// Кода: метка `Q` + coda_bars тактов после тела.
    pub coda: bool,
    pub coda_bars: i32,
}

impl NewChart {
    /// Дефолты python-диалога (app_settings: DEFAULT_*; dialogs.py:99).
    pub fn defaults() -> Self {
        NewChart {
            title: "My Progression".to_string(),
            composer: String::new(),
            key: "C".to_string(),
            style: "Medium Swing".to_string(),
            bpm: 120,
            template: String::new(),
            blues_bars: 12,
            bars_a: 8,
            bars_b: 8,
            bars_c: 8,
            bars_d: 8,
            intro: false,
            intro_bars: 4,
            coda: false,
            coda_bars: 4,
        }
    }
}

/// Последовательность секций AABA-семейства по буквам — как `sequences`
/// в python `_apply_template` (app_io.py:73). Для не-форм — пусто.
fn form_sequence(template: &str) -> &'static [char] {
    match template {
        "AABA" => &['a', 'a', 'b', 'a'],
        "ABAC" => &['a', 'b', 'a', 'c'],
        "ABAB" => &['a', 'b', 'a', 'b'],
        "ABCD" => &['a', 'b', 'c', 'd'],
        _ => &[],
    }
}

/// Наложить шаблон на прогрессию — калька python `_apply_template`
/// (app_io.py:47-87): вступление (метка `*i`), тело (блюз — просто такты без
/// меток; AABA-семейство — метка `*A..*D` на первую долю каждой секции), кода
/// (метка `Q`); затем `total_measures = max(total_measures, курсор-1)`.
fn apply_template(cp: &mut ChordProgression, spec: &NewChart) {
    let intro_bars = if spec.intro { spec.intro_bars } else { 0 };
    let coda_bars = if spec.coda { spec.coda_bars } else { 0 };

    // Курсор (1-based), как в python: куда начнётся следующий фрагмент.
    let mut cursor = 1;

    if intro_bars > 0 {
        cp.add_section_mark(cursor, "*i");
        cursor += intro_bars;
    }

    if spec.template == "Blues" {
        // Блюз без репетиционных меток; недопустимое число тактов → 12.
        let bars = if matches!(spec.blues_bars, 12 | 16 | 24) {
            spec.blues_bars
        } else {
            12
        };
        cursor += bars;
    } else {
        for &letter in form_sequence(&spec.template) {
            let (mark, bars) = match letter {
                'a' => ("*A", spec.bars_a),
                'b' => ("*B", spec.bars_b),
                'c' => ("*C", spec.bars_c),
                'd' => ("*D", spec.bars_d),
                _ => ("", 0),
            };
            cp.add_section_mark(cursor, mark);
            cursor += bars;
        }
    }

    if coda_bars > 0 {
        cp.add_section_mark(cursor, "Q");
        cursor += coda_bars;
    }

    cp.total_measures = cp.total_measures.max(cursor - 1);
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

    /// Новая цифровка из данных формы (Ctrl+N) — как python `new_project`
    /// (app_io.py:340): пустая прогрессия на 4/4 с полями формы, затем шаблон
    /// (`apply_template`). Без шаблона документ пуст — такты появятся по мере
    /// ввода аккордов (как в python).
    pub fn new_chart(spec: &NewChart) -> Self {
        let ts = TimeSignature::new(4, 4); // python: DEFAULT_TIME_SIG = (4, 4)
        let mut cp = ChordProgression::new(&spec.title, ts, &spec.key, &spec.style);
        cp.composer = spec.composer.clone();
        // BPM вне диапазона python молча игнорирует — остаётся дефолт 120.
        if (BPM_MIN..=BPM_MAX).contains(&spec.bpm) {
            cp.bpm = spec.bpm;
        }
        apply_template(&mut cp, spec);
        Doc { cp, cursor: 1 }
    }

    /// Последний такт документа (не ниже 1). Длина песни — это `total_measures`
    /// (как в python): у новой цифровки с шаблоном такты есть, даже если они
    /// пока пустые (метки/аккорды появятся при вводе).
    pub fn last_measure(&self) -> i32 {
        self.cp.last_measure().max(self.cp.total_measures).max(1)
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

    // --- Новая цифровка из формы (Ctrl+N): калька python new_project/_apply_template ---

    #[test]
    fn new_chart_assigns_fields_and_bpm() {
        let mut s = NewChart::defaults();
        s.title = "Blue Bossa".into();
        s.composer = "Kenny Dorham".into();
        s.key = "C-".into();
        s.style = "Bossa Nova".into();
        s.bpm = 200;
        let d = Doc::new_chart(&s);
        assert_eq!(d.cp.title, "Blue Bossa");
        assert_eq!(d.cp.composer, "Kenny Dorham");
        assert_eq!(d.cp.key, "C-");
        assert_eq!(d.cp.style, "Bossa Nova");
        assert_eq!(d.cp.bpm, 200, "bpm в диапазоне применяется");
        assert_eq!(d.cursor, 1, "курсор новой цифровки — на первом такте");
    }

    #[test]
    fn new_chart_out_of_range_bpm_keeps_default() {
        let mut s = NewChart::defaults();
        s.bpm = 300;
        assert_eq!(Doc::new_chart(&s).cp.bpm, 120, "выше BPM_MAX — python игнорирует");
        s.bpm = 20;
        assert_eq!(Doc::new_chart(&s).cp.bpm, 120, "ниже BPM_MIN — python игнорирует");
        s.bpm = 100;
        assert_eq!(Doc::new_chart(&s).cp.bpm, 100);
    }

    #[test]
    fn new_chart_empty_template_is_empty_document() {
        let d = Doc::new_chart(&NewChart::defaults());
        assert_eq!(d.cp.total_measures, 0, "без шаблона тактов нет, как в python");
        assert!(d.cp.section_marks.is_empty());
        assert_eq!(d.cp.last_measure(), 1, "пустой документ держится на такте 1");
    }

    #[test]
    fn new_chart_blues_twelve_no_section_marks() {
        let mut s = NewChart::defaults();
        s.template = "Blues".into();
        let d = Doc::new_chart(&s);
        assert_eq!(d.last_measure(), 12);
        assert!(d.cp.section_marks.is_empty(), "блюз без репетиционных меток");
    }

    #[test]
    fn new_chart_blues_bars_choice_and_coercion() {
        let mut s = NewChart::defaults();
        s.template = "Blues".into();
        s.blues_bars = 24;
        assert_eq!(Doc::new_chart(&s).last_measure(), 24);
        s.blues_bars = 99;
        assert_eq!(Doc::new_chart(&s).last_measure(), 12, "не 12/16/24 → 12, как python");
    }

    #[test]
    fn new_chart_aaba_defaults_thirty_two_bars() {
        let mut s = NewChart::defaults();
        s.template = "AABA".into();
        let d = Doc::new_chart(&s);
        assert_eq!(d.last_measure(), 32);
        assert_eq!(d.cp.get_section_mark(1), Some("*A"));
        assert_eq!(d.cp.get_section_mark(9), Some("*A"), "повтор A");
        assert_eq!(d.cp.get_section_mark(17), Some("*B"));
        assert_eq!(d.cp.get_section_mark(25), Some("*A"), "финальный A");
        assert_eq!(d.cp.get_section_mark(2), None, "внутри секции меток нет");
    }

    #[test]
    fn new_chart_aaba_with_intro_and_coda() {
        let mut s = NewChart::defaults();
        s.template = "AABA".into();
        s.intro = true;
        s.intro_bars = 4;
        s.coda = true;
        s.coda_bars = 4;
        let d = Doc::new_chart(&s);
        assert_eq!(d.cp.get_section_mark(1), Some("*i"), "вступление");
        assert_eq!(d.cp.get_section_mark(5), Some("*A"), "A после 4 тактов вступления");
        assert_eq!(d.cp.get_section_mark(13), Some("*A"), "второй A");
        assert_eq!(d.cp.get_section_mark(21), Some("*B"));
        assert_eq!(d.cp.get_section_mark(29), Some("*A"), "финальный A");
        assert_eq!(d.cp.get_section_mark(37), Some("Q"), "кода после последней секции");
        assert_eq!(d.cp.total_measures, 40, "4 вступления + 32 формы + 4 коды");
        assert_eq!(d.last_measure(), 40);
    }

    #[test]
    fn new_chart_abac_custom_section_bars() {
        let mut s = NewChart::defaults();
        s.template = "ABAC".into();
        s.bars_a = 8;
        s.bars_b = 4;
        let d = Doc::new_chart(&s);
        // A(8) → *B на 9; B(4) → *A на 13; A(8) → *C на 21; C(8) → всего 28.
        assert_eq!(d.cp.get_section_mark(1), Some("*A"));
        assert_eq!(d.cp.get_section_mark(9), Some("*B"));
        assert_eq!(d.cp.get_section_mark(13), Some("*A"));
        assert_eq!(d.cp.get_section_mark(21), Some("*C"));
        assert_eq!(d.cp.total_measures, 28);
        assert_eq!(d.last_measure(), 28);
    }

    #[test]
    fn new_chart_announces_first_section() {
        let mut s = NewChart::defaults();
        s.template = "AABA".into();
        let d = Doc::new_chart(&s);
        let a1 = d.announce_measure(1);
        assert!(a1.contains("секция A"), "озвучка метки секции: {a1}");
    }
}
