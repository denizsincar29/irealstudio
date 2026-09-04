#!/usr/bin/env python3
"""Generate golden_progression.rs: ChordProgression behavior verified against
irealstudio/chords.py. Each scenario is a list of ops (add chords/sections,
repeat/volta brackets, transpose), then a probe sweep of navigation/geometry
methods across measures 1..scan_end. The Rust test replays the same ops and
compares the resulting brackets/items/sections + the full probe sweep.
"""
import sys

sys.path.insert(0, '/home/superlisa/workspace/irealstudio')
from chords import ChordProgression, TimeSignature, Position  # noqa: E402

# Make the message-returning bracket methods safe without gettext bindings.
import chords as _ch  # noqa: E402
_ch._ = lambda s: s
_ch.ngettext = lambda s, p, n: s


def TS(n=4, d=4):
    return TimeSignature(n, d)


# op helpers: (op, a, b, c, s, t)
def OP(section, m, s):      return ('section', m, 0, 0, s, '')
def OPchord(name, m, b, bas): return ('chord', m, b, 0, name, bas)
def OPrepeat(rs, re):       return ('repeat', rs, re, 0, '', '')
def OPvolta(rs, re, vs):    return ('volta', rs, re, vs, '', '')
def OPvstart(m):            return ('vstart', m, 0, 0, '', '')
def OPnochord(m):           return ('nochord', m, 0, 0, '', '')
def OPtwhole(st):           return ('twhole', st, 0, 0, '', '')
def OPtpos(st, m, b):       return ('tpos', st, m, b, '', '')


def run_ops(cp, ops):
    """Execute ops on the progression AND return the same ops (annotated for Rust)."""
    for op in ops:
        kind = op[0]
        if kind == 'section':
            cp.add_section_mark(op[1], op[4])
        elif kind == 'chord':
            cp.add_chord_by_name(op[4], op[1], op[2], op[5])
        elif kind == 'repeat':
            cp.add_repeat_bracket(op[1], op[2])
        elif kind == 'volta':
            cp.add_volta_bracket(op[1], op[2], op[3])
        elif kind == 'vstart':
            cp.add_volta_start(op[1])
        elif kind == 'nochord':
            cp.add_no_chord(op[1])
        elif kind == 'twhole':
            cp.transpose(op[1])
        elif kind == 'tpos':
            pos = Position(op[2], op[3], cp.time_signature)
            cp.transpose(op[1], [pos])


def scan(cp, scan_end):
    rows = []
    for m in range(1, scan_end + 1):
        vc = cp.get_virtual_context(m)
        vc0, vc1 = vc if vc else (-1, -1)
        d = cp.navigate_down_from_measure(m)
        u = cp.navigate_up_from_measure(m)
        rows.append((
            m,
            vc0, vc1,
            d if d is not None else -1,
            u if u is not None else -1,
            int(cp.is_in_virtual_range(m)),
            int(cp.is_in_hidden_range(m)),
            int(cp._is_plain_virtual(m)),
            cp.resolve_virtual_measure(m),
            cp.get_repeat_num_for_measure(m),
            int(cp.get_volta_bracket_for_measure(m) is not None),
            cp.primary_skip_past_virtual(1, m),
        ))
    return rows


def snapshot(cp):
    brackets = [[vb.repeat_start, vb.ending1_start, vb.ending1_end,
                 vb.ending2_start, vb.num_repeats, int(vb.is_repeat_only())]
                for vb in cp.volta_brackets]
    items = [[it.chord.name, it.position.measure, it.position.beat, it.bass_note]
             for it in cp.items]
    sections = [[s.measure, s.mark] for s in cp.section_marks]
    return {
        'brackets': brackets,
        'items': items,
        'sections': sections,
        'nochord': sorted(cp.no_chord_measures),
        'structural': cp.structural_marker_measures(),
        'last_measure': cp.last_measure(),
        'key': cp.key,
        # Экспорт-URL: python-эталон для порта to_ireal_url/to_irealb_url.
        'url': cp.to_ireal_url(True),
        'url_raw': cp.to_ireal_url(False),
        'irealb': cp.to_irealb_url(True),
        'irealb_raw': cp.to_irealb_url(False),
    }


def scen_plain():
    ops = [
        OP('section', 1, '*A'),
        OPchord('C', 2, 1, ''), OPchord('F', 3, 1, ''), OPchord('A', 3, 3, ''),
        OPchord('G', 4, 1, ''),
        OPrepeat(2, 5),
        OPchord('C7', 11, 1, ''), OPchord('F', 12, 3, ''),
        OPnochord(14),
    ]
    cp = ChordProgression('Plain', TS(), 'C', 'Rock')
    run_ops(cp, ops)
    return cp, ops


def scen_volta_explicit():
    ops = [
        OP('section', 1, '*A'),
        OPchord('C', 2, 1, ''), OPchord('F', 3, 1, ''),
        OPchord('G', 4, 1, ''), OPchord('Am', 5, 1, ''),
        OPchord('E7', 7, 1, ''),   # inside the hidden range (6..7) -> cleared
        OPvolta(2, 5, 4),
        OPchord('D7', 8, 1, ''), OPchord('G7', 10, 1, ''),
    ]
    cp = ChordProgression('VoltaEx', TS(), 'C', 'Rock')
    run_ops(cp, ops)
    return cp, ops


def scen_volta_section():
    ops = [
        OP('section', 1, '*A'),
        OP('section', 8, '*B'),
        OPchord('C', 1, 1, ''), OPchord('F', 2, 1, ''), OPchord('G', 3, 1, ''),
        OPchord('A7', 10, 1, ''),  # inside derived hidden range (8..10) -> cleared
        OPvstart(4),
        OPchord('D7', 11, 1, ''), OPchord('G7', 12, 1, ''), OPchord('C', 15, 1, ''),
    ]
    cp = ChordProgression('VoltaSec', TS(), 'C', 'Rock')
    run_ops(cp, ops)
    return cp, ops


def scen_replace():
    ops = [
        OPrepeat(2, 5),
        OPvolta(2, 5, 4),
        OPchord('D7', 4, 1, ''),
    ]
    cp = ChordProgression('Replace', TS(), 'C', 'Rock')
    run_ops(cp, ops)
    return cp, ops


def scen_transpose():
    ops = [
        OPchord('C7', 1, 1, ''), OPchord('F', 3, 1, ''), OPchord('G', 4, 3, 'B'),
        OPtwhole(6),
        OPtpos(5, 3, 1),
    ]
    cp = ChordProgression('Transpose', TS(), 'C', 'Rock')
    run_ops(cp, ops)
    return cp, ops


def main():
    scan_end = 22
    scenarios = []
    for name, builder in [
        ('plain', scen_plain),
        ('volta_explicit', scen_volta_explicit),
        ('volta_section', scen_volta_section),
        ('replace', scen_replace),
        ('transpose', scen_transpose),
    ]:
        cp, ops = builder()
        scenarios.append((name, cp, ops, snapshot(cp), scan_end, scan(cp, scan_end)))
    emit(scenarios)
    print('scenarios generated:', [s[0] for s in scenarios])


def emit(scenarios):
    L = []
    L.append('// AUTO-GENERATED by gen_progression_golden.py — do not edit.')
    L.append('// ChordProgression behavior verified against irealstudio/chords.py')
    L.append('// (порт progression.rs).')
    L.append('')
    L.append('pub struct OpFlat { pub op: &\'static str, pub a: i32, pub b: i32, pub c: i32, pub s: &\'static str, pub t: &\'static str }')
    L.append('pub struct BracketFlat { pub rs: i32, pub e1s: i32, pub e1e: i32, pub e2s: i32, pub nr: i32, pub ro: i32 }')
    L.append('pub struct ItemFlat { pub chord: &\'static str, pub m: i32, pub b: i32, pub bass: &\'static str }')
    L.append('pub struct SecFlat { pub m: i32, pub mark: &\'static str }')
    L.append('pub struct RowFlat { pub m: i32, pub vc0: i32, pub vc1: i32, pub down: i32, pub up: i32, pub inv: i32, pub hid: i32, pub pv: i32, pub res: i32, pub rep: i32, pub vb: i32, pub skip: i32 }')
    L.append('pub struct ProgGolden { pub name: &\'static str, pub title: &\'static str, pub ops: &\'static [OpFlat], pub brackets: &\'static [BracketFlat], pub items: &\'static [ItemFlat], pub sections: &\'static [SecFlat], pub nochord: &\'static [i32], pub structural: &\'static [i32], pub last_measure: i32, pub key: &\'static str, pub url: &\'static str, pub url_raw: &\'static str, pub irealb: &\'static str, pub irealb_raw: &\'static str, pub scan_end: i32, pub rows: &\'static [RowFlat] }')
    L.append('')
    L.append('pub const ALL: &[ProgGolden] = &[')
    for name, cp, ops, snap, scan_end, rows in scenarios:
        L.append(f'  ProgGolden {{')
        L.append(f'    name: "{name}",')
        L.append(f'    title: "{cp.title}",')
        L.append('    ops: &[')
        for op in ops:
            L.append(f'      OpFlat {{ op: "{op[0]}", a: {op[1]}, b: {op[2]}, c: {op[3]}, s: "{op[4]}", t: "{op[5]}" }},')
        L.append('    ],')
        L.append('    brackets: &[')
        for rs, e1s, e1e, e2s, nr, ro in snap['brackets']:
            L.append(f'      BracketFlat {{ rs: {rs}, e1s: {e1s}, e1e: {e1e}, e2s: {e2s}, nr: {nr}, ro: {ro} }},')
        L.append('    ],')
        L.append('    items: &[')
        for chord, m, b, bass in snap['items']:
            L.append(f'      ItemFlat {{ chord: "{chord}", m: {m}, b: {b}, bass: "{bass}" }},')
        L.append('    ],')
        L.append('    sections: &[')
        for sm, mark in snap['sections']:
            L.append(f'      SecFlat {{ m: {sm}, mark: "{mark}" }},')
        L.append('    ],')
        L.append('    nochord: &[' + ', '.join(str(x) for x in snap['nochord']) + '],')
        L.append('    structural: &[' + ', '.join(str(x) for x in snap['structural']) + '],')
        L.append(f'    last_measure: {snap["last_measure"]},')
        L.append(f'    key: "{snap["key"]}",')
        L.append(f'    url: "{snap["url"]}",')
        L.append(f'    url_raw: "{snap["url_raw"]}",')
        L.append(f'    irealb: "{snap["irealb"]}",')
        L.append(f'    irealb_raw: "{snap["irealb_raw"]}",')
        L.append(f'    scan_end: {scan_end},')
        L.append('    rows: &[')
        for row in rows:
            flds = ('m: {0}, vc0: {1}, vc1: {2}, down: {3}, up: {4}, inv: {5}, hid: {6}, '
                    'pv: {7}, res: {8}, rep: {9}, vb: {10}, skip: {11}').format(*row)
            L.append(f'      RowFlat {{ {flds} }},')
        L.append('    ],')
        L.append('  },')
    L.append('];')
    path = '/home/superlisa/workspace/irealwx/core/tests/golden_progression.rs'
    with open(path, 'w') as f:
        f.write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
