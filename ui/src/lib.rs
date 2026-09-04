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

use irealwx_core::{chord_name_to_spoken, ChordProgression, Position, TimeSignature};

/// Потолок стека undo — как python `_UNDO_MAX = 50` (main.py).
pub const UNDO_MAX: usize = 50;

/// Один аккорд в буфере обмена (одиночный: имя + слэш-бас).
pub struct ClipboardItem {
    pub name: String,
    pub bass: String,
}

/// Текущая цифровка + курсор по тактам.
///
/// Модель редактирования (этап 2, slice 5) — «клетка такта»: у Doc курсор
/// тактовый (без доли), поэтому все правки адресуют первый аккорд такта.
/// Это упрощение зафиксировано в slice 1; такты с аккордами на 1 и 3 долях
/// (как в демо) редактируются только по первой доле — вставка/замена идёт на
/// доле 1, а F2/копирование/удаление работают с первым аккордом такта.
pub struct Doc {
    pub cp: ChordProgression,
    /// Номер текущего такта (1-based), в пределах документа.
    pub cursor: i32,
    /// Стек undo — снимки `cp.to_json()` до правки (как python `_undo_stack`).
    pub undo_stack: Vec<String>,
    /// Стек redo — снимки состояния, отменённые undo.
    pub redo_stack: Vec<String>,
    /// Буфер обмена одиночного аккорда (имя + бас).
    pub clipboard: Option<ClipboardItem>,
    /// Цифровка менялась после последнего сохранения (для «*» в заголовке).
    pub dirty: bool,
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
            undo_stack: Vec::new(),
            redo_stack: Vec::new(),
            clipboard: None,
            dirty: false,
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
            undo_stack: Vec::new(),
            redo_stack: Vec::new(),
            clipboard: None,
            dirty: false,
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
            undo_stack: Vec::new(),
            redo_stack: Vec::new(),
            clipboard: None,
            dirty: false,
        })
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

// ===========================================================================
// Редактирование «клетки такта» (slice 5) — калька python app_io/main.py.
//
// Курсор у Doc тактовый, без доли (см. шапку): правки адресуют первый аккорд
// такта. Возврат каждого метода — готовая строка для озвучки (что проговорить
// одним вызовом NVDA); пустая строка = молчание (например, диалог вставки не
// меняет имя — python тоже ничего не говорит). Стек undo/redo, буфер обмена и
// dirty — как в python (main.py `_undo_stack`/`_redo_stack`/`_clipboard`).
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

    /// Первый (по доле) аккорд реального такта под курсором — «активная клетка».
    fn active_chord(&self) -> Option<(i32 /*real_m*/, i32 /*beat*/, String, String)> {
        let m = self.real_measure();
        let first = self.cp.find_chords_in_measure(m).into_iter().next();
        first.map(|it| {
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
        self.dirty = true;
        "Повторено".to_string()
    }

    /// Вставить аккорд по имени на долю 1 такта под курсором (заменяет аккорд
    /// на той же доле, как core `add_chord_raw`) — как python
    /// `_insert_chord_from_menu` (app_io.py:629). Возвращает «Вставлен аккорд: …».
    pub fn insert_chord(&mut self, name: &str, bass: &str) -> String {
        let name = name.trim().to_string();
        if name.is_empty() {
            return String::new();
        }
        let m = self.real_measure();
        self.push_undo();
        self.cp.add_chord_by_name(&name, m, 1, bass);
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

    /// Переключить N.C. на такте — как python `toggle_no_chord` (main.py:843).
    pub fn toggle_no_chord(&mut self) -> String {
        let m = self.real_measure();
        if self.cp.is_no_chord(m) {
            self.push_undo();
            self.cp.remove_no_chord(m);
            self.dirty = true;
            format!("N.C. убрано в такте {m}")
        } else {
            self.push_undo();
            self.cp.add_no_chord(m);
            self.dirty = true;
            format!("N.C. в такте {m}")
        }
    }

    /// Скопировать аккорд под курсором — как python `copy_chord` (main.py:778).
    pub fn copy_chord(&mut self) -> String {
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

    /// Вырезать аккорд — как python `cut_chord` (main.py:791): копирует в
    /// буфер и удаляет из прогрессии.
    pub fn cut_chord(&mut self) -> String {
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
                format!("Вырезано: {name}")
            }
            None => "Нет аккорда под курсором".to_string(),
        }
    }

    /// Вставить аккорд из буфера на долю 1 такта под курсором — как python
    /// `paste_chord` (main.py:807). Буфер НЕ очищается (python читает и хранит
    /// дальше) — повторный Ctrl+V клеит тот же аккорд в следующий такт.
    /// В отличие от python сохраняет и слэш-бас (копирование не теряет басовую ноту).
    pub fn paste_chord(&mut self) -> String {
        let Some(item) = self.clipboard.as_ref() else {
            return "Буфер обмена пуст".to_string();
        };
        let name = item.name.clone();
        let bass = item.bass.clone();
        let m = self.real_measure();
        self.push_undo();
        self.cp.add_chord_by_name(&name, m, 1, &bass);
        self.dirty = true;
        format!("Вставлено: {name}")
    }

    /// Добавить басовую ноту (слэш-бас) к аккорду под курсором, а если такт
    /// пуст — к последнему аккорду слева — как python `add_bass_note`
    /// (main.py:1648). Говорит озвученный аккорд с новым басом.
    pub fn add_bass_note(&mut self, root: &str) -> String {
        let note = root.trim().to_uppercase();
        if !BASS_SPELLINGS.contains(&note.as_str()) {
            return "Неверная нота".to_string();
        }
        // Аккорд под курсором, иначе последний слева (в т.ч. через повторы).
        let (m, beat, name) = match self.active_chord() {
            Some((m, beat, name, _bass)) => (m, beat, name),
            None => {
                let ts = self.cp.time_signature;
                let pos = Position::new(self.cursor, 1, ts);
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
    /// python `delete_at_cursor` (main.py:1714). Если на такте есть аккорд —
    /// удаляет его и говорит «Удалено. <озвучка такта под курсором>»; иначе
    /// снимает метку секции/знак повтора/N.C. и говорит что удалено.
    pub fn delete_at_cursor(&mut self) -> String {
        match self.active_chord() {
            Some((m, beat, _name, _bass)) => {
                let pos = Position::new(m, beat, self.cp.time_signature);
                self.push_undo();
                self.cp.delete_chord_at(&pos);
                self.dirty = true;
                // Пусто в такте? Тогда — на предыдущий аккорд (или такт 1),
                // как python: иначе остаёмся на том же такте.
                if self.cp.find_chords_in_measure(m).is_empty() {
                    let prev = self.cp.find_last_chord_to_left(&pos);
                    self.cursor = prev.map(|i| i.position.measure).unwrap_or(1);
                }
                format!("Удалено. {}", self.announce_measure(self.cursor))
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
    fn no_chord_toggle_roundtrip() {
        let mut d = empty_doc();
        assert!(!d.cp.is_no_chord(1));
        assert_eq!(d.toggle_no_chord(), "N.C. в такте 1");
        assert!(d.cp.is_no_chord(1));
        assert_eq!(d.toggle_no_chord(), "N.C. убрано в такте 1");
        assert!(!d.cp.is_no_chord(1));
    }

    #[test]
    fn delete_chord_moves_cursor_to_previous() {
        let mut d = empty_doc();
        d.insert_chord("C", "");
        d.cursor = 2;
        d.insert_chord("G", "");
        assert_eq!(d.active_chord().map(|a| a.2), Some("G".to_string()));
        let msg = d.delete_at_cursor();
        assert!(msg.starts_with("Удалено. "), "{msg}");
        assert!(d.cp.find_chords_in_measure(2).is_empty(), "аккорд удалён");
        assert_eq!(d.cursor, 1, "курсор ушёл на предыдущий аккорд");
        assert!(msg.contains("такт 1"), "озвучка нового такта: {msg}");
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
    fn editing_measures_with_two_chords_targets_first_beat() {
        // В такте с аккордами на 1 и 3 долях (как демо) клетка = первая доля:
        // F2 правит первый, вставка заменяет долю 1, вторая доля не трогается.
        let mut d = empty_doc();
        d.insert_chord("B-7", "");
        // Добавим аккорд на долю 3 напрямую в cp (как в demo-цифровке).
        d.cp.add_chord_by_name("E-7", 1, 3, "");
        assert_eq!(d.cp.find_chords_in_measure(1).len(), 2);
        d.edit_chord("B7");
        let view = d.measure_view(1);
        let syms: Vec<String> = view.chords.iter().map(|c| c.symbol.clone()).collect();
        assert_eq!(syms, vec!["B7", "E-7"], "правка тронула только первую долю");
        d.cursor = 1;
        d.delete_at_cursor();
        let view = d.measure_view(1);
        let syms: Vec<String> = view.chords.iter().map(|c| c.symbol.clone()).collect();
        assert_eq!(syms, vec!["E-7"], "удалена первая доля, вторая осталась");
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
