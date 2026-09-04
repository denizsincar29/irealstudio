//! irealwx_speech — вывод речи в скринридер, «аутпут через prism».
//!
//! Сегодня в irealstudio это `accessible_output3.Auto()` (NVDA ControllerClient)
//! за хелпером `self.speak()` в main.py. Сюда переносим ровно этот механизм:
//! тонкий трейт `Speak` + реализация через NVDA ControllerClient (FFI/с-крейт).
//!
//! Границы крейта:
//! - Принимает строки «для озвучки» (уже готовый текст, числа прописью).
//! - Ничего не знает о GUI: панель тактов и меню зовут его снаружи.
//! - На не-Windows хостах — no-op реализация, чтобы всё собиралось.

/// Контракт речевого вывода.
pub trait Speak {
    /// Немедленно озвучить строку (прерывая текущую речь, как NVDA).
    fn speak(&self, text: &str);
}

/// No-op заглушка для не-Windows сборки/тестов.
#[derive(Default)]
pub struct SilentSpeak;

impl Speak for SilentSpeak {
    fn speak(&self, _text: &str) {}
}

/// Активный вывод. Под Windows реальная реализация идёт через
/// NVDA ControllerClient (`nvdaControllerClient.dll`): `nvdaController_speakText`.
#[cfg(target_os = "windows")]
pub struct NvdaSpeak;

#[cfg(target_os = "windows")]
impl Speak for NvdaSpeak {
    fn speak(&self, text: &str) {
        // TODO: FFI к nvdaControllerClient.dll (nvdaController_speakText,
        // nvdaController_testIfRunning). Данные юникод-строки — wide (UTF-16).
        let _ = text;
    }
}

/// Выбрать активный вывод: NVDA под Windows, тишина на остальных.
pub fn default_speak() -> Box<dyn Speak> {
    #[cfg(target_os = "windows")]
    {
        Box::new(NvdaSpeak)
    }
    #[cfg(not(target_os = "windows"))]
    {
        Box::new(SilentSpeak)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn silent_never_panics() {
        let s = default_speak();
        s.speak("тест озвучки");
    }
}
