//! irealwx_speech — вывод речи в скринридер, «аутпут через prism».
//!
//! В irealstudio это `accessible_output3.Auto()` (main.py) — кроссплатформенный
//! автодиспетчер: на Windows говорит через активный скринридер (у Дениза NVDA →
//! nvdaControllerClient.dll), на Linux — Speech Dispatcher, на macOS — VoiceOver.
//! Здесь тот же узор: тонкий трейт `Speak` + `default_speak()`, который по ОС
//! возвращает живой бэкенд, а если его нет/не запущен — молчание (`SilentSpeak`).
//! Реализованы: Windows — NVDA ControllerClient (FFI, динамическая загрузка DLL,
//! как у accessible_output3); Linux/macOS — системный CLI (`spd-say` из
//! speech-dispatcher / `say`) без C-линковки. Ни один вызов не паникует.
//!
//! Границы крейта:
//! - Принимает строки «для озвучки» (уже готовый текст, числа прописью).
//! - Ничего не знает о GUI: панель тактов и меню зовут его снаружи.

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

/// Бэкенд через системный CLI — путь без C-линковки для Linux/macOS:
/// Linux — `spd-say` из speech-dispatcher (речь в Orca/др. идёт как раз через
/// speech-dispatcher), macOS — `say`. Если команды нет или она не запустилась —
/// молчание (вызов никогда не падает и не блокирует: процесс не ждём).
pub struct CliSpeak {
    bin: &'static str,
}

impl CliSpeak {
    pub fn new(bin: &'static str) -> Self {
        CliSpeak { bin }
    }
}

impl Speak for CliSpeak {
    fn speak(&self, text: &str) {
        use std::process::{Command, Stdio};
        let Ok(_child) = Command::new(self.bin)
            .arg(text)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
        else {
            return;
        };
        // Child дропается: процесс продолжает говорить сам, мы ничего не ждём.
    }
}

/// Активный вывод. Под Windows реальная реализация идёт через
/// NVDA ControllerClient (`nvdaControllerClient.dll`): `nvdaController_speakText`.
#[cfg(target_os = "windows")]
pub struct NvdaSpeak;

#[cfg(target_os = "windows")]
mod nvda {
    //! Динамическая загрузка `nvdaControllerClient.dll` — без внешних крейтов.
    //! Функции те же, что зовёт accessible_output3 в irealstudio (python).
    //! DLL ищется рядом с exe, в каталогах NVDA, затем голым именем (путь
    //! приложения/PATH). Если не найдена или NVDA не запущена — молчаливый no-op.

    use std::ffi::c_void;
    use std::sync::OnceLock;

    #[link(name = "Kernel32")]
    extern "system" {
        fn LoadLibraryW(lp_file_name: *const u16) -> *mut c_void;
        fn GetProcAddress(h_module: *mut c_void, lp_proc_name: *const u8) -> *mut c_void;
    }

    type SpeakTextFn = unsafe extern "system" fn(*const u16) -> i32;

    /// Opaque-хендл загруженной DLL (HMODULE). Никогда не разыменовывается —
    /// только хранится и отдаётся обратно в WinAPI, поэтому Send+Sync обёртка
    /// звукобезопасна (общий контракт Windows-хендлов). Сырой `*mut c_void` в
    /// `static` легально не положить: он !Send/!Sync, а static требует Sync.
    #[derive(Copy, Clone)]
    struct DllHandle(*mut c_void);
    // SAFETY: DllHandle — opaque-хендл; единственное использование — аргумент
    // GetProcAddress/LoadLibraryW. Дереференса нет, передача между потоками
    // безопасна, как и для любого Windows HANDLE.
    unsafe impl Send for DllHandle {}
    unsafe impl Sync for DllHandle {}

    fn wide(s: &str) -> Vec<u16> {
        s.encode_utf16().chain(std::iter::once(0)).collect()
    }

    fn load() -> Option<DllHandle> {
        let mut candidates: Vec<String> = Vec::new();
        if let Ok(exe) = std::env::current_exe() {
            if let Some(dir) = exe.parent() {
                candidates.push(
                    dir.join("nvdaControllerClient.dll").to_string_lossy().to_string(),
                );
            }
        }
        candidates.push("C:\\Program Files (x86)\\NVDA\\nvdaControllerClient.dll".to_string());
        candidates.push("C:\\Program Files\\NVDA\\nvdaControllerClient.dll".to_string());
        // Голое имя: Windows ищет в каталоге приложения и в PATH.
        candidates.push("nvdaControllerClient.dll".to_string());
        for c in &candidates {
            let w = wide(c);
            let m = unsafe { LoadLibraryW(w.as_ptr()) };
            if !m.is_null() {
                return Some(DllHandle(m));
            }
        }
        None
    }

    static DLL: OnceLock<Option<DllHandle>> = OnceLock::new();

    fn dll() -> Option<DllHandle> {
        *DLL.get_or_init(load)
    }

    pub fn speak(text: &str) {
        let Some(module) = dll() else { return };
        let name = b"nvdaController_speakText\0";
        let proc = unsafe { GetProcAddress(module.0, name.as_ptr()) };
        if proc.is_null() {
            return;
        }
        let f: SpeakTextFn = unsafe { std::mem::transmute(proc) };
        let w = wide(text);
        unsafe { f(w.as_ptr()) };
    }
}

#[cfg(target_os = "windows")]
impl Speak for NvdaSpeak {
    fn speak(&self, text: &str) {
        nvda::speak(text);
    }
}

/// Выбрать активный вывод по ОС — как `accessible_output3.Auto()` в python:
/// Windows → NVDA ControllerClient, Linux → Speech Dispatcher (`spd-say`),
/// macOS → `say`. На хостах, где инструмента нет, бэкенд молчит.
pub fn default_speak() -> Box<dyn Speak> {
    #[cfg(target_os = "windows")]
    {
        Box::new(NvdaSpeak)
    }
    #[cfg(target_os = "linux")]
    {
        Box::new(CliSpeak::new("spd-say"))
    }
    #[cfg(target_os = "macos")]
    {
        Box::new(CliSpeak::new("say"))
    }
    #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
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

    #[test]
    fn cli_missing_bin_is_silent() {
        // Бинарника нет ни на одной ОС — вызов обязан просто ничего не сделать.
        let s = CliSpeak::new("irealwx-no-such-speech-binary-xyz");
        s.speak("тест озвучки");
    }

    #[test]
    fn cli_never_panics_on_empty_text() {
        let s = CliSpeak::new("irealwx-no-such-speech-binary-xyz");
        s.speak("");
    }
}
