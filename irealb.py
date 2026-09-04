"""irealb.py — iReal Pro "irealb" (new) format codec.

The modern iReal Pro sharing format looks like ``irealb://...`` and carries
rich metadata that the classic readable ``irealbook://`` format lacks: an
explicit BPM (``actual_tempo``), a playback style override (``actual_style``),
a repeat count and an optional transposition key (``actual_key``).

Only the chord data itself is hidden, and even that is not encryption: it is a
fixed, keyless obfuscation (a magic prefix, three token substitutions and a
self-inverse byte scramble).  The scheme was reverse engineered by the
open-source community; the reference implementation used here is
``Data::iRealPro`` (https://github.com/sciurius/perl-Data-iRealPro).  This
module is an independent, dependency-free Python port.

Layout of an ``irealb://`` payload (after percent-decoding)::

    irealb://<song>===<song>===...===<PlaylistName>     (playlist)

where a single song is one 10-field record::

    <Title>=<Composer>=<a2>=<Style>=<Key>=<ActualKey>=<chords>=<ActualStyle>=<Tempo>=<Repeats>

``<chords>`` starts with the magic string ``1r34LbKcu7`` followed by the
obfuscated chord data.  A payload with a single song and no trailing playlist
name opens directly in iReal Pro; a payload with several songs (or an explicit
name) is offered as a playlist.
"""

from __future__ import annotations

import re
from urllib.parse import quote, unquote

__all__ = [
    'MAGIC',
    'obfuscate',
    'deobfuscate',
    'hussle',
    'Song',
    'decode_payload',
    'encode_song',
    'build_url',
    'irealbook_to_irealb',
    'url_encode',
]

MAGIC = '1r34LbKcu7'

#: The obfuscation is a symmetric (self-inverse) scramble of 50-byte blocks.
_HUSSLE_BLOCK = 50

# Chord-data token substitutions used by the obfuscation.
_ENC_SUBS = (('   ', 'XyQ'),   # 3 spaces  -> XyQ
             (' |', 'LZ'),     # space+bar -> LZ
             ('| x', 'Kcl'))   # bar+x    -> Kcl


def hussle(text: str) -> str:
    """Apply the symmetric byte scramble (applied on encode AND decode).

    The string is processed in 50-character segments; each segment is re-issued
    as seven reordered (some reversed) chunks.  The permutation is its own
    inverse, which is why the same function is used in both directions.
    """
    out: list[str] = []
    while len(text) > _HUSSLE_BLOCK:
        seg, text = text[:_HUSSLE_BLOCK], text[_HUSSLE_BLOCK:]
        if len(text) < 2:
            # Perl reference keeps a trailing near-empty remainder intact.
            out.append(seg)
            continue
        out.append(seg[45:50][::-1])
        out.append(seg[5:10])
        out.append(seg[26:40][::-1])
        out.append(seg[24:26])
        out.append(seg[10:24][::-1])
        out.append(seg[40:45])
        out.append(seg[0:5][::-1])
    out.append(text)
    return ''.join(out)


def obfuscate(chord_data: str) -> str:
    """Encode readable chord data into the hidden form (with magic prefix)."""
    t = chord_data
    for plain, coded in _ENC_SUBS:
        t = t.replace(plain, coded)
    t = hussle(t)
    return MAGIC + t


def deobfuscate(text: str) -> str:
    """Recover readable chord data from an obfuscated (magic-prefixed) string."""
    if not text.startswith(MAGIC):
        raise ValueError('not an iRealPro obfuscated chord blob '
                         '(missing magic prefix)')
    t = text[len(MAGIC):]
    t = hussle(t)
    for plain, coded in _ENC_SUBS:
        t = t.replace(coded, plain)
    return t


def url_encode(text: str) -> str:
    """Percent-encode a payload for embedding in a URL, UTF-8 aware.

    Mirrors the escape set of the reference implementation (keeps
    ``A-Za-z0-9 - _ . * / '`` intact).
    """
    return quote(text.encode('utf-8'), safe="-_.A-Za-z*/'")


class Song:
    """One song in the new iRealPro format.

    ``chords`` holds the *readable* chord data string; the metadata fields map
    directly onto the ten ``=``-separated fields of the format.
    """

    __slots__ = ('title', 'composer', 'a2', 'style', 'key', 'actual_key',
                 'chords', 'actual_style', 'tempo', 'repeats')

    def __init__(self, *, title: str, composer: str = 'Unknown', style: str = 'Medium Swing',
                 key: str = 'C', chords: str = '', a2: str = '', actual_key: str = '',
                 actual_style: str = '', tempo: int = 0, repeats: int = 0) -> None:
        self.title = title
        self.composer = composer
        self.a2 = a2
        self.style = style
        self.key = key
        self.chords = chords
        self.actual_key = actual_key
        self.actual_style = actual_style
        self.tempo = tempo
        self.repeats = repeats

    def to_field_record(self) -> str:
        """Return the 10-field ``=`` record (chord data obfuscated)."""
        return '='.join([
            self.title,
            self.composer,
            self.a2,
            self.style,
            self.key,
            self.actual_key,
            obfuscate(self.chords),
            self.actual_style,
            str(self.tempo or 0),
            str(self.repeats or 0),
        ])


def encode_song(song: Song) -> str:
    """Return the single-song ``irealb://`` payload (no playlist name)."""
    return song.to_field_record()


def build_url(songs: list[Song], playlist_name: str | None = None) -> str:
    """Build a full ``irealb://`` URL from one or more songs.

    A single song with no *playlist_name* yields a payload that opens that song
    directly in iReal Pro; anything else is offered as a playlist.
    """
    payload = '==='.join(s.to_field_record() for s in songs)
    if playlist_name:
        payload += '===' + playlist_name
    return 'irealb://' + url_encode(payload)


def _song_from_irealpro_fields(fields: list[str], *, transpose: int = 0) -> Song:
    if len(fields) != 10:
        raise ValueError(f'bad iRealPro song record: expected 10 fields, '
                         f'got {len(fields)}')
    (title, composer, a2, style, key, actual_key,
     raw, actual_style, tempo, repeats) = fields
    song = Song(title=title, composer=composer, style=style, key=key, a2=a2,
                actual_key=actual_key, actual_style=actual_style,
                tempo=int(tempo or 0), repeats=int(repeats or 0))
    song.chords = deobfuscate(raw)
    return song


def _song_from_irealbook_fields(fields: list[str], *, transpose: int = 0) -> Song:
    # Classic readable record: Title=Composer=Style=<a3>=Key=<chord data>.
    if len(fields) != 6:
        raise ValueError(f'bad irealbook record: expected 6 fields, '
                         f'got {len(fields)}')
    title, composer, style, a3, key, raw = fields
    # iRealPro writes the record as ...=Style=Key=n=<data>; the sentinel 'n'
    # lands in the *key* slot, so swap it back.
    if key == 'n':
        key, a3 = a3, 'n'
    return Song(title=title, composer=composer, style=style, key=key,
                chords=raw, tempo=0)


def decode_payload(data: str) -> list[Song]:
    """Parse a raw (percent-decoded, ``irealb://``-less) payload into songs.

    Accepts both the modern ``irealpro`` records and classic readable
    ``irealbook`` records (a payload of only one readable song is fine).
    """
    # A playlist payload is song===song===...===Name ; a bare single song has no
    # '===' at all.
    parts = data.split('===')
    if len(parts) > 1:
        parts = parts[:-1]  # drop the trailing playlist name
    songs: list[Song] = []
    for part in parts:
        fields = part.split('=')
        if len(fields) == 10:
            songs.append(_song_from_irealpro_fields(fields))
        elif len(fields) == 6:
            songs.append(_song_from_irealbook_fields(fields))
        else:
            raise ValueError(f'unsupported iRealPro record with '
                             f'{len(fields)} fields')
    return songs


def decode_url(text: str) -> list[Song]:
    """Extract and parse songs from an ``irealb://`` / ``irealbook://`` URL.

    Tolerates surrounding HTML/text and newlines, mirrors the reference parser.
    """
    cleaned = re.sub(r'[\r\n]*', '', text)
    m = re.search(r'irealb(?:ook)?://(.*)', cleaned)
    if not m:
        raise ValueError('no irealb:// or irealbook:// URL found')
    payload = unquote(m.group(1))
    return decode_payload(payload)


# ---------------------------------------------------------------------------
# irealstudio integration helpers
# ---------------------------------------------------------------------------

def irealbook_to_irealb(readable_irealbook_url: str, *, tempo: int = 120,
                        actual_style: str = '', actual_key: str = '',
                        repeats: int = 0, urlencode: bool = True) -> str:
    """Convert the classic readable ``irealbook://`` URL to the new format.

    Used by irealstudio to emit the modern format while keeping its existing,
    well-tested chord-data builder: the readable URL already carries
    title/composer/style/key/chords, and the extra metadata (notably BPM) is
    supplied from the caller.
    """
    songs = decode_url(readable_irealbook_url)
    if len(songs) != 1:
        raise ValueError('irealbook_to_irealb expects a single-song URL')
    song = songs[0]
    song.tempo = tempo or 0
    song.actual_style = actual_style
    song.actual_key = actual_key
    song.repeats = repeats or 0
    payload = song.to_field_record()
    if urlencode:
        return 'irealb://' + url_encode(payload)
    return 'irealb://' + payload


if __name__ == '__main__':  # pragma: no cover - quick self test
    import sys

    # Two real songs shared from iReal Pro, taken from the Data::iRealPro test
    # suite.  These are the ground truth the codec must decode.
    REAL = [
        # (title, expected tempo, url)
        ("You're Still The One", 155,
         'irealb://You\'re%20Still%20The%20One%3DTwain%20Shania%3D%3DRock%20'
         'Ballad%3DC%3D%3D1r34LbKcu7L%23F/D4DLZD%7D%20AZLGZL%23F/DZLAD*%7B%0A'
         '%7D%20AZLGZL%23F/%0A%7CDLZ4Ti*%7BDZLAZLZSDLGZLDB*%7B%0A%5D%20AZLALZG'
         'ZLDZLAZLAZLGZLZE-LAZLGZ%23F/DZALZN1%5D%20%3EadoC%20la%20.S.%3CD%20A2N'
         '%7CQyXQyX%7D%20G%0A%5BQDLZLGZLLZGLZfA%20Z%20%3D%3D155%3D0'),
        ('Ik Zie Jou', 180,
         'irealb://Ik%20Zie%20Jou%3DTrudie%20van%20den%20Bos%3D%3DMedium%20'
         'Swing%3DC%3D%3D1r34LbKcu7KQyXG-XyQK3%3Cx%7CF%7Cx%7C-A%7B%7D%3Ex%3C4%20'
         'lcKQyX-BZL%20lcx%3E%20%7D%7CA43T%7Bcl%20LZ%20x%20LZ%20x%20%20%5D%20%3D'
         'Pop-Slow%20Rock%3D180%3D3'),
    ]

    failures = 0
    for title, tempo, url in REAL:
        songs = decode_url(url)
        ok = len(songs) == 1 and songs[0].title == title and songs[0].tempo == tempo
        print(f'[{"ok" if ok else "FAIL"}] {title}  tempo={songs[0].tempo}')
        print('   chords>>>')
        for line in songs[0].chords.splitlines():
            print('   |', line)
        failures += 0 if ok else 1
        # Round trip: re-encode (no BPM preservation required on decode object)
        reencoded = build_url([songs[0]])
        again = decode_url(reencoded)[0]
        if again.chords != songs[0].chords:
            print('   round-trip chord mismatch!')
            failures += 1

    sys.exit(1 if failures else 0)
