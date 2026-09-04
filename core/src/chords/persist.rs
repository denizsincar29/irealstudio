//! JSON-персистентность ChordProgression — порт `to_json`/`from_json`
//! (chords.py 1555-1588).
//!
//! Байтовый контракт — python `json.dumps(data, indent=2)` с дефолтным
//! `ensure_ascii=True`: вся не-ASCII уходит в `\uXXXX` (астральные символы —
//! суррогатной парой), ключи — в порядке вставки, пустые контейнеры пишутся
//! инлайн (`[]`/`{}`), отступ 2 пробела на уровень. Свой кодировщик/декодер
//! вместо serde: core остаётся dep-free и побайтово совпадает с python-эталоном
//! (serde_json так не умеет — у него нет ensure_ascii).

use std::fmt::Write as _;

use super::model::{Chord, Position, ProgressionItem, SectionMark, TimeSignature, VoltaBracket};
use super::progression::ChordProgression;

// ---------------------------------------------------------------------------
// Python-совместимый JSON
// ---------------------------------------------------------------------------

enum Json {
    Null,
    Bool(bool),
    Num(i64),
    Str(String),
    Arr(Vec<Json>),
    Obj(Vec<(String, Json)>),
}

/// JSON-строка как в python: `"` и `\` экранируются, управляющие символы —
/// короткими эскейпами (\b \f \n \r \t) или `\u00xx`, всё >= U+0080 — `\uXXXX`
/// (суррогатная пара для астрали), hex в нижнем регистре.
fn json_quote(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c if (c as u32) < 0x7f => out.push(c),
            c => {
                let mut buf = [0u16; 2];
                for u in c.encode_utf16(&mut buf) {
                    let _ = write!(out, "\\u{:04x}", u);
                }
            }
        }
    }
    out.push('"');
    out
}

fn indent(out: &mut String, col: usize) {
    for _ in 0..col {
        out.push(' ');
    }
}

/// Рекурсивный pretty-вывод: колонка `col` — отступ строки, на которой открылся
/// контейнер. Дети — на col+2, закрывающая скобка — на col (ровно как python).
fn emit(j: &Json, out: &mut String, col: usize) {
    match j {
        Json::Null => out.push_str("null"),
        Json::Bool(true) => out.push_str("true"),
        Json::Bool(false) => out.push_str("false"),
        Json::Num(n) => {
            let _ = write!(out, "{n}");
        }
        Json::Str(s) => out.push_str(&json_quote(s)),
        Json::Arr(items) => {
            if items.is_empty() {
                out.push_str("[]");
                return;
            }
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                out.push('\n');
                indent(out, col + 2);
                emit(item, out, col + 2);
                if i + 1 < items.len() {
                    out.push(',');
                }
            }
            out.push('\n');
            indent(out, col);
            out.push(']');
        }
        Json::Obj(pairs) => {
            if pairs.is_empty() {
                out.push_str("{}");
                return;
            }
            out.push('{');
            for (i, (k, v)) in pairs.iter().enumerate() {
                out.push('\n');
                indent(out, col + 2);
                out.push_str(&json_quote(k));
                out.push_str(": ");
                emit(v, out, col + 2);
                if i + 1 < pairs.len() {
                    out.push(',');
                }
            }
            out.push('\n');
            indent(out, col);
            out.push('}');
        }
    }
}

// --- Парсер (json.loads): значения, строки с \uXXXX (в т.ч. суррогатные пары),
// числа (целые; плавающие для нашей схемы не нужны — ошибаемся явно).

struct Parser<'a> {
    b: &'a [u8],
    i: usize,
}

impl<'a> Parser<'a> {
    fn skip_ws(&mut self) {
        while self.i < self.b.len() {
            match self.b[self.i] {
                b' ' | b'\t' | b'\n' | b'\r' => self.i += 1,
                _ => break,
            }
        }
    }

    fn peek(&self) -> Option<u8> {
        self.b.get(self.i).copied()
    }

    fn expect(&mut self, ch: u8) -> Result<(), String> {
        if self.peek() == Some(ch) {
            self.i += 1;
            Ok(())
        } else {
            Err(format!("ожидался '{}' на позиции {}", ch as char, self.i))
        }
    }

    fn value(&mut self) -> Result<Json, String> {
        self.skip_ws();
        match self.peek() {
            None => Err("пустой JSON".into()),
            Some(b'{') => self.object(),
            Some(b'[') => self.array(),
            Some(b'"') => Ok(Json::Str(self.string()?)),
            Some(b't') => self.lit("true", Json::Bool(true)),
            Some(b'f') => self.lit("false", Json::Bool(false)),
            Some(b'n') => self.lit("null", Json::Null),
            Some(c) if c == b'-' || c.is_ascii_digit() => self.number(),
            Some(c) => Err(format!("неожиданный символ '{}' на позиции {}", c as char, self.i)),
        }
    }

    fn lit(&mut self, word: &str, val: Json) -> Result<Json, String> {
        if self.b[self.i..].starts_with(word.as_bytes()) {
            self.i += word.len();
            Ok(val)
        } else {
            Err(format!("битый литерал на позиции {}", self.i))
        }
    }

    fn object(&mut self) -> Result<Json, String> {
        self.expect(b'{')?;
        let mut pairs: Vec<(String, Json)> = Vec::new();
        self.skip_ws();
        if self.peek() == Some(b'}') {
            self.i += 1;
            return Ok(Json::Obj(pairs));
        }
        loop {
            self.skip_ws();
            let key = self.string()?;
            self.skip_ws();
            self.expect(b':')?;
            let val = self.value()?;
            // python dict: дубликат ключа перекрывает, позиция сохраняется.
            if let Some(slot) = pairs.iter_mut().find(|(k, _)| *k == key) {
                slot.1 = val;
            } else {
                pairs.push((key, val));
            }
            self.skip_ws();
            match self.peek() {
                Some(b',') => self.i += 1,
                Some(b'}') => {
                    self.i += 1;
                    return Ok(Json::Obj(pairs));
                }
                _ => return Err(format!("ожидалась ',' или '}}' на позиции {}", self.i)),
            }
        }
    }

    fn array(&mut self) -> Result<Json, String> {
        self.expect(b'[')?;
        let mut items: Vec<Json> = Vec::new();
        self.skip_ws();
        if self.peek() == Some(b']') {
            self.i += 1;
            return Ok(Json::Arr(items));
        }
        loop {
            items.push(self.value()?);
            self.skip_ws();
            match self.peek() {
                Some(b',') => self.i += 1,
                Some(b']') => {
                    self.i += 1;
                    return Ok(Json::Arr(items));
                }
                _ => return Err(format!("ожидалась ',' или ']' на позиции {}", self.i)),
            }
        }
    }

    fn hex4(&mut self) -> Result<u32, String> {
        if self.i + 4 > self.b.len() {
            return Err("обрезанный \\uXXXX".into());
        }
        let mut v: u32 = 0;
        for _ in 0..4 {
            let c = self.b[self.i] as char;
            self.i += 1;
            let d = match c {
                '0'..='9' => c as u32 - '0' as u32,
                'a'..='f' => c as u32 - 'a' as u32 + 10,
                'A'..='F' => c as u32 - 'A' as u32 + 10,
                _ => return Err("битый hex в \\uXXXX".into()),
            };
            v = v * 16 + d;
        }
        Ok(v)
    }

    fn string(&mut self) -> Result<String, String> {
        self.expect(b'"')?;
        let mut out = String::new();
        loop {
            let c = self.peek().ok_or_else(|| "незакрытая строка".to_string())?;
            match c {
                b'"' => {
                    self.i += 1;
                    return Ok(out);
                }
                b'\\' => {
                    self.i += 1;
                    let e = self.peek().ok_or_else(|| "обрезанный эскейп".to_string())?;
                    self.i += 1;
                    match e {
                        b'"' => out.push('"'),
                        b'\\' => out.push('\\'),
                        b'/' => out.push('/'),
                        b'b' => out.push('\u{8}'),
                        b'f' => out.push('\u{c}'),
                        b'n' => out.push('\n'),
                        b'r' => out.push('\r'),
                        b't' => out.push('\t'),
                        b'u' => {
                            let hi = self.hex4()?;
                            if (0xd800..0xdc00).contains(&hi) {
                                // суррогатная пара: обязателен низкий код.
                                if self.b[self.i..].starts_with(b"\\u") {
                                    self.i += 2;
                                    let lo = self.hex4()?;
                                    if !(0xdc00..0xe000).contains(&lo) {
                                        return Err("битая суррогатная пара".into());
                                    }
                                    let cp = 0x10000 + ((hi - 0xd800) << 10) + (lo - 0xdc00);
                                    match char::from_u32(cp) {
                                        Some(ch) => out.push(ch),
                                        None => return Err("битый код-поинт".into()),
                                    }
                                } else {
                                    return Err("одинокий высокий суррогат".into());
                                }
                            } else {
                                match char::from_u32(hi) {
                                    Some(ch) => out.push(ch),
                                    None => return Err("битый код-поинт".into()),
                                }
                            }
                        }
                        _ => return Err("неизвестный эскейп".into()),
                    }
                }
                _ => {
                    // Ищем конец обычного UTF-8 символа от self.i.
                    let rest = &self.b[self.i..];
                    let ch_len = utf8_len(rest[0]).min(rest.len());
                    let s = std::str::from_utf8(&rest[..ch_len])
                        .map_err(|_| "битый UTF-8".to_string())?;
                    out.push_str(s);
                    self.i += ch_len;
                }
            }
        }
    }

    fn number(&mut self) -> Result<Json, String> {
        let start = self.i;
        if self.peek() == Some(b'-') {
            self.i += 1;
        }
        let mut ndigits = 0;
        while let Some(c) = self.peek() {
            if c.is_ascii_digit() {
                self.i += 1;
                ndigits += 1;
            } else {
                break;
            }
        }
        if ndigits == 0 {
            return Err("битое число".into());
        }
        if let Some(c) = self.peek() {
            if c == b'.' || c == b'e' || c == b'E' {
                return Err("дробные числа не поддерживаются схемой".into());
            }
        }
        let text = std::str::from_utf8(&self.b[start..self.i]).unwrap();
        text.parse::<i64>()
            .map(Json::Num)
            .map_err(|_| "число вне i64".into())
    }
}

fn utf8_len(b: u8) -> usize {
    if b < 0x80 {
        1
    } else if b >> 5 == 0b110 {
        2
    } else if b >> 4 == 0b1110 {
        3
    } else if b >> 3 == 0b11110 {
        4
    } else {
        1 // битый лидер: from_utf8 вернёт ошибку
    }
}

fn parse_json(s: &str) -> Result<Json, String> {
    let mut p = Parser { b: s.as_bytes(), i: 0 };
    let v = p.value()?;
    p.skip_ws();
    if p.i != s.len() {
        return Err(format!("хвост после JSON на позиции {}", p.i));
    }
    Ok(v)
}

fn render(j: &Json) -> String {
    let mut out = String::new();
    emit(j, &mut out, 0);
    out
}

// ---------------------------------------------------------------------------
// ChordProgression ⇄ JSON
// ---------------------------------------------------------------------------

fn get<'a>(obj: &'a [(String, Json)], key: &str) -> Option<&'a Json> {
    obj.iter().find(|(k, _)| k == key).map(|(_, v)| v)
}

fn obj_str(obj: &[(String, Json)], key: &str) -> Option<String> {
    match get(obj, key) {
        Some(Json::Str(s)) => Some(s.clone()),
        _ => None,
    }
}

fn obj_num(obj: &[(String, Json)], key: &str) -> Option<i32> {
    match get(obj, key) {
        Some(Json::Num(n)) => i32::try_from(*n).ok(),
        _ => None,
    }
}

impl ChordProgression {
    /// Сериализация в JSON-строку python-формата (to_json из chords.py).
    /// Ключи — в фиксированном порядке, `no_chord_measures` — по возрастанию.
    pub fn to_json(&self) -> String {
        let items: Vec<Json> = self
            .items
            .iter()
            .map(|it| {
                Json::Obj(vec![
                    ("chord".into(), Json::Str(it.chord.name().to_string())),
                    ("measure".into(), Json::Num(it.position.measure as i64)),
                    ("beat".into(), Json::Num(it.position.beat as i64)),
                    ("bass_note".into(), Json::Str(it.bass_note.clone())),
                ])
            })
            .collect();
        let sections: Vec<Json> = self
            .section_marks
            .iter()
            .map(|s| {
                Json::Obj(vec![
                    ("measure".into(), Json::Num(s.measure as i64)),
                    ("mark".into(), Json::Str(s.mark.clone())),
                ])
            })
            .collect();
        let voltas: Vec<Json> = self
            .volta_brackets
            .iter()
            .map(|vb| {
                Json::Obj(vec![
                    ("repeat_start".into(), Json::Num(vb.repeat_start as i64)),
                    ("ending1_start".into(), Json::Num(vb.ending1_start as i64)),
                    ("ending1_end".into(), Json::Num(vb.ending1_end as i64)),
                    ("ending2_start".into(), Json::Num(vb.ending2_start as i64)),
                    ("num_repeats".into(), Json::Num(vb.num_repeats as i64)),
                ])
            })
            .collect();
        let mut no_chord: Vec<i32> = self.no_chord_measures.iter().copied().collect();
        no_chord.sort_unstable();
        let nochord: Vec<Json> = no_chord.iter().map(|m| Json::Num(*m as i64)).collect();

        let root = Json::Obj(vec![
            ("title".into(), Json::Str(self.title.clone())),
            ("key".into(), Json::Str(self.key.clone())),
            ("style".into(), Json::Str(self.style.clone())),
            ("bpm".into(), Json::Num(self.bpm as i64)),
            ("composer".into(), Json::Str(self.composer.clone())),
            (
                "time_signature".into(),
                Json::Str(format!("{}", self.time_signature)),
            ),
            ("total_measures".into(), Json::Num(self.total_measures as i64)),
            ("items".into(), Json::Arr(items)),
            ("section_marks".into(), Json::Arr(sections)),
            ("volta_brackets".into(), Json::Arr(voltas)),
            ("no_chord_measures".into(), Json::Arr(nochord)),
        ]);
        render(&root)
    }

    /// Десериализация из python-совместимого JSON (from_json из chords.py).
    /// Обязательны title/key/style/time_signature; остальное — с python-дефолтами
    /// (bpm=120, composer='Unknown', total_measures=0, пустые списки, num_repeats
    /// клампится в 2..4 как в VoltaBracket.from_dict).
    pub fn from_json(json_str: &str) -> Result<ChordProgression, String> {
        let root = parse_json(json_str)?;
        let obj = match root {
            Json::Obj(pairs) => pairs,
            _ => return Err("верхний уровень JSON должен быть объектом".into()),
        };
        let title = obj_str(&obj, "title").ok_or("нет поля title")?;
        let key = obj_str(&obj, "key").ok_or("нет поля key")?;
        let style = obj_str(&obj, "style").ok_or("нет поля style")?;
        let ts_str = obj_str(&obj, "time_signature").ok_or("нет поля time_signature")?;
        let ts = TimeSignature::from_string(&ts_str);
        let bpm = obj_num(&obj, "bpm").unwrap_or(120);
        let composer = obj_str(&obj, "composer").unwrap_or_else(|| "Unknown".to_string());
        let total_measures = obj_num(&obj, "total_measures").unwrap_or(0);

        let mut prog = ChordProgression {
            title,
            time_signature: ts,
            key,
            style,
            bpm,
            composer,
            total_measures,
            items: Vec::new(),
            section_marks: Vec::new(),
            volta_brackets: Vec::new(),
            no_chord_measures: std::collections::HashSet::new(),
        };

        if let Some(Json::Arr(arr)) = get(&obj, "items") {
            for item in arr {
                let d = match item {
                    Json::Obj(p) => p,
                    _ => return Err("item не объект".into()),
                };
                let chord_name = obj_str(d, "chord").ok_or("нет поля chord в item")?;
                let measure = obj_num(d, "measure").ok_or("нет поля measure в item")?;
                let beat = obj_num(d, "beat").ok_or("нет поля beat в item")?;
                let bass = obj_str(d, "bass_note").unwrap_or_default();
                prog.items.push(ProgressionItem {
                    chord: Chord::new(&chord_name),
                    position: Position::new(measure, beat, ts),
                    bass_note: bass,
                });
            }
        }
        if let Some(Json::Arr(arr)) = get(&obj, "section_marks") {
            for item in arr {
                let d = match item {
                    Json::Obj(p) => p,
                    _ => return Err("section_mark не объект".into()),
                };
                prog.section_marks.push(SectionMark {
                    measure: obj_num(d, "measure").ok_or("нет поля measure в section_mark")?,
                    mark: obj_str(d, "mark").ok_or("нет поля mark в section_mark")?,
                });
            }
        }
        if let Some(Json::Arr(arr)) = get(&obj, "volta_brackets") {
            for item in arr {
                let d = match item {
                    Json::Obj(p) => p,
                    _ => return Err("volta_bracket не объект".into()),
                };
                let num_repeats =
                    obj_num(d, "num_repeats").unwrap_or(2).clamp(2, 4);
                prog.volta_brackets.push(VoltaBracket {
                    repeat_start: obj_num(d, "repeat_start")
                        .ok_or("нет поля repeat_start в volta_bracket")?,
                    ending1_start: obj_num(d, "ending1_start")
                        .ok_or("нет поля ending1_start в volta_bracket")?,
                    ending1_end: obj_num(d, "ending1_end").unwrap_or(0),
                    ending2_start: obj_num(d, "ending2_start").unwrap_or(0),
                    num_repeats,
                });
            }
        }
        if let Some(Json::Arr(arr)) = get(&obj, "no_chord_measures") {
            for m in arr {
                if let Json::Num(n) = m {
                    if let Ok(v) = i32::try_from(*n) {
                        prog.no_chord_measures.insert(v);
                    }
                }
            }
        }
        Ok(prog)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_object_and_array_inline() {
        // Пустые контейнеры python пишет инлайн, даже с indent.
        let j = Json::Obj(vec![("a".into(), Json::Arr(vec![]))]);
        assert_eq!(render(&j), "{\n  \"a\": []\n}");
        let j = Json::Obj(vec![("a".into(), Json::Obj(vec![]))]);
        assert_eq!(render(&j), "{\n  \"a\": {}\n}");
    }

    #[test]
    fn ensure_ascii_escaping() {
        let j = Json::Str("Любовь ✓😀 \"x\" \\ \n \t".into());
        let s = render(&j);
        assert_eq!(
            s,
            "\"\\u041b\\u044e\\u0431\\u043e\\u0432\\u044c \\u2713\\ud83d\\ude00 \\\"x\\\" \\\\ \\n \\t\""
        );
    }

    #[test]
    fn nested_layout() {
        let j = Json::Obj(vec![("a".into(), Json::Obj(vec![("b".into(), Json::Num(1))]))]);
        assert_eq!(render(&j), "{\n  \"a\": {\n    \"b\": 1\n  }\n}");
        let j = Json::Arr(vec![Json::Arr(vec![Json::Num(1)]), Json::Arr(vec![])]);
        assert_eq!(render(&j), "[\n  [\n    1\n  ],\n  []\n]");
    }

    #[test]
    fn from_json_defaults() {
        // Минимальный документ: как python — дефолты для остального.
        let s = r#"{
  "title": "X",
  "key": "C",
  "style": "Rock",
  "time_signature": "4/4"
}"#;
        let cp = ChordProgression::from_json(s).unwrap();
        assert_eq!(cp.bpm, 120);
        assert_eq!(cp.composer, "Unknown");
        assert_eq!(cp.total_measures, 0);
        assert_eq!(cp.title, "X");
    }

    #[test]
    fn from_json_clamps_num_repeats() {
        let s = r#"{"title":"X","key":"C","style":"R","time_signature":"4/4",
            "volta_brackets":[{"repeat_start":1,"ending1_start":2,
            "ending1_end":3,"ending2_start":4,"num_repeats":9}]}"#;
        let cp = ChordProgression::from_json(s).unwrap();
        assert_eq!(cp.volta_brackets[0].num_repeats, 4);
    }
}
