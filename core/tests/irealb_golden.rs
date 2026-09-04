//! Сверка Rust-кодека с python-эталоном irealstudio на реальных песнях
//! из iReal Pro. Данные (tests/golden_songs.rs) автогенерированы модулем
//! `irealb.py`: URL -> ожидаемые поля + каноническая `=`-запись. Rust обязан
//! выдать ровно то же самое — иначе порт разошёлся с эталоном.

use irealwx_core::irealb::{build_url, decode_url, Song};

mod data {
    include!("golden_songs.rs");
}

use data::{ALL, GoldenSong};

fn assert_song_matches(s: &Song, want: &GoldenSong, label: &str) {
    assert_eq!(s.title, want.title, "title {label}");
    assert_eq!(s.composer, want.composer, "composer {label}");
    assert_eq!(s.a2, want.a2, "a2 {label}");
    assert_eq!(s.style, want.style, "style {label}");
    assert_eq!(s.key, want.key, "key {label}");
    assert_eq!(s.actual_key, want.actual_key, "actual_key {label}");
    assert_eq!(s.actual_style, want.actual_style, "actual_style {label}");
    assert_eq!(s.tempo, want.tempo, "tempo {label}");
    assert_eq!(s.repeats, want.repeats, "repeats {label}");
    assert_eq!(s.chords, want.chords, "chords {label}");
    assert_eq!(s.to_field_record(), want.record, "record {label}");
}

#[test]
fn golden_decode_matches_python_reference() {
    assert!(!ALL.is_empty(), "golden vectors must not be empty");
    for want in ALL {
        let songs = decode_url(want.url)
            .unwrap_or_else(|e| panic!("decode {}: {e}", want.title));
        assert_eq!(songs.len(), 1, "one song per URL ({})", want.title);
        assert_song_matches(&songs[0], want, want.title);
    }
}

#[test]
fn golden_reencode_round_trip_preserves_chords() {
    for want in ALL {
        let s = decode_url(want.url)
            .unwrap_or_else(|e| panic!("decode {}: {e}", want.title))
            .into_iter()
            .next()
            .unwrap();
        let again = decode_url(&build_url(&[s.clone()], None))
            .unwrap_or_else(|e| panic!("re-decode {}: {e}", want.title))
            .into_iter()
            .next()
            .unwrap();
        assert_eq!(again.chords, s.chords, "chords round trip {}", want.title);
        assert_eq!(again.title, s.title, "title round trip {}", want.title);
        assert_eq!(again.to_field_record(), want.record, "record round trip {}", want.title);
    }
}
