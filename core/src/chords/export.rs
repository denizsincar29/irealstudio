//! Экспорт прогрессии в читаемый `irealbook://` URL и в новый `irealb://`.
//!
//! Порт `pyrealpro.py` (Song/Measure/TimeSignature — рендер-грамматика) и
//! методов `ChordProgression.to_ireal_url` / `to_irealb_url` из chords.py.
//! Ядро остаётся dep-free: percent-кодирование под `quote(safe=":/=")` — своё,
//! списки стилей/тональностей — константы из pyrealpro.

use super::progression::ChordProgression;

// ---------------------------------------------------------------------------
// Константы pyrealpro
// ---------------------------------------------------------------------------

/// Валидные для iReal Pro тональности (KEY_SIGNATURES).
pub const KEY_SIGNATURES: &[&str] = &[
    "C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B", "A-", "Bb-", "B-", "C-",
    "C#-", "D-", "Eb-", "E-", "F-", "F#-", "G-", "G#-",
];

/// Репетиционные метки, которые понимает iReal Pro.
pub const REHEARSAL_MARKS: &[&str] = &["*A", "*B", "*C", "*D", "*V", "*i", "S", "Q", "f"];

/// Джазовые стили.
pub const STYLES_JAZZ: &[&str] = &[
    "Afro 12/8",
    "Ballad Double Time Feel",
    "Ballad Even",
    "Ballad Melodic",
    "Ballad Swing",
    "Blue Note",
    "Bossa Nova",
    "Doo Doo Cats",
    "Double Time Swing",
    "Even 8ths",
    "Even 8ths Open",
    "Even 16ths",
    "Guitar Trio",
    "Gypsy Jazz",
    "Latin",
    "Latin/Swing",
    "Long Notes",
    "Medium Swing",
    "Medium Up Swing",
    "Medium Up Swing 2",
    "New Orleans Swing",
    "Second Line",
    "Slow Swing",
    "Swing Two/Four",
    "Trad Jazz",
    "Up Tempo Swing",
    "Up Tempo Swing 2",
];

/// Латиноамериканские стили.
pub const STYLES_LATIN: &[&str] = &[
    "Argentina: Tango",
    "Brazil: Bossa Acoustic",
    "Brazil: Bossa Electric",
    "Brazil: Samba",
    "Cuba: Bolero",
    "Cuba: Cha Cha Cha",
    "Cuba: Son Montuno 2-3",
    "Cuba: Son Montuno 3-2",
];

/// Поп-стили.
pub const STYLES_POP: &[&str] = &[
    "Bluegrass",
    "Country",
    "Disco",
    "Funk",
    "Glam Funk",
    "House",
    "Reggae",
    "Rock",
    "Rock 12/8",
    "RnB",
    "Shuffle",
    "Slow Rock",
    "Smooth",
    "Soul",
    "Virtual Funk",
];

/// Все стили (STYLES_ALL) — JAZZ + LATIN + POP в том же порядке.
pub const STYLES_ALL: &[&str] = &[
    "Afro 12/8",
    "Ballad Double Time Feel",
    "Ballad Even",
    "Ballad Melodic",
    "Ballad Swing",
    "Blue Note",
    "Bossa Nova",
    "Doo Doo Cats",
    "Double Time Swing",
    "Even 8ths",
    "Even 8ths Open",
    "Even 16ths",
    "Guitar Trio",
    "Gypsy Jazz",
    "Latin",
    "Latin/Swing",
    "Long Notes",
    "Medium Swing",
    "Medium Up Swing",
    "Medium Up Swing 2",
    "New Orleans Swing",
    "Second Line",
    "Slow Swing",
    "Swing Two/Four",
    "Trad Jazz",
    "Up Tempo Swing",
    "Up Tempo Swing 2",
    "Argentina: Tango",
    "Brazil: Bossa Acoustic",
    "Brazil: Bossa Electric",
    "Brazil: Samba",
    "Cuba: Bolero",
    "Cuba: Cha Cha Cha",
    "Cuba: Son Montuno 2-3",
    "Cuba: Son Montuno 3-2",
    "Bluegrass",
    "Country",
    "Disco",
    "Funk",
    "Glam Funk",
    "House",
    "Reggae",
    "Rock",
    "Rock 12/8",
    "RnB",
    "Shuffle",
    "Slow Rock",
    "Smooth",
    "Soul",
    "Virtual Funk",
];

// ---------------------------------------------------------------------------
// Percent-кодирование как `urllib.parse.quote(text, safe=":/=")`
// ---------------------------------------------------------------------------

/// Python `quote` держит `~` всегда-safe отдельно от safe; с `safe=":/="`
/// не кодируются: буквы, цифры, `_ . - ~` и `: / =`. Остальное — `%HH`
/// (шестнадцатеричные — заглавные, байты UTF-8).
fn quote_safe(b: u8) -> bool {
    b.is_ascii_alphanumeric() || matches!(b, b'_' | b'.' | b'-' | b'~' | b':' | b'/' | b'=')
}

fn quote_irealbook(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for &b in text.as_bytes() {
        if quote_safe(b) {
            out.push(b as char);
        } else {
            use std::fmt::Write as _;
            let _ = write!(out, "%{b:02X}");
        }
    }
    out
}

// ---------------------------------------------------------------------------
// Грамматика Measure/TimeSignature (pyrealpro)
// ---------------------------------------------------------------------------

/// Строка размера: 12/8 → "T12", иначе "T{beats}{duration}" (TimeSignature.__str__).
fn time_signature_str(beats: i32, duration: i32) -> String {
    if beats == 12 {
        "T12".to_string()
    } else {
        format!("T{beats}{duration}")
    }
}

/// Чем заполнен такт при построении Measure: одиночная строка (python-ветка
/// `type(chords) == str` — растягивается на весь такт пробелами) либо аккорды
/// по долям (ровно `beats` элементов).
enum ChordsArg {
    Whole(String),
    PerBeat(Vec<String>),
}

/// Аккордовая строка такта (Measure.__str__): элементы джойнятся через `,`
/// если их больше одного, иначе без разделителя.
fn chords_str(arg: &ChordsArg, beats: i32) -> String {
    match arg {
        ChordsArg::Whole(c) => {
            // str-ветка: [c] + пробелы до beats; sep = "," при beats > 1.
            let mut v = vec![c.clone()];
            while v.len() < beats.max(1) as usize {
                v.push(" ".to_string());
            }
            if v.len() > 1 {
                v.join(",")
            } else {
                v.join("")
            }
        }
        ChordsArg::PerBeat(list) => {
            if list.len() > 1 {
                list.join(",")
            } else {
                list.join("")
            }
        }
    }
}

/// Готовый к склейке такт с раздельными частями, чтобы Song.url() мог
/// подправить первый открывающий и последний закрывающий до рендера.
struct MeasureStr {
    reh_start: String,
    open: String,
    mid: String, // ts(render_ts) + ending + chords + reh_end
    close: String,
}

impl MeasureStr {
    /// Полная строка такта (Measure.__str__): reh_start + open + mid + close.
    fn render(&self) -> String {
        format!("{}{}{}{}", self.reh_start, self.open, self.mid, self.close)
    }
}

impl ChordProgression {
    /// Экспорт в читаемый `irealbook://` URL (порт `to_ireal_url`).
    ///
    /// Раскладка iReal Pro: 16 ячеек на строку; такт в размере `beats/d`
    /// занимает `beats` ячеек → `16 // beats` тактов на строку. `Y`
    /// вставляется после заполненной строки, но не после структурных
    /// заграждений (`}`, `]`, `Z`) и не перед открытием повтора/секции —
    /// там iReal сам начинает новую строку.
    pub fn to_ireal_url(&self, urlencode: bool) -> String {
        let beats = self.time_signature.numerator;
        let ts = time_signature_str(beats, self.time_signature.denominator);

        // Маппинг style/key на валидные для iReal Pro значения.
        let style = if STYLES_ALL.contains(&self.style.as_str()) {
            self.style.as_str()
        } else {
            "Medium Swing"
        };
        let key = if KEY_SIGNATURES.contains(&self.key.as_str()) {
            self.key.as_str()
        } else {
            "C"
        };
        // Song.composer_name: pyrealpro получает composer_name_first=self.composer,
        // composer_name_last остаётся 'Unknown' → имя совпадает с composer.
        let composer = if self.composer == "Unknown" || self.composer.is_empty() {
            "Unknown"
        } else {
            self.composer.as_str()
        };

        // Крайний *записываемый* такт: отступаем назад из виртуальных диапазонов,
        // чтобы не итерировать по чистым копиям повторов / скрытым телам вольт.
        let total_m = {
            let mut t = self.last_measure().max(self.total_measures);
            while t > 0 && self.is_in_virtual_range(t) {
                t -= 1;
            }
            t
        };

        // Записываемые такты (1-индексные), пропуская виртуальные.
        let mut to_write: Vec<i32> = Vec::new();
        let mut m = 1;
        while m <= total_m {
            if !self.is_in_virtual_range(m) {
                to_write.push(m);
            }
            m += 1;
        }

        // Сколько тактов помещается в строку из 16 ячеек (4/4 → 4, 3/4 → 5…).
        let measures_per_row = (16 / beats).max(1);

        let mut measures: Vec<MeasureStr> = Vec::with_capacity(to_write.len());
        let mut row_measure_count = 0;
        let n = to_write.len();

        for (idx, &measure_num) in to_write.iter().enumerate() {
            let chords_in_measure = self.find_chords_in_measure(measure_num);

            let chords_arg = if !chords_in_measure.is_empty() {
                let mut chord_list: Vec<String> = vec![" ".to_string(); beats.max(1) as usize];
                for item in chords_in_measure {
                    let beat_idx = item.position.beat - 1;
                    if beat_idx >= 0 && beat_idx < beats {
                        chord_list[beat_idx as usize] = item.ireal_chord_name();
                    }
                }
                if chord_list.iter().skip(1).all(|c| c == " ") {
                    // Доли после первой пустые → компактная строка-шорткат.
                    ChordsArg::Whole(chord_list[0].clone())
                } else {
                    ChordsArg::PerBeat(chord_list)
                }
            } else if self.is_no_chord(measure_num) {
                ChordsArg::Whole("n".to_string()) // N.C.
            } else {
                ChordsArg::Whole("x".to_string()) // повтор такта
            };

            // Открывающая: '{' на начале повтора.
            let mut barline_open = "";
            for vb in &self.volta_brackets {
                if measure_num == vb.repeat_start {
                    barline_open = "{";
                    break;
                }
            }

            // Закрывающая: '}' в конце окончания 1 (у полной структуры).
            let mut barline_close: Option<&str> = None;
            for vb in &self.volta_brackets {
                if vb.is_complete() && measure_num == vb.ending1_end {
                    barline_close = Some("}");
                    break;
                }
            }

            // Окончание: N1 в начале окончания 1, N2 в начале окончания 2.
            let mut ending = "";
            for vb in &self.volta_brackets {
                if vb.is_repeat_only() {
                    continue;
                }
                if measure_num == vb.ending1_start {
                    ending = "N1";
                    break;
                }
                if vb.is_complete() && measure_num == vb.ending2_start {
                    ending = "N2";
                    break;
                }
            }

            // Репетиционная метка из секции (если iReal Pro её понимает).
            let mut reh_start = "";
            let mut reh_end = "";
            if let Some(sm) = self.get_section_mark(measure_num) {
                if REHEARSAL_MARKS.contains(&sm) {
                    if sm.starts_with('Q') || sm.starts_with('f') {
                        reh_end = sm;
                    } else {
                        reh_start = sm;
                    }
                }
            }

            // --- Логика переноса строки (Y) ---
            let is_structural_close = matches!(barline_close, Some("}") | Some("]") | Some("Z"));
            let is_structural_open = barline_open == "{" || barline_open == "[";

            // Открытие повтора/секции: iReal сам начинает новую строку — сброс
            // счётчика без эмиссии Y.
            if is_structural_open {
                row_measure_count = 0;
            }
            row_measure_count += 1;

            let is_last = idx == n - 1;
            let mut want_row_break =
                row_measure_count >= measures_per_row && !is_structural_close && !is_last;

            // Заглядываем вперёд: секция на следующем такте начинает свежую
            // строку, если текущая не закрыта структурно.
            if !want_row_break && !is_last {
                let next_num = to_write[idx + 1];
                if self.get_section_mark(next_num).is_some() {
                    want_row_break = !is_structural_close && row_measure_count > 0;
                }
            }

            // Применяем Y добавлением к закрывающей черте: ...|Y|...
            let mut effective_close = barline_close.unwrap_or("|").to_string();
            if want_row_break {
                if effective_close.is_empty() {
                    effective_close = "|".to_string();
                }
                effective_close.push_str("Y|");
                row_measure_count = 0;
            }
            if is_structural_close {
                row_measure_count = 0;
            }

            // Размер печатаем только в первом записываемом такте.
            let ts_part = if idx == 0 { ts.as_str() } else { "" };
            let chords = chords_str(&chords_arg, beats);

            measures.push(MeasureStr {
                reh_start: reh_start.to_string(),
                open: barline_open.to_string(),
                mid: format!("{ts_part}{ending}{chords}{reh_end}"),
                close: effective_close,
            });
        }

        // Song.url(): первый такт без открывающей получает '[', последний с
        // обычной '|' — 'Z' (конец песни).
        if let Some(first) = measures.first_mut() {
            if first.open.is_empty() {
                first.open = "[".to_string();
            }
        }
        if let Some(last) = measures.last_mut() {
            if last.close == "|" || last.close.is_empty() {
                last.close = "Z".to_string();
            }
        }

        let measures_str: String = measures.iter().map(MeasureStr::render).collect();
        let url = format!(
            "irealbook://{title}={composer}={style}={key}=n={measures_str}",
            title = self.title
        );
        if urlencode {
            quote_irealbook(&url)
        } else {
            url
        }
    }

    /// Экспорт в современный `irealb://` URL (обфусцированный, с BPM).
    ///
    /// Аккорд-данные строит тот же проверенный билдер, что и `to_ireal_url`;
    /// отличается только URL-обёртка (читаемый URL декодируется и переносится
    /// в десятипольную запись с обфускацией).
    pub fn to_irealb_url(&self, urlencode: bool) -> String {
        let readable = self.to_ireal_url(false);
        let params = crate::irealb::ModernizeParams {
            tempo: self.bpm,
            actual_style: String::new(),
            actual_key: String::new(),
            repeats: 0,
            urlencode,
        };
        crate::irealb::irealbook_to_irealb(&readable, &params)
            .expect("читаемый irealbook URL обязан декодироваться")
    }
}
