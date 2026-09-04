//! Распознавание имени аккорда по набору нот (без внешних зависимостей).
//! Перенос `_identify_chord_name` из `chords.py`.

use crate::chords::notes::pc_of;

/// Распознать имя аккорда из нот (первая/нижняя = корень).
///
/// Принимает и бемоли, и диезы; корень возвращённого имени сохраняет запись
/// первой ноты. `None`, если распознать нечего.
pub fn identify_chord_name(notes: &[&str]) -> Option<String> {
    // Дедупликация с сохранением порядка.
    let mut clean: Vec<&str> = Vec::new();
    for &n in notes {
        if pc_of(n).is_some() && !clean.contains(&n) {
            clean.push(n);
        }
    }
    if clean.is_empty() {
        return None;
    }

    let root = clean[0];
    let root_pc = pc_of(root).unwrap();

    // Интервалы от корня (mod 12, без 0).
    let mut ivals: Vec<i32> = Vec::new();
    for &n in &clean[1..] {
        let st = (pc_of(n).unwrap() - root_pc).rem_euclid(12);
        if st != 0 && !ivals.contains(&st) {
            ivals.push(st);
        }
    }
    let has = |st: i32| ivals.contains(&st);

    let has_min3 = has(3);
    let has_maj3 = has(4);
    let has_4th = has(5);
    let has_tritone = has(6);
    let has_5th = has(7);
    let has_aug5 = has(8);
    let has_6th = has(9);
    let has_b7 = has(10);
    let has_maj7 = has(11);
    let has_b9 = has(1);
    let has_nat9 = has(2);

    // Валидация 1: b3+maj3 вместе → 3-ступень это #9.
    let sharp9 = has_min3 && has_maj3;
    let min3 = has_min3 && !has_maj3;

    // Валидация 2: тритон при (maj7 или 5) → это #11.
    let sharp11 = has_tritone && (has_maj7 || has_5th);
    let flat5 = has_tritone && !sharp11;

    // Валидация 3: кварта без терции → sus4.
    let sus4 = has_4th && !has_min3 && !has_maj3;

    let exts_str = |parts: &[&str]| -> String {
        if parts.is_empty() {
            String::new()
        } else {
            format!("({})", parts.join(""))
        }
    };

    if sus4 {
        let base = if has_b7 {
            format!("{root}7sus4")
        } else if has_maj7 {
            format!("{root}maj7sus4")
        } else {
            format!("{root}sus4")
        };
        let mut exts: Vec<&str> = Vec::new();
        if has_b9 {
            exts.push("b9");
        }
        if has_6th {
            exts.push("13");
        }
        return Some(base + &exts_str(&exts));
    }

    if min3 && flat5 {
        // Уменьшённое семейство.
        if has_b7 {
            let base = format!("{root}m7b5");
            let mut exts: Vec<&str> = Vec::new();
            if has_b9 {
                exts.push("b9");
            } else if has_nat9 {
                exts.push("9");
            }
            return Some(base + &exts_str(&exts));
        }
        if has_6th {
            return Some(format!("{root}dim7"));
        }
        return Some(format!("{root}dim"));
    }

    if min3 {
        // Минорное семейство.
        let base = if has_maj7 {
            format!("{root}mM7")
        } else if has_b7 {
            if has_4th && has_nat9 {
                return Some(format!("{root}m11"));
            }
            format!("{root}m7")
        } else if has_aug5 {
            return Some(format!("{root}m#5"));
        } else {
            format!("{root}m")
        };
        let mut exts: Vec<&str> = Vec::new();
        if has_nat9 {
            exts.push("9");
        }
        if has_4th {
            exts.push("11");
        }
        if sharp11 {
            exts.push("#11");
        }
        if has_6th {
            exts.push("13");
        }
        return Some(base + &exts_str(&exts));
    }

    if has_maj3 && has_aug5 && !has_5th {
        // Увеличенное семейство.
        if has_b7 {
            return Some(format!("{root}aug7"));
        }
        if has_maj7 {
            return Some(format!("{root}augM7"));
        }
        return Some(format!("{root}aug"));
    }

    if has_maj3 {
        // Мажорное семейство.
        if has_b7 {
            let base = format!("{root}7");
            let mut exts: Vec<&str> = Vec::new();
            if has_b9 {
                exts.push("b9");
            } else if sharp9 {
                exts.push("#9");
            } else if has_nat9 {
                exts.push("9");
            }
            if flat5 {
                exts.push("b5");
            }
            if sharp11 {
                exts.push("#11");
            }
            if has_6th {
                exts.push("13");
            }
            return Some(base + &exts_str(&exts));
        }
        if has_maj7 {
            let base = format!("{root}maj7");
            let mut exts: Vec<&str> = Vec::new();
            if has_nat9 {
                exts.push("9");
            }
            if sharp11 {
                exts.push("#11");
            }
            if has_6th {
                exts.push("13");
            }
            return Some(base + &exts_str(&exts));
        }
        // Мажорное трезвучие с добавками.
        if has_nat9 && has_6th {
            return Some(format!("{root}6/9"));
        }
        if has_6th {
            return Some(format!("{root}6"));
        }
        if has_nat9 {
            return Some(format!("{root}add9"));
        }
        return Some(root.to_string());
    }

    // Нет узнаваемой терции — корень (power chord / одиночная нота).
    Some(root.to_string())
}
