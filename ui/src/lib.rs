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

use irealwx_core::{
    chord_name_to_spoken, normalize_bass_note, parse_chord_entry, ChordEntryError,
    ChordProgression, Position, TimeSignature, VoltaBracket,
};

/// Потолок стека undo — как python `_UNDO_MAX = 50` (main.py).
pub const UNDO_MAX: usize = 50;

/// Один аккорд в буфере обмена (одиночный: имя + слэш-бас).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClipboardItem {
    pub name: String,
    pub bass: String,
}

/// Аккорд в мульти-буфере выделения (слайс 14, #52): имя + бас + смещение от
/// первого аккорда выделения в долях (как python `bfs_offset`). При вставке
/// смещение отсчитывается от целевой доли — весь блок переносится с той же
/// внутренней геометрией.
pub struct SelChord {
    pub bfs_offset: i64,
    pub name: String,
    pub bass: String,
}

/// Диапазон выделения (слайс 14, #52): якорь (`a_*`, где встал первый
/// Shift+стрелка) и активный край (`b_*`, куда ушёл курсор). Храним физические
/// такт+долю, как python `_sel_anchor`/`_sel_active` (main.py:1029).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SelRange {
    pub a_m: i32,
    pub a_b: i32,
    pub b_m: i32,
    pub b_b: i32,
}

impl SelRange {
    pub fn new(a_m: i32, a_b: i32, b_m: i32, b_b: i32) -> Self {
        SelRange { a_m, a_b, b_m, b_b }
    }

    /// Нормированный диапазон (start, end) по порядку (такт, доля).
    pub fn normalized(&self) -> ((i32, i32), (i32, i32)) {
        let (a, b) = ((self.a_m, self.a_b), (self.b_m, self.b_b));
        if b < a {
            (b, a)
        } else {
            (a, b)
        }
    }
}

/// Текущая цифровка + курсор по тактам.
///
/// Модель редактирования (этап 2, slice 5) — «клетка такта»: правки (вставка
/// на доле 1, F2/копирование/удаление) адресуют первый аккорд такта. Слайс 11
/// добавил к курсору *долю* — MuseScore-навигацию: простая стрелка ходит по
/// событиям (от аккорда к следующему аккорду, в том числе на второй аккорд
/// того же такта; когда аккордов впереди нет — по пустым тактам «в такт»).
/// Редактирование при этом остаётся на «клетке такта» (первый аккорд); доля
/// живёт только для навигации и озвучки текущей позиции.
pub struct Doc {
    pub cp: ChordProgression,
    /// Номер текущего такта (1-based), в пределах документа.
    pub cursor: i32,
    /// Доля внутри такта (1-based), на которой стоит курсор; для шага по
    /// аккордам внутри такта. При движении на новый такт сбрасывается на 1.
    pub beat: i32,
    /// Стек undo — снимки `cp.to_json()` до правки (как python `_undo_stack`).
    pub undo_stack: Vec<String>,
    /// Стек redo — снимки состояния, отменённые undo.
    pub redo_stack: Vec<String>,
    /// Буфер обмена одиночного аккорда (имя + бас).
    pub clipboard: Option<ClipboardItem>,
    /// Цифровка менялась после последнего сохранения (для «*» в заголовке).
    pub dirty: bool,
    /// Маркеры повтора «[»/«]» (slice 7) — временное состояние между нажатиями,
    /// как python `_pending_repeat_start/_end` (main.py:410). Живут в документе,
    /// но не входят в undo-снимок (как в python) и сбрасываются на undo/redo.
    pub pending_repeat_start: Option<i32>,
    pub pending_repeat_end: Option<i32>,
    /// Активное выделение Shift+стрелки (слайс 14, #52). None — выделения нет.
    pub selection: Option<SelRange>,
    /// Мульти-буфер выделенного блока (≥2 аккордов); сдвигается при Ctrl+X/C,
    /// вставляется как блок. Одиночное копирование кладёт в `clipboard`.
    pub sel_clipboard: Option<Vec<SelChord>>,
}

impl Doc {
    /// Снять выделение (курсор остаётся на месте).
    pub fn clear_selection(&mut self) {
        self.selection = None;
    }
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
        Doc {
            cp,
            cursor: 1.min(last.max(1)),
            beat: 1,
            undo_stack: Vec::new(),
            redo_stack: Vec::new(),
            clipboard: None,
            dirty: false,
            pending_repeat_start: None,
            pending_repeat_end: None,
            selection: None,
            sel_clipboard: None,
        }
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
        Doc {
            cp,
            cursor: 1,
            beat: 1,
            undo_stack: Vec::new(),
            redo_stack: Vec::new(),
            clipboard: None,
            dirty: false,
            pending_repeat_start: None,
            pending_repeat_end: None,
            selection: None,
            sel_clipboard: None,
        }
    }

    /// Сохранить цифровку в строку файла `.ips`/`.ipst` — как python
    /// `progression.to_json()` (app_io.py:160). Сам JSON печатает core
    /// (`persist.rs`, байтово сверен с python json.dumps).
    pub fn to_json(&self) -> String {
        self.cp.to_json()
    }

    /// Загрузить цифровку из строки файла `.ips`/`.ipst` — как python
    /// `ChordProgression.from_json` при открытии (app_io.py:223).
    /// Курсор — на такт 1 (python ставит Position(1,1)).
    pub fn from_json(json: &str) -> Result<Self, String> {
        let cp = ChordProgression::from_json(json)?;
        Ok(Doc {
            cp,
            cursor: 1,
            beat: 1,
            undo_stack: Vec::new(),
            redo_stack: Vec::new(),
            clipboard: None,
            dirty: false,
            pending_repeat_start: None,
            pending_repeat_end: None,
            selection: None,
            sel_clipboard: None,
        })
    }

    /// Последний такт документа (не ниже 1). Длина песни — это `total_measures`
    /// (как в python): у новой цифровки с шаблоном такты есть, даже если они
    /// пока пустые (метки/аккорды появятся при вводе).
    pub fn last_measure(&self) -> i32 {
        self.cp.last_measure().max(self.cp.total_measures).max(1)
    }

    /// Курсор вправо по тактам (Ctrl+→): линейный шаг на следующий такт,
    /// включая пустые. Не дальше конца документа. Доля сбрасывается на 1.
    pub fn go_right(&mut self) {
        let n = self.cursor + 1;
        if n <= self.last_measure() {
            self.cursor = n;
            self.beat = 1;
        }
    }

    /// Курсор влево по тактам (Ctrl+←): линейный шаг на предыдущий такт.
    pub fn go_left(&mut self) {
        if self.cursor > 1 {
            self.cursor -= 1;
            self.beat = 1;
        }
    }

    /// К следующей структурной метке (секция/вольта) после курсора
    /// (Ctrl+Alt+→, slice 12; раньше сидело на Alt).
    pub fn go_next_structural(&mut self) {
        let m = self.cp.navigate_next_structural(self.cursor);
        if m > self.cursor {
            self.cursor = m;
            self.beat = 1;
        }
    }

    /// К предыдущей структурной метке до курсора (Ctrl+Alt+←).
    pub fn go_prev_structural(&mut self) {
        let m = self.cp.navigate_prev_structural(self.cursor);
        if m < self.cursor {
            self.cursor = m;
            self.beat = 1;
        }
    }

    /// Привести `beat` в норму после правки такта: если доля больше не несёт
    /// аккорд (или такт опустел) — встать на первый аккорд такта / долю 1.
    fn clamp_beat(&mut self) {
        let chords = self.cp.find_chords_in_measure(self.cursor);
        if chords.is_empty() {
            self.beat = 1;
        } else if !chords.iter().any(|c| c.position.beat == self.beat) {
            self.beat = chords.first().map(|c| c.position.beat).unwrap_or(1);
        }
    }

    /// Простая стрелка вправо — по-мьюзскоровски, по событиям (slice 11):
    /// на следующий аккорд (в том числе на второй аккорд того же такта), а если
    /// аккордов впереди нет — на следующий пустой такт «в такт» (хвост/пауза).
    /// Возвращает true, если курсор сдвинулся. Калька python `navigate('right')`
    /// (by_measure=False) без виртуальных зон (у нас сетка физическая).
    pub fn go_chord_right(&mut self) -> bool {
        self.clamp_beat();
        let start_m = self.cursor;
        let start_b = self.beat;
        let pos = Position::new(self.cursor, self.beat, self.cp.time_signature);
        if let Some(next) = self.cp.find_next_chord_to_right(&pos) {
            self.cursor = next.position.measure;
            self.beat = next.position.beat;
        } else if self.cursor < self.last_measure() {
            self.cursor += 1;
            self.beat = 1;
        }
        self.cursor != start_m || self.beat != start_b
    }

    /// Простая стрелка влево — зеркально `go_chord_right`: на предыдущий
    /// аккорд (в том числе на первый аккорд того же такта). Из ПУСТОГО такта
    /// (ушли вправо по паузам) — шаг ровно на один такт назад, а не «магнит»
    /// к последнему аккорду за километр (msg 1607): право-влево по пустому
    /// хвосту ходит обратимо, по такту за нажатие.
    pub fn go_chord_left(&mut self) -> bool {
        let start_m = self.cursor;
        let start_b = self.beat;
        // Пустой такт — на предыдущий такт (как «обратная» правая стрелка).
        if self.cp.find_chords_in_measure(self.cursor).is_empty() {
            if self.cursor > 1 {
                self.cursor -= 1;
                self.beat = 1;
            }
            return self.cursor != start_m || self.beat != start_b;
        }
        let pos = Position::new(self.cursor, self.beat, self.cp.time_signature);
        if let Some(prev) = self.cp.find_last_chord_to_left(&pos) {
            self.cursor = prev.position.measure;
            self.beat = prev.position.beat;
        } else if self.cursor > 1 {
            self.cursor -= 1;
            self.beat = 1;
        }
        self.cursor != start_m || self.beat != start_b
    }

    /// Число долей в такте (размер такта) — граница шага Alt+стрелки.
    fn beats_per_measure(&self) -> i32 {
        self.cp.time_signature.numerator.max(1)
    }

    /// Alt+→ — по долям внутри такта, как MuseScore (slice 12): шаг на
    /// следующую долю, в том числе ПУСТУЮ — на неё потом можно вставить аккорд
    /// (Ctrl+Enter встаёт на долю курсора). С последней доли такта — на долю 1
    /// следующего такта; за концом документа шаг не сдвигает. Долю НЕ зажимает
    /// к аккордам (в отличие от go_chord_right) — цель удержать позицию на
    /// пустой доле. Возвращает true, если позиция сдвинулась.
    pub fn go_beat_right(&mut self) -> bool {
        let m0 = self.cursor;
        let b0 = self.beat;
        if self.beat < self.beats_per_measure() {
            self.beat += 1;
        } else if self.cursor < self.last_measure() {
            self.cursor += 1;
            self.beat = 1;
        }
        self.cursor != m0 || self.beat != b0
    }

    /// Alt+← — зеркально `go_beat_right`: с первой доли такта на последнюю долю
    /// предыдущего; за началом документа не сдвигает.
    pub fn go_beat_left(&mut self) -> bool {
        let m0 = self.cursor;
        let b0 = self.beat;
        if self.beat > 1 {
            self.beat -= 1;
        } else if self.cursor > 1 {
            self.cursor -= 1;
            self.beat = self.beats_per_measure();
        }
        self.cursor != m0 || self.beat != b0
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

    /// Озвучка клетки «позиция» — что слышится при шаге внутрь такта (Alt+←/→
    /// по долям, шаг на соседний аккорд того же такта). Аккорд первым, без
    /// запятых: «Ми бемоль 7 такт 1 доля 1» (msg 1598). На пустой доле —
    /// «такт N доля M пусто» (туда можно вставить аккорд); на такте N.C.
    /// аккордовая сетка не редактируется — целиком такт.
    pub fn announce_beat_cell(&self) -> String {
        let v = self.measure_view(self.cursor);
        if v.no_chord {
            return self.announce_measure(self.cursor);
        }
        if let Some(c) = v.chords.iter().find(|c| c.beat == self.beat) {
            format!("{} такт {} доля {}", c.spoken.trim(), self.cursor, self.beat)
        } else {
            format!("такт {} доля {} пусто", self.cursor, self.beat)
        }
    }

    /// Озвучка после простого шага стрелкой (`go_chord_left/right`): всегда
    /// позиция-клетка «аккорд такт N доля M» — и внутри такта, и при переходе
    /// на новый такт (msg 1602: «пусть озвучивает так же текущий элемент, а не
    /// блин весь такт»). `from_measure` оставлен для совместимости вызова.
    pub fn announce_after_chord_step(&self, _from_measure: i32) -> String {
        self.announce_beat_cell()
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

// ===========================================================================
// Редактирование «клетки такта» (slice 5) — калька python app_io/main.py.
//
// Курсор у Doc — (такт, доля): с slice 12 правки доля-точные (msg 1598) —
// редактирование/копирование/удаление адресуют аккорд НА доле курсора, а
// вставка и вставка-из-буфера кладут аккорд на долю курсора (в т.ч. пустую —
// на неё курсор ставят Alt+←/→). Возврат
// каждого метода — готовая строка для озвучки (что проговорить одним вызовом
// NVDA); пустая строка = молчание (например, диалог вставки не меняет имя —
// python тоже ничего не говорит). Стек undo/redo, буфер обмена и dirty — как
// в python (main.py `_undo_stack`/`_redo_stack`/`_clipboard`).
// ===========================================================================

/// Репетиционные метки по буквам клавиатуры — как python `SECTION_KEYS`
/// (chords.py:358): a/b/c/d → *A..*D, v → *V, i → *i, s → Segno, q → Coda,
/// f → Fine. Строчные и прописные принимаются.
pub fn section_mark_from_letter(letter: char) -> Option<&'static str> {
    match letter.to_ascii_lowercase() {
        'a' => Some("*A"),
        'b' => Some("*B"),
        'c' => Some("*C"),
        'd' => Some("*D"),
        'v' => Some("*V"),
        'i' => Some("*i"),
        's' => Some("S"),
        'q' => Some("Q"),
        'f' => Some("f"),
        _ => None,
    }
}

/// Русское имя метки для озвучки — как python `_section_name` (main.py:1580):
/// `*A` → «Часть A», `*i` → «Вступление», `S` → «Сеньо» и т.д.
pub fn section_display_name(mark: &str) -> String {
    match mark {
        "*A" => "Часть A".to_string(),
        "*B" => "Часть B".to_string(),
        "*C" => "Часть C".to_string(),
        "*D" => "Часть D".to_string(),
        "*V" => "Куплет".to_string(),
        "*i" => "Вступление".to_string(),
        "S" => "Сеньо".to_string(),
        "Q" => "Кода".to_string(),
        "f" => "Фине".to_string(),
        other => other.to_string(),
    }
}

/// Суффикс «(удалён N скрытый аккорд)» после создания вольты — как python
/// ngettext (chords.py): когда скрытый диапазон (тело повтора) содержал
/// аккорды, они удаляются, и это озвучивается. `cleared == 0` → пусто.
/// Русская плюрализация по правилам gettext (locales/ru/.../irealstudio.po):
/// 1 → «удалён 1 скрытый аккорд», 2–4 → «удалено 2 скрытых аккорда»,
/// 5+ → «удалено 5 скрытых аккордов».
fn hidden_removed_suffix(cleared: usize) -> String {
    if cleared == 0 {
        return String::new();
    }
    let n = cleared as i64;
    let n10 = n % 10;
    let n100 = n % 100;
    let word = if n10 == 1 && n100 != 11 {
        "скрытый аккорд"
    } else if (2..=4).contains(&n10) && !(12..=14).contains(&n100) {
        "скрытых аккорда"
    } else {
        "скрытых аккордов"
    };
    let verb = if n10 == 1 && n100 != 11 {
        "удалён"
    } else {
        "удалено"
    };
    format!(" ({verb} {n} {word})")
}

/// Озвучка созданной вольты: «Реприза с такта {rs}, вольта 1: {vs}–{e1e},
/// вольта 2 начинается с такта {e2s}» + суффикс об удалённых скрытых аккордах
/// — как python _() из chords.py (add_volta_start/add_volta_bracket).
fn repeat_from_message(rs: i32, vs: i32, e1e: i32, e2s: i32, cleared: usize) -> String {
    let mut msg = format!(
        "Реприза с такта {rs}, вольта 1: {vs}–{e1e}, вольта 2 начинается с такта {e2s}"
    );
    msg.push_str(&hidden_removed_suffix(cleared));
    msg
}

/// Допустимые написания басовой ноты (слэш-бас). Шире python `NOTE_NAMES`
/// (там только натуральные/бемольные): принимаем все хроматические написания —
/// диезные тоже, чтобы диалог не отклонял осмысленный ввод.
pub const BASS_SPELLINGS: [&str; 17] = [
    "C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B",
];

/// Корни для выбора тональности — как python `KEY_ROOT_NOTES` (dialogs.py):
/// 12 энгармонически «бемольных» написаний.
pub const KEY_ROOTS: [&str; 12] = [
    "C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B",
];

/// iReal-имя минора по корню — python `_MINOR_KEY_MAP` (dialogs.py:31):
/// бемольный корень → диезное имя минора (Db→C#-), остальные → «{root}-».
pub const ROOT_MINOR: [(&str, &str); 12] = [
    ("C", "C-"),
    ("Db", "C#-"),
    ("D", "D-"),
    ("Eb", "Eb-"),
    ("E", "E-"),
    ("F", "F-"),
    ("Gb", "F#-"),
    ("G", "G-"),
    ("Ab", "G#-"),
    ("A", "A-"),
    ("Bb", "Bb-"),
    ("B", "B-"),
];

/// Собрать iReal-имя тональности из корня и лада — как python
/// `root_mode_to_key` (dialogs.py): мажор = корень как есть; минор — из
/// ROOT_MINOR (неизвестный корень → «{root}-»).
pub fn key_from_root_mode(root: &str, minor: bool) -> String {
    if minor {
        ROOT_MINOR
            .iter()
            .find(|(r, _)| *r == root)
            .map(|(_, k)| k.to_string())
            .unwrap_or_else(|| format!("{root}-"))
    } else {
        root.to_string()
    }
}

/// Разобрать iReal-имя тональности на (корень, лад) для диалога — обратная к
/// `key_from_root_mode`. «B-» → («B», минор), «C#-» → («Db», минор), «Bb» →
/// («Bb», мажор). Незнакомый ключ → («C», мажор).
pub fn key_to_root_mode(key: &str) -> (String, bool) {
    if let Some(stripped) = key.strip_suffix('-') {
        for (r, k) in ROOT_MINOR {
            if k == key {
                return (r.to_string(), true);
            }
        }
        // Минора из знакомой таблицы нет (напр. файл с диезным корнем) —
        // берём корень как записан.
        (stripped.to_string(), true)
    } else if KEY_ROOTS.contains(&key) {
        (key.to_string(), false)
    } else {
        ("C".to_string(), false)
    }
}

/// Поля формы «Настройки цифровки» (Ctrl+P) — калька python
/// `project_settings_dialog` (dialogs.py:562). `time_sig` — строка вида «4/4».
#[derive(Clone, Default)]
pub struct ProjectSettings {
    pub title: String,
    pub composer: String,
    pub bpm: i32,
    pub key: String,
    pub style: String,
    pub time_sig: String,
}

impl ProjectSettings {
    /// Значения по умолчанию для формы: текущие поля прогрессии.
    pub fn from_cp(cp: &ChordProgression) -> Self {
        ProjectSettings {
            title: cp.title.clone(),
            composer: cp.composer.clone(),
            bpm: cp.bpm,
            key: cp.key.clone(),
            style: cp.style.clone(),
            time_sig: cp.time_signature.to_string(),
        }
    }
}

/// Разобрать «4/4» на размер такта. Не «N/D» двумя целыми → None (как python,
/// который ловит ValueError/AttributeError и молча пропускает).
fn parse_time_sig(s: &str) -> Option<TimeSignature> {
    let mut it = s.trim().split('/');
    let num: i32 = it.next()?.trim().parse().ok()?;
    let den: i32 = it.next()?.trim().parse().ok()?;
    if it.next().is_some() || num < 1 || den < 1 {
        return None;
    }
    Some(TimeSignature::new(num, den))
}

impl Doc {
    /// Виртуальный такт → реальный (для правок внутри повторов/вольт), как
    /// python `progression.resolve_virtual_measure(cursor.measure)`.
    fn real_measure(&self) -> i32 {
        self.cp.resolve_virtual_measure(self.cursor)
    }

    /// Аккорд на доле курсора реального такта — «активная клетка» (slice 12).
    /// Точность по доле: F2/копирование/удаление действуют на аккорд ПОД
    /// КУРСОРОМ, а не на первый в такте (msg 1598). None — на доле аккорда нет.
    fn active_chord(&self) -> Option<(i32 /*real_m*/, i32 /*beat*/, String, String)> {
        let m = self.real_measure();
        let ts = self.cp.time_signature;
        let pos = Position::new(m, self.beat, ts);
        self.cp.find_chords_at_position(&pos).into_iter().next().map(|it| {
            (
                m,
                it.position.beat,
                it.chord.name().to_string(),
                it.bass_note.clone(),
            )
        })
    }

    /// Имя и слэш-бас аккорда под курсором — дефолт форм вставки/правки
    /// (как python берёт текущий аккорд для предзаполнения). None — такт пуст.
    pub fn chord_under_cursor(&self) -> Option<(String, String)> {
        self.active_chord().map(|(_m, _beat, name, bass)| (name, bass))
    }

    // =======================================================================
    // Ввод с валидацией (слайс 14, #46/#50) — гейты для диалогов ввода аккорда.
    // =======================================================================

    /// Полный символ аккорда для предзаполнения форм: имя + слэш-бас
    /// («Bb7/G»). Именно полный символ редактирует F2 (msg 1607: «пишет Bb7,
    /// а не Bb7/G — не изменить бас»).
    pub fn full_symbol(name: &str, bass: &str) -> String {
        if bass.is_empty() {
            name.to_string()
        } else {
            format!("{name}/{bass}")
        }
    }

    /// Текст ошибки ввода (что говорить пользователю — стиль «Ошибка: …»).
    fn entry_error(e: ChordEntryError, raw: &str) -> String {
        match e {
            ChordEntryError::Empty => String::new(),
            ChordEntryError::Bass => format!(
                "Ошибка: «{raw}» — после / не нота или такой ноты не существует"
            ),
            ChordEntryError::Root | ChordEntryError::Quality => {
                format!("Ошибка: аккорд «{raw}» не существует в iReal Pro")
            }
        }
    }

    /// Вставить аккорд по полному символу (можно со слэш-басом) — гейт ввода:
    /// корень и функция обязаны существовать в iReal Pro (msg 1607). Невалидный
    /// ввод не попадает в цифровку — возвращается «Ошибка: …». Имена
    /// канонизируются: «B-7» хранится как «Bm7» (запись python/.ips).
    pub fn insert_chord_entry(&mut self, raw: &str) -> String {
        let raw = raw.trim().to_string();
        match parse_chord_entry(&raw) {
            Err(ChordEntryError::Empty) => String::new(),
            Err(e) => Self::entry_error(e, &raw),
            Ok(pc) => {
                let bass = pc.bass.unwrap_or_default();
                let base = self.insert_chord(&pc.name, &bass);
                // insert_chord говорит только имя — при слэш-басе озвучиваем
                // полный символ («Вставлен аккорд: Bb7/G»), как ввёл пользователь.
                if bass.is_empty() {
                    base
                } else {
                    format!("Вставлен аккорд: {}", Self::full_symbol(&pc.name, &bass))
                }
            }
        }
    }

    /// Отредактировать аккорд по полному символу (имя и/или слэш-бас) — гейт
    /// F2 (#50). Правка меняет и имя, и бас (раньше бас сохранялся, изменить
    /// его было нельзя). Имя не изменилось → молчание (как python).
    pub fn edit_chord_entry(&mut self, raw: &str) -> String {
        let raw = raw.trim().to_string();
        match self.active_chord() {
            None => "Нет аккорда для редактирования".to_string(),
            Some((m, beat, old_name, old_bass)) => {
                let old_symbol = Self::full_symbol(&old_name, &old_bass);
                if raw.is_empty() || raw == old_symbol {
                    return String::new();
                }
                match parse_chord_entry(&raw) {
                    Err(ChordEntryError::Empty) => String::new(),
                    Err(e) => Self::entry_error(e, &raw),
                    Ok(pc) => {
                        let bass = pc.bass.unwrap_or_default();
                        self.push_undo();
                        self.cp.add_chord_by_name(&pc.name, m, beat, &bass);
                        self.dirty = true;
                        format!(
                            "Аккорд отредактирован: {}",
                            Self::full_symbol(&pc.name, &bass)
                        )
                    }
                }
            }
        }
    }

    // =======================================================================
    // Выделение Shift+стрелки (слайс 14, #52) — порт python main.py:1025.
    // =======================================================================

    /// Глобальный номер доли (0-based от начала песни) — python
    /// `Position.beat_from_start`. Используется для смещений мульти-буфера.
    fn bfs(&self, m: i32, b: i32) -> i64 {
        let bpm = self.cp.time_signature.numerator.max(1) as i64;
        (m as i64 - 1) * bpm + b as i64 - 1
    }

    /// Обратно из глобальной доли в (такт, доля).
    fn measure_beat_of(&self, bfs: i64) -> (i32, i32) {
        let bpm = self.cp.time_signature.numerator.max(1) as i64;
        let m = bfs / bpm;
        let b = bfs % bpm;
        ((m + 1) as i32, (b + 1) as i32)
    }

    /// Реальные аккорды внутри нормированного диапазона выделения, вместе с
    /// их физическими (такт, доля). Виртуальные повторы не разворачиваем
    /// (сетка физическая; повтор-зоны — отдельный слайс).
    fn chords_in_range(
        &self,
        start: (i32, i32),
        end: (i32, i32),
    ) -> Vec<(i32, i32, String, String)> {
        let (sm, sb) = start;
        let (em, eb) = end;
        let mut out: Vec<(i32, i32, String, String)> = Vec::new();
        for m in sm..=em {
            for it in self.cp.find_chords_in_measure(m) {
                let b = it.position.beat;
                let inside = if m == sm && m == em {
                    b >= sb && b <= eb
                } else if m == sm {
                    b >= sb
                } else if m == em {
                    b <= eb
                } else {
                    true
                };
                if inside {
                    out.push((m, b, it.chord.name().to_string(), it.bass_note.clone()));
                }
            }
        }
        out
    }

    /// Аккорды активного выделения + глобальная доля первого из них (якорь
    /// смещений мульти-буфера). None — выделения нет или в нём нет аккордов.
    fn chords_in_selection(&self) -> Option<(Vec<(i32, i32, String, String)>, i64)> {
        let sr = self.selection?;
        let (start, end) = sr.normalized();
        let chords = self.chords_in_range(start, end);
        if chords.is_empty() {
            return None;
        }
        let anchor_bfs = self.bfs(chords[0].0, chords[0].1);
        Some((chords, anchor_bfs))
    }

    /// Слово «аккорд» по числу (1/2/5) — русская плюрализация.
    fn chord_word(n: usize) -> String {
        let n10 = n % 10;
        let n100 = n % 100;
        if n10 == 1 && n100 != 11 {
            "аккорд".to_string()
        } else if n10 >= 2 && n10 <= 4 && !(n100 >= 12 && n100 <= 14) {
            "аккорда".to_string()
        } else {
            "аккордов".to_string()
        }
    }

    /// Озвучка выделения: ведущий аккорд (на активном крае) + число.
    pub fn selection_announce(&self) -> String {
        let Some(sr) = self.selection else {
            return String::new();
        };
        let Some((chords, _)) = self.chords_in_selection() else {
            return "Нет аккордов в выделении".to_string();
        };
        let n = chords.len();
        // Аккорд на активном крае (под курсором), иначе первый в диапазоне.
        let edge_pos = (sr.b_m, sr.b_b);
        let edge_name = chords
            .iter()
            .find(|(m, b, _, _)| (*m, *b) == edge_pos)
            .or_else(|| chords.first())
            .map(|(_, _, name, _)| name.clone())
            .unwrap_or_default();
        let lead = if edge_name.is_empty() {
            String::new()
        } else {
            format!("{} — ", chord_name_to_spoken(&edge_name, ""))
        };
        format!("{lead}выделено: {n} {}", Self::chord_word(n))
    }

    /// Взять якорь, если выделения ещё нет (первое нажатие Shift+стрелка).
    fn start_selection(&mut self) {
        if self.selection.is_none() {
            self.selection =
                Some(SelRange::new(self.cursor, self.beat, self.cursor, self.beat));
        }
    }

    /// Передвинуть активный край выделения на курсор.
    fn refresh_selection(&mut self) {
        if let Some(s) = self.selection.as_mut() {
            s.b_m = self.cursor;
            s.b_b = self.beat;
        }
    }

    /// Shift+←/→ по аккордам: расширяет выделение тем же движением, что и
    /// простая стрелка. Озвучка — диапазон («… выделено: N аккордов»).
    pub fn extend_chord_step(&mut self, left: bool) -> String {
        self.start_selection();
        let moved = if left {
            self.go_chord_left()
        } else {
            self.go_chord_right()
        };
        if !moved {
            return String::new();
        }
        self.refresh_selection();
        self.selection_announce()
    }

    /// Shift+Ctrl+←/→ по тактам (включая пустые).
    pub fn extend_measure_step(&mut self, left: bool) -> String {
        self.start_selection();
        let before = self.cursor;
        if left {
            self.go_left();
        } else {
            self.go_right();
        }
        if self.cursor == before {
            return String::new();
        }
        self.refresh_selection();
        self.selection_announce()
    }

    /// Shift+Alt+←/→ по долям (включая пустые).
    pub fn extend_beat_step(&mut self, left: bool) -> String {
        self.start_selection();
        let moved = if left {
            self.go_beat_left()
        } else {
            self.go_beat_right()
        };
        if !moved {
            return String::new();
        }
        self.refresh_selection();
        self.selection_announce()
    }

    /// Shift+Ctrl+Alt+←/→ по секциям/вольтам.
    pub fn extend_section_step(&mut self, left: bool) -> String {
        self.start_selection();
        let before = self.cursor;
        if left {
            self.go_prev_structural();
        } else {
            self.go_next_structural();
        }
        if self.cursor == before {
            return String::new();
        }
        self.refresh_selection();
        self.selection_announce()
    }

    /// Выделить всю цифровку от первого до последнего аккорда (python
    /// `_select_all`, main.py:1217): якорь — первый аккорд, активный край —
    /// последний, курсор в конец диапазона. Ctrl+C после этого копирует весь
    /// документ мульти-блоком; в пустой цифровке — сообщение, ничего не трогаем.
    pub fn select_all(&mut self) -> String {
        let first = self.cp.items.first().map(|i| (i.position.measure, i.position.beat));
        let last = self.cp.items.last().map(|i| (i.position.measure, i.position.beat));
        let (Some((fm, fb)), Some((lm, lb))) = (first, last) else {
            return "Нет аккордов для выделения".to_string();
        };
        self.selection = Some(SelRange::new(fm, fb, lm, lb));
        self.cursor = lm;
        self.beat = lb;
        self.selection_announce()
    }

    // =======================================================================
    // Буфер обмена выделения (Ctrl+C/X, Del) + вставка блока (Ctrl+V).
    // =======================================================================

    /// Скопировать выделение в буфер: один аккорд — одиночный `clipboard`,
    /// несколько — мульти-блок `sel_clipboard` со смещениями (python
    /// `_copy_selection`, main.py:1228). Без выделения — одиночное копирование.
    fn copy_selection(&mut self) -> String {
        let Some((chords, anchor_bfs)) = self.chords_in_selection() else {
            return String::new();
        };
        if chords.len() == 1 {
            let (_, _, name, bass) = &chords[0];
            self.clipboard = Some(ClipboardItem {
                name: name.clone(),
                bass: bass.clone(),
            });
            self.sel_clipboard = None;
            format!("Скопировано: {name}")
        } else {
            let block = chords
                .iter()
                .map(|(m, b, name, bass)| SelChord {
                    bfs_offset: self.bfs(*m, *b) - anchor_bfs,
                    name: name.clone(),
                    bass: bass.clone(),
                })
                .collect();
            self.sel_clipboard = Some(block);
            self.clipboard = None;
            let n = chords.len();
            format!("Скопировано: {n} {}", Self::chord_word(n))
        }
    }

    /// Вырезать выделение (копия + удаление реальных аккордов) — python
    /// `_cut_selection` (main.py:1251). None → одиночное вырезание.
    fn cut_selection(&mut self) -> String {
        let Some((chords, anchor_bfs)) = self.chords_in_selection() else {
            return String::new();
        };
        if chords.len() == 1 {
            let (_, _, name, bass) = &chords[0];
            self.clipboard = Some(ClipboardItem {
                name: name.clone(),
                bass: bass.clone(),
            });
            self.sel_clipboard = None;
            self.remove_chords_at(&chords);
            let msg = format!("Вырезано: {name}");
            self.after_selection_removal();
            msg
        } else {
            let block = chords
                .iter()
                .map(|(m, b, name, bass)| SelChord {
                    bfs_offset: self.bfs(*m, *b) - anchor_bfs,
                    name: name.clone(),
                    bass: bass.clone(),
                })
                .collect();
            self.sel_clipboard = Some(block);
            self.clipboard = None;
            let n = chords.len();
            self.remove_chords_at(&chords);
            let msg = format!("Вырезано: {n} {}", Self::chord_word(n));
            self.after_selection_removal();
            msg
        }
    }

    /// Удалить выделение (без копирования) — python `_delete_selection`
    /// (main.py:1288). Курсор — на последний аккорд перед диапазоном.
    pub fn delete_selection(&mut self) -> String {
        let Some((chords, _)) = self.chords_in_selection() else {
            self.clear_selection();
            return "Нет аккордов в выделении".to_string();
        };
        let n = chords.len();
        self.remove_chords_at(&chords);
        let msg = format!("Удалено: {n} {}", Self::chord_word(n));
        self.after_selection_removal();
        msg
    }

    /// Снять аккорды диапазона (один undo на весь блок).
    fn remove_chords_at(&mut self, chords: &[(i32, i32, String, String)]) {
        self.push_undo();
        for (m, b, _, _) in chords {
            let pos = Position::new(*m, *b, self.cp.time_signature);
            self.cp.delete_chord_at(&pos);
        }
        self.dirty = true;
    }

    /// После вырезания/удаления диапазона: курсор — последний аккорд слева от
    /// старта, выделение снято.
    fn after_selection_removal(&mut self) {
        let start_pos = self
            .selection
            .and_then(|sr| Some(sr.normalized().0))
            .map(|(m, b)| Position::new(m, b, self.cp.time_signature));
        self.clear_selection();
        match start_pos {
            Some(pos) => {
                if let Some(prev) = self.cp.find_last_chord_to_left(&pos) {
                    let it = prev.clone();
                    self.cursor = it.position.measure;
                    self.beat = it.position.beat;
                } else {
                    self.cursor = 1;
                    self.beat = 1;
                }
            }
            None => {
                self.cursor = 1;
                self.beat = 1;
            }
        }
    }

    /// Вставить мульти-блок выделения с долей курсора как якорем; без блока
    /// возвращает None (дальше — одиночная вставка).
    fn paste_selection_block(&mut self) -> Option<String> {
        let block: Vec<(i64, String, String)> = self
            .sel_clipboard
            .as_ref()?
            .iter()
            .map(|sc| (sc.bfs_offset, sc.name.clone(), sc.bass.clone()))
            .collect();
        if block.is_empty() {
            return Some("Буфер обмена пуст".to_string());
        }
        let target_bfs = self.bfs(self.real_measure(), self.beat);
        self.push_undo();
        for (offset, name, bass) in &block {
            let (m, b) = self.measure_beat_of(target_bfs + offset);
            self.cp.add_chord_by_name(name, m, b, bass);
        }
        self.dirty = true;
        let n = block.len();
        Some(format!("Вставлено: {n} {}", Self::chord_word(n)))
    }

    /// Снимок прогрессии в стек undo (с дедупликацией и потолком), чистит redo.
    fn push_undo(&mut self) {
        let snapshot = self.cp.to_json();
        if self.undo_stack.last() == Some(&snapshot) {
            return;
        }
        self.undo_stack.push(snapshot);
        if self.undo_stack.len() > UNDO_MAX {
            self.undo_stack.remove(0);
        }
        self.redo_stack.clear();
    }

    /// Текущий такт перестаёт быть «изменённым» (после сохранения/открытия).
    pub fn mark_clean(&mut self) {
        self.dirty = false;
    }

    /// Отменить последнюю правку — как python `undo()` (main.py:748): снимок
    /// возвращается из стека, курсор зажимается в конец документа.
    pub fn undo(&mut self) -> String {
        if self.undo_stack.is_empty() {
            return "Нечего отменить".to_string();
        }
        self.redo_stack.push(self.cp.to_json());
        let snapshot = self.undo_stack.pop().unwrap();
        if let Ok(cp) = ChordProgression::from_json(&snapshot) {
            self.cp = cp;
        }
        let last = self.cp.last_measure().max(1);
        self.cursor = self.cursor.min(last).max(1);
        self.clamp_beat();
        // python undo() сбрасывает pending-маркеры повтора (main.py:759).
        self.pending_repeat_start = None;
        self.pending_repeat_end = None;
        self.dirty = true;
        "Отменено".to_string()
    }

    /// Вернуть отменённую правку — как python `redo()` (main.py:763).
    pub fn redo(&mut self) -> String {
        if self.redo_stack.is_empty() {
            return "Нечего повторить".to_string();
        }
        self.undo_stack.push(self.cp.to_json());
        let snapshot = self.redo_stack.pop().unwrap();
        if let Ok(cp) = ChordProgression::from_json(&snapshot) {
            self.cp = cp;
        }
        // python redo() тоже сбрасывает pending-маркеры повтора (main.py:770).
        self.pending_repeat_start = None;
        self.pending_repeat_end = None;
        self.dirty = true;
        self.clamp_beat();
        "Повторено".to_string()
    }

    /// Вставить аккорд по имени НА ДОЛЮ КУРСОРА (slice 12): заменяет аккорд на
    /// той же доле (core `add_chord_raw`), а на пустой доле — кладёт новый — как
    /// python `_insert_chord_from_menu` (app_io.py:629), который ставил на долю 1.
    /// Возвращает «Вставлен аккорд: …».
    pub fn insert_chord(&mut self, name: &str, bass: &str) -> String {
        let name = name.trim().to_string();
        if name.is_empty() {
            return String::new();
        }
        let m = self.real_measure();
        let b = self.beat.clamp(1, self.beats_per_measure());
        self.push_undo();
        self.cp.add_chord_by_name(&name, m, b, bass);
        self.dirty = true;
        format!("Вставлен аккорд: {name}")
    }

    /// Отредактировать аккорд под курсором (F2) — как python
    /// `_edit_chord_in_place` (app_io.py:638). Имя не изменилось → молчание.
    /// Существующий слэш-бас сохраняется.
    pub fn edit_chord(&mut self, name: &str) -> String {
        let name = name.trim().to_string();
        match self.active_chord() {
            None => "Нет аккорда для редактирования".to_string(),
            Some((m, beat, old, bass)) => {
                if name.is_empty() || name == old {
                    return String::new();
                }
                self.push_undo();
                self.cp.add_chord_by_name(&name, m, beat, &bass);
                self.dirty = true;
                format!("Аккорд отредактирован: {name}")
            }
        }
    }

    /// Поставить N.C. на такте — только СТАВИТ, повторное нажатие не убирает
    /// (msg 1607: «nc можно не убирать по второму нажатию»). Снятие — через
    /// Backspace (Delete структурного такта `delete_structure_at_measure`).
    /// Держим имя метода `toggle_no_chord` ради совместимости вызова (клавиша
    /// N / меню «Вставить N.C.»).
    pub fn toggle_no_chord(&mut self) -> String {
        let m = self.real_measure();
        if self.cp.is_no_chord(m) {
            return format!("N.C. уже стоит в такте {m}");
        }
        self.push_undo();
        self.cp.add_no_chord(m);
        self.dirty = true;
        format!("N.C. в такте {m}")
    }

    /// Скопировать аккорд/выделение под курсором — как python `copy_chord`
    /// (main.py:778), который при активном выделении копирует ВЕСЬ диапазон
    /// (Ctrl+C больше не берёт только первый аккорд — #52).
    pub fn copy_chord(&mut self) -> String {
        if self.selection.is_some() {
            let msg = self.copy_selection();
            if !msg.is_empty() {
                return msg;
            }
            return "Нет аккордов в выделении".to_string();
        }
        match self.active_chord() {
            Some((_m, _beat, name, bass)) => {
                self.clipboard = Some(ClipboardItem {
                    name: name.clone(),
                    bass,
                });
                format!("Скопировано: {name}")
            }
            None => "Нет аккорда под курсором".to_string(),
        }
    }

    /// Вырезать аккорд/выделение — как python `cut_chord` (main.py:791):
    /// копирует в буфер (одиночный аккорд или блок диапазона) и удаляет из
    /// прогрессии. При активном выделении — вырезает весь диапазон (#52).
    pub fn cut_chord(&mut self) -> String {
        if self.selection.is_some() {
            let msg = self.cut_selection();
            if !msg.is_empty() {
                return msg;
            }
            self.clear_selection();
            return "Нет аккордов в выделении".to_string();
        }
        match self.active_chord() {
            Some((m, beat, name, bass)) => {
                self.clipboard = Some(ClipboardItem {
                    name: name.clone(),
                    bass: bass.clone(),
                });
                self.push_undo();
                let pos = Position::new(m, beat, self.cp.time_signature);
                self.cp.delete_chord_at(&pos);
                self.dirty = true;
                self.clamp_beat();
                format!("Вырезано: {name}")
            }
            None => "Нет аккорда под курсором".to_string(),
        }
    }

    /// Вставить аккорд из буфера на долю курсора (slice 12) — как python
    /// `paste_chord` (main.py:807), который клеил на долю 1. Буфер НЕ очищается
    /// (python читает и хранит дальше) — повторный Ctrl+V клеит тот же аккорд
    /// в следующий такт/долю. В отличие от python сохраняет и слэш-бас. Если в
    /// буфере блок выделения (#52) — вставляет весь блок с внутренней геометрией.
    pub fn paste_chord(&mut self) -> String {
        if let Some(msg) = self.paste_selection_block() {
            return msg;
        }
        let Some(item) = self.clipboard.as_ref() else {
            return "Буфер обмена пуст".to_string();
        };
        let name = item.name.clone();
        let bass = item.bass.clone();
        let m = self.real_measure();
        let b = self.beat.clamp(1, self.beats_per_measure());
        self.push_undo();
        self.cp.add_chord_by_name(&name, m, b, &bass);
        self.dirty = true;
        format!("Вставлено: {name}")
    }

    /// Добавить басовую ноту (слэш-бас) к аккорду под курсором, а если такт
    /// пуст — к последнему аккорду слева — как python `add_bass_note`
    /// (main.py:1648). Говорит озвученный аккорд с новым басом.
    pub fn add_bass_note(&mut self, root: &str) -> String {
        // Канонизация через core: регистронезависимо («e», «bb»), бемоли и
        // диезы как в словаре ALL_ROOTS. Одна нота — иначе «Неверная нота».
        let Some(note) = normalize_bass_note(root) else {
            return "Неверная нота".to_string();
        };
        // Аккорд под курсором, иначе последний слева (в т.ч. через повторы).
        let (m, beat, name) = match self.active_chord() {
            Some((m, beat, name, _bass)) => (m, beat, name),
            None => {
                // От позиции курсора (такт+доля), чтобы аккорд на доле раньше
                // в том же такте имел приоритет перед аккордом прошлого такта.
                let ts = self.cp.time_signature;
                let pos = Position::new(self.cursor, self.beat, ts);
                match self.cp.find_last_chord_to_left(&pos) {
                    Some(item) => {
                        let it = item.clone();
                        (it.position.measure, it.position.beat, it.chord.name().to_string())
                    }
                    None => return "Нет аккорда для изменения".to_string(),
                }
            }
        };
        let _ = m;
        self.push_undo();
        self.cp.add_chord_by_name(&name, m, beat, &note);
        self.dirty = true;
        chord_name_to_spoken(&name, &note)
    }

    /// Удалить аккорд/структуру на такте под курсором (Del/Backspace) — как
    /// python `delete_at_cursor` (main.py:1714). Если активно выделение — удаляет
    /// выделенный диапазон. Если под курсором аккорд — снимает его и говорит
    /// «Удалено. <клетка под курсором>», курсор ОСТАЁТСЯ на той же доле (#48:
    /// «удалил аккорд в доле 3 — остаёмся в доле 3, там пустота, а не чёрная
    /// дыра»; ни магнита к доле 1, ни перескока к предыдущему аккорду). Иначе
    /// снимает метку секции/знак повтора/N.C. и говорит что удалено.
    pub fn delete_at_cursor(&mut self) -> String {
        if self.selection.is_some() {
            return self.delete_selection();
        }
        match self.active_chord() {
            Some((m, beat, _name, _bass)) => {
                let pos = Position::new(m, beat, self.cp.time_signature);
                self.push_undo();
                self.cp.delete_chord_at(&pos);
                self.dirty = true;
                format!("Удалено. {}", self.announce_beat_cell())
            }
            None => self.delete_structure_at_measure(self.real_measure()),
        }
    }

    /// Удалить структуру на такте (Ctrl+Del/Ctrl+Backspace) — как python
    /// `delete_structural_at_cursor` (main.py:1772): метку секции, знак повтора
    /// и N.C., игнорируя аккорд. Возвращает, что именно удалено.
    pub fn delete_structural_at_cursor(&mut self) -> String {
        self.delete_structure_at_measure(self.cursor)
    }

    /// Общая часть структурного удаления (по реальному или виртуальному такту).
    fn delete_structure_at_measure(&mut self, m: i32) -> String {
        let mut deleted: Vec<&'static str> = Vec::new();
        if self.cp.get_section_mark(m).is_some() {
            self.push_undo();
            self.cp.remove_section_mark(m);
            self.dirty = true;
            deleted.push("метка части");
        }
        let vbs_to_remove: Vec<i32> = self
            .cp
            .volta_brackets
            .iter()
            .filter(|vb| {
                vb.repeat_start == m
                    || vb.ending1_start == m
                    || (vb.is_complete() && vb.ending2_start == m)
            })
            .map(|vb| vb.repeat_start)
            .collect();
        if !vbs_to_remove.is_empty() {
            if deleted.is_empty() {
                self.push_undo();
            }
            for rs in vbs_to_remove {
                self.cp.volta_brackets.retain(|vb| vb.repeat_start != rs);
            }
            self.dirty = true;
            deleted.push("знак повтора");
        }
        if self.cp.is_no_chord(m) {
            if deleted.is_empty() {
                self.push_undo();
            }
            self.cp.remove_no_chord(m);
            self.dirty = true;
            deleted.push("N.C.");
        }
        if deleted.is_empty() {
            format!("Нечего удалить в такте {m} доле 1")
        } else {
            format!("Удалено: {} в такте {m}", deleted.join(", "))
        }
    }

    /// Поставить репетиционную метку на такте под курсором по букве клавиатуры
    /// (Ctrl+Shift+letter) — как python `add_section_mark` (main.py:1639).
    /// Неизвестная буква → молчание. Говорит «Часть A в такте {m}» и т.п.
    pub fn add_section_mark_by_letter(&mut self, letter: char) -> String {
        let Some(mark) = section_mark_from_letter(letter) else {
            return String::new();
        };
        self.push_undo();
        self.cp.add_section_mark(self.cursor, mark);
        self.dirty = true;
        format!(
            "{} в такте {}",
            section_display_name(mark),
            self.cursor
        )
    }

    // -------------------------------------------------------------------
    // Создание вольт / повторов (slice 7) — клавиши [, ] и V.
    // -------------------------------------------------------------------
    //
    // Калька python (main.py:1667-1712 + chords.py add_repeat_bracket/
    // add_volta_bracket/add_volta_start):
    //   [  — отметить начало повтора на текущем такте (сброс старого конца);
    //   ]  — отметить конец и сразу создать обычный повтор [start–end];
    //   V  — вольта: если заданы и начало, и конец — превратить повтор в
    //        вольту с окончаниями (вольта 1 = такты с vs по repeat_end),
    //        иначе — legacy-режим: координаты выводятся из меток секций.
    // Тексты озвучки сверены с locales/ru/LC_MESSAGES/irealstudio.po.

    /// Отметить текущий такт как начало повтора («[») — как python
    /// `set_repeat_start` (main.py:1667). Само по себе цифровку не меняет:
    /// ни undo-снимка, ни dirty (маркер — временное состояние).
    pub fn set_repeat_start(&mut self) -> String {
        let m = self.cursor;
        self.pending_repeat_start = Some(m);
        self.pending_repeat_end = None; // переустановка начала сбрасывает конец
        format!("Начало повтора задано на такте {m}")
    }

    /// Отметить текущий такт как конец повтора («]») и создать обычный повтор
    /// — как python `set_repeat_end` (main.py:1673): ошибка, если начала нет
    /// или конец не после начала; иначе undo-снимок + `add_repeat_bracket`.
    pub fn set_repeat_end(&mut self) -> String {
        let Some(rs) = self.pending_repeat_start else {
            return "Сначала задайте начало повтора клавишей [".to_string();
        };
        let re = self.cursor;
        if re <= rs {
            return "Конец повтора должен быть после начала".to_string();
        }
        self.pending_repeat_end = Some(re);
        self.push_undo();
        self.cp.add_repeat_bracket(rs, re);
        self.dirty = true;
        format!("Повтор задан: {rs}–{re}. Если нужны окончания, перейдите к окончанию 1 и нажмите V.")
    }

    /// Вольта/окончание («V») — как python `add_volta` (main.py:1692).
    /// При заданных «[» и «]» создаёт вольту с окончаниями (маркеры
    /// сбрасываются); без них — legacy `add_volta_start` по меткам секций.
    /// Undo-снимок и dirty ставятся всегда, даже при неверных маркерах
    /// (python делает то же).
    pub fn add_volta(&mut self) -> String {
        self.push_undo();
        let msg = match (self.pending_repeat_start, self.pending_repeat_end) {
            (Some(rs), Some(re)) => {
                let vs = self.cursor;
                // Маркеры сбрасываются после создания вольты (python:1706).
                self.pending_repeat_start = None;
                self.pending_repeat_end = None;
                if !(rs < vs && vs <= re) {
                    format!("Неверные маркеры вольты: начало {rs}, вольта {vs}, конец {re}")
                } else {
                    let ending2_start = re + (vs - rs) + 1;
                    let cleared = self.count_hidden_chords(VoltaBracket {
                        repeat_start: rs,
                        ending1_start: vs,
                        ending1_end: re,
                        ending2_start,
                        num_repeats: 2,
                    });
                    self.cp.add_volta_bracket(rs, re, vs);
                    repeat_from_message(rs, vs, re, ending2_start, cleared)
                }
            }
            _ => {
                // Legacy V без маркеров: границы вольты выводятся из секций
                // (chords.py add_volta_start). Расчёт повторяет core 1-в-1,
                // чтобы озвучить готовый результат до вызова мутации.
                let m = self.cursor;
                let rs = self.cp.find_section_start(m);
                let next = self.cp.find_next_section_start(m);
                let ending_length = (next - m).max(1);
                let ending1_end = m + ending_length - 1;
                let ending2_start = next + (m - rs);
                let cleared = self.count_hidden_chords(VoltaBracket {
                    repeat_start: rs,
                    ending1_start: m,
                    ending1_end,
                    ending2_start,
                    num_repeats: 2,
                });
                self.cp.add_volta_start(m);
                repeat_from_message(rs, m, ending1_end, ending2_start, cleared)
            }
        };
        self.dirty = true;
        msg
    }

    /// Сколько аккордов попадёт в скрытый диапазон вольты (между окончанием 1
    /// и окончанием 2) — они будут удалены при создании скобки (как python
    /// «hidden chord(s) removed»). Считаем по геометрии новой скобки до
    /// мутации core: hidden_range у одноимённой фиктивной скобки.
    fn count_hidden_chords(&self, probe: VoltaBracket) -> usize {
        match probe.hidden_range() {
            None => 0,
            Some((hs, he)) => self
                .cp
                .items
                .iter()
                .filter(|i| i.position.measure >= hs && i.position.measure <= he)
                .count(),
        }
    }

    /// Транспонировать всю цифровку — как python `_on_transpose`
    /// (app_menu.py:364): кратно 12 — молчание; иначе транспонирует аккорды и
    /// тональность, говорит «Транспонировано на N полутон(ов), новая тональность: …».
    pub fn transpose(&mut self, raw_semitones: i32) -> String {
        if raw_semitones % 12 == 0 {
            return String::new();
        }
        // Как python: знак сохраняется, значение зажато в ±(1..11).
        let semitones = if raw_semitones > 0 {
            raw_semitones % 12
        } else {
            -(raw_semitones.abs() % 12)
        };
        self.push_undo();
        self.cp.transpose(semitones, None);
        self.dirty = true;
        let unit = ru_semitones_unit(semitones);
        format!(
            "Транспонировано на {semitones} {unit}, новая тональность: {}",
            self.cp.key
        )
    }

    /// Применить форму «Настройки цифровки» (Ctrl+P) — калька python
    /// `_open_project_settings` (app_io.py:562). Python-семантика:
    ///   - меняются только изменившиеся поля; пустой title/composer после
    ///     обрезки считается «не задан» (не меняет, в changed не участвует);
    ///   - смена тональности НЕ транспонирует аккорды (как в python);
    ///   - bpm вне [BPM_MIN, BPM_MAX] не применяется;
    ///   - размер такта — строго «N/D»: мусор молча пропускается, как
    ///     python try/except вокруг `TimeSignature.from_string`;
    ///   - ничего не изменилось → тишина (пустая строка).
    /// Изменения кладут снимок в undo и ставят dirty. Отдаёт
    /// «Settings updated: {title}». (recording_bpm из python-формы не входит —
    /// подсистемы записи в этой версии нет.)
    pub fn apply_settings(&mut self, s: &ProjectSettings) -> String {
        let title = s.title.trim();
        let composer = s.composer.trim();
        let ts_str = s.time_sig.trim();
        let bpm_ok = (BPM_MIN..=BPM_MAX).contains(&s.bpm);
        // changed-детект для размера — по строке, ДО разбора (как python:
        // мусорный размер всё равно открывает undo и озвучку).
        let ts_changed = !ts_str.is_empty() && ts_str != self.cp.time_signature.to_string();

        let changed = (!title.is_empty() && title != self.cp.title)
            || (!composer.is_empty() && composer != self.cp.composer)
            || (!s.key.is_empty() && s.key != self.cp.key)
            || (!s.style.is_empty() && s.style != self.cp.style)
            || (bpm_ok && s.bpm != self.cp.bpm)
            || ts_changed;
        if !changed {
            return String::new();
        }

        self.push_undo();
        if !title.is_empty() {
            self.cp.title = title.to_string();
        }
        if !composer.is_empty() {
            self.cp.composer = composer.to_string();
        }
        if !s.key.is_empty() {
            self.cp.key = s.key.clone();
        }
        if !s.style.is_empty() {
            self.cp.style = s.style.clone();
        }
        if bpm_ok {
            self.cp.bpm = s.bpm;
        }
        if ts_changed {
            if let Some(ts) = parse_time_sig(ts_str) {
                self.cp.time_signature = ts;
            }
        }
        self.dirty = true;
        format!("Settings updated: {}", self.cp.title)
    }
}

/// «полутон/полутона/полутонов» по правилам русского множественного числа.
fn ru_semitones_unit(n: i32) -> &'static str {
    let a = n.abs() % 100;
    let b = n.abs() % 10;
    if b == 1 && a != 11 {
        "полутон"
    } else if b >= 2 && b <= 4 && !(a >= 12 && a <= 14) {
        "полутона"
    } else {
        "полутонов"
    }
}

/// Безопасное имя файла из названия цифровки — калька python
/// `_safe_filename` (app_settings.py:84): вырезает запрещённые для Windows
/// символы и слэши, пробелы → `_`, режет краевые `.`/`_`, пусто → "export".
/// Используется для имени по умолчанию при экспорте/сохранении.
pub fn safe_file_base(title: &str) -> String {
    let cleaned: String = title
        .chars()
        .filter(|c| !matches!(c, '\\' | '/' | ':' | '*' | '?' | '"' | '<' | '>' | '|'))
        .collect();
    let underscored = cleaned.replace(' ', "_");
    let trimmed = underscored.trim_matches(|c| c == '.' || c == '_');
    if trimmed.is_empty() {
        "export".to_string()
    } else {
        trimmed.to_string()
    }
}

/// HTML-обёртка экспорта в iReal Pro — побайтово калька python
/// `export_ireal` (app_io.py:413): авто-редирект на `irealb://` URL через
/// `<script>window.location.href`, плюс ссылка-фолбэк. Так iReal Pro
/// открывает цифровку, когда страницу открывают на устройстве с ним.
pub fn export_ireal_html(title: &str, url: &str) -> String {
    format!(
        "<!DOCTYPE html>\n<html>\n<head><title>{title}</title></head>\n<body>\n\
         <p>Opening in iReal Pro...</p>\n<p><a href=\"{url}\">{title}</a></p>\n\
         <script>window.location.href = \"{url}\";</script>\n</body>\n</html>"
    )
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

    // --- Открыть/сохранить (.ips = progression.to_json()): калька python
    // app_io.py open_file/_save_to_path. Документ целиком уходит в строку и
    // возвращается из неё без потерь; курсор после загрузки — такт 1. ---

    #[test]
    fn open_save_roundtrip_keeps_song() {
        let d = Doc::new_demo();
        let json = d.to_json();
        assert!(json.contains("Rhythm Changes"), "в JSON есть название: {json}");
        let loaded = Doc::from_json(&json).expect("валидный JSON загружается");
        // Вся цифровка вернулась без потерь — озвучка идентична.
        assert_eq!(loaded.announce_song(), d.announce_song());
        assert_eq!(loaded.last_measure(), d.last_measure());
        assert_eq!(loaded.cp.title, "Rhythm Changes (демо)");
        assert_eq!(loaded.cp.key, "B-");
        assert_eq!(loaded.cursor, 1, "после открытия курсор на такте 1");
    }

    #[test]
    fn from_json_does_not_carry_old_cursor() {
        // Курсор в JSON не хранится: даже если текущий документ был в середине,
        // загрузка файла ставит курсор на такт 1 (python: Position(1,1)).
        let mut d = Doc::new_demo();
        for _ in 0..6 {
            d.go_right();
        }
        assert_eq!(d.cursor, 7);
        let json = d.to_json();
        let loaded = Doc::from_json(&json).unwrap();
        assert_eq!(loaded.cursor, 1);
    }

    #[test]
    fn from_invalid_json_errors() {
        assert!(Doc::from_json("не json").is_err(), "мусор не грузится");
        assert!(Doc::from_json("").is_err(), "пустой файл не грузится");
        assert!(
            Doc::from_json("{\"title\": 42}").is_err(),
            "структура не той формы — ошибка"
        );
    }

    // --- Экспорт в iReal Pro (Ctrl+E): чистые хелперы сверены с python
    // `_safe_filename` (app_settings.py) и HTML-обёрткой `export_ireal`
    // (app_io.py). ---

    #[test]
    fn safe_file_base_matches_python() {
        assert_eq!(safe_file_base("My Song"), "My_Song");
        assert_eq!(safe_file_base("Rush E."), "Rush_E", "краевые точки срезаются");
        assert_eq!(safe_file_base("a/b:c*?\"<>|"), "abc", "запрещённые символы вырезаются");
        assert_eq!(safe_file_base("  ._.  "), "export", "после чистки пусто → export");
        assert_eq!(safe_file_base("."), "export");
        assert_eq!(safe_file_base("Капли дождя"), "Капли_дождя");
    }

    #[test]
    fn export_html_matches_python() {
        let expected = "<!DOCTYPE html>\n<html>\n<head><title>My Song</title></head>\n\
            <body>\n<p>Opening in iReal Pro...</p>\n<p><a href=\"irealb://dXzY\">My Song</a></p>\n\
            <script>window.location.href = \"irealb://dXzY\";</script>\n</body>\n</html>";
        assert_eq!(export_ireal_html("My Song", "irealb://dXzY"), expected);
    }

    #[test]
    fn demo_builds_irealb_url_and_html() {
        // Сквозной путь Ctrl+E: из демо-документа строится irealb URL, а
        // HTML-обёртка несёт авто-редирект на него.
        let d = Doc::new_demo();
        let url = d.cp.to_irealb_url(true);
        assert!(!url.is_empty(), "URL строится для демо");
        assert!(url.len() > 20, "в URL есть обфусцированные данные: {url}");
        let html = export_ireal_html(&d.cp.title, &url);
        assert!(html.contains("window.location.href"));
        assert!(html.contains(&d.cp.title));
        // Текстовый («debug») экспорт — сырой не-URL-encoded irealbook.
        let raw = d.cp.to_ireal_url(false);
        assert!(raw.starts_with("irealbook://"), "{raw}");
    }

    /// Документ из примера Дениза (msg 1594): в 1-м такте два аккорда
    /// (доли 1 и 3), 2-й такт пустой, 3-й — с аккордом на доле 1, 4-й —
    /// пустой хвост. Проверка шагания «по аккордам и по пустым тактам».
    fn nav_doc() -> Doc {
        let ts = TimeSignature::new(4, 4);
        let mut cp = ChordProgression::new("nav", ts, "C", "Swing");
        cp.add_chord_by_name("B-7", 1, 1, "");
        cp.add_chord_by_name("E-7", 1, 3, "");
        cp.add_chord_by_name("A-7", 3, 1, "");
        cp.total_measures = 4; // пустой 4-й такт — хвост
        Doc {
            cp,
            cursor: 1,
            beat: 1,
            undo_stack: Vec::new(),
            redo_stack: Vec::new(),
            clipboard: None,
            dirty: false,
            pending_repeat_start: None,
            pending_repeat_end: None,
            selection: None,
            sel_clipboard: None,
        }
    }

    #[test]
    fn chord_step_navigation_musescore_parity() {
        let mut d = nav_doc();
        // ←/→ по событиям (как python by-chord, msg 1594).
        assert!(d.go_chord_right(), "шаг 1: должен сдвинуться");
        assert_eq!((d.cursor, d.beat), (1, 3), "на второй аккорд того же такта");
        assert!(d.go_chord_right(), "шаг 2");
        assert_eq!((d.cursor, d.beat), (3, 1), "пустой 2-й такт пропущен → аккорд 3-го");
        assert!(d.go_chord_right(), "шаг 3");
        assert_eq!((d.cursor, d.beat), (4, 1), "аккордов впереди нет → «в такт» пустого 4-го");
        assert!(!d.go_chord_right(), "за концом документа шаг не сдвигает");
        assert_eq!((d.cursor, d.beat), (4, 1));

        // Влево — зеркально: с пустого такта на предыдущий аккорд (3-й такт).
        assert!(d.go_chord_left());
        assert_eq!((d.cursor, d.beat), (3, 1));
        assert!(d.go_chord_left(), "с аккорда 3-го такта на последний аккорд 1-го");
        assert_eq!((d.cursor, d.beat), (1, 3), "пустой 2-й такт влево тоже пропускается");
        assert!(d.go_chord_left(), "на первый аккорд того же такта");
        assert_eq!((d.cursor, d.beat), (1, 1));
        assert!(!d.go_chord_left(), "левее первого такта шаг не сдвигает");
        assert_eq!((d.cursor, d.beat), (1, 1));
    }

    #[test]
    fn ctrl_arrows_step_measures_and_reset_beat() {
        let mut d = nav_doc();
        d.go_chord_right(); // на (1, 3) — вторая доля первого такта
        assert_eq!((d.cursor, d.beat), (1, 3));
        // Ctrl+→ — по тактам, включая пустые, доля сбрасывается.
        d.go_right();
        assert_eq!((d.cursor, d.beat), (2, 1), "Ctrl+→ идёт в пустой такт 2");
        d.go_right();
        assert_eq!((d.cursor, d.beat), (3, 1));
        d.go_right();
        assert_eq!((d.cursor, d.beat), (4, 1));
        d.go_left();
        assert_eq!((d.cursor, d.beat), (3, 1));
    }

    #[test]
    fn chord_step_announce_cell_always() {
        let mut d = nav_doc();
        // Шаг внутри такта → озвучка позиции: аккорд первым, без запятых
        // (msg 1598: «E-7 такт 1 доля 3», не «такт 1, доля 3, E-7»).
        let from = d.cursor;
        d.go_chord_right();
        let s = d.announce_after_chord_step(from);
        assert!(s.ends_with("такт 1 доля 3"), "клетка: {s}");
        assert!(!s.contains(','), "без запятых: {s}");
        // Шаг на НОВЫЙ такт — тоже элемент, а не весь такт (msg 1602).
        let from = d.cursor;
        d.go_chord_right();
        let s = d.announce_after_chord_step(from);
        assert!(s.ends_with("такт 3 доля 1"), "элемент нового такта: {s}");
        assert!(!s.contains(','), "без запятых: {s}");
        // Пустая доля в пустом такте → «такт N доля M пусто».
        d.cursor = 2;
        d.beat = 1;
        assert_eq!(d.announce_after_chord_step(2), "такт 2 доля 1 пусто");
    }

    #[test]
    fn alt_arrows_step_beats_within_and_across_measures() {
        let mut d = nav_doc();
        assert_eq!((d.cursor, d.beat), (1, 1));
        // Внутри такта — по долям, в т.ч. по пустым (доля 2 аккорда не несёт).
        for _ in 0..3 {
            assert!(d.go_beat_right(), "шаг по долям внутри такта");
        }
        assert_eq!((d.cursor, d.beat), (1, 4), "с доли 1 до доли 4");
        // Граница такта → доля 1 следующего такта (пустой такт 2).
        assert!(d.go_beat_right());
        assert_eq!((d.cursor, d.beat), (2, 1));
        // Влево с первой доли → на последнюю долю предыдущего такта.
        assert!(d.go_beat_left());
        assert_eq!((d.cursor, d.beat), (1, 4));
        assert!(d.go_beat_left());
        assert_eq!((d.cursor, d.beat), (1, 3));
        // За границы документа шаг не сдвигает.
        d.cursor = 1;
        d.beat = 1;
        assert!(!d.go_beat_left(), "левее первого такта");
        d.cursor = 4;
        d.beat = 4;
        assert!(!d.go_beat_right(), "правее последнего такта");
    }

    #[test]
    fn deleting_cursor_chord_keeps_cursor_beat() {
        // #48: Del на доле 3 снимает ИМЕННО аккорд доли 3 (slice 12), а курсор
        // ОСТАЁТСЯ на доле 3 — «там пустота, а не чёрная дыра» (msg 1607),
        // никакого магнита к доле 1 или к аккорду доли 1.
        let mut d = nav_doc();
        d.go_chord_right(); // на (1, 3) — второй аккорд такта 1
        assert_eq!((d.cursor, d.beat), (1, 3));
        d.delete_at_cursor();
        let syms: Vec<String> = d
            .measure_view(1)
            .chords
            .iter()
            .map(|c| c.symbol.clone())
            .collect();
        assert_eq!(syms, vec!["B-7"], "удалён только аккорд доли 3");
        assert_eq!((d.cursor, d.beat), (1, 3), "курсор остался на доле удаления");
        // Undo вернул E-7 на долю 3 — курсор на прежнем месте.
        d.undo();
        assert_eq!(d.cp.find_chords_in_measure(1).len(), 2);
        assert_eq!((d.cursor, d.beat), (1, 3));
        // Стрелка вправо с доли 3 (последний аккорд такта 1) — на следующий
        // аккорд документа (A-7 в такте 3), пустой такт 2 перешагивается.
        assert!(d.go_chord_right());
        assert_eq!((d.cursor, d.beat), (3, 1));
    }

    #[test]
    fn left_arrow_from_empty_tail_steps_one_measure() {
        // #47 (msg 1607): стрелка влево из пустого хвоста идёт по одному такту
        // назад за нажатие, а НЕ магнитится через километр к последнему аккорду.
        let ts = TimeSignature::new(4, 4);
        let mut cp = ChordProgression::new("left", ts, "C", "Swing");
        cp.add_chord_by_name("C", 1, 1, "");
        cp.total_measures = 4; // такты 2–4 пустые
        let mut d = Doc {
            cp,
            cursor: 4,
            beat: 1,
            undo_stack: Vec::new(),
            redo_stack: Vec::new(),
            clipboard: None,
            dirty: false,
            pending_repeat_start: None,
            pending_repeat_end: None,
            selection: None,
            sel_clipboard: None,
        };
        // Четыре шага влево — по одному такту, и только потом упираемся в C.
        assert!(d.go_chord_left());
        assert_eq!((d.cursor, d.beat), (3, 1), "такт 3, не прыжок к аккорду");
        assert!(d.go_chord_left());
        assert_eq!((d.cursor, d.beat), (2, 1), "такт 2");
        assert!(d.go_chord_left());
        assert_eq!((d.cursor, d.beat), (1, 1), "такт 1 — аккорд C");
        assert!(!d.go_chord_left(), "за начало документа шага нет");
    }
}

#[cfg(test)]
mod edit_tests {
    use super::*;

    /// Пустая цифровка без шаблона — такты появляются при вводе (как python).
    fn empty_doc() -> Doc {
        Doc::new_chart(&NewChart::defaults())
    }

    #[test]
    fn insert_places_and_replaces_at_beat_one() {
        let mut d = empty_doc();
        assert_eq!(d.insert_chord("C", ""), "Вставлен аккорд: C");
        let v = d.measure_view(1);
        assert_eq!(v.chords.len(), 1, "один аккорд в такте");
        assert_eq!(v.chords[0].beat, 1);
        assert_eq!(v.chords[0].symbol, "C");
        // Тот же такт, новая вставка заменяет (core add_chord_raw — как python).
        d.insert_chord("G7", "");
        let v = d.measure_view(1);
        assert_eq!(v.chords.len(), 1);
        assert_eq!(v.chords[0].symbol, "G7");
        assert_eq!(d.last_measure(), 1, "вставка создала такт");
    }

    #[test]
    fn unknown_chord_name_is_echoed_without_panic() {
        // regression (msg 1602): «C6», введённый в русской раскладке (кириллица),
        // не имеет распознанного корня → раньше announce паниковал в spoken.rs и
        // речь умирала. Теперь имя хранится как есть и читается как есть.
        let mut d = empty_doc();
        let msg = d.insert_chord("С6", "");
        assert_eq!(msg, "Вставлен аккорд: С6");
        let m = d.measure_view(1);
        assert_eq!(m.chords[0].symbol, "С6");
        assert_eq!(m.chords[0].spoken, "С6");
        let a = d.announce_measure(1);
        assert!(a.contains("С6"), "имя читается в озвучке такта: {a}");
        assert_eq!(d.announce_beat_cell(), "С6 такт 1 доля 1");
        // Сетка не паникует и несёт то же сырое имя.
        assert_eq!(d.grid_cell_text(1), "С6");
    }

    #[test]
    fn edit_chord_in_place_keeps_bass() {
        let mut d = empty_doc();
        // F2 на пустом такте — ошибка, как python.
        assert_eq!(d.edit_chord("C7"), "Нет аккорда для редактирования");
        d.insert_chord("D7", "A");
        assert_eq!(d.edit_chord("D9"), "Аккорд отредактирован: D9");
        // Слэш-бас пережил редактирование (python bass_note=item.bass_note).
        let v = d.measure_view(1);
        assert_eq!(v.chords[0].symbol, "D9/A");
        // То же имя — молчание (пустая строка = не озвучивать).
        assert_eq!(d.edit_chord("D9"), "");
    }

    #[test]
    fn no_chord_is_set_only() {
        // #49: N.C. ТОЛЬКО ставится по H/N; повторное нажатие не убирает
        // (msg 1607) — снятие через Backspace (delete_structure_at_measure).
        let mut d = empty_doc();
        assert!(!d.cp.is_no_chord(1));
        assert_eq!(d.toggle_no_chord(), "N.C. в такте 1");
        assert!(d.cp.is_no_chord(1));
        assert_eq!(d.toggle_no_chord(), "N.C. уже стоит в такте 1");
        assert!(d.cp.is_no_chord(1), "повтор не убирает N.C.");
        // Снятие — структурным удалением (Backspace на такте N.C.).
        assert_eq!(d.delete_at_cursor(), "Удалено: N.C. в такте 1");
        assert!(!d.cp.is_no_chord(1));
    }

    #[test]
    fn delete_last_chord_stays_on_its_beat() {
        // #48: удалили последний аккорд песни — остаёмся на его доле (пустота
        // в такте, куда можно вставить новый аккорд), не прыгаем к предыдущему.
        let mut d = empty_doc();
        d.insert_chord("C", "");
        d.cursor = 2;
        d.insert_chord("G", "");
        assert_eq!(d.active_chord().map(|a| a.2), Some("G".to_string()));
        let msg = d.delete_at_cursor();
        assert!(d.cp.find_chords_in_measure(2).is_empty(), "аккорд удалён");
        assert_eq!((d.cursor, d.beat), (2, 1), "курсор остался на доле удаления");
        assert!(msg.contains("такт 2"), "озвучка места удаления: {msg}");
    }

    #[test]
    fn delete_on_empty_toggled_measure_removes_nc_and_structure() {
        let mut d = empty_doc();
        d.toggle_no_chord();
        let msg = d.delete_at_cursor();
        assert_eq!(msg, "Удалено: N.C. в такте 1");
        assert!(!d.cp.is_no_chord(1));
        // Пустой такт без структуры — «нечего удалить».
        d.cursor = 3; // такта нет, но мера пустая
        let msg = d.delete_at_cursor();
        assert_eq!(msg, "Нечего удалить в такте 3 доле 1");
    }

    #[test]
    fn delete_structural_ignores_chord() {
        let mut d = empty_doc();
        d.insert_chord("C", "");
        d.add_section_mark_by_letter('a');
        assert_eq!(d.cp.get_section_mark(1), Some("*A"));
        let msg = d.delete_structural_at_cursor();
        assert_eq!(msg, "Удалено: метка части в такте 1");
        assert_eq!(d.cp.get_section_mark(1), None);
        assert_eq!(d.cp.find_chords_in_measure(1).len(), 1, "аккорд не тронут");
    }

    #[test]
    fn clipboard_copy_paste_cut_flow() {
        let mut d = empty_doc();
        assert_eq!(d.paste_chord(), "Буфер обмена пуст");
        d.insert_chord("D7", "A");
        assert_eq!(d.copy_chord(), "Скопировано: D7");
        // Вставка в пустой такт 2: имя и бас сохраняются.
        d.cursor = 2;
        assert_eq!(d.paste_chord(), "Вставлено: D7");
        let v = d.measure_view(2);
        assert_eq!(v.chords[0].symbol, "D7/A", "слэш-бас не теряется");
        // Повторная вставка не очищает буфер (python хранит дальше) — Ctrl+V
        // в следующий такт клеит тот же аккорд снова.
        d.cursor = 3;
        assert_eq!(d.paste_chord(), "Вставлено: D7");
        assert_eq!(d.cp.find_chords_in_measure(3).len(), 1);
        let item3 = &d.cp.find_chords_in_measure(3)[0];
        assert_eq!(item3.chord.name(), "D7");
        assert_eq!(item3.bass_note, "A");
        // Cut — копирует и удаляет источник.
        d.cursor = 1;
        assert_eq!(d.cut_chord(), "Вырезано: D7");
        assert!(d.cp.find_chords_in_measure(1).is_empty());
        d.cursor = 2;
        assert_eq!(d.paste_chord(), "Вставлено: D7");
        assert_eq!(d.cp.find_chords_in_measure(2).len(), 1);
    }

    #[test]
    fn insert_chord_entry_gate_validates_and_canonicalizes() {
        // #46: гейт ввода пропускает только валидные для iReal Pro аккорды и
        // канонизирует запись («B-7» хранится как «Bm7»). Невалидное — ошибка,
        // в цифровку ничего не попадает.
        let mut d = empty_doc();
        assert_eq!(d.insert_chord_entry("B-7"), "Вставлен аккорд: Bm7");
        assert_eq!(d.measure_view(1).chords[0].symbol, "Bm7", "канонизация на входе");
        assert_eq!(d.insert_chord_entry("Bb7/G"), "Вставлен аккорд: Bb7/G");
        // Невалидные: не-корень (в т.ч. кириллица «С6»), не-функция, плохой бас.
        assert_eq!(
            d.insert_chord_entry("С6"),
            "Ошибка: аккорд «С6» не существует в iReal Pro"
        );
        assert_eq!(
            d.insert_chord_entry("H7"),
            "Ошибка: аккорд «H7» не существует в iReal Pro"
        );
        assert_eq!(
            d.insert_chord_entry("Cm6x"),
            "Ошибка: аккорд «Cm6x» не существует в iReal Pro"
        );
        assert_eq!(
            d.insert_chord_entry("C/G7"),
            "Ошибка: «C/G7» — после / не нота или такой ноты не существует"
        );
        // Пустой ввод — молчание, не ошибка.
        assert_eq!(d.insert_chord_entry("   "), "");
        let n = d.measure_view(1).chords.len();
        assert_eq!(n, 1, "невалидные вводы не попадают в цифровку: {n}");
    }

    #[test]
    fn edit_chord_entry_rewrites_name_and_bass() {
        // #50: F2 правит ПОЛНЫЙ символ «Bb7/G» — можно изменить/снять бас.
        let mut d = empty_doc();
        d.insert_chord("Bb7", "G");
        assert_eq!(Doc::full_symbol("Bb7", "G"), "Bb7/G", "префилл форм");
        // Без изменений — молчание.
        assert_eq!(d.edit_chord_entry("Bb7/G"), "");
        // Меняем бас.
        assert_eq!(d.edit_chord_entry("Bb7/D"), "Аккорд отредактирован: Bb7/D");
        assert_eq!(d.measure_view(1).chords[0].symbol, "Bb7/D");
        // Снимаем бас целиком.
        assert_eq!(d.edit_chord_entry("Bb7"), "Аккорд отредактирован: Bb7");
        assert_eq!(d.measure_view(1).chords[0].symbol, "Bb7");
        // Невалидные правки — ошибка, аккорд не меняется.
        assert_eq!(
            d.edit_chord_entry("Bb7/H"),
            "Ошибка: «Bb7/H» — после / не нота или такой ноты не существует"
        );
        assert_eq!(
            d.edit_chord_entry("С6"),
            "Ошибка: аккорд «С6» не существует в iReal Pro"
        );
        assert_eq!(d.measure_view(1).chords[0].symbol, "Bb7");
    }

    #[test]
    fn bass_note_accepts_lowercase_and_flat_case() {
        // #51: диалог «/» принимает ноту независимо от регистра и нормализует
        // в каноническую запись («bb» → «Bb», «e» → «E»).
        let mut d = empty_doc();
        d.insert_chord("C", "");
        d.add_bass_note("e");
        assert_eq!(d.measure_view(1).chords[0].symbol, "C/E");
        d.add_bass_note("bb");
        assert_eq!(d.measure_view(1).chords[0].symbol, "C/Bb");
        assert_eq!(d.add_bass_note("X"), "Неверная нота");
    }

    /// Документ с аккордами на (1,1), (1,3), (3,1) и пустым хвостом такта 4 —
    /// для проверки выделения диапазона Shift+стрелки.
    fn sel_doc() -> Doc {
        let mut d = empty_doc();
        d.cp.add_chord_by_name("C", 1, 1, "");
        d.cp.add_chord_by_name("G7", 1, 3, "");
        d.cp.add_chord_by_name("A-7", 3, 1, "");
        d.cp.total_measures = 4;
        d.cursor = 1;
        d.beat = 1;
        d
    }

    #[test]
    fn selection_extend_announces_and_copies_whole_range() {
        // #52: Shift+→ расширяет выделение от якоря; озвучка — число аккордов;
        // Ctrl+C копирует ВЕСЬ диапазон (не только первый аккорд).
        let mut d = sel_doc();
        let a1 = d.extend_chord_step(false); // (1,1) → (1,3)
        assert!(a1.contains("выделено: 2 аккорда"), "{a1}");
        let a2 = d.extend_chord_step(false); // (1,3) → (3,1)
        assert!(a2.contains("выделено: 3 аккорда"), "{a2}");
        assert_eq!(d.copy_chord(), "Скопировано: 3 аккорда");
        let block = d.sel_clipboard.as_ref().expect("блок в буфере");
        assert_eq!(block.len(), 3, "весь диапазон в мульти-буфере");
        assert_eq!(d.clipboard, None, "одиночный буфер не используется");
        // Расширение влево назад до одного аккорда — пересчёт озвучки.
        let a3 = d.extend_chord_step(true); // (3,1) → (1,3)
        assert!(a3.contains("выделено: 2 аккорда"), "{a3}");
    }

    #[test]
    fn selection_cut_delete_and_block_paste() {
        // #52: Ctrl+X вырезает весь диапазон в мульти-буфер; Ctrl+V вставляет
        // блок с той же внутренней геометрией (доли и такты-разрывы сохраняются).
        let mut d = sel_doc();
        d.extend_chord_step(false);
        d.extend_chord_step(false); // выделены C, G7, A-7
        assert_eq!(d.cut_chord(), "Вырезано: 3 аккорда");
        assert!(d.cp.find_chords_in_measure(1).is_empty());
        assert!(d.cp.find_chords_in_measure(3).is_empty());
        assert_eq!((d.cursor, d.beat), (1, 1), "курсор — до начала диапазона");
        // Вставляем блок в пустой такт 4: C→(4,1), G7→(4,3), A-7→(5,1).
        d.cursor = 4;
        d.beat = 1;
        assert_eq!(d.paste_chord(), "Вставлено: 3 аккорда");
        let beats4: Vec<i32> = d
            .measure_view(4)
            .chords
            .iter()
            .map(|c| c.beat)
            .collect();
        assert_eq!(beats4, vec![1, 3], "геометрия внутри блока сохранена: {beats4:?}");
        // Разрыв: исходный такт 2 был пустым — после вставки в такт 4 пустым
        // остаётся такт 5, а A-7 ложится в такт 6 (промежуток сохранён).
        assert!(d.measure_view(5).chords.is_empty(), "пустой такт-разрыв перенесён");
        assert_eq!(d.measure_view(6).chords[0].symbol, "A-7", "хвост блока на такте 6");
    }

    #[test]
    fn delete_selection_removes_range_and_repositions() {
        // #52: Del при активном выделении удаляет диапазон целиком; курсор —
        // последний аккорд перед диапазоном (или такт 1).
        let mut d = sel_doc();
        d.extend_chord_step(false); // → (1,3)
        d.extend_chord_step(false); // → (3,1), выделены C, G7, A-7
        let msg = d.delete_at_cursor();
        assert_eq!(msg, "Удалено: 3 аккорда");
        assert!(d.cp.find_chords_in_measure(1).is_empty());
        assert!(d.cp.find_chords_in_measure(3).is_empty());
        assert_eq!((d.cursor, d.beat), (1, 1), "до начала диапазона аккордов нет");
        assert_eq!(d.selection, None, "выделение снято после удаления");
    }

    #[test]
    fn select_all_spans_whole_document() {
        // Аудит python (msg 1612): `_select_all` (main.py:1217) выделяет все
        // аккорды от первого до последнего; Ctrl+C после этого копирует блоком.
        let mut d = sel_doc();
        let msg = d.select_all();
        assert!(msg.contains("выделено: 3 аккорда"), "{msg}");
        assert_eq!((d.cursor, d.beat), (3, 1), "курсор — на последний аккорд");
        assert_eq!(d.copy_chord(), "Скопировано: 3 аккорда");
        let block = d.sel_clipboard.as_ref().expect("мульти-блок в буфере");
        assert_eq!(block.len(), 3);
        // Вставка блока в пустой такт 4 повторяет геометрию исходника.
        d.cursor = 4;
        d.beat = 1;
        assert_eq!(d.paste_chord(), "Вставлено: 3 аккорда");
        assert_eq!(d.measure_view(4).chords[0].symbol, "C");
        assert_eq!(d.measure_view(6).chords[0].symbol, "A-7");
    }

    #[test]
    fn select_all_on_empty_document_is_quiet() {
        let mut d = empty_doc();
        assert_eq!(d.select_all(), "Нет аккордов для выделения");
        assert_eq!(d.selection, None);
    }

    #[test]
    fn undo_redo_cycle_restores_state() {
        let mut d = empty_doc();
        d.insert_chord("C", "");
        assert_eq!(d.cp.find_chords_in_measure(1).len(), 1);
        assert_eq!(d.undo(), "Отменено");
        assert!(d.cp.find_chords_in_measure(1).is_empty(), "undo убрал аккорд");
        assert_eq!(d.undo(), "Нечего отменить");
        assert_eq!(d.redo(), "Повторено");
        assert_eq!(d.cp.find_chords_in_measure(1).len(), 1, "redo вернул аккорд");
        assert_eq!(d.redo(), "Нечего повторить");
        // Новая правка чистит redo (как python).
        d.undo();
        d.insert_chord("G", "");
        assert_eq!(d.redo(), "Нечего повторить");
    }

    #[test]
    fn undo_clamps_cursor_to_restored_length() {
        let mut d = empty_doc();
        // Длинная цифровка, курсор в конце.
        d.insert_chord("C", "");
        d.cursor = 8;
        d.insert_chord("G", "");
        assert_eq!(d.cursor, 8);
        // undo вернул состояние, где аккорда на 8 нет — курсор зажат.
        d.undo();
        assert!(d.cursor <= d.last_measure(), "курсор не выходит за документ");
        assert_eq!(d.cursor, 1);
    }

    #[test]
    fn section_mark_insert_speaks_russian() {
        let mut d = empty_doc();
        assert_eq!(d.add_section_mark_by_letter('a'), "Часть A в такте 1");
        assert_eq!(d.cp.get_section_mark(1), Some("*A"));
        // Повторная — заменяет (python add_section_mark).
        assert_eq!(d.add_section_mark_by_letter('b'), "Часть B в такте 1");
        assert_eq!(d.cp.get_section_mark(1), Some("*B"));
        assert_eq!(d.add_section_mark_by_letter('z'), "", "неизвестная — молчание");
        assert_eq!(section_mark_from_letter('Q'), Some("Q"));
        assert_eq!(section_display_name("*i"), "Вступление");
    }

    #[test]
    fn bass_note_validation_and_targets() {
        let mut d = empty_doc();
        assert_eq!(d.add_bass_note("X"), "Неверная нота");
        // Нет аккорда ни под курсором, ни слева — ошибка.
        assert_eq!(d.add_bass_note("E"), "Нет аккорда для изменения");
        d.insert_chord("C", "");
        // Бас к аккорду под курсором; озвучка возвращает аккорд с басом.
        let msg = d.add_bass_note("E");
        assert!(!msg.is_empty() && msg != "Неверная нота", "{msg}");
        let v = d.measure_view(1);
        assert_eq!(v.chords[0].symbol, "C/E");
        // Пустой такт → бас уходит последнему аккорду слева.
        d.cursor = 2;
        assert!(d.cp.find_chords_in_measure(2).is_empty());
        d.add_bass_note("G");
        assert_eq!(d.measure_view(2).chords.len(), 0);
        assert_eq!(d.measure_view(1).chords[0].symbol, "C/G", "бас к аккорду слева");
    }

    #[test]
    fn transpose_whole_song_speaks_key() {
        let mut d = empty_doc();
        d.cp.key = "C".to_string();
        d.insert_chord("C", "");
        let msg = d.transpose(3);
        assert!(msg.starts_with("Транспонировано на 3 полутона,"), "{msg}");
        assert!(msg.contains("новая тональность:"), "{msg}");
        assert_ne!(d.cp.key, "C", "тональность сдвинута");
        // Кратно 12 — python молча игнорирует.
        d.insert_chord("G", ""); // ensure something to look at
        assert_eq!(d.transpose(12), "");
        assert_eq!(d.transpose(-12), "");
        // Нижний регистр -3 говорит «полутона».
        assert!(d.transpose(-3).contains("полутона"));
        // 1 полутон — единственное число.
        assert!(d.transpose(1).contains("полутон, новая"));
    }

    #[test]
    fn dirty_flag_follows_edits() {
        let mut d = empty_doc();
        assert!(!d.dirty);
        d.insert_chord("C", "");
        assert!(d.dirty);
        d.mark_clean();
        assert!(!d.dirty);
        d.undo();
        assert!(d.dirty, "undo тоже меняет состояние");
    }

    #[test]
    fn editing_and_deleting_target_chord_at_cursor_beat() {
        // В такте с аккордами на 1 и 3 долях правки доля-точные (slice 12):
        // F2 правит аккорд НА доле курсора, а не первый в такте (msg 1598).
        let mut d = empty_doc();
        d.insert_chord("B-7", ""); // на (1, 1) — доля по умолчанию
        // Добавим аккорд на долю 3 напрямую в cp (как в demo-цифровке).
        d.cp.add_chord_by_name("E-7", 1, 3, "");
        assert_eq!(d.cp.find_chords_in_measure(1).len(), 2);
        // Курсор на доле 3 → F2 меняет E-7, B-7 на доле 1 не тронут.
        d.beat = 3;
        d.edit_chord("F#-7");
        let syms: Vec<String> = d
            .measure_view(1)
            .chords
            .iter()
            .map(|c| c.symbol.clone())
            .collect();
        assert_eq!(syms, vec!["B-7", "F#-7"], "правка тронула только долю 3");
        // Курсор на доле 1 → Del снимает B-7, аккорд доли 3 остаётся.
        d.beat = 1;
        d.delete_at_cursor();
        let syms: Vec<String> = d
            .measure_view(1)
            .chords
            .iter()
            .map(|c| c.symbol.clone())
            .collect();
        assert_eq!(syms, vec!["F#-7"], "удалён аккорд доли 1, доли 3 цел");
        // На пустой доле того же такта F2 говорит, что редактировать нечего,
        // а не «ловит» первый аккорд такта.
        d.beat = 1;
        assert_eq!(d.edit_chord("G7"), "Нет аккорда для редактирования");
        let syms: Vec<String> = d
            .measure_view(1)
            .chords
            .iter()
            .map(|c| c.symbol.clone())
            .collect();
        assert_eq!(syms, vec!["F#-7"]);
    }

    #[test]
    fn insert_places_chord_on_empty_beat_of_cursor() {
        // Alt+→ по долям ставит курсор на ПУСТУЮ долю — Ctrl+Enter кладёт
        // аккорд туда, а не на долю 1 (slice 12, msg 1598).
        let mut d = empty_doc();
        d.insert_chord("C", ""); // (1, 1)
        d.beat = 2; // встали на пустую долю 2 (Alt+→ с доли 1)
        d.insert_chord("G7", "");
        let beats: Vec<i32> = d
            .measure_view(1)
            .chords
            .iter()
            .map(|c| c.beat)
            .collect();
        assert_eq!(beats, vec![1, 2], "аккорд встал на долю 2, не заменив долю 1");
        assert_eq!(d.cp.find_chords_in_measure(1).len(), 2);
        // Ctrl+V на пустой доле тоже встаёт туда же.
        d.copy_chord();
        d.beat = 3;
        d.paste_chord();
        let beats: Vec<i32> = d
            .measure_view(1)
            .chords
            .iter()
            .map(|c| c.beat)
            .collect();
        assert_eq!(beats, vec![1, 2, 3]);
    }
}

#[cfg(test)]
mod settings_tests {
    use super::*;

    fn demo() -> Doc {
        Doc::new_demo()
    }

    #[test]
    fn key_helpers_roundtrip_all_roots() {
        // Мажор: корень как записан; минор: имя из ROOT_MINOR; туда-обратно.
        for r in KEY_ROOTS {
            assert_eq!(key_from_root_mode(r, false), r);
            assert_eq!(key_to_root_mode(r), (r.to_string(), false), "мажор {r}");
        }
        for (r, k) in ROOT_MINOR {
            assert_eq!(key_from_root_mode(r, true), k, "минор от {r}");
            let (back, minor) = key_to_root_mode(k);
            assert_eq!((back.as_str(), minor), (r, true), "обратно из {k}");
        }
    }

    #[test]
    fn key_helpers_fallbacks() {
        // Незнакомый ключ/корень — дефолты, как в python-выборе.
        assert_eq!(key_to_root_mode("H"), ("C".to_string(), false));
        assert_eq!(key_to_root_mode(""), ("C".to_string(), false));
        assert_eq!(key_from_root_mode("X", true), "X-");
        // G#- — знакомый минор (из бемольного корня Ab): корень бемольный.
        assert_eq!(key_to_root_mode("G#-"), ("Ab".to_string(), true));
        // Диезное имя минора вне ROOT_MINOR (D# нет в таблице) — корень как есть.
        assert_eq!(key_to_root_mode("D#-"), ("D#".to_string(), true));
    }

    #[test]
    fn apply_settings_changes_fields_no_transpose() {
        let mut d = demo();
        let before = d.to_json();
        // Ключ меняется, но аккорды python НЕ транспонирует.
        let s = ProjectSettings {
            title: "  Rhythm Changes (демо)  ".into(), // трим → тот же → не менять
            composer: "Gershwin".into(),
            bpm: 200,
            key: "G".into(),
            style: "Bossa Nova".into(),
            time_sig: "3/4".into(),
        };
        let msg = d.apply_settings(&s);
        assert_eq!(msg, "Settings updated: Rhythm Changes (демо)");
        assert_eq!(d.cp.title, "Rhythm Changes (демо)", "титул не тронут");
        assert_eq!(d.cp.composer, "Gershwin");
        assert_eq!(d.cp.bpm, 200);
        assert_eq!(d.cp.key, "G");
        assert_eq!(d.cp.style, "Bossa Nova");
        assert_eq!(d.cp.time_signature.to_string(), "3/4");
        // Первая доля такта 1 как была B-7 — смена ключа не транспонирует.
        let view = d.measure_view(1);
        assert_eq!(view.chords[0].symbol, "B-7");
        assert!(d.dirty);
        assert_eq!(d.undo_stack.len(), 1, "снимок до правок");
        // Отмена возвращает и ключ, и аккорды.
        d.undo();
        assert_eq!(d.cp.key, "B-");
        assert_eq!(d.to_json(), before);
    }

    #[test]
    fn apply_settings_noop_is_silent() {
        let mut d = demo();
        let s = ProjectSettings::from_cp(&d.cp);
        assert_eq!(d.apply_settings(&s), "", "ничего не менялось — тишина");
        assert!(!d.dirty);
        assert!(d.undo_stack.is_empty());
    }

    #[test]
    fn apply_settings_empty_title_not_applied() {
        let mut d = demo();
        let mut s = ProjectSettings::from_cp(&d.cp);
        s.title = "   ".into();
        s.composer = "Виноградов".into();
        let msg = d.apply_settings(&s);
        assert_eq!(msg, "Settings updated: Rhythm Changes (демо)");
        assert_eq!(d.cp.title, "Rhythm Changes (демо)", "пустой титул не стирает старый");
        assert_eq!(d.cp.composer, "Виноградов");
    }

    #[test]
    fn apply_settings_bpm_out_of_range_ignored() {
        let mut d = demo();
        let mut s = ProjectSettings::from_cp(&d.cp);
        s.bpm = 300;
        assert_eq!(d.apply_settings(&s), "", "один вне-диапазона bpm — тишина");
        assert_eq!(d.cp.bpm, 160);
        assert!(!d.dirty);
    }

    #[test]
    fn apply_settings_bad_time_signature_quirk() {
        // Python-парадокс: мусорный размер открывает changed (undo+dirty+озвучка),
        // но сам не применяется (try/except вокруг from_string молча глотает).
        let mut d = demo();
        let mut s = ProjectSettings::from_cp(&d.cp);
        s.time_sig = "abc".into();
        let msg = d.apply_settings(&s);
        assert_eq!(msg, "Settings updated: Rhythm Changes (демо)");
        assert_eq!(d.cp.time_signature.to_string(), "4/4", "мусор не применился");
        assert!(d.dirty, "python всё равно ставит dirty и undo");
        assert_eq!(d.undo_stack.len(), 1);
    }
}

#[cfg(test)]
mod volta_tests {
    use super::*;

    /// Документ с по одному аккорду C в каждом такте 1..=last.
    fn filled_doc(last: i32) -> Doc {
        let mut d = Doc::new_chart(&NewChart::defaults());
        for m in 1..=last {
            d.cursor = m;
            d.insert_chord("C", "");
        }
        d.cursor = 1;
        d
    }

    fn count_items(cp: &ChordProgression, lo: i32, hi: i32) -> usize {
        cp.items
            .iter()
            .filter(|i| i.position.measure >= lo && i.position.measure <= hi)
            .count()
    }

    #[test]
    fn start_marker_does_not_touch_doc() {
        let mut d = Doc::new_demo();
        d.cursor = 3;
        assert_eq!(d.set_repeat_start(), "Начало повтора задано на такте 3");
        assert!(!d.dirty, "маркер не меняет цифровку");
        assert!(d.undo_stack.is_empty(), "маркер не открывает undo");
        assert!(d.cp.volta_brackets.is_empty());
    }

    #[test]
    fn end_without_start_is_error() {
        let mut d = Doc::new_demo();
        assert_eq!(
            d.set_repeat_end(),
            "Сначала задайте начало повтора клавишей ["
        );
        assert!(!d.dirty);
        assert!(d.undo_stack.is_empty());
    }

    #[test]
    fn end_not_after_start_is_error() {
        let mut d = Doc::new_demo();
        d.cursor = 5;
        assert_eq!(d.set_repeat_start(), "Начало повтора задано на такте 5");
        d.cursor = 3;
        assert_eq!(d.set_repeat_end(), "Конец повтора должен быть после начала");
        assert!(!d.dirty, "ошибка не открывает undo/dirty");
        assert!(d.undo_stack.is_empty());
    }

    #[test]
    fn start_remarks_reset_previous_end() {
        let mut d = Doc::new_demo();
        d.cursor = 2;
        d.set_repeat_start();
        d.cursor = 4;
        d.set_repeat_end();
        assert_eq!(d.pending_repeat_start, Some(2));
        assert_eq!(d.pending_repeat_end, Some(4));
        // Повторная пометка начала сбрасывает конец; старый повтор 2–4 остаётся.
        d.cursor = 6;
        d.set_repeat_start();
        assert_eq!(d.pending_repeat_start, Some(6));
        assert_eq!(d.pending_repeat_end, None);
        assert_eq!(d.cp.volta_brackets.len(), 1);
        assert!(d.cp.volta_brackets[0].is_repeat_only());
    }

    #[test]
    fn plain_repeat_created_by_brackets() {
        let mut d = filled_doc(8);
        d.cursor = 2;
        assert_eq!(d.set_repeat_start(), "Начало повтора задано на такте 2");
        let undo_before = d.undo_stack.len();
        d.cursor = 5;
        let msg = d.set_repeat_end();
        assert_eq!(
            msg,
            "Повтор задан: 2–5. Если нужны окончания, перейдите к окончанию 1 и нажмите V."
        );
        assert!(d.dirty);
        assert_eq!(d.undo_stack.len(), undo_before + 1, "один снимок на скобку");
        assert_eq!(d.cp.volta_brackets.len(), 1);
        let vb = &d.cp.volta_brackets[0];
        assert_eq!(vb.repeat_start, 2);
        assert_eq!(vb.ending1_start, 6);
        assert_eq!(vb.ending1_end, 5);
        assert_eq!(vb.ending2_start, 2);
        assert!(vb.is_repeat_only(), "обычный повтор без окончаний N1/N2");
        // У обычного повтора ничего не удаляется.
        assert_eq!(count_items(&d.cp, 1, 8), 8);
    }

    #[test]
    fn undo_after_repeat_clears_bracket_and_markers() {
        let mut d = filled_doc(8);
        d.cursor = 2;
        d.set_repeat_start();
        d.cursor = 5;
        d.set_repeat_end();
        assert_eq!(d.cp.volta_brackets.len(), 1);
        assert_eq!(d.undo(), "Отменено");
        assert!(d.cp.volta_brackets.is_empty(), "снимок вернул документ без скобки");
        assert_eq!(d.pending_repeat_start, None, "undo сбрасывает маркеры");
        assert_eq!(d.pending_repeat_end, None);
        // После undo клавиша ] без [ снова даёт ошибку — маркеры реально сброшены.
        assert_eq!(d.set_repeat_end(), "Сначала задайте начало повтора клавишей [");
    }

    #[test]
    fn volta_from_markers_removes_hidden_and_reports() {
        let mut d = filled_doc(12);
        d.cursor = 2;
        d.set_repeat_start();
        d.cursor = 7;
        d.set_repeat_end(); // простой повтор 2–7
        d.cursor = 5; // vs — первая мера окончания 1
        let msg = d.add_volta();
        assert_eq!(
            msg,
            "Реприза с такта 2, вольта 1: 5–7, вольта 2 начинается с такта 11 (удалено 3 скрытых аккорда)"
        );
        assert_eq!(d.cp.volta_brackets.len(), 1);
        let vb = &d.cp.volta_brackets[0];
        assert_eq!(vb.repeat_start, 2);
        assert_eq!(vb.ending1_start, 5);
        assert_eq!(vb.ending1_end, 7);
        assert_eq!(vb.ending2_start, 11);
        assert!(!vb.is_repeat_only());
        assert_eq!(count_items(&d.cp, 8, 10), 0, "скрытое тело повтора очищено");
        assert_eq!(count_items(&d.cp, 1, 12), 9);
        // Маркеры сброшены после создания вольты.
        assert_eq!(d.pending_repeat_start, None);
        assert_eq!(d.pending_repeat_end, None);
    }

    #[test]
    fn volta_single_hidden_uses_singular() {
        let mut d = filled_doc(8);
        d.cursor = 2;
        d.set_repeat_start();
        d.cursor = 4;
        d.set_repeat_end();
        d.cursor = 3; // body_length = 1 → один скрытый такт 5
        let msg = d.add_volta();
        assert_eq!(
            msg,
            "Реприза с такта 2, вольта 1: 3–4, вольта 2 начинается с такта 6 (удалён 1 скрытый аккорд)"
        );
        assert_eq!(count_items(&d.cp, 5, 5), 0);
    }

    #[test]
    fn volta_empty_hidden_no_suffix() {
        // Такты только 1–3: скрытый диапазон (4–4) не содержит аккордов —
        // вольта создаётся без суффикса об удалении.
        let mut d = Doc::new_chart(&NewChart::defaults());
        for m in [1, 2, 3] {
            d.cursor = m;
            d.insert_chord("C", "");
        }
        d.cursor = 1;
        d.set_repeat_start();
        d.cursor = 3;
        d.set_repeat_end(); // простой повтор 1–3
        d.cursor = 2; // vs — вольта 1 = 2–3
        let msg = d.add_volta();
        assert_eq!(
            msg,
            "Реприза с такта 1, вольта 1: 2–3, вольта 2 начинается с такта 5"
        );
        assert_eq!(count_items(&d.cp, 4, 4), 0, "в скрытом такте не было аккордов");
    }

    #[test]
    fn volta_invalid_markers_reports_and_resets() {
        let mut d = filled_doc(12);
        d.cursor = 2;
        d.set_repeat_start();
        d.cursor = 7;
        d.set_repeat_end();
        let undone_before = d.undo_stack.len();
        d.cursor = 2; // vs == rs — вольта 1 обязана начинаться после повтора
        let msg = d.add_volta();
        assert_eq!(msg, "Неверные маркеры вольты: начало 2, вольта 2, конец 7");
        assert_eq!(d.pending_repeat_start, None, "маркеры сброшены и при ошибке");
        assert_eq!(d.pending_repeat_end, None);
        // python всё равно пушит снимок и ставит dirty на неверной вольте.
        assert_eq!(d.undo_stack.len(), undone_before + 1);
        assert!(d.dirty);
        assert_eq!(d.cp.volta_brackets.len(), 1);
        assert!(d.cp.volta_brackets[0].is_repeat_only(), "повтор 2–7 не тронут");
    }

    #[test]
    fn legacy_volta_from_section_marks() {
        // Демо: секции *A(1), *B(9), *A(11). V на такте 9 → вольта по границам
        // секции B: rs=9, вольта 1 = 9–10, вольта 2 начинается с 11.
        let mut d = Doc::new_demo();
        d.cursor = 9;
        let msg = d.add_volta();
        assert_eq!(
            msg,
            "Реприза с такта 9, вольта 1: 9–10, вольта 2 начинается с такта 11"
        );
        assert_eq!(d.cp.volta_brackets.len(), 1);
        let vb = &d.cp.volta_brackets[0];
        assert_eq!(vb.repeat_start, 9);
        assert_eq!(vb.ending1_start, 9);
        assert_eq!(vb.ending1_end, 10);
        assert_eq!(vb.ending2_start, 11);
        // Аккорд на такте 11 (начало вольты 2) не удаляется — он вне скрытого.
        assert_eq!(count_items(&d.cp, 11, 11), 1);
    }
}
