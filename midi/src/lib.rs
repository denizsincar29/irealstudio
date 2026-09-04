//! irealwx_midi — MIDI-выход, аналог `midi_handler.py` в irealstudio.
//!
//! Границы крейта:
//! - Шлёт MIDI-события (note on/off, program) на выбранный порт.
//! - Тайминг тактов приходит снаружи (драйвер проигрывания); тут только
//!   транспортировка и выбор порта.
//! - Не зависит от GUI, речи и аудио — чинится отдельно.
//!
//! Платформа: midir под Windows (Windows Multimedia — midir его поддерживает).

/// Один MIDI-канал вывода. Создаётся из имени порта; `None` = заглушка.
pub struct MidiOut;

impl MidiOut {
    /// Список доступных выходных портов (имена).
    pub fn port_names() -> Vec<String> {
        // TODO: midir::MidiOutput::new + ports() при подключении зависимости.
        Vec::new()
    }

    /// Открыть порт по имени (или системный по умолчанию).
    pub fn open(_name: Option<&str>) -> Option<Self> {
        None
    }

    /// Отправить событие note on/off: канал 0-15, нота 0-127, velocity 0-127.
    pub fn note(&self, _on: bool, _channel: u8, _note: u8, _velocity: u8) {}
}
