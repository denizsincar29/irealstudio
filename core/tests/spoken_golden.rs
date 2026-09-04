//! Сверка порта озвучки аккордов (spoken.rs) с python-эталоном, работающим
//! под ru-каталогом irealstudio (что и слышит пользователь). Данные в
//! golden_spoken.rs: 485 кейсов (имя, бас, ожидаемая русская строка),
//! сгенерированы chords.py::chord_name_to_spoken + locales/ru.

use irealwx_core::chords::chord_name_to_spoken;

mod data {
    include!("golden_spoken.rs");
}

use data::*;

#[test]
fn spoken_cases_match_python_reference() {
    for c in ALL {
        let got = chord_name_to_spoken(c.name, c.bass);
        assert_eq!(got, c.out, "{:?} (bass {:?})", c.name, c.bass);
    }
}
