//! Вокализация аккорда в MIDI-ноты (правила из task.md).
//! Перенос `_QUALITY_INTERVALS` / `_quality_to_intervals` / `voice_chord_midi`
//! из `chords.py`.

use crate::chords::notes::{pc_of, root_prefix};

// Диапазон MIDI для корня (E1=28 … Bb2=46).
const VOICE_ROOT_LOW: i32 = 28;
const VOICE_ROOT_HIGH: i32 = 46;
// Диапазон MIDI для основных тонов аккорда (Eb3=51 … Ab4=68).
const VOICE_CORE_LOW: i32 = 51;
const VOICE_CORE_HIGH: i32 = 68;

/// (качество → (основные интервалы, интервалы-расширения)).
const QUALITY_INTERVALS: &[(&str, &[i32], &[i32])] = &[
    ("", &[4, 7], &[]),
    ("m", &[3, 7], &[]),
    ("dim", &[3, 6], &[]),
    ("aug", &[4, 8], &[]),
    ("sus4", &[5, 7], &[]),
    ("sus2", &[2, 7], &[]),
    ("sus", &[5, 7], &[]),
    ("7", &[4, 7, 10], &[]),
    ("maj7", &[4, 7, 11], &[]),
    ("m7", &[3, 7, 10], &[]),
    ("mM7", &[3, 7, 11], &[]),
    ("m7b5", &[3, 6, 10], &[]),
    ("m7(b5)", &[3, 6, 10], &[]),
    ("dim7", &[3, 6, 9], &[]),
    ("aug7", &[4, 8, 10], &[]),
    ("augM7", &[4, 8, 11], &[]),
    ("7sus4", &[5, 7, 10], &[]),
    ("7sus", &[5, 7, 10], &[]),
    ("6", &[4, 7, 9], &[]),
    ("m6", &[3, 7, 9], &[]),
    ("m#5", &[3, 8], &[]),
    ("add9", &[4, 7], &[14]),
    ("9", &[4, 7, 10], &[14]),
    ("maj9", &[4, 7, 11], &[14]),
    ("m9", &[3, 7, 10], &[14]),
    ("mM7(9)", &[3, 7, 11], &[14]),
    ("m11", &[3, 7, 10], &[14, 17]),
    ("m13", &[3, 7, 10], &[14, 21]),
    ("maj11", &[4, 7, 11], &[14, 17]),
    ("maj13", &[4, 7, 11], &[14, 21]),
    ("11", &[4, 7, 10], &[14, 17]),
    ("13", &[4, 7, 10], &[14, 21]),
    ("6/9", &[4, 7, 9], &[14]),
    ("m6/9", &[3, 7, 9], &[14]),
    ("7(b9)", &[4, 7, 10], &[13]),
    ("7(#9)", &[4, 7, 10], &[15]),
    ("7(#11)", &[4, 7, 10], &[18]),
    ("7(b5)", &[4, 6, 10], &[]),
    ("7(b13)", &[4, 7, 10], &[20]),
    ("7(9)", &[4, 7, 10], &[14]),
    ("7(13)", &[4, 7, 10], &[21]),
    ("7(b9#11)", &[4, 7, 10], &[13, 18]),
    ("7(#9#11)", &[4, 7, 10], &[15, 18]),
    ("7(b9b5)", &[4, 6, 10], &[13]),
    ("7(#9b5)", &[4, 6, 10], &[15]),
    ("7(9b5)", &[4, 6, 10], &[14]),
    ("7(#9#5)", &[4, 8, 10], &[15]),
    ("7(b9#5)", &[4, 8, 10], &[13]),
    ("maj7(#11)", &[4, 7, 11], &[18]),
    ("maj7(9)", &[4, 7, 11], &[14]),
    ("maj7(9#11)", &[4, 7, 11], &[14, 18]),
    ("maj7(13)", &[4, 7, 11], &[21]),
    ("m7(9)", &[3, 7, 10], &[14]),
    ("m7(#11)", &[3, 7, 10], &[18]),
    ("m7(13)", &[3, 7, 10], &[21]),
    ("m7b5(b9)", &[3, 6, 10], &[13]),
    ("m7b5(9)", &[3, 6, 10], &[14]),
    ("7sus4(b9)", &[5, 7, 10], &[13]),
    ("maj7sus4", &[5, 7, 11], &[]),
];

/// Токен расширения → дополнительный интервал (длинные первыми).
const EXT_TOKEN_INTERVALS: &[(&str, i32)] = &[
    ("#11", 18),
    ("b13", 20),
    ("#9", 15),
    ("b9", 13),
    ("#5", 8),
    ("b5", 6),
    ("13", 21),
    ("11", 17),
    ("9", 14),
    ("7", 10),
    ("6", 9),
];

/// Качество → (основные интервалы, расширения). Сначала точное совпадение,
/// потом longest-prefix + разбор токенов расширения. Fallback — мажорное трезвучие.
fn quality_to_intervals(quality: &str) -> (Vec<i32>, Vec<i32>) {
    for &(q, core, ext) in QUALITY_INTERVALS {
        if quality == q {
            return (core.to_vec(), ext.to_vec());
        }
    }

    // Срезать внешние скобки.
    let inner = strip_parens(quality);

    // Longest-prefix среди известных качеств.
    let mut best_base = "";
    for &(q, _, _) in QUALITY_INTERVALS {
        if inner.starts_with(q) && q.len() > best_base.len() {
            best_base = q;
        }
    }

    if !best_base.is_empty() {
        let (core, ext) = QUALITY_INTERVALS
            .iter()
            .find(|(q, _, _)| *q == best_base)
            .map(|(_, c, e)| (c.to_vec(), e.to_vec()))
            .unwrap();
        let mut core = core;
        let mut ext = ext;

        let mut remainder = &inner[best_base.len()..];
        remainder = strip_parens(remainder);

        let mut pos = 0;
        while pos < remainder.len() {
            let rest = &remainder[pos..];
            let mut matched = false;
            for &(token, interval) in EXT_TOKEN_INTERVALS {
                if rest.starts_with(token) {
                    if interval >= 12 {
                        ext.push(interval);
                    } else {
                        core.push(interval);
                    }
                    pos += token.len();
                    matched = true;
                    break;
                }
            }
            if !matched {
                pos += 1; // пропустить незнакомый символ
            }
        }
        return (core, ext);
    }

    // Fallback: мажорное трезвучие.
    (vec![4, 7], vec![])
}

fn strip_parens(s: &str) -> &str {
    if s.len() >= 2 && s.starts_with('(') && s.ends_with(')') {
        &s[1..s.len() - 1]
    } else {
        s
    }
}

/// Выбрать MIDI-ноту корня с голосоведением в [ROOT_LOW, ROOT_HIGH].
fn pick_root_midi(root_pc: i32, prev_root: Option<i32>) -> i32 {
    let mut candidates: Vec<i32> = (VOICE_ROOT_LOW..=VOICE_ROOT_HIGH)
        .filter(|&n| n % 12 == root_pc)
        .collect();
    if candidates.is_empty() {
        let mut n = VOICE_ROOT_LOW;
        while n % 12 != root_pc {
            n += 1;
        }
        candidates.push(n);
    }
    match prev_root {
        None => candidates[0],
        Some(prev) => *candidates
            .iter()
            .min_by_key(|&&x| (x - prev).abs())
            .unwrap(),
    }
}

/// Озвучить аккорд как список MIDI-нот + MIDI корня.
///
/// Слэш-бас (/E) отрезается перед вокализацией. *prev_root* — MIDI корня
/// предыдущего аккорда (голосоведение); None = самый низкий кандидат.
pub fn voice_chord_midi(name: &str, prev_root: Option<i32>) -> (Vec<i32>, i32) {
    let root_str = root_prefix(name);
    if root_str.is_empty() {
        return (Vec::new(), 0);
    }
    let mut quality = &name[root_str.len()..];

    // Срезать слэш-бас (например '/E') из качества.
    if let Some(idx) = quality.rfind('/') {
        if idx + 1 < quality.len()
            && quality.as_bytes()[idx + 1].is_ascii_uppercase()
        {
            quality = &quality[..idx];
        }
    }

    let root_pc = pc_of(root_str).unwrap_or(0);
    let (mut core_ivals, mut ext_ivals) = quality_to_intervals(quality);

    // Sus-вокализация: корень + b7 (если есть) + 9 + 11 (+13). Без 3-й и 5-й.
    // Ветку ведём от *токена* качества, а не от наличия интервала 5: иначе
    // maj7sus4 (с чистой квартой, но мажорно-септовой окраской) схлопнулся бы
    // в простой sus и потерял тона.
    let has_sus = quality.starts_with("sus4") || quality.starts_with("7sus4");
    if has_sus {
        let b7_present = core_ivals.contains(&10);
        core_ivals = if b7_present { vec![10] } else { Vec::new() };
        // Всегда стэкаем 9 (14) и 11 (17); 13 оставляем, если была.
        let mut sus_ext = vec![14, 17];
        for x in &ext_ivals {
            if !sus_ext.contains(x) {
                sus_ext.push(*x);
            }
        }
        ext_ivals = sus_ext;
    } else {
        // Джазовое озвучивание: убираем чистую квинту (7) у доминант
        // (мажорная терция + минорная септима), кроме мажорных 7-х и т.п.
        if core_ivals.contains(&4) && core_ivals.contains(&10) {
            core_ivals.retain(|&x| x != 7);
        }
    }

    let root_midi = pick_root_midi(root_pc, prev_root);
    let mut notes: Vec<i32> = vec![root_midi];

    // Порядок основных тонов: у доминант b7 кладём ПЕРЕД терцией (shell-вокализ).
    let core_order: Vec<i32> = if !has_sus && core_ivals.contains(&4) && core_ivals.contains(&10) {
        let mut other: Vec<i32> = core_ivals
            .iter()
            .copied()
            .filter(|&i| i != 4 && i != 10)
            .collect();
        other.sort();
        let mut v = vec![10, 4];
        v.extend(other);
        v
    } else {
        let mut v = core_ivals.clone();
        v.sort();
        v.dedup();
        v
    };

    let mut cursor = root_midi;
    for &ival in &core_order {
        let note_pc = (root_pc + ival).rem_euclid(12);
        let mut n = (cursor / 12) * 12 + note_pc;
        while n <= cursor {
            n += 12;
        }
        while n > VOICE_CORE_HIGH {
            n -= 12;
        }
        if n < VOICE_CORE_LOW {
            n += 12;
        }
        if !notes.contains(&n) {
            notes.push(n);
            cursor = n;
        }
    }

    // Расширения строго выше самого верхнего основного тона, но не ниже
    // октавы от корня (root_midi + 12).
    let mut ext_base = std::cmp::max(root_midi + 12, cursor + 1);
    let mut exts: Vec<i32> = ext_ivals.clone();
    exts.sort();
    exts.dedup();
    for &ival in &exts {
        let note_pc = (root_pc + ival).rem_euclid(12);
        let mut n = (ext_base / 12) * 12 + note_pc;
        while n < ext_base {
            n += 12;
        }
        if !notes.contains(&n) {
            notes.push(n);
            ext_base = n + 1;
        }
    }

    notes.sort();
    (notes, root_midi)
}
