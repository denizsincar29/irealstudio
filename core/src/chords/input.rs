//! Валидация и канонизация вводимого пользователем имени аккорда (слайс 14,
//! msg 1607): «если корня и функции нет в iReal Pro — значит нет. Ошиба!»
//!
//! Гейт ввода (диалоги «Добавить аккорд» / F2 / «/» бас) прогоняет сырой текст
//! через `parse_chord_entry`: распознаётся корень из `ALL_ROOTS`, качество
//! сверяется со словарём озвучки (`QUALITY`/`EXT` в spoken.rs — это ровно то,
//! что мы умеем произнести и экспортировать в iReal), дисплейные маркеры
//! `-7`/`^7` приводятся к канонической записи `m7`/`maj7` (как в python и в
//! файлах .ips: `Cm7`, `Bbmaj7`). Всё, что не разбирается (кириллица, опечатка,
//! несуществующая функция) — отклоняется с ошибкой; ничего незнакомого в
//! цифровку не попадает.
//!
//! Надёжные пути (открытие .ips, экспорт, вставка из буфера, transpose) этот
//! гейт НЕ проходят — там имена уже валидны.

use super::notes::{root_prefix, ALL_ROOTS};
use super::spoken::{display_to_canonical, EXT, QUALITY};

/// Разобранный валидный ввод: каноническое имя (напр. `Bm7`) и слэш-бас.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ParsedChord {
    /// Каноническое имя: корень как введён + качество в канонической записи
    /// (`-7`→`m7`, `^7`→`maj7`, `M7`→`maj7`). Без баса.
    pub name: String,
    /// Каноническая басовая нота, если ввод нёс `/нота`.
    pub bass: Option<String>,
}

/// Причина отклонения ввода (для сообщения об ошибке — формулирует ui).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChordEntryError {
    /// Пустой ввод — не ошибка, а «ничего не введено» (диалог закрыт без текста).
    Empty,
    /// Корень не распознан (кириллица «С6», опечатка, мусор в начале).
    Root,
    /// Функция (качество) не существует в словаре iReal Pro.
    Quality,
    /// После `/` стоит не нота, или нота не существует (`/H`, `/X`, `/G7`).
    Bass,
}

/// Первую ASCII-букву — в верхний регистр (корень/бас пишутся с заглавной;
/// остальное, включая бемоль-маркер `b` и качество, не трогаем — `b7`-нотация
/// уже каноническая строчная). Так «bm7» → «Bm7», «bb7» → «Bb7», а «maj7»
/// остаётся как есть.
fn fix_root_case(s: &str) -> String {
    let mut out: Vec<char> = s.chars().collect();
    if let Some(first) = out.first_mut() {
        if first.is_ascii_alphabetic() {
            *first = first.to_ascii_uppercase();
        }
    }
    out.into_iter().collect()
}

/// Привести дисплейные/неканонические маркеры качества к канонической записи:
/// `-7`→`m7` (дисплейный минор), `^7`→`maj7` (дисплейный мажор), ведущий `M7`
///→`maj7`, а также регистр слова-качества (`MAJ7`→`maj7`, `SUS4`→`sus4`, …).
/// Парентезы и extension-токены не трогаем.
pub(crate) fn normalize_quality(q: &str) -> String {
    let s = display_to_canonical(q);
    // Ведущий `M` как мажор (только перед цифрой/скобкой/концом — «M7», «M9»;
    // в «Maj7» буква M — часть слова, её разберёт блок ниже).
    if s.len() == 1 && s == "M" {
        return "maj".to_string();
    }
    if let Some(rest) = s.strip_prefix('M') {
        if let Some(c) = rest.chars().next() {
            if c.is_ascii_digit() || c == '(' {
                return format!("maj{rest}");
            }
        }
    }
    // Слово-качество в верхнем регистре → канонический нижний («MAJ7»→«maj7»,
    // «DIM»→«dim»). Смешанный регистр («Maj7») не трогаем.
    let end = s
        .find(|c: char| !c.is_ascii_alphabetic())
        .unwrap_or(s.len());
    let run = &s[..end];
    if !run.is_empty() && run.bytes().all(|b| b.is_ascii_uppercase()) {
        let lc = run.to_ascii_lowercase();
        if matches!(lc.as_str(), "m" | "maj" | "dim" | "sus" | "aug" | "add") {
            return lc + &s[end..];
        }
    }
    s
}

/// Съедобно ли качество целиком: точное совпадение со словарём ИЛИ разложение
/// на базовое качество + extension-токены без остатка (как `spoken_quality_fallback`).
/// Пустая строка = голое трезвучие корня — валидно («C»).
fn quality_is_valid(quality: &str) -> bool {
    let norm = normalize_quality(quality);
    if norm.is_empty() {
        return true;
    }
    if QUALITY.iter().any(|(src, _)| *src == norm) {
        return true;
    }

    // Разложение: убрать внешние скобки и взять самую длинную приставку-качество.
    let mut inner = norm.as_str();
    if inner.starts_with('(') && inner.ends_with(')') && inner.len() >= 2 {
        inner = &inner[1..inner.len() - 1];
    }
    let mut best_base = "";
    for (src, _) in QUALITY {
        if inner.starts_with(src) && src.len() > best_base.len() {
            best_base = src;
        }
    }
    if best_base.is_empty() {
        return false; // «b9» без базы — не функция аккорда.
    }
    let mut remainder = &inner[best_base.len()..];
    if remainder.starts_with('(') && remainder.ends_with(')') && remainder.len() >= 2 {
        remainder = &remainder[1..remainder.len() - 1];
    }
    // Остаток должен целиком состоять из известных extension-токенов.
    let mut pos = 0;
    while pos < remainder.len() {
        let rest = &remainder[pos..];
        let mut matched = false;
        for (token, _) in EXT {
            if rest.starts_with(token) {
                pos += token.len();
                matched = true;
                break;
            }
        }
        if !matched {
            return false;
        }
    }
    true
}

/// Разобрать и валидировать ноту баса (после `/` или из диалога «/»).
/// Принимает все хроматические написания из `ALL_ROOTS`, первую букву —
/// независимо от регистра. `None` — не нота или несуществующая нота.
pub fn normalize_bass_note(raw: &str) -> Option<String> {
    let t = fix_root_case(raw.trim());
    if t.is_empty() {
        return None;
    }
    // Басовой нотой может быть ТОЛЬКО ровно один корень из словаря.
    if ALL_ROOTS.iter().any(|r| *r == t.as_str()) {
        Some(t)
    } else {
        None
    }
}

/// Полный гейт ввода имени аккорда (можно со слэш-басом).
///
/// Принимает: `B-7`, `Bm7`, `Bb7/G`, `C^7`, `Cmaj7(9)`, `G7(b9)`, `F7b9`…
/// Отклоняет: пустое, не-корень (`С6` — кириллица, `H7`, мусор), незнакомую
/// функцию (`C69` без известных токенов), несуществующую ноту после `/`.
pub fn parse_chord_entry(raw: &str) -> Result<ParsedChord, ChordEntryError> {
    // Пробелы внутри записи («B m7», «C / G») несущественны — убираем.
    let compact: String = raw
        .trim()
        .chars()
        .filter(|c| !c.is_whitespace())
        .collect();
    if compact.is_empty() {
        return Err(ChordEntryError::Empty);
    }
    let t = fix_root_case(&compact);

    // Слэш-бас: '/' перед буквой — нота баса (`C/E`, `Bb7/G`); '/' перед цифрой —
    // часть качества (`m6/9`). В отличие от python принимаем и строчную басовую
    // ноту (`C/e`) — регистр нормируется ниже.
    let mut bass = None;
    let mut head = t.as_str();
    if let Some(pos) = t.rfind('/') {
        let tail = &t[pos + 1..];
        match tail.chars().next() {
            None => return Err(ChordEntryError::Bass), // «C/» — после / нет ноты
            Some(c) if c.is_ascii_alphabetic() => {
                // '/' перед буквой — нота баса. Хвост обязан быть ровно одной
                // нотой, иначе («C/G7», «C/X») — ошибка.
                match normalize_bass_note(tail) {
                    Some(b) => {
                        bass = Some(b);
                        head = &t[..pos];
                    }
                    None => return Err(ChordEntryError::Bass),
                }
            }
            // '/' перед цифрой — часть качества (`m6/9`), баса нет.
            _ => {}
        }
    }

    if head.is_empty() {
        return Err(ChordEntryError::Root);
    }
    let root = root_prefix(head);
    if root.is_empty() {
        return Err(ChordEntryError::Root);
    }
    let quality = &head[root.len()..];
    if !quality_is_valid(quality) {
        return Err(ChordEntryError::Quality);
    }
    let canonical_q = normalize_quality(quality);
    let mut name = root.to_string();
    name.push_str(&canonical_q);
    Ok(ParsedChord { name, bass })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ok(raw: &str) -> ParsedChord {
        parse_chord_entry(raw).unwrap_or_else(|e| panic!("{raw}: ожидался валидный ввод, {e:?}"))
    }
    fn err(raw: &str) -> ChordEntryError {
        match parse_chord_entry(raw) {
            Ok(p) => panic!("{raw}: ожидалась ошибка, получено {p:?}"),
            Err(e) => e,
        }
    }

    #[test]
    fn accepts_canonical_and_display() {
        // Каноническая запись python/.ips проходит как есть.
        assert_eq!(ok("Bm7"), ParsedChord { name: "Bm7".into(), bass: None });
        assert_eq!(ok("Bbmaj7"), ParsedChord { name: "Bbmaj7".into(), bass: None });
        assert_eq!(ok("Cm7(9)"), ParsedChord { name: "Cm7(9)".into(), bass: None });
        assert_eq!(ok("G7(b9)"), ParsedChord { name: "G7(b9)".into(), bass: None });
        assert_eq!(ok("C"), ParsedChord { name: "C".into(), bass: None });
        assert_eq!(ok("Am6/9"), ParsedChord { name: "Am6/9".into(), bass: None });
        // Дисплейные маркеры iReal Pro канонизируются в «m»/«maj».
        assert_eq!(ok("B-7"), ParsedChord { name: "Bm7".into(), bass: None });
        assert_eq!(ok("C^7"), ParsedChord { name: "Cmaj7".into(), bass: None });
        assert_eq!(ok("F^7"), ParsedChord { name: "Fmaj7".into(), bass: None });
        // Неканонический регистр качества.
        assert_eq!(ok("Cmaj7"), ok("C^7"));
    }

    #[test]
    fn accepts_case_tolerant_roots() {
        assert_eq!(ok("bm7").name, "Bm7");
        assert_eq!(ok("bb7").name, "Bb7");
        assert_eq!(ok("db7").name, "Db7");
        assert_eq!(ok("e-7").name, "Em7");
    }

    #[test]
    fn accepts_slash_bass() {
        assert_eq!(
            ok("Bb7/G"),
            ParsedChord { name: "Bb7".into(), bass: Some("G".into()) }
        );
        assert_eq!(
            ok("C/e"),
            ParsedChord { name: "C".into(), bass: Some("E".into()) }
        );
        // Слэш перед цифрой — часть качества, не бас.
        assert_eq!(ok("Cm6/9").bass, None);
        // Двойной слэш: последний перед буквой — бас.
        assert_eq!(
            ok("Cm6/9/Bb"),
            ParsedChord { name: "Cm6/9".into(), bass: Some("Bb".into()) }
        );
    }

    #[test]
    fn rejects_unknown() {
        assert_eq!(err("С6"), ChordEntryError::Root, "кириллический корень");
        assert_eq!(err("H7"), ChordEntryError::Root, "несуществующая нота H");
        assert_eq!(err(""), ChordEntryError::Empty);
        assert_eq!(err("   "), ChordEntryError::Empty);
        assert_eq!(err("Cm6x"), ChordEntryError::Quality, "незнакомый токен в функции");
        assert_eq!(err("Cmaj7x"), ChordEntryError::Quality, "хвост после функции");
        assert_eq!(err("Cq7"), ChordEntryError::Quality, "q не функция");
        assert_eq!(err("C6x"), ChordEntryError::Quality, "хвост после функции");
    }

    #[test]
    fn rejects_known_root_with_bad_function() {
        assert_eq!(err("Cb9"), ChordEntryError::Quality, "b9 без септаккорда");
        assert_eq!(err("Cm7q"), ChordEntryError::Quality);
        assert_eq!(err("Cm7(9x)"), ChordEntryError::Quality);
    }

    #[test]
    fn rejects_bad_bass() {
        assert_eq!(err("C/X"), ChordEntryError::Bass);
        assert_eq!(err("C/G7"), ChordEntryError::Bass, "после / не одна нота");
        assert_eq!(err("C/"), ChordEntryError::Bass, "после / пусто");
    }

    #[test]
    fn bass_note_validation() {
        assert_eq!(normalize_bass_note("G"), Some("G".to_string()));
        assert_eq!(normalize_bass_note("e"), Some("E".to_string()));
        assert_eq!(normalize_bass_note("Bb"), Some("Bb".to_string()));
        assert_eq!(normalize_bass_note("bb"), Some("Bb".to_string()));
        assert_eq!(normalize_bass_note("H"), None);
        assert_eq!(normalize_bass_note(""), None);
        assert_eq!(normalize_bass_note("G7"), None);
    }
}
