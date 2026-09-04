//! irealwx_core — портируемое ядро irealstudio.
//!
//! Без GUI и без платформенных зависимостей: собирается и тестируется где
//! угодно. Слой wx (Windows) и аудио/MIDI/речь — отдельные крейты/модули.

pub mod irealb;

pub use irealb::*;
