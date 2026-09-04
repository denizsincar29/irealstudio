//! Сверка порта гармонии с python-эталоном irealstudio (chords.py).
//! Данные в golden_chords.rs автогенерированы из python-функций чистого ядра:
//! распознавание, ireal-перевод, транспонирование, вокализация, ноты тональностей.

use irealwx_core::chords::{
    chord_name_to_ireal, identify_chord_name, note_names_for_key, transpose_chord_name,
    voice_chord_midi, NOTE_NAMES, NOTE_NAMES_SHARP,
};

mod data {
    include!("golden_chords.rs");
}

use data::*;

#[test]
fn identify_matches_python_reference() {
    for case in IDENT {
        let notes: Vec<&str> = case.notes.to_vec();
        let got = match identify_chord_name(&notes) {
            Some(n) => n,
            None => "None".to_string(),
        };
        assert_eq!(got, case.want, "identify {:?}", case.notes);
    }
}

#[test]
fn ireal_translation_matches_python_reference() {
    for &(name, want) in IREAL_Q {
        assert_eq!(chord_name_to_ireal(name), want, "to_ireal {name}");
    }
}

#[test]
fn transpose_matches_python_reference() {
    for &(name, semitones, scheme, want) in TRANSPOSE {
        let names = if scheme == "sharp" {
            &NOTE_NAMES_SHARP[..]
        } else {
            &NOTE_NAMES[..]
        };
        assert_eq!(
            transpose_chord_name(name, semitones, names),
            want,
            "transpose {name} {semitones} ({scheme})"
        );
    }
}

#[test]
fn voicing_matches_python_reference() {
    for &(name, prev, notes, root) in VOICE {
        let prev_opt = if prev == 0 { None } else { Some(prev) };
        let (got_notes, got_root) = voice_chord_midi(name, prev_opt);
        assert_eq!(got_notes, notes.to_vec(), "voice {name} prev={prev}");
        assert_eq!(got_root, root, "voice root {name} prev={prev}");
    }
}

#[test]
fn key_note_names_match_python_reference() {
    for &(key, second) in KEY_NAMES {
        let names = note_names_for_key(key);
        assert_eq!(names[1], second, "note names for key {key}");
    }
}
