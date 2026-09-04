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
        fn GetLastError() -> u32;
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

    static DLL: OnceLock<Result<DllHandle, String>> = OnceLock::new();

    /// Загрузить DLL, кешируя результат вместе с причиной отказа (для дебага).
    fn load() -> &'static Result<DllHandle, String> {
        DLL.get_or_init(try_load)
    }

    fn try_load() -> Result<DllHandle, String> {
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
        let mut present_failed: Option<(String, u32)> = None;
        let mut absent: Vec<String> = Vec::new();
        for c in &candidates {
            let on_disk = std::fs::metadata(c.as_str()).is_ok();
            let w = wide(c);
            let m = unsafe { LoadLibraryW(w.as_ptr()) };
            if !m.is_null() {
                return Ok(DllHandle(m));
            }
            let code = unsafe { GetLastError() };
            if on_disk {
                present_failed = Some((c.clone(), code));
            } else {
                absent.push(c.clone());
            }
        }
        if let Some((path, code)) = present_failed {
            Err(format!(
                "DLL есть на диске, но не загрузилась: {path}, код ошибки {code}. \
                 Частая причина — разрядность DLL (32/64) не совпадает с разрядностью exe."
            ))
        } else {
            Err(format!(
                "NVDA ControllerClient DLL не найдена. Искал: {}",
                absent.join("; ")
            ))
        }
    }

    /// Вызвать `nvdaController_speakText`; Ok(код возврата) — вызов передан в DLL.
    fn call(module: DllHandle, text: &str) -> Result<i32, String> {
        let name = b"nvdaController_speakText\0";
        let proc = unsafe { GetProcAddress(module.0, name.as_ptr()) };
        if proc.is_null() {
            return Err(
                "DLL загружена, но в ней нет экспорта nvdaController_speakText".to_string(),
            );
        }
        let f: SpeakTextFn = unsafe { std::mem::transmute(proc) };
        let w = wide(text);
        Ok(unsafe { f(w.as_ptr()) })
    }

    /// Fire-and-forget для трейта `Speak`: молчит при любой ошибке (как раньше).
    pub fn speak(text: &str) {
        if let Ok(module) = load() {
            let _ = call(*module, text);
        }
    }

    /// Проговорить с диагностикой: Err(причина) — если озвучить не удалось.
    pub fn speak_diag(text: &str) -> Result<(), String> {
        match load() {
            Err(reason) => Err(reason.clone()),
            Ok(module) => {
                let code = call(*module, text)?;
                if code != 0 {
                    Err(format!(
                        "nvdaController_speakText вернул код {code} — обычно NVDA не запущен"
                    ))
                } else {
                    Ok(())
                }
            }
        }
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

/// Проговорить *text* и вернуть диагноз: Ok — текст передан в работающий вывод;
/// Err(причина) — почему озвучить не вышло (используется дебаг-клавишей D в UI).
/// На Windows проходит через NVDA ControllerClient и сообщает, если DLL не
/// найдена/не загрузилась или NVDA не запущен.
pub fn speak_diagnose(text: &str) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        nvda::speak_diag(text)
    }
    #[cfg(target_os = "linux")]
    {
        cli_diag("spd-say", text)
    }
    #[cfg(target_os = "macos")]
    {
        cli_diag("say", text)
    }
    #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
    {
        Err("речевой вывод на этой ОС не реализован".to_string())
    }
}

/// Запустить системный речевой CLI и сообщить, если его нет в системе.
fn cli_diag(bin: &str, text: &str) -> Result<(), String> {
    use std::process::Command;
    match Command::new(bin).arg(text).spawn() {
        Ok(_) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            Err(format!("не найден {bin} (системный речевой диспетчер недоступен)"))
        }
        Err(e) => Err(format!("не удалось запустить {bin}: {e}")),
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
