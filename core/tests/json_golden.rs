//! Сверка JSON-персистентности ChordProgression (persist.rs) с python-эталоном.
//! Данные в golden_json.rs: каждый сценарий = параметры конструктора + ops,
//! и python-вывод cp.to_json() (json.dumps indent=2, ensure_ascii). Здесь те же
//! ops отыгрываются на Rust-порте; to_json должен совпасть побайтово, а
//! from_json(to_json) должен дать то же состояние (round-trip).

use irealwx_core::chords::{ChordProgression, Position, TimeSignature};

mod data {
    include!("golden_json.rs");
}

use data::*;

fn replay(g: &JsonGolden) -> ChordProgression {
    let ts = TimeSignature::new(g.ts_num, g.ts_den);
    let mut cp = ChordProgression::new(g.title, ts, g.key, g.style);
    cp.bpm = g.bpm;
    cp.composer = g.composer.to_string();
    for op in g.ops {
        match op.op {
            "section" => cp.add_section_mark(op.a, op.s),
            "chord" => cp.add_chord_by_name(op.s, op.a, op.b, op.t),
            "repeat" => {
                cp.add_repeat_bracket(op.a, op.b);
            }
            "volta" => {
                cp.add_volta_bracket(op.a, op.b, op.c);
            }
            "vstart" => {
                cp.add_volta_start(op.a);
            }
            "nochord" => cp.add_no_chord(op.a),
            "twhole" => cp.transpose(op.a, None),
            "tpos" => {
                let pos = Position::new(op.b, op.c, cp.time_signature);
                cp.transpose(op.a, Some(&[pos]));
            }
            other => panic!("{other}: неизвестная op"),
        }
    }
    cp
}

#[test]
fn to_json_matches_python_reference() {
    for g in ALL {
        let name = g.name;
        let cp = replay(g);
        let got = cp.to_json();
        assert_eq!(got, g.json, "{name}: to_json побайтово");
    }
}

#[test]
fn from_json_roundtrips_python_output() {
    for g in ALL {
        let name = g.name;
        // Эталон состояния после python-ops: Rust-порт отыгрывает те же ops
        // с тех же параметров конструктора. Именно с ним сверяем from_json:
        // поля golden хранят параметры КОНСТРУКТОРА (до ops), а from_json
        // читает финальный вывод — мутируемые поля (key через transpose,
        // total_measures, items) равны только состоянию после replay.
        let replay = replay(g);
        let cp = ChordProgression::from_json(g.json).expect(name);

        // Из python-вывода читаем обратно то же состояние: повторная
        // сериализация должна дать ровно исходные байты.
        assert_eq!(cp.to_json(), g.json, "{name}: from_json→to_json round-trip");

        // Полная структура совпадает с replay-состоянием.
        assert_eq!(cp.title, replay.title, "{name}: title");
        assert_eq!(cp.key, replay.key, "{name}: key");
        assert_eq!(cp.style, replay.style, "{name}: style");
        assert_eq!(cp.bpm, replay.bpm, "{name}: bpm");
        assert_eq!(cp.composer, replay.composer, "{name}: composer");
        assert_eq!(
            cp.time_signature.numerator, replay.time_signature.numerator,
            "{name}: ts numerator"
        );
        assert_eq!(
            cp.time_signature.denominator, replay.time_signature.denominator,
            "{name}: ts denominator"
        );
        assert_eq!(cp.total_measures, replay.total_measures, "{name}: total_measures");
        let items: Vec<_> = cp
            .items
            .iter()
            .map(|i| (i.chord.name().to_string(), i.position.measure, i.position.beat, i.bass_note.clone()))
            .collect();
        let ritems: Vec<_> = replay
            .items
            .iter()
            .map(|i| (i.chord.name().to_string(), i.position.measure, i.position.beat, i.bass_note.clone()))
            .collect();
        assert_eq!(items, ritems, "{name}: items");
        let sm: Vec<_> = cp.section_marks.iter().map(|s| (s.measure, s.mark.clone())).collect();
        let rsm: Vec<_> = replay.section_marks.iter().map(|s| (s.measure, s.mark.clone())).collect();
        assert_eq!(sm, rsm, "{name}: section_marks");
        let vb: Vec<_> = cp
            .volta_brackets
            .iter()
            .map(|v| (v.repeat_start, v.ending1_start, v.ending1_end, v.ending2_start, v.num_repeats))
            .collect();
        let rvb: Vec<_> = replay
            .volta_brackets
            .iter()
            .map(|v| (v.repeat_start, v.ending1_start, v.ending1_end, v.ending2_start, v.num_repeats))
            .collect();
        assert_eq!(vb, rvb, "{name}: volta_brackets");
        assert_eq!(cp.no_chord_measures, replay.no_chord_measures, "{name}: no_chord_measures");
    }
}
