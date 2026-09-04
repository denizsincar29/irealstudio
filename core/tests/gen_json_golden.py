#!/usr/bin/env python3
"""Generate golden_json.rs: ChordProgression.to_json byte-verified against
irealstudio/chords.py (json.dumps indent=2, ensure_ascii). Each case = constructor
params (title/key/style/bpm/composer/time_signature — captured BEFORE ops run) +
ops; python to_json of the resulting progression is the golden. The Rust test
replays the same ops from the same constructor and compares to_json byte-for-byte,
then round-trips through from_json.

Also covers non-ASCII: Cyrillic, quotes, newlines, emoji (astral → surrogate
pair 😀), so the ensure_ascii encoder is locked to python.
"""
import sys

sys.path.insert(0, '/home/superlisa/workspace/irealstudio')
sys.path.insert(0, '/home/superlisa/workspace/irealwx/core/tests')
from chords import ChordProgression, TimeSignature  # noqa: E402

from gen_progression_golden import OP, OPchord, OPrepeat, OPvolta, OPvstart, \
    OPnochord, OPtwhole, OPtpos, run_ops  # noqa: E402


def TS(n=4, d=4):
    return TimeSignature(n, d)


def rust_escape(s: str) -> str:
    """Escape a python string into a Rust double-quoted string literal."""
    out = []
    for ch in s:
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        else:
            out.append(ch)
    return ''.join(out)


# Сценарий = (ctor, ops): ctor — dict с параметрами конструктора и bpm/composer,
# ops — плоский список операций (как в gen_progression_golden).

def case_plain_cyrillic():
    ctor = dict(title='«Песня» — тест', key='Db', style='Latin', bpm=96,
                composer='Дениз Алиев ✓', ts=TS())
    ops = [
        OP('section', 1, '*A'),
        OPchord('C7', 1, 1, ''), OPchord('F', 2, 1, ''),
        OPchord('C', 3, 3, 'E'), OPchord('G7b5', 4, 1, ''),
        OPnochord(5),
        OPrepeat(1, 4),
    ]
    return ctor, ops


def case_emoji_newlines():
    ctor = dict(title='Night "in" \\ 東京\t\nполёт 😀 дальше', key='Bb',
                style='Swing', bpm=144, composer='Mozart, W.A. / Амадей', ts=TS(12, 8))
    ops = [
        OPchord('Cmaj7', 1, 1, ''), OPchord('Bbm7', 2, 1, ''),
        OPchord('Am7(b5)', 3, 1, ''), OPchord('G7(b9)', 4, 1, ''),
        OPchord('F#', 6, 1, ''), OPnochord(8),
    ]
    return ctor, ops


def case_empty():
    ctor = dict(title='Empty', key='C', style='Rock', bpm=120,
                composer='Unknown', ts=TS())
    ops = []
    return ctor, ops


def case_volta_plain_repeat():
    ctor = dict(title='VoltaPlain', key='G', style='Bossa Nova', bpm=88,
                composer='João', ts=TS(6, 8))
    ops = [
        OPchord('C', 1, 1, ''), OPchord('F', 2, 1, ''),
        OPvstart(1),
        OPrepeat(1, 2),
        OPchord('G', 4, 1, ''),
    ]
    return ctor, ops


def case_transpose():
    # Транспонирование меняет key и имена аккордов — проверяем, что to_json
    # фиксирует именно конечное состояние (как python после тех же ops).
    ctor = dict(title='TransposeJson', key='C', style='Rock', bpm=120,
                composer='Unknown', ts=TS())
    ops = [
        OPchord('C7', 1, 1, ''), OPchord('F', 3, 1, ''), OPchord('G', 4, 3, 'B'),
        OPtwhole(6),
        OPtpos(5, 3, 1),
        OP('section', 2, '*B'),
        OPnochord(2),
    ]
    return ctor, ops


def case_many_measures():
    ctor = dict(title='Many', key='F', style='Rock', bpm=120,
                composer='Unknown', ts=TS())
    ops = []
    # 8 тактов по 4 аккорда, потом 4 такта по одному аккорду.
    m = 1
    for name in ['C', 'Dm7', 'G7', 'Cmaj7', 'F', 'Bdim', 'E7', 'Am']:
        for b in (1, 2, 3, 4):
            ops.append(OPchord(name, m, b, ''))
        m += 1
    for name in ['C', 'F', 'G7', 'C']:
        ops.append(OPchord(name, m, 1, ''))
        m += 1
    ops.append(OPnochord(20))
    ops.append(OPnochord(12))
    ops.append(OPnochord(20))  # дубль в set не должен продублироваться в выводе
    return ctor, ops


def main():
    cases = [
        ('cyrillic', case_plain_cyrillic),
        ('emoji_newlines', case_emoji_newlines),
        ('empty', case_empty),
        ('volta_plain', case_volta_plain_repeat),
        ('transpose', case_transpose),
        ('many', case_many_measures),
    ]
    rows = []
    for name, builder in cases:
        ctor, ops = builder()
        cp = ChordProgression(ctor['title'], ctor['ts'], ctor['key'], ctor['style'])
        cp.bpm = ctor['bpm']
        cp.composer = ctor['composer']
        run_ops(cp, ops)
        ts = ctor['ts']
        rows.append({
            'name': name,
            'title': ctor['title'],
            'key': ctor['key'],
            'style': ctor['style'],
            'bpm': ctor['bpm'],
            'composer': ctor['composer'],
            'ts_num': ts.numerator,
            'ts_den': ts.denominator,
            'ops': ops,
            'json': cp.to_json(),
        })
    emit(rows)
    print('json cases generated:', [r['name'] for r in rows])


def emit(rows):
    L = []
    L.append('// AUTO-GENERATED by gen_json_golden.py — do not edit.')
    L.append('// ChordProgression.to_json byte-verified against chords.py')
    L.append('// (порт persist.rs). JSON как python json.dumps(indent=2, ensure_ascii).')
    L.append('')
    L.append('pub struct JOp { pub op: &\'static str, pub a: i32, pub b: i32, pub c: i32, pub s: &\'static str, pub t: &\'static str }')
    L.append('pub struct JsonGolden { pub name: &\'static str, pub title: &\'static str, pub key: &\'static str, pub style: &\'static str, pub bpm: i32, pub composer: &\'static str, pub ts_num: i32, pub ts_den: i32, pub ops: &\'static [JOp], pub json: &\'static str }')
    L.append('')
    L.append('pub const ALL: &[JsonGolden] = &[')
    for r in rows:
        L.append(f'  JsonGolden {{')
        L.append(f'    name: "{r["name"]}",')
        L.append(f'    title: "{rust_escape(r["title"])}",')
        L.append(f'    key: "{rust_escape(r["key"])}",')
        L.append(f'    style: "{rust_escape(r["style"])}",')
        L.append(f'    bpm: {r["bpm"]},')
        L.append(f'    composer: "{rust_escape(r["composer"])}",')
        L.append(f'    ts_num: {r["ts_num"]}, ts_den: {r["ts_den"]},')
        L.append('    ops: &[')
        for op in r['ops']:
            L.append(f'      JOp {{ op: "{op[0]}", a: {op[1]}, b: {op[2]}, c: {op[3]}, s: "{rust_escape(op[4])}", t: "{rust_escape(op[5])}" }},')
        L.append('    ],')
        L.append(f'    json: "{rust_escape(r["json"])}",')
        L.append('  },')
    L.append('];')
    path = '/home/superlisa/workspace/irealwx/core/tests/golden_json.rs'
    with open(path, 'w') as f:
        f.write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
