//! Сверка порта ChordProgression с python-эталоном irealstudio.
//! Данные в golden_progression.rs сгенерированы из chords.py: каждый сценарий —
//! список ops (аккорды/секции/вольты/повторы/транспонирование) плюс полный
//! свип навигации по тактам. Здесь те же ops отыгрываются на Rust-порте и
//! сравниваются снапшот структуры и все ответы навигации.

use irealwx_core::chords::{ChordProgression, Position, TimeSignature};

mod data {
    include!("golden_progression.rs");
}

use data::*;

fn replay(g: &ProgGolden) -> ChordProgression {
    let ts = TimeSignature::new(4, 4);
    let mut cp = ChordProgression::new(g.name, ts, "C", "Rock");
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
fn progression_scenarios_match_python_reference() {
    for g in ALL {
        let cp = replay(g);
        let name = g.name;

        // Структурный снапшот: brackets / items / sections / nochord / markers.
        let brackets: Vec<(i32, i32, i32, i32, i32, i32)> = g
            .brackets
            .iter()
            .map(|b| (b.rs, b.e1s, b.e1e, b.e2s, b.nr, b.ro))
            .collect();
        let got_brackets: Vec<(i32, i32, i32, i32, i32, i32)> = cp
            .volta_brackets
            .iter()
            .map(|vb| {
                (
                    vb.repeat_start,
                    vb.ending1_start,
                    vb.ending1_end,
                    vb.ending2_start,
                    vb.num_repeats,
                    i32::from(vb.is_repeat_only()),
                )
            })
            .collect();
        assert_eq!(got_brackets, brackets, "{name}: brackets");

        let items: Vec<(String, i32, i32, String)> = g
            .items
            .iter()
            .map(|i| (i.chord.to_string(), i.m, i.b, i.bass.to_string()))
            .collect();
        let got_items: Vec<(String, i32, i32, String)> = cp
            .items
            .iter()
            .map(|i| {
                (
                    i.chord.name().to_string(),
                    i.position.measure,
                    i.position.beat,
                    i.bass_note.clone(),
                )
            })
            .collect();
        assert_eq!(got_items, items, "{name}: items");

        let sections: Vec<(i32, String)> = g
            .sections
            .iter()
            .map(|s| (s.m, s.mark.to_string()))
            .collect();
        let got_sections: Vec<(i32, String)> = cp
            .section_marks
            .iter()
            .map(|s| (s.measure, s.mark.clone()))
            .collect();
        assert_eq!(got_sections, sections, "{name}: sections");

        let nochord: Vec<i32> = g.nochord.to_vec();
        let mut got_nochord: Vec<i32> = cp.no_chord_measures.iter().copied().collect();
        got_nochord.sort();
        assert_eq!(got_nochord, nochord, "{name}: no_chord_measures");

        let structural: Vec<i32> = g.structural.to_vec();
        assert_eq!(cp.structural_marker_measures(), structural, "{name}: structural markers");

        assert_eq!(cp.last_measure(), g.last_measure, "{name}: last_measure");
        assert_eq!(cp.key, g.key, "{name}: key");

        // Свип навигации.
        for want in g.rows {
            let m = want.m;
            let vc = cp.get_virtual_context(m);
            let (vc0, vc1) = match vc {
                Some((s, e)) => (s, e),
                None => (-1, -1),
            };
            let down = cp.navigate_down_from_measure(m).unwrap_or(-1);
            let up = cp.navigate_up_from_measure(m).unwrap_or(-1);
            let got = (
                m,
                vc0,
                vc1,
                down,
                up,
                i32::from(cp.is_in_virtual_range(m)),
                i32::from(cp.is_in_hidden_range(m)),
                i32::from(cp.is_plain_virtual(m)),
                cp.resolve_virtual_measure(m),
                cp.get_repeat_num_for_measure(m),
                i32::from(cp.get_volta_bracket_for_measure(m).is_some()),
                cp.primary_skip_past_virtual(1, m),
            );
            let exp = (
                want.m,
                want.vc0,
                want.vc1,
                want.down,
                want.up,
                want.inv,
                want.hid,
                want.pv,
                want.res,
                want.rep,
                want.vb,
                want.skip,
            );
            assert_eq!(got, exp, "{name}: measure {m}");
        }
    }
}
