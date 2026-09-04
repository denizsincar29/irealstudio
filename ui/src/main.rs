// irealwx — этап 2: живое ядро в окне wxDragon (Windows).
//
// А11y-модель (решение Дениза): главное окно БЕЗ a11y-контролов. Весь ввод —
// через альт-меню (нативный HMENU) и хоткеи; панель тактов рисуется в on_paint
// (только видна, в дерево доступности не попадает); навигация озвучивается
// через irealwx_speech (NVDA ControllerClient) и дублируется в статус-строку.
// Обычные wx-контролы — только в диалогах: «Новая цифровка» (Ctrl+N), файловые
// диалоги открыть/сохранить .ips (Ctrl+O / Ctrl+S), экспорт в iReal Pro
// (Ctrl+E — HTML/текст с irealb-ссылкой) и правка (slice 5): аккорд/правка/
// бас (Ctrl+Enter / F2 / поле), N.C. (N), метки частей (Ctrl+Shift+буква),
// удаление (Del/Ctrl+Del), буфер обмена (Ctrl+X/C/V), отмена/повтор (Ctrl+Z/Y),
// транспонирование (Ctrl+T), переход к такту (Ctrl+F), настройки цифровки
// (Ctrl+P — название/композитор/темп/тональность/размер/стиль), Выход (Ctrl+Q).
//
// Сборка на любом хосте с тулчейном wxDragon (см. README): cargo build -p irealwx_ui.
// Целевая платформа проекта — Windows (NVDA); сам wx-код кроссплатформенный.
// Данные — Doc из lib.rs (демо-цифровка поверх ChordProgression core).

use std::cell::{Cell, RefCell};
use std::fs;
use std::path::{Path, PathBuf};
use std::rc::Rc;

use wxdragon::dc::{AutoBufferedPaintDC, BrushStyle, PenStyle};
use wxdragon::event::WindowEventData;
use wxdragon::keycode::{WXK_BACK, WXK_DELETE, WXK_END, WXK_HOME, WXK_LEFT, WXK_RIGHT};
use wxdragon::menus::ItemKind;
use wxdragon::prelude::*;

use irealwx_speech::{default_speak, speak_diagnose, Speak};
use irealwx_ui::{
    export_ireal_html, key_from_root_mode, key_to_root_mode, safe_file_base,
    BPM_MAX, BPM_MIN, Doc, NewChart, ProjectSettings, KEY_ROOTS,
};

// --- ID пунктов меню (кроме ID_EXIT/ID_ABOUT из прелюда) ---
const ID_NEW: i32 = 1001;
const ID_OPEN: i32 = 1002;
const ID_SAVE: i32 = 1003;
const ID_SAVE_AS: i32 = 1004;
const ID_EXPORT: i32 = 1005;
const ID_SPEAK: i32 = 2001;
const ID_SPEAK_ALL: i32 = 2002;
const ID_GOTO_START: i32 = 2003;
const ID_GOTO_END: i32 = 2004;
// Навигация (slice 11, MuseScore): ←/→ по аккордам и пустым тактам,
// Ctrl+←/→ по тактам. Акселераторы — как у Home/End: клавиши стрелок доходят
// до окна только через пункты меню (msg 1589: голые стрелки молчали).
const ID_NAV_CHORD_LEFT: i32 = 2005;
const ID_NAV_CHORD_RIGHT: i32 = 2006;
const ID_NAV_MEASURE_LEFT: i32 = 2007;
const ID_NAV_MEASURE_RIGHT: i32 = 2008;
// «Закрыть окно» (Ctrl+W) — то же закрытие, что X / Alt+F4 / Ctrl+Q.
const ID_CLOSE_WINDOW: i32 = 2009;
// Меню «Правка» (Edit): undo/redo/буфер обмена/транспонирование.
const ID_UNDO: i32 = 3001;
const ID_REDO: i32 = 3002;
const ID_CUT: i32 = 3003;
const ID_COPY: i32 = 3004;
const ID_PASTE: i32 = 3005;
const ID_TRANSPOSE: i32 = 3006;
// Меню «Вставка» (Insert): аккорд, правка, N.C., бас, метки частей, вольта.
const ID_INS_CHORD: i32 = 3007;
const ID_EDIT_CHORD: i32 = 3008;
const ID_INS_NC: i32 = 3009;
const ID_INS_BASS: i32 = 3010;
const ID_INS_VOLTA: i32 = 3020;
// Подменю «Метка части» — Ctrl+Shift+буква (как python, без Fine: его
// iReal-смысл python оставил «на уточнение», пункт в меню скрыт).
const ID_SM_A: i32 = 3011;
const ID_SM_B: i32 = 3012;
const ID_SM_C: i32 = 3013;
const ID_SM_D: i32 = 3014;
const ID_SM_V: i32 = 3015;
const ID_SM_I: i32 = 3016;
const ID_SM_S: i32 = 3017;
const ID_SM_Q: i32 = 3018;
// Меню «Песня»: переход к такту по номеру.
const ID_GOTO_MEASURE: i32 = 3019;
// Меню «Настройки»: свойства цифровки.
const ID_PROJ_SETTINGS: i32 = 4001;
// Меню «Справка»: клавиатурные сокращения (F1).
const ID_HELP: i32 = 4002;

/// Состояние панели тактов: короткие строки-ячейки + курсор.
struct GridState {
    cells: Vec<String>,
    cursor: i32,
}

fn bg() -> Colour {
    Colour::new(250, 250, 248, 255)
}
fn cell_fill() -> Colour {
    Colour::new(255, 255, 255, 255)
}
fn cursor_fill() -> Colour {
    Colour::new(255, 244, 180, 255)
}
fn text_dark() -> Colour {
    Colour::new(40, 40, 40, 255)
}
fn border() -> Colour {
    Colour::new(160, 160, 160, 255)
}
fn accent() -> Colour {
    Colour::new(150, 90, 0, 255)
}

/// Создать панель тактов: обычный Panel + on_paint (как в примере custom_widget,
/// где макрос строит ровно Panel). Состояние ячеек и курсора — в Rc<RefCell>,
/// им управляют хоткеи/меню, а не событие.
fn make_grid(parent: &Frame, doc: &Doc) -> (Panel, Rc<RefCell<GridState>>) {
    let panel = Panel::builder(parent).build();
    let state = Rc::new(RefCell::new(GridState {
        cells: doc.grid_cells(),
        cursor: doc.cursor,
    }));
    panel.set_background_style(BackgroundStyle::Paint);

    let state_paint = state.clone();
    panel.on_paint(move |event| {
        let st = state_paint.borrow();
        draw_grid(&panel, &st);
        event.skip(true);
    });

    (panel, state)
}

/// Отрисовка сетки: по такту на ячейку, колонками по 4; курсор подсвечен.
fn draw_grid(panel: &Panel, st: &GridState) {
    let size = panel.get_size();
    let w = size.width;
    let h = size.height;
    let dc = AutoBufferedPaintDC::new(panel);
    if w <= 0 || h <= 0 {
        return;
    }

    // Фон (перо прозрачное — чисто заливка, без рамки по краю).
    dc.set_brush(bg(), BrushStyle::Solid);
    dc.set_pen(Colour::new(0, 0, 0, 0), 0, PenStyle::Transparent);
    dc.draw_rectangle(0, 0, w, h);

    let n = st.cells.len();
    if n == 0 {
        return;
    }
    let cols = if n < 4 { n } else { 4 };
    let cw = (w / cols as i32).max(1);
    let row_h: i32 = 64;

    for (idx, text) in st.cells.iter().enumerate() {
        let measure = idx as i32 + 1;
        let r = idx / cols;
        let c = idx % cols;
        let x = c as i32 * cw;
        let y = r as i32 * row_h;
        let is_cursor = measure == st.cursor;

        if is_cursor {
            dc.set_brush(cursor_fill(), BrushStyle::Solid);
            dc.set_pen(accent(), 3, PenStyle::Solid);
        } else {
            dc.set_brush(cell_fill(), BrushStyle::Solid);
            dc.set_pen(border(), 1, PenStyle::Solid);
        }
        dc.draw_rectangle(x, y, cw, row_h);

        // Номер такта + содержимое (обрезаем до ширины ячейки).
        dc.set_text_foreground(text_dark());
        dc.draw_text(&format!("{measure}"), x + 6, y + 4);
        let max_chars = ((cw / 7).max(4)) as usize;
        let clipped = clip_text(text, max_chars);
        dc.draw_text(&clipped, x + 6, y + 20);
    }
}

/// Обрезать строку до *max_chars* символов с многоточием.
fn clip_text(s: &str, max_chars: usize) -> String {
    if s.chars().count() <= max_chars {
        return s.to_string();
    }
    let mut out: String = s.chars().take(max_chars - 1).collect();
    out.push('…');
    out
}

/// Обновить ячейки/курсор сетки под документ и перерисовать.
fn sync_grid(doc: &Doc, state: &Rc<RefCell<GridState>>, panel: &Panel) {
    {
        let mut st = state.borrow_mut();
        st.cells = doc.grid_cells();
        st.cursor = doc.cursor;
    }
    panel.refresh(false, None);
}

/// Озвучить текущий такт, показать в статусе.
fn announce(doc: &Doc, speaker: &dyn Speak, frame: &Frame) {
    let text = doc.announce_current();
    speaker.speak(&text);
    frame.set_status_text(
        &format!("Такт {} из {}", doc.cursor, doc.last_measure()),
        0,
    );
}

/// Шаг простой стрелкой (slice 11): по событиям — на следующий/предыдущий
/// аккорд (в т.ч. внутри такта), а если впереди аккордов нет — «в такт» по
/// пустым. Возвращает готовую строку для озвучки; пустая — курсор не сдвинулся.
fn nav_chord_step(doc: &mut Doc, left: bool) -> String {
    let from = doc.cursor;
    let moved = if left {
        doc.go_chord_left()
    } else {
        doc.go_chord_right()
    };
    if moved {
        doc.announce_after_chord_step(from)
    } else {
        String::new()
    }
}

/// Шаг Ctrl+стрелка: по тактам, включая пустые (доля сбрасывается). Возвращает
/// строку для озвучки; пустая — курсор на границе, шага не было.
fn nav_measure_step(doc: &mut Doc, left: bool) -> String {
    let before = doc.cursor;
    if left {
        doc.go_left();
    } else {
        doc.go_right();
    }
    if doc.cursor != before {
        doc.announce_current()
    } else {
        String::new()
    }
}

/// Применить шаг навигации (msg — готовая озвучка; пустая = молчание, шага не
/// было): перерисовать сетку, проговорить и показать статус «Такт X из Y».
fn apply_navigation(
    msg: &str,
    doc: &Rc<RefCell<Doc>>,
    speaker: &Rc<RefCell<Box<dyn Speak>>>,
    state: &Rc<RefCell<GridState>>,
    panel: &Panel,
    frame: &Frame,
) {
    if msg.is_empty() {
        return;
    }
    {
        let d = doc.borrow();
        let dref = &*d;
        sync_grid(dref, state, panel);
        frame.set_status_text(
            &format!("Такт {} из {}", dref.cursor, dref.last_measure()),
            0,
        );
    }
    speaker.borrow().speak(msg);
}

/// Диагностика дебаг-клавиши D: строка в консоль (eprintln) и в файл
/// `irealwx_speech_debug.txt` рядом с exe (fallback — системный temp), чтобы
/// причина «NVDA молчит» была видна и без консольного окна.
fn debug_log(line: &str) {
    eprintln!("[debug] {line}");
    use std::io::Write;
    let base = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(std::env::temp_dir);
    let path = base.join("irealwx_speech_debug.txt");
    if let Ok(mut f) = fs::OpenOptions::new().create(true).append(true).open(&path) {
        let _ = writeln!(f, "{line}");
    }
}

/// Заголовок окна: «irealstudio — <название цифровки>», звёздочка спереди —
/// признак несохранённых правок (как python `_mark_dirty` рисует звёздочку).
fn window_title(doc: &Doc) -> String {
    let base = format!("irealstudio — {}", doc.cp.title);
    if doc.dirty {
        format!("* {base}")
    } else {
        base
    }
}

/// Применить результат правки Doc (метод уже мутировал документ и вернул строку
/// для озвучки; пустая = молчание): перерисовать сетку, проговорить/показать в
/// статусе сообщение и обновить «звёздочку» в заголовке.
fn commit_edit(
    msg: &str,
    doc: &Rc<RefCell<Doc>>,
    speaker: &Rc<RefCell<Box<dyn Speak>>>,
    state: &Rc<RefCell<GridState>>,
    panel: &Panel,
    frame: &Frame,
) {
    let d = doc.borrow();
    sync_grid(&d, state, panel);
    if !msg.is_empty() {
        speaker.borrow().speak(msg);
        frame.set_status_text(msg, 0);
    }
    frame.set_title(&window_title(&d));
}

/// Обновить заголовок после открытия/создания/сохранения (без правок).
fn refresh_title(doc: &Rc<RefCell<Doc>>, frame: &Frame) {
    let d = doc.borrow();
    frame.set_title(&window_title(&d));
}

// --- Открыть/сохранить (.ips = progression.to_json()) ---
//
// Калька python IOMixin (app_io.py): `.ips` — это ровно JSON цифровки
// (`ChordProgression.to_json`), пишется UTF-8. Имя по умолчанию при сохранении —
// `title.replace(' ','_') + ".ips"`. Озвучка как в python: «Открыто: <название>»,
// «Сохранено: <имя файла>»; ошибки — «Не удалось открыть/сохранить: <причина>».

/// Фильтр файлов — тот же wildcard, что python save_as/open_file.
const IPS_WILDCARD: &str = "IReal Studio files (*.ips)|*.ips|All files (*.*)|*.*";

/// Диалог «Открыть цифровку» (wxFileDialog) → путь; None — отмена.
fn pick_open_path(parent: &Frame) -> Option<PathBuf> {
    let dlg = FileDialog::builder(parent)
        .with_message("Открыть цифровку")
        .with_wildcard(IPS_WILDCARD)
        .with_style(FileDialogStyle::Open | FileDialogStyle::FileMustExist)
        .build();
    if dlg.show_modal() == ID_OK {
        dlg.get_path().map(PathBuf::from)
    } else {
        None
    }
}

/// Диалог «Сохранить цифровку как» → путь; None — отмена. Имя по умолчанию —
/// из названия цифровки (как python app_io.save_as).
fn pick_save_path(parent: &Frame, default_name: &str) -> Option<PathBuf> {
    let dlg = FileDialog::builder(parent)
        .with_message("Сохранить цифровку")
        .with_default_file(default_name)
        .with_wildcard(IPS_WILDCARD)
        .with_style(FileDialogStyle::Save | FileDialogStyle::OverwritePrompt)
        .build();
    if dlg.show_modal() == ID_OK {
        dlg.get_path().map(PathBuf::from)
    } else {
        None
    }
}

/// Заменить документ на загруженный и привести интерфейс в соответствие
/// (курсор уже на такте 1 — как python _apply_loaded_progression → Position(1,1)).
/// Путь запоминается как текущий файл.
fn install_loaded(
    loaded: Doc,
    path: PathBuf,
    doc: &Rc<RefCell<Doc>>,
    spk: &Rc<RefCell<Box<dyn Speak>>>,
    state: &Rc<RefCell<GridState>>,
    panel: &Panel,
    current_file: &Rc<RefCell<Option<PathBuf>>>,
    frame: &Frame,
) {
    let title = loaded.cp.title.clone();
    *doc.borrow_mut() = loaded;
    *current_file.borrow_mut() = Some(path);
    let d = doc.borrow();
    sync_grid(&d, state, panel);
    frame.set_title(&window_title(&d));
    let msg = format!("Открыто: {title}");
    spk.borrow().speak(&msg);
    frame.set_status_text(
        &format!("{msg}. Такт {} из {}", d.cursor, d.last_measure()),
        0,
    );
}

/// Написать цифровку в файл `.ips` — как python `_save_to_path` (UTF-8 JSON).
fn write_to_path(path: &Path, doc: &Doc) -> Result<(), String> {
    fs::write(path, doc.to_json()).map_err(|e| e.to_string())
}

/// «Сохранить как» — калька python `app_io.save_as`: диалог с именем по умолчанию
/// `title.replace(' ','_') + ".ips"`, запись, запоминание пути как текущего файла,
/// озвучка «Сохранено: <имя файла>».
fn save_as_progression(
    doc: &Rc<RefCell<Doc>>,
    spk: &Rc<RefCell<Box<dyn Speak>>>,
    current_file: &Rc<RefCell<Option<PathBuf>>>,
    frame: &Frame,
) {
    let default_name = {
        let d = doc.borrow();
        format!("{}.ips", d.cp.title.replace(' ', "_"))
    };
    if let Some(path) = pick_save_path(frame, &default_name) {
        let name = path
            .file_name()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_default();
        let res = {
            let d = doc.borrow();
            write_to_path(&path, &d)
        };
        match res {
            Ok(()) => {
                *current_file.borrow_mut() = Some(path);
                {
                    let mut d = doc.borrow_mut();
                    d.mark_clean();
                }
                spk.borrow().speak(&format!("Сохранено: {name}"));
                frame.set_status_text(&format!("Сохранено: {name}"), 0);
                refresh_title(doc, frame);
            }
            Err(e) => {
                spk.borrow().speak(&format!("Не удалось сохранить: {e}"));
            }
        }
    }
}

/// «Сохранить текущий документ» для грязных-диалогов (slice 8): в текущий файл,
/// если он есть; иначе — «Сохранить как». Возвращает true, если документ
/// сохранён (чистый); false, если сохранение отменено или не удалось — в этом
/// случае продолжать (закрытие / новая цифровка) нельзя, как python new_project
/// проверяет `_is_dirty` после `self.save()`.
fn save_current_or_as(
    doc: &Rc<RefCell<Doc>>,
    spk: &Rc<RefCell<Box<dyn Speak>>>,
    current_file: &Rc<RefCell<Option<PathBuf>>>,
    frame: &Frame,
) -> bool {
    // Клонируем путь из Ref явно (у RefCell::Ref свой Clone — голый .clone()
    // склонировал бы обёртку, а не Option).
    let cur = {
        let cf = current_file.borrow();
        (*cf).clone()
    };
    match cur {
        Some(path) => {
            // Текущий файл есть — пишем прямо в него (как python save()).
            let name = path
                .file_name()
                .map(|s| s.to_string_lossy().into_owned())
                .unwrap_or_default();
            let res = {
                let d = doc.borrow();
                write_to_path(&path, &d)
            };
            match res {
                Ok(()) => {
                    doc.borrow_mut().mark_clean();
                    spk.borrow().speak(&format!("Сохранено: {name}"));
                    frame.set_status_text(&format!("Сохранено: {name}"), 0);
                    refresh_title(doc, frame);
                    true
                }
                Err(e) => {
                    let msg = format!("Не удалось сохранить: {e}");
                    spk.borrow().speak(&msg);
                    frame.set_status_text(&msg, 0);
                    false
                }
            }
        }
        None => {
            // Файла нет — как python save() → save_as(); отмена диалога оставляет
            // документ грязным → false.
            save_as_progression(doc, spk, current_file, frame);
            !doc.borrow().dirty
        }
    }
}

// --- Экспорт в iReal Pro (Ctrl+E) ---
//
// Калька python `app_io.export_ireal`: сохраняет HTML с авто-редиректом на
// `irealb://` URL (открыв его на устройстве с iReal Pro, цифровка импортируется
// с темпом). Расширение `.txt` — отладочный вариант: сырой не-URL-encoded
// `irealbook://` URL без HTML-обёртки. Имя по умолчанию — `title + ".html"`
// рядом с текущим файлом (как python `_safe_filename`).

/// Диалог «Экспорт в iReal Pro» (сохранить HTML/текст) → путь; None — отмена.
fn pick_export_path(parent: &Frame, default_name: &str, default_dir: &str) -> Option<PathBuf> {
    let dlg = FileDialog::builder(parent)
        .with_message("Экспорт в iReal Pro")
        .with_default_dir(default_dir)
        .with_default_file(default_name)
        .with_wildcard("HTML files (*.html)|*.html|Text files (*.txt)|*.txt|All files (*.*)|*.*")
        .with_style(FileDialogStyle::Save | FileDialogStyle::OverwritePrompt)
        .build();
    if dlg.show_modal() == ID_OK {
        dlg.get_path().map(PathBuf::from)
    } else {
        None
    }
}

/// Поставить метку части по букве (пункт подменю «Метка части») и проговорить
/// результат — как python `add_section_mark(letter)`.
fn add_section_mark_menu(
    letter: char,
    doc: &Rc<RefCell<Doc>>,
    speaker: &Rc<RefCell<Box<dyn Speak>>>,
    state: &Rc<RefCell<GridState>>,
    panel: &Panel,
    frame: &Frame,
) {
    let msg = {
        let mut d = doc.borrow_mut();
        d.add_section_mark_by_letter(letter)
    };
    commit_edit(&msg, doc, speaker, state, panel, frame);
}

/// Экспорт текущей цифровки в HTML/текст — как python export_ireal.
fn export_progression(
    doc: &Rc<RefCell<Doc>>,
    spk: &Rc<RefCell<Box<dyn Speak>>>,
    current_file: &Rc<RefCell<Option<PathBuf>>>,
    frame: &Frame,
) {
    // Диалог открываем без живого borrow документа (модальный цикл wx).
    let default_dir = {
        let cf = current_file.borrow();
        cf.as_ref()
            .and_then(|p| p.parent().map(|x| x.to_string_lossy().into_owned()))
            .unwrap_or_default()
    };
    let (title, url, default_name) = {
        let d = doc.borrow();
        let url = d.cp.to_irealb_url(true);
        let base = safe_file_base(&d.cp.title);
        (d.cp.title.clone(), url, format!("{base}.html"))
    };
    if let Some(path) = pick_export_path(frame, &default_name, &default_dir) {
        let name = path
            .file_name()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_default();
        // `.txt` — отладочный экспорт: сырой irealbook URL без HTML.
        let is_txt = path
            .extension()
            .map(|e| e.to_string_lossy().eq_ignore_ascii_case("txt"))
            .unwrap_or(false);
        let content = if is_txt {
            doc.borrow().cp.to_ireal_url(false)
        } else {
            export_ireal_html(&title, &url)
        };
        match fs::write(&path, content) {
            Ok(()) => {
                spk.borrow().speak(&format!("Экспортировано: {name}"));
                frame.set_status_text(&format!("Экспортировано: {name}"), 0);
            }
            Err(e) => {
                spk.borrow().speak(&format!("Экспорт не удался: {e}"));
            }
        }
    }
}

// --- Правка цифровки (slice 5): меню «Правка»/«Вставка», формы-диалоги ---
//
// Поле ввода (имя аккорда, басовая нота) и счётчик (транспонирование, переход
// к такту) — калька python-диалогов (dialogs.py insert_chord/go_to_measure/
// transpose). Курсор у Doc тактовый, поэтому клетка = первый аккорд такта (см.
// lib.rs). Диалоги устроены как show_new_chart_dialog ниже: настоящий wxDialog
// с ролью для NVDA, порядок контролов = порядок табов.

/// Модальный диалог с одним текстовым полем. OK → введённая строка (как есть,
/// без трима — решает сам Doc), Отмена/ESC → None.
fn modal_text(parent: &Frame, title: &str, label: &str, initial: &str) -> Option<String> {
    let dialog = Dialog::builder(parent, title)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let panel = Panel::builder(&dialog).build();
    let ctrl = TextCtrl::builder(&panel).with_value(initial).build();

    let col = BoxSizer::builder(Orientation::Vertical).build();
    add_labeled_row(&col, &panel, label, &ctrl);

    let ok_button = Button::builder(&panel).with_id(ID_OK).with_label("ОК").build();
    let cancel_button = Button::builder(&panel)
        .with_id(ID_CANCEL)
        .with_label("Отмена")
        .build();
    ok_button.set_default();
    let ok_dialog = dialog;
    ok_button.on_click(move |_| ok_dialog.end_modal(ID_OK));
    let cancel_dialog = dialog;
    cancel_button.on_click(move |_| cancel_dialog.end_modal(ID_CANCEL));

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    buttons.add(&ok_button, 0, SizerFlag::AlignCenterVertical | SizerFlag::Right, 4);
    buttons.add(&cancel_button, 0, SizerFlag::AlignCenterVertical | SizerFlag::Right, 4);
    col.add_sizer(&buttons, 0, SizerFlag::AlignRight | SizerFlag::Top, 8);

    panel.set_sizer(col, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer_and_fit(dialog_sizer, true);

    // Начальный фокус — в поле (как python `SetFocus` на первом контроле):
    // без него фокус не уходит в диалог и NVDA молчит на открытии.
    ctrl.set_focus();

    let result = dialog.show_modal();
    let value = if result == ID_OK { Some(ctrl.get_value()) } else { None };
    dialog.destroy();
    value
}

/// Модальный диалог со счётчиком в заданном диапазоне. OK → число, иначе None.
fn modal_spin(
    parent: &Frame,
    title: &str,
    label: &str,
    min: i32,
    max: i32,
    initial: i32,
) -> Option<i32> {
    let dialog = Dialog::builder(parent, title)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let panel = Panel::builder(&dialog).build();
    let spin = SpinCtrl::builder(&panel)
        .with_range(min, max)
        .with_initial_value(initial)
        .build();

    let col = BoxSizer::builder(Orientation::Vertical).build();
    add_labeled_row(&col, &panel, label, &spin);

    let ok_button = Button::builder(&panel).with_id(ID_OK).with_label("ОК").build();
    let cancel_button = Button::builder(&panel)
        .with_id(ID_CANCEL)
        .with_label("Отмена")
        .build();
    ok_button.set_default();
    let ok_dialog = dialog;
    ok_button.on_click(move |_| ok_dialog.end_modal(ID_OK));
    let cancel_dialog = dialog;
    cancel_button.on_click(move |_| cancel_dialog.end_modal(ID_CANCEL));

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    buttons.add(&ok_button, 0, SizerFlag::AlignCenterVertical | SizerFlag::Right, 4);
    buttons.add(&cancel_button, 0, SizerFlag::AlignCenterVertical | SizerFlag::Right, 4);
    col.add_sizer(&buttons, 0, SizerFlag::AlignRight | SizerFlag::Top, 8);

    panel.set_sizer(col, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer_and_fit(dialog_sizer, true);

    spin.set_focus();
    let result = dialog.show_modal();
    let value = if result == ID_OK { Some(spin.value()) } else { None };
    dialog.destroy();
    value
}

// --- Диалог «Несохранённые изменения» (slice 8) ---
//
// Калька python `wx.MessageDialog(YES_NO|CANCEL|YES_DEFAULT|ICON_WARNING)` из
// `_on_close_window` (main.py) и `new_project` (app_io.py): подтверждение перед
// закрытием окна / созданием новой цифровки, когда есть несохранённые правки.

/// Выбор пользователя в диалоге несохранённых изменений (wx.YES / NO / CANCEL).
#[derive(Clone, Copy, PartialEq, Eq)]
enum UnsavedChoice {
    /// Сохранить правки (в текущий файл или «Сохранить как»).
    Save,
    /// Не сохранять — продолжить действие (закрыть/создать новую).
    Discard,
    /// Отмена — вернуться к текущему документу.
    Cancel,
}

/// Показать модальный диалог несохранённых изменений. *message* — уже готовый
/// текст вопроса («…содержит несохранённые изменения.\n\nСохранить …?»).
/// Нативный месседж-бокс (slice 11, msg 1587): вопрос — текст диалога, а не
/// текстовое поле, NVDA читает и текст, и кнопки штатно. Кнопки «Сохранить» /
/// «Не сохранять» / «Отмена»; Enter = Сохранить (дефолт Yes), Esc = Отмена.
fn ask_unsaved(parent: &Frame, message: &str) -> UnsavedChoice {
    let dlg = MessageDialog::builder(parent, message, "Несохранённые изменения")
        .with_style(
            MessageDialogStyle::YesNo | MessageDialogStyle::Cancel | MessageDialogStyle::IconWarning,
        )
        .build();
    dlg.set_yes_no_labels("Сохранить", "Не сохранять");
    let result = dlg.show_modal();
    let choice = if result == ID_YES {
        UnsavedChoice::Save
    } else if result == ID_NO {
        UnsavedChoice::Discard
    } else {
        UnsavedChoice::Cancel
    };
    // MessageDialog уничтожается сам (Drop → destroy_once).
    choice
}

/// Погасить close-событие (окно не закрывается) — как python `event.Veto()`.
/// CLOSE_WINDOW приходит как `WindowEventData::General(Event)` (в wxdragon у
/// этого варианта нет отдельной ветки), а veto есть на самом `Event`.
fn veto_close(event: &WindowEventData) {
    if let WindowEventData::General(e) = event {
        if e.can_veto() {
            e.veto();
        }
    }
}

// --- Диалог «Клавиатурные сокращения» (F1, slice 9) ---
//
// Калька python `_show_keyboard_shortcuts` (app_io.py:521): read-only
// многострочный текст со всеми хоткеями и одно «ОК». Текст в поле с начальным
// фокусом — NVDA читает его с открытия (список длинный, и в нативном
// месседж-боксе он бы не листался). Нативный месседж-бокс — только там, где
// текста мало и важен вопрос с кнопками (ask_unsaved, msg 1587).
// Слайс аддитивный: новое меню и диалог, поведение пунктов 1–84 не меняется.

/// Справка построчно (join в диалоге). Сверена с реальными биндингами:
/// акселераторы из меток пунктов меню (\t) + клавиши в handle_key.
const HELP_LINES: &[&str] = &[
    "Файл",
    "Ctrl+N — новая цифровка",
    "Ctrl+O — открыть из файла .ips",
    "Ctrl+S — сохранить (нет файла — откроется «Сохранить как»)",
    "Ctrl+Shift+S — сохранить как (в новый файл)",
    "Ctrl+E — экспорт в iReal Pro",
    "Ctrl+W — закрыть окно, Ctrl+Q — выход",
    "Закрытие при правках спросит подтверждение",
    "",
    "Правка",
    "Ctrl+Z — отменить, Ctrl+Y — повторить",
    "Ctrl+X — вырезать аккорд, Ctrl+C — копировать, Ctrl+V — вставить",
    "Ctrl+T — транспонировать всю цифровку",
    "",
    "Вставка",
    "Ctrl+Enter — добавить аккорд в текущий такт",
    "F2 — изменить аккорд под курсором",
    "N — без аккорда (N.C.) на текущем такте",
    "V — вольта / окончание",
    "[ — начало повтора, ] — конец повтора",
    "Метка части (подменю «Вставка»):",
    "Ctrl+Shift+A/B/C/D — Части A, B, C, D",
    "Ctrl+Shift+V — Куплет, Ctrl+Shift+I — Вступление",
    "Сеньо — через «Вставка → Метка части» (без хоткея)",
    "Ctrl+Shift+Q — Кода",
    "Басовая нота — «Вставка → Басовая нота…»",
    "",
    "Песня (навигация как в MuseScore)",
    "← / → — по аккордам и пустым тактам (внутри такта — второй аккорд)",
    "Ctrl+← / Ctrl+→ — по тактам, включая пустые",
    "Alt+← / Alt+→ — в начало / конец секции",
    "Home — первый такт, End — последний такт",
    "Del / Backspace — удалить аккорд",
    "Ctrl+Del / Ctrl+Backspace — удалить только метку / повтор / N.C.",
    "F5 — озвучить текущий такт, F6 — озвучить всю цифровку",
    "Ctrl+F — перейти к такту по номеру",
    "",
    "Настройки",
    "Ctrl+P — настройки цифровки (название, темп, тональность и др.)",
    "",
    "Справка",
    "F1 — этот список клавиш",
    "",
    "Отладка",
    "D — проверка озвучки (NVDA): проговорит тест; при сбое причина — в консоль",
    "и файл irealwx_speech_debug.txt рядом с программой",
    "",
    "В диалогах: Enter — подтвердить (кнопка по умолчанию), Esc — отмена.",
];

/// Показать модальный диалог со списком горячих клавиш. Read-only многострочный
/// текст в реальном wxDialog (slice 9, калька python `_show_keyboard_shortcuts`):
/// список длинный (~45 строк) — для NVDA такой текст читается и листается
/// стрелками целиком, в отличие от нативного месседж-бокса. Поле read-only,
/// начальный фокус в него. (msg 1587 был про текст вопроса в поле — его
/// исправлен нативный ask_unsaved; справка осталась текстом, как в python.)
fn show_help_dialog(parent: &Frame) {
    let dialog = Dialog::builder(parent, "Клавиатурные сокращения — irealstudio")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let panel = Panel::builder(&dialog).build();
    let text = HELP_LINES.join("\n");
    let text_ctrl = TextCtrl::builder(&panel)
        .with_value(&text)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly)
        .with_size(Size::new(600, 440))
        .build();

    let ok_button = Button::builder(&panel)
        .with_id(ID_OK)
        .with_label("ОК")
        .build();
    ok_button.set_default();
    let d_ok = dialog;
    ok_button.on_click(move |_| d_ok.end_modal(ID_OK));

    let col = BoxSizer::builder(Orientation::Vertical).build();
    col.add(&text_ctrl, 1, SizerFlag::Expand, 4);
    col.add_spacer(4);
    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    buttons.add(&ok_button, 0, SizerFlag::AlignCenterVertical | SizerFlag::Right, 4);
    col.add_sizer(&buttons, 0, SizerFlag::AlignRight | SizerFlag::Top, 8);
    panel.set_sizer(col, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer_and_fit(dialog_sizer, true);

    // Начальный фокус в текст — иначе NVDA на открытии диалога молчит.
    text_ctrl.set_focus();
    let _ = dialog.show_modal();
    dialog.destroy();
}

// --- Форма «Новая цифровка» (Ctrl+N) ---
//
// Калька python `_NewProjectDlg` (dialogs.py:240) в реальный wxDialog: NVDA
// объявляет его как диалог, табы идут по порядку создания контролов (как в
// wxPython-версии). Поля формы собирают `NewChart`, дальше его строит
// `Doc::new_chart` в lib (тот же путь, что python `new_project`).

/// Все 50 стилей iReal — порядок python `STYLES_ALL` (pyrealpro.py:25).
const STYLES_ALL: [&str; 50] = [
    "Afro 12/8",
    "Ballad Double Time Feel",
    "Ballad Even",
    "Ballad Melodic",
    "Ballad Swing",
    "Blue Note",
    "Bossa Nova",
    "Doo Doo Cats",
    "Double Time Swing",
    "Even 8ths",
    "Even 8ths Open",
    "Even 16ths",
    "Guitar Trio",
    "Gypsy Jazz",
    "Latin",
    "Latin/Swing",
    "Long Notes",
    "Medium Swing",
    "Medium Up Swing",
    "Medium Up Swing 2",
    "New Orleans Swing",
    "Second Line",
    "Slow Swing",
    "Swing Two/Four",
    "Trad Jazz",
    "Up Tempo Swing",
    "Up Tempo Swing 2",
    "Argentina: Tango",
    "Brazil: Bossa Acoustic",
    "Brazil: Bossa Electric",
    "Brazil: Samba",
    "Cuba: Bolero",
    "Cuba: Cha Cha Cha",
    "Cuba: Son Montuno 2-3",
    "Cuba: Son Montuno 3-2",
    "Bluegrass",
    "Country",
    "Disco",
    "Funk",
    "Glam Funk",
    "House",
    "Reggae",
    "Rock",
    "Rock 12/8",
    "RnB",
    "Shuffle",
    "Slow Rock",
    "Smooth",
    "Soul",
    "Virtual Funk",
];

/// Шаблоны формы: индексы совпадают у меток (`TEMPLATE_LABELS`) и ключей
/// (`TEMPLATE_KEYS`) — первый пункт «без шаблона» даёт пустой `NewChart.template`.
const TEMPLATE_LABELS: [&str; 6] =
    ["Без шаблона", "Blues", "AABA", "ABAC", "ABAB", "ABCD"];
const TEMPLATE_KEYS: [&str; 6] = ["", "Blues", "AABA", "ABAC", "ABAB", "ABCD"];

/// Ряд «метка + расширяемый контрол» в вертикальную колонку формы.
///
/// NVDA-лейбл контрола (slice 11, msg 1585): имя задаётся контролу явно через
/// `set_name` (текст метки без двоеточия). Слепой эвристике MSAA «статик слева
/// от поля = имя» доверять нельзя — метки в python-формах рождались до контролов
/// (dialogs.py), а здесь контролы создаются до меток, и NVDA читала просто тип
/// («Редактор», «Комбобокс»). Явное имя чинит все формы сразу.
fn add_labeled_row<W: WxWidget>(col: &BoxSizer, panel: &Panel, label: &str, ctrl: &W) {
    let row = BoxSizer::builder(Orientation::Horizontal).build();
    let lab = StaticText::builder(panel).with_label(label).build();
    // Без конфликта wxEXPAND с флагами выравнивания: в box-sizer wxEXPAND сам
    // задаёт кросс-ось, комбинация с wxALIGN_* даёт debug-assert «wxEXPAND
    // overrides alignment flags in box sizers» (sizer.cpp). Поле тянется по
    // ширине ряда (пропорция 1), ряд — по ширине колонки (wxEXPAND).
    row.add(&lab, 0, SizerFlag::AlignCenterVertical, 8);
    row.add(ctrl, 1, SizerFlag::Expand, 0);
    col.add_sizer(&row, 0, SizerFlag::Expand, 4);
    let name = label.trim_end_matches(':').trim();
    if !name.is_empty() {
        ctrl.set_name(name);
    }
}

/// Модальный диалог новой цифровки. Возвращает `NewChart` при OK,
/// `None` при отмене — как python `new_project_dialog` (dict/None).
fn show_new_chart_dialog(parent: &Frame) -> Option<NewChart> {
    // wxDialog с нативной ролью диалога для NVDA (как в python-версии).
    let dialog = Dialog::builder(parent, "Новая цифровка")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let panel = Panel::builder(&dialog).build();

    // --- Поля: порядок создания = порядок табов (как в python-форме) ---
    // Название / композитор / темп — текстовые поля.
    let title_ctrl = TextCtrl::builder(&panel).with_value("My Progression").build();
    let composer_ctrl = TextCtrl::builder(&panel).with_value("").build();
    let bpm_spin = SpinCtrl::builder(&panel)
        .with_range(BPM_MIN, BPM_MAX)
        .with_initial_value(120)
        .build();

    // Тональность: корень + лад (два комбобокса, как в python-сетке).
    let key_default = "C";
    let root_choice = Choice::builder(&panel)
        .with_choices(KEY_ROOTS.iter().map(|s| s.to_string()).collect())
        .with_selection(Some(KEY_ROOTS.iter().position(|r| *r == key_default).unwrap_or(0) as u32))
        .build();
    let mode_choice = Choice::builder(&panel)
        .with_choices(vec!["мажор".to_string(), "минор".to_string()])
        .with_selection(Some(0))
        .build();

    // Стиль: все 50 стилей iReal, по умолчанию «Medium Swing».
    let style_default = "Medium Swing";
    let style_choice = Choice::builder(&panel)
        .with_choices(STYLES_ALL.iter().map(|s| s.to_string()).collect())
        .with_selection(
            Some(
                STYLES_ALL
                    .iter()
                    .position(|s| *s == style_default)
                    .unwrap_or(0) as u32,
            ),
        )
        .build();

    // Шаблон структуры (в этом slice — без динамических подпанелей: блюз
    // по умолчанию 12 тактов, AABA-семейство по 8 тактов на секцию).
    let template_choice = Choice::builder(&panel)
        .with_choices(TEMPLATE_LABELS.iter().map(|s| s.to_string()).collect())
        .with_selection(Some(0))
        .build();

    // --- Раскладка: колонка из рядов «метка + контрол» ---
    let col = BoxSizer::builder(Orientation::Vertical).build();
    add_labeled_row(&col, &panel, "Название:", &title_ctrl);
    add_labeled_row(&col, &panel, "Композитор:", &composer_ctrl);
    add_labeled_row(&col, &panel, "Темп (BPM):", &bpm_spin);
    add_labeled_row(&col, &panel, "Тональность:", &root_choice);
    add_labeled_row(&col, &panel, "Лад:", &mode_choice);
    add_labeled_row(&col, &panel, "Стиль:", &style_choice);
    add_labeled_row(&col, &panel, "Шаблон:", &template_choice);

    // --- Кнопки ОК / Отмена (справа) ---
    let ok_button = Button::builder(&panel)
        .with_id(ID_OK)
        .with_label("ОК")
        .build();
    let cancel_button = Button::builder(&panel)
        .with_id(ID_CANCEL)
        .with_label("Отмена")
        .build();
    ok_button.set_default();

    let ok_dlg = dialog;
    ok_button.on_click(move |_| {
        ok_dlg.end_modal(ID_OK);
    });
    let cancel_dlg = dialog;
    cancel_button.on_click(move |_| {
        cancel_dlg.end_modal(ID_CANCEL);
    });

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    buttons.add(&ok_button, 0, SizerFlag::AlignCenterVertical | SizerFlag::Right, 4);
    buttons.add(&cancel_button, 0, SizerFlag::AlignCenterVertical | SizerFlag::Right, 4);
    col.add_sizer(&buttons, 0, SizerFlag::AlignRight | SizerFlag::Top, 8);

    panel.set_sizer(col, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer_and_fit(dialog_sizer, true);

    // Начальный фокус в первое поле — иначе NVDA на открытии формы молчит
    // (как python `list(self._ctrls.values())[0].SetFocus()` в _NewProjectDlg).
    title_ctrl.set_focus();

    let result = dialog.show_modal();
    let spec = if result == ID_OK {
        // Читаем значения ПОСЛЕ закрытия модального цикла, но ДО destroy.
        let mut spec = NewChart::defaults();
        let raw_title = title_ctrl.get_value();
        if !raw_title.is_empty() {
            spec.title = raw_title;
        }
        spec.composer = composer_ctrl.get_value();
        let root_idx = root_choice.get_selection().unwrap_or(0) as usize;
        let root = KEY_ROOTS.get(root_idx).copied().unwrap_or("C");
        let minor = mode_choice.get_selection() == Some(1);
        spec.key = key_from_root_mode(root, minor);
        spec.style = style_choice
            .get_string_selection()
            .unwrap_or_else(|| style_default.to_string());
        spec.bpm = bpm_spin.value();
        let tpl_idx = template_choice.get_selection().unwrap_or(0) as usize;
        spec.template = TEMPLATE_KEYS
            .get(tpl_idx)
            .copied()
            .unwrap_or("")
            .to_string();
        Some(spec)
    } else {
        None
    };
    dialog.destroy();
    spec
}

// --- Форма «Настройки цифровки» (Ctrl+P) ---
//
// Калька python `project_settings_dialog` (dialogs.py:562): те же поля, что в
// «Новой цифровке», но предзаполнены текущей цифровкой и без шаблона. Поле
// Recording BPM из python не переносим — подсистемы записи в этой версии нет.
// Собранный `ProjectSettings` применяет `Doc::apply_settings` в lib (тот же
// путь, что python `_open_project_settings`); смена тональности аккорды НЕ
// транспонирует.

/// Модальный диалог настроек цифровки. OK → `ProjectSettings`, отмена → None.
fn show_project_settings_dialog(
    parent: &Frame,
    defaults: &ProjectSettings,
) -> Option<ProjectSettings> {
    let dialog = Dialog::builder(parent, "Настройки цифровки")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let panel = Panel::builder(&dialog).build();

    // --- Поля: порядок создания = порядок табов (как в python-форме) ---
    let title_ctrl = TextCtrl::builder(&panel)
        .with_value(defaults.title.as_str())
        .build();
    let composer_ctrl = TextCtrl::builder(&panel)
        .with_value(defaults.composer.as_str())
        .build();
    let bpm_spin = SpinCtrl::builder(&panel)
        .with_range(BPM_MIN, BPM_MAX)
        .with_initial_value(defaults.bpm)
        .build();
    let time_ctrl = TextCtrl::builder(&panel)
        .with_value(defaults.time_sig.as_str())
        .build();

    // Тональность: текущий ключ разбираем на (корень, лад) обратной функцией.
    let (root_str, minor) = key_to_root_mode(&defaults.key);
    let root_choice = Choice::builder(&panel)
        .with_choices(KEY_ROOTS.iter().map(|s| s.to_string()).collect())
        .with_selection(Some(
            KEY_ROOTS.iter().position(|r| *r == root_str).unwrap_or(0) as u32,
        ))
        .build();
    let mode_choice = Choice::builder(&panel)
        .with_choices(vec!["мажор".to_string(), "минор".to_string()])
        .with_selection(Some(if minor { 1 } else { 0 }))
        .build();
    let style_choice = Choice::builder(&panel)
        .with_choices(STYLES_ALL.iter().map(|s| s.to_string()).collect())
        .with_selection(
            Some(
                STYLES_ALL
                    .iter()
                    .position(|s| *s == defaults.style)
                    .unwrap_or(0) as u32,
            ),
        )
        .build();

    // --- Раскладка: колонка из рядов «метка + контрол» ---
    let col = BoxSizer::builder(Orientation::Vertical).build();
    add_labeled_row(&col, &panel, "Название:", &title_ctrl);
    add_labeled_row(&col, &panel, "Композитор:", &composer_ctrl);
    add_labeled_row(&col, &panel, "Темп (BPM):", &bpm_spin);
    add_labeled_row(&col, &panel, "Размер такта:", &time_ctrl);
    add_labeled_row(&col, &panel, "Тональность:", &root_choice);
    add_labeled_row(&col, &panel, "Лад:", &mode_choice);
    add_labeled_row(&col, &panel, "Стиль:", &style_choice);

    // --- Кнопки ОК / Отмена (справа) ---
    let ok_button = Button::builder(&panel)
        .with_id(ID_OK)
        .with_label("ОК")
        .build();
    let cancel_button = Button::builder(&panel)
        .with_id(ID_CANCEL)
        .with_label("Отмена")
        .build();
    ok_button.set_default();

    let ok_dlg = dialog;
    ok_button.on_click(move |_| {
        ok_dlg.end_modal(ID_OK);
    });
    let cancel_dlg = dialog;
    cancel_button.on_click(move |_| {
        cancel_dlg.end_modal(ID_CANCEL);
    });

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    buttons.add(&ok_button, 0, SizerFlag::AlignCenterVertical | SizerFlag::Right, 4);
    buttons.add(&cancel_button, 0, SizerFlag::AlignCenterVertical | SizerFlag::Right, 4);
    col.add_sizer(&buttons, 0, SizerFlag::AlignRight | SizerFlag::Top, 8);

    panel.set_sizer(col, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer_and_fit(dialog_sizer, true);

    title_ctrl.set_focus();
    let result = dialog.show_modal();
    let spec = if result == ID_OK {
        // Читаем значения ПОСЛЕ закрытия модального цикла, но ДО destroy.
        let root_idx = root_choice.get_selection().unwrap_or(0) as usize;
        let root = KEY_ROOTS.get(root_idx).copied().unwrap_or("C");
        let minor = mode_choice.get_selection() == Some(1);
        Some(ProjectSettings {
            title: title_ctrl.get_value(),
            composer: composer_ctrl.get_value(),
            bpm: bpm_spin.value(),
            key: key_from_root_mode(root, minor),
            style: style_choice
                .get_string_selection()
                .unwrap_or_else(|| defaults.style.clone()),
            time_sig: time_ctrl.get_value(),
        })
    } else {
        None
    };
    dialog.destroy();
    spec
}

/// Клавиатурная навигация: один обработчик для frame и для панели тактов
/// (фокус может быть у любого из них — панель без a11y, но ловит клавиши).
fn handle_key(
    ev: WindowEventData,
    doc: &Rc<RefCell<Doc>>,
    speaker: &Rc<RefCell<Box<dyn Speak>>>,
    state: &Rc<RefCell<GridState>>,
    frame: &Frame,
    panel: &Panel,
) {
    let mut handled = false;
    if let WindowEventData::Keyboard(ref key) = ev {
        let code = key.get_key_code().unwrap_or(0);
        let alt = key.alt_down();
        let ctrl = key.control_down();
        let shift = key.shift_down();
        let mut d = doc.borrow_mut();
        let mut changed = false;
        // Результат правки (строка для озвучки; пустая = молчание). Меню
        // «Правка/Вставка» идёт через on_menu_selected, сюда — только горячие
        // клавиши без пунктов меню: Del/Backspace, N (N.C.), V/[ / ] (вольта и
        // повторы), как python.
        let mut edited: Option<String> = None;
        match code {
            // Простые стрелки — по событиям (MuseScore, slice 11): на аккорд
            // (в т.ч. на второй аккорд того же такта) или «в такт» по пустым,
            // как python by-chord (msg 1594). На границе — беззвучный no-op.
            WXK_LEFT if !alt && !ctrl => {
                let msg = nav_chord_step(&mut d, true);
                if !msg.is_empty() {
                    edited = Some(msg);
                }
            }
            WXK_RIGHT if !alt && !ctrl => {
                let msg = nav_chord_step(&mut d, false);
                if !msg.is_empty() {
                    edited = Some(msg);
                }
            }
            // Ctrl+стрелки — по тактам, включая пустые (доля сбрасывается на 1).
            WXK_LEFT if ctrl && !alt => {
                let msg = nav_measure_step(&mut d, true);
                if !msg.is_empty() {
                    edited = Some(msg);
                }
            }
            WXK_RIGHT if ctrl && !alt => {
                let msg = nav_measure_step(&mut d, false);
                if !msg.is_empty() {
                    edited = Some(msg);
                }
            }
            // Alt+стрелки — структурная навигация по секциям (проверено: доходит).
            WXK_LEFT if alt => {
                let before = d.cursor;
                d.go_prev_structural();
                changed = d.cursor != before;
            }
            WXK_RIGHT if alt => {
                let before = d.cursor;
                d.go_next_structural();
                changed = d.cursor != before;
            }
            WXK_HOME => {
                d.cursor = 1;
                d.beat = 1;
                changed = true;
            }
            WXK_END => {
                d.cursor = d.last_measure();
                d.beat = 1;
                changed = true;
            }
            // Del/Backspace — удалить аккорд; Ctrl+Del/Ctrl+Backspace — только
            // структуру (метку части/знак повтора/N.C.), как python delete_at_cursor.
            WXK_DELETE | WXK_BACK => {
                edited = Some(if ctrl {
                    d.delete_structural_at_cursor()
                } else {
                    d.delete_at_cursor()
                });
            }
            // 'N' — переключение N.C. (клавиша отдаётся прописной ASCII, 78).
            78 if !ctrl && !alt && !shift => {
                edited = Some(d.toggle_no_chord());
            }
            // 'V' (86) — вольта/повтор; '[' (91) / ']' (93) — маркеры начала и
            // конца повтора — как python app_keys.py: V без гейта, [ и ] как
            // set_repeat_start/set_repeat_end (в python тоже на IDLE-рекордера).
            86 if !ctrl && !alt && !shift => {
                edited = Some(d.add_volta());
            }
            91 if !ctrl && !alt && !shift => {
                edited = Some(d.set_repeat_start());
            }
            93 if !ctrl && !alt && !shift => {
                edited = Some(d.set_repeat_end());
            }
            // 'D' (68) — проверка озвучки (дебаг). Проговаривает контрольную
            // фразу тем же путём, что и обычные объявления (NVDA ControllerClient);
            // при сбое причина пишется в консоль и файл irealwx_speech_debug.txt
            // рядом с exe и показывается в статус-строке.
            68 if !ctrl && !alt && !shift => {
                let text = format!("Проверка озвучки. {}", d.announce_current());
                match speak_diagnose(&text) {
                    Ok(()) => {
                        frame.set_status_text("Озвучка NVDA: работает (текст принят)", 0);
                        debug_log("OK: озвучка NVDA приняла текст");
                    }
                    Err(reason) => {
                        let line = format!("NVDA молчит: {reason}");
                        debug_log(&line);
                        frame.set_status_text(&line, 0);
                    }
                }
                handled = true;
            }
            _ => {}
        }
        if let Some(msg) = edited {
            sync_grid(&d, state, panel);
            if !msg.is_empty() {
                let spk = speaker.borrow();
                spk.speak(&msg);
                frame.set_status_text(&msg, 0);
            }
            frame.set_title(&window_title(&d));
            handled = true;
        } else if changed {
            sync_grid(&d, state, panel);
            announce(&d, &**speaker.borrow(), frame);
            handled = true;
        }
    }
    // skip(true) = «не обработано, пропустить дальше»: если мы сдвинули курсор,
    // останавливаем событие (иначе его перехватит второй обработчик на frame/панели).
    ev.skip(!handled);
}

fn main() {
    // wx без манифеста на MSW показывает на старте предупреждение — глушим
    // (манифест добавим в релизной сборке через build.rs). На gtk/cocoa опция
    // не нужна и безопасно не устанавливается.
    #[cfg(target_os = "windows")]
    SystemOptions::set_option_by_int("msw.no-manifest-check", 1);

    let _ = wxdragon::main(|_app| {
        // --- Документ, озвучка и текущий файл (общие для меню и клавиатуры) ---
        let doc: Rc<RefCell<Doc>> = Rc::new(RefCell::new(Doc::new_demo()));
        let speaker: Rc<RefCell<Box<dyn Speak>>> =
            Rc::new(RefCell::new(default_speak()));
        // Путь открытого/сохранённого .ips — None, пока цифровка не связана
        // с файлом (как python `self._current_file`).
        let current_file: Rc<RefCell<Option<PathBuf>>> = Rc::new(RefCell::new(None));

        // --- Главное окно ---
        let frame = Frame::builder()
            .with_title("irealstudio")
            .with_size(Size::new(920, 640))
            .build();

        // --- Менюбар ---
        let file_menu = Menu::builder()
            .append_item(ID_NEW, "&Новая цифровка…\tCtrl+N", "Создать новую цифровку")
            .append_separator()
            .append_item(ID_OPEN, "&Открыть…\tCtrl+O", "Открыть цифровку из файла .ips")
            .append_item(ID_SAVE, "&Сохранить\tCtrl+S", "Сохранить цифровку в файл .ips")
            // Слайс 11 (msg 1585): Ctrl+Shift+S — «Сохранить как» (как python);
            // у «Сеньо» в подменю «Метка части» хоткея больше нет.
            .append_item(
                ID_SAVE_AS,
                "Сохранить &как…\tCtrl+Shift+S",
                "Сохранить цифровку в новый файл",
            )
            .append_separator()
            .append_item(
                ID_EXPORT,
                "Экспорт в &iReal Pro…\tCtrl+E",
                "Сохранить HTML/текст с irealb-ссылкой для iReal Pro",
            )
            .append_separator()
            .append_item(
                ID_CLOSE_WINDOW,
                "&Закрыть окно\tCtrl+W",
                "Закрыть окно (при правках спросит подтверждение)",
            )
            .append_item(ID_EXIT, "&Выход\tCtrl+Q", "Выйти из программы")
            .build();

        // --- Правка (Edit): undo/redo, буфер обмена, транспонирование ---
        let edit_menu = Menu::builder()
            .append_item(ID_UNDO, "&Отменить\tCtrl+Z", "Отменить последнюю правку")
            .append_item(ID_REDO, "&Повторить\tCtrl+Y", "Вернуть отменённую правку")
            .append_separator()
            .append_item(ID_CUT, "&Вырезать\tCtrl+X", "Вырезать аккорд под курсором")
            .append_item(ID_COPY, "&Копировать\tCtrl+C", "Скопировать аккорд под курсором")
            .append_item(ID_PASTE, "В&ставить\tCtrl+V", "Вставить аккорд из буфера")
            .append_separator()
            .append_item(
                ID_TRANSPOSE,
                "&Транспонировать…\tCtrl+T",
                "Транспонировать всю цифровку",
            )
            .build();

        // --- Вставка (Insert): аккорд, правка, метка части, N.C., бас ---
        let section_menu = Menu::builder()
            .append_item(ID_SM_A, "Часть A\tCtrl+Shift+A", "Метка «Часть A»")
            .append_item(ID_SM_B, "Часть B\tCtrl+Shift+B", "Метка «Часть B»")
            .append_item(ID_SM_C, "Часть C\tCtrl+Shift+C", "Метка «Часть C»")
            .append_item(ID_SM_D, "Часть D\tCtrl+Shift+D", "Метка «Часть D»")
            .append_separator()
            .append_item(ID_SM_V, "Куплет\tCtrl+Shift+V", "Метка «Куплет»")
            .append_item(ID_SM_I, "Вступление\tCtrl+Shift+I", "Метка «Вступление»")
            .append_item(ID_SM_S, "Сеньо", "Метка «Сеньо» (без хоткея)")
            .append_item(ID_SM_Q, "Кода\tCtrl+Shift+Q", "Метка «Кода»")
            .build();
        let insert_menu = Menu::builder()
            .append_item(
                ID_INS_CHORD,
                "Добавить &аккорд…\tCtrl+Return",
                "Вставить аккорд в текущий такт",
            )
            .append_item(
                ID_EDIT_CHORD,
                "&Изменить аккорд…\tF2",
                "Перезаписать аккорд под курсором",
            )
            .append_separator()
            .build();
        insert_menu.append_submenu(
            section_menu,
            "&Метка части",
            "Репетиционные метки (Ctrl+Shift+буква)",
        );
        insert_menu.append(
            ID_INS_VOLTA,
            "&Вольта / Окончание\tV",
            "Вольта/повтор: [ — начало, ] — конец, V — на первом такте окончания 1",
            ItemKind::Normal,
        );
        insert_menu.append(
            ID_INS_NC,
            "&Без аккорда (N.C.)",
            "Переключить N.C. на текущем такте (клавиша N)",
            ItemKind::Normal,
        );
        insert_menu.append(
            ID_INS_BASS,
            "&Басовая нота…",
            "Слэш-бас к аккорду под курсором (например, E → C/E)",
            ItemKind::Normal,
        );

        // --- Песня: озвучивание, навигация, переход к такту по номеру ---
        let song_menu = Menu::builder()
            .append_item(ID_SPEAK, "Озвучить &такт\tF5", "Прочитать текущий такт")
            .append_item(
                ID_SPEAK_ALL,
                "Озвучить &всю цифровку\tF6",
                "Прочитать цифровку целиком",
            )
            .append_separator()
            // Простые стрелки идут через акселераторы меню (slice 11): голые
            // стрелки до окна не доходили (msg 1589) — а пункты меню, как F5
            // и Home, доходят всегда. Шаг по аккордам и пустым тактам (←/→)
            // и по тактам (Ctrl+←/→).
            .append_item(
                ID_NAV_CHORD_LEFT,
                "← к аккорду\tLeft",
                "На предыдущий аккорд (нет — на пустой такт)",
            )
            .append_item(
                ID_NAV_CHORD_RIGHT,
                "→ к аккорду\tRight",
                "На следующий аккорд (нет — на пустой такт)",
            )
            .append_item(
                ID_NAV_MEASURE_LEFT,
                "Ctrl+← по такту\tCtrl+Left",
                "Предыдущий такт",
            )
            .append_item(
                ID_NAV_MEASURE_RIGHT,
                "Ctrl+→ по такту\tCtrl+Right",
                "Следующий такт",
            )
            .append_separator()
            .append_item(ID_GOTO_START, "В &начало\tHome", "Первый такт")
            .append_item(ID_GOTO_END, "В &конец\tEnd", "Последний такт")
            .append_item(
                ID_GOTO_MEASURE,
                "Перейти к &такту…\tCtrl+F",
                "Перейти к такту по номеру",
            )
            .build();

        // --- Настройки: свойства цифровки (Ctrl+P) ---
        let settings_menu = Menu::builder()
            .append_item(
                ID_PROJ_SETTINGS,
                "Настройки &цифровки…\tCtrl+P",
                "Изменить название, композитора, темп, тональность, размер, стиль",
            )
            .build();

        let help_menu = Menu::builder()
            .append_item(
                ID_HELP,
                "Клавиатурные &сокращения\tF1",
                "Все горячие клавиши программы",
            )
            .append_separator()
            .append_item(ID_ABOUT, "О &программе", "Информация о сборке")
            .build();

        let menu_bar = MenuBar::builder()
            .append(file_menu, "&Файл")
            .append(edit_menu, "&Правка")
            .append(insert_menu, "&Вставка")
            .append(song_menu, "&Песня")
            .append(settings_menu, "&Настройки")
            .append(help_menu, "&Справка")
            .build();
        frame.set_menu_bar(menu_bar);

        StatusBar::builder(&frame)
            .with_fields_count(1)
            .add_initial_text(
                0,
                "irealstudio (Rust). Ctrl+N — новая, Ctrl+O — открыть, Ctrl+S — сохранить, Ctrl+Shift+S — сохранить как, Ctrl+E — экспорт, Ctrl+P — настройки. ←/→ — по аккордам и пустым тактам, Ctrl+←/→ — по тактам, Alt+стрелки — по секциям. Ctrl+Enter — аккорд, F2 — правка, Del — удалить, Ctrl+Z/Y — отмена/повтор. Вольта: [ — начало, ] — конец, V — окончание 1. Ctrl+W — закрыть окно.",
            )
            .build();

        // --- Панель тактов (рисованная, без a11y-контролов) ---
        let (grid_panel, grid_state) = make_grid(&frame, &doc.borrow());

        let root = BoxSizer::builder(Orientation::Vertical).build();
        root.add(&grid_panel, 1, SizerFlag::Expand | SizerFlag::All, 0);
        frame.set_sizer(root, true);

        // Заголовок окна из текущего документа (дальше его обновляют открытие,
        // сохранение и правки — «звёздочка» = несохранённые изменения).
        {
            let d = doc.borrow();
            frame.set_title(&window_title(&d));
        }

        // --- События меню ---
        let doc_menu = doc.clone();
        let spk_menu = speaker.clone();
        let state_menu = grid_state.clone();
        let frame_menu = frame.clone();
        let panel_menu = grid_panel.clone();
        let current_menu = current_file.clone();
        frame.on_menu_selected(move |event| match event.get_id() {
            ID_NEW => {
                // Грязный документ? — спросить, как python new_project (slice 8):
                // Сохранить (в текущий файл или «Сохранить как»; отмена/ошибка
                // сохранения отменяет создание новой), Не сохранять — продолжить,
                // Отмена — ничего не делать. Заметь: «Не сохранять» ещё НЕ стирает
                // правки — документ заменяется только когда новая цифровка создана
                // (диалог подтверждён), как в python.
                let proceed = {
                    let dirty = doc_menu.borrow().dirty;
                    if dirty {
                        let title = doc_menu.borrow().cp.title.clone();
                        let message = format!(
                            "«{title}» содержит несохранённые изменения.\n\n\
                             Сохранить перед созданием новой цифровки?"
                        );
                        match ask_unsaved(&frame_menu, &message) {
                            UnsavedChoice::Save => save_current_or_as(
                                &doc_menu,
                                &spk_menu,
                                &current_menu,
                                &frame_menu,
                            ),
                            UnsavedChoice::Discard => true,
                            UnsavedChoice::Cancel => false,
                        }
                    } else {
                        true
                    }
                };
                if proceed {
                    // Модальная форма (wxDialog). None — пользователь нажал Отмена.
                    if let Some(spec) = show_new_chart_dialog(&frame_menu) {
                        // Новая цифровка не связана с файлом — как python new_project:
                        // self._current_file = None (дальше Ctrl+S предложит «Сохранить как»).
                        *current_menu.borrow_mut() = None;
                        let mut d = doc_menu.borrow_mut();
                        *d = Doc::new_chart(&spec);
                        let dref = &*d;
                        sync_grid(dref, &state_menu, &panel_menu);
                        // Как python new_project: озвучить «Новая цифровка: <название>».
                        let spk = spk_menu.borrow();
                        spk.speak(&format!("Новая цифровка: {}", spec.title));
                        frame_menu.set_status_text(
                            &format!("Такт {} из {}", dref.cursor, dref.last_measure()),
                            0,
                        );
                    }
                    refresh_title(&doc_menu, &frame_menu);
                }
            }
            ID_OPEN => {
                if let Some(path) = pick_open_path(&frame_menu) {
                    let res = fs::read_to_string(&path)
                        .map_err(|e| e.to_string())
                        .and_then(|json| Doc::from_json(&json));
                    match res {
                        Ok(loaded) => install_loaded(
                            loaded,
                            path,
                            &doc_menu,
                            &spk_menu,
                            &state_menu,
                            &panel_menu,
                            &current_menu,
                            &frame_menu,
                        ),
                        Err(e) => {
                            spk_menu
                                .borrow()
                                .speak(&format!("Не удалось открыть: {e}"));
                        }
                    }
                }
            }
            ID_SAVE => {
                // Сохранить в текущий файл, а если его нет — «Сохранить как».
                // Возврат (успех/неудача) сейчас не важен — результат озвучен.
                let _ = save_current_or_as(&doc_menu, &spk_menu, &current_menu, &frame_menu);
            }
            ID_SAVE_AS => {
                save_as_progression(&doc_menu, &spk_menu, &current_menu, &frame_menu);
            }
            ID_EXPORT => {
                export_progression(&doc_menu, &spk_menu, &current_menu, &frame_menu);
            }
            ID_PROJ_SETTINGS => {
                // Дефолт формы — текущие поля цифровки (как python defaults=…).
                let defaults = {
                    let d = doc_menu.borrow();
                    ProjectSettings::from_cp(&d.cp)
                };
                if let Some(s) = show_project_settings_dialog(&frame_menu, &defaults) {
                    let msg = {
                        let mut d = doc_menu.borrow_mut();
                        d.apply_settings(&s)
                    };
                    commit_edit(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
                }
            }
            // --- Правка / Вставка (slice 5) ---
            ID_UNDO => {
                let msg = {
                    let mut d = doc_menu.borrow_mut();
                    d.undo()
                };
                commit_edit(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
            }
            ID_REDO => {
                let msg = {
                    let mut d = doc_menu.borrow_mut();
                    d.redo()
                };
                commit_edit(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
            }
            ID_COPY => {
                let msg = {
                    let mut d = doc_menu.borrow_mut();
                    d.copy_chord()
                };
                commit_edit(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
            }
            ID_CUT => {
                let msg = {
                    let mut d = doc_menu.borrow_mut();
                    d.cut_chord()
                };
                commit_edit(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
            }
            ID_PASTE => {
                let msg = {
                    let mut d = doc_menu.borrow_mut();
                    d.paste_chord()
                };
                commit_edit(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
            }
            ID_TRANSPOSE => {
                // Спин -11..11 как python transpose_dialog; 0 и ±12 — молчание.
                if let Some(n) = modal_spin(
                    &frame_menu,
                    "Транспонировать",
                    "На сколько полутонов:",
                    -11,
                    11,
                    0,
                ) {
                    let msg = {
                        let mut d = doc_menu.borrow_mut();
                        d.transpose(n)
                    };
                    commit_edit(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
                }
            }
            ID_INS_CHORD => {
                // Дефолт поля — аккорд под курсором, иначе C (как python).
                let initial = {
                    let d = doc_menu.borrow();
                    d.chord_under_cursor()
                        .map(|(name, _bass)| name)
                        .unwrap_or_else(|| "C".to_string())
                };
                if let Some(name) = modal_text(&frame_menu, "Добавить аккорд", "Аккорд:", &initial) {
                    let msg = {
                        let mut d = doc_menu.borrow_mut();
                        d.insert_chord(&name, "")
                    };
                    commit_edit(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
                }
            }
            ID_EDIT_CHORD => {
                let default = {
                    let d = doc_menu.borrow();
                    d.chord_under_cursor()
                };
                match default {
                    None => {
                        // Правки нет — как python: «No chord to edit».
                        spk_menu.borrow().speak("Нет аккорда для редактирования");
                    }
                    Some((name, _bass)) => {
                        if let Some(new_name) =
                            modal_text(&frame_menu, "Изменить аккорд", "Аккорд:", &name)
                        {
                            let msg = {
                                let mut d = doc_menu.borrow_mut();
                                d.edit_chord(&new_name)
                            };
                            commit_edit(
                                &msg,
                                &doc_menu,
                                &spk_menu,
                                &state_menu,
                                &panel_menu,
                                &frame_menu,
                            );
                        }
                    }
                }
            }
            ID_INS_NC => {
                let msg = {
                    let mut d = doc_menu.borrow_mut();
                    d.toggle_no_chord()
                };
                commit_edit(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
            }
            ID_INS_BASS => {
                if let Some(note) = modal_text(&frame_menu, "Басовая нота", "Нота (например, E):", "")
                {
                    let msg = {
                        let mut d = doc_menu.borrow_mut();
                        d.add_bass_note(&note)
                    };
                    commit_edit(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
                }
            }
            ID_INS_VOLTA => {
                let msg = {
                    let mut d = doc_menu.borrow_mut();
                    d.add_volta()
                };
                commit_edit(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
            }
            // Метки частей — Ctrl+Shift+буква (a/b/c/d/v/i/s/q).
            ID_SM_A => add_section_mark_menu('a', &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu),
            ID_SM_B => add_section_mark_menu('b', &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu),
            ID_SM_C => add_section_mark_menu('c', &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu),
            ID_SM_D => add_section_mark_menu('d', &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu),
            ID_SM_V => add_section_mark_menu('v', &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu),
            ID_SM_I => add_section_mark_menu('i', &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu),
            ID_SM_S => add_section_mark_menu('s', &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu),
            ID_SM_Q => add_section_mark_menu('q', &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu),
            ID_SPEAK => {
                let d = doc_menu.borrow();
                let spk = spk_menu.borrow();
                spk.speak(&d.announce_current());
            }
            ID_SPEAK_ALL => {
                let d = doc_menu.borrow();
                let spk = spk_menu.borrow();
                spk.speak(&d.announce_song());
            }
            // Шаг по аккордам/тактам (акселераторы ← / → / Ctrl+← / Ctrl+→,
            // slice 11). Озвучка как при хоткее: сменился такт — целиком,
            // шаг внутри такта — «такт N, доля M, аккорд».
            ID_NAV_CHORD_LEFT => {
                let msg = {
                    let mut d = doc_menu.borrow_mut();
                    nav_chord_step(&mut d, true)
                };
                apply_navigation(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
            }
            ID_NAV_CHORD_RIGHT => {
                let msg = {
                    let mut d = doc_menu.borrow_mut();
                    nav_chord_step(&mut d, false)
                };
                apply_navigation(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
            }
            ID_NAV_MEASURE_LEFT => {
                let msg = {
                    let mut d = doc_menu.borrow_mut();
                    nav_measure_step(&mut d, true)
                };
                apply_navigation(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
            }
            ID_NAV_MEASURE_RIGHT => {
                let msg = {
                    let mut d = doc_menu.borrow_mut();
                    nav_measure_step(&mut d, false)
                };
                apply_navigation(&msg, &doc_menu, &spk_menu, &state_menu, &panel_menu, &frame_menu);
            }
            ID_GOTO_START => {
                let mut d = doc_menu.borrow_mut();
                d.cursor = 1;
                d.beat = 1;
                let dref = &*d;
                sync_grid(dref, &state_menu, &panel_menu);
                announce(dref, &**spk_menu.borrow(), &frame_menu);
            }
            ID_GOTO_END => {
                let mut d = doc_menu.borrow_mut();
                d.cursor = d.last_measure();
                d.beat = 1;
                let dref = &*d;
                sync_grid(dref, &state_menu, &panel_menu);
                announce(dref, &**spk_menu.borrow(), &frame_menu);
            }
            ID_GOTO_MEASURE => {
                // Переход к такту по номеру — как python navigate_to_measure.
                let (cur, last) = {
                    let d = doc_menu.borrow();
                    (d.cursor, d.last_measure())
                };
                let target = modal_spin(
                    &frame_menu,
                    "Перейти к такту",
                    &format!("Номер такта (1–{last}):"),
                    1,
                    last.max(1),
                    cur.max(1).min(last.max(1)),
                );
                if let Some(target) = target {
                    let mut d = doc_menu.borrow_mut();
                    d.cursor = target.max(1).min(d.last_measure());
                    d.beat = 1;
                    let dref = &*d;
                    sync_grid(dref, &state_menu, &panel_menu);
                    announce(dref, &**spk_menu.borrow(), &frame_menu);
                }
            }
            ID_HELP => {
                // «Клавиатурные сокращения» (F1 и Справка → пункт меню).
                show_help_dialog(&frame_menu);
            }
            ID_ABOUT => {
                frame_menu.set_status_text(
                    "irealstudio (Rust) — wxDragon 0.9.21 / wxWidgets 3.3.3",
                    0,
                )
            }
            // «Закрыть окно» (Ctrl+W), «Выход» (Ctrl+Q) идут через то же
            // закрытие окна, что X / Alt+F4 (python `_on_quit` →
            // `self._frame.Close()` без force): EVT_CLOSE попадает в on_close
            // ниже, где стоит вопрос о несохранённых правках и можно отменить
            // (veto). force=true этого бы не позволил.
            ID_CLOSE_WINDOW => frame_menu.close(false),
            ID_EXIT => frame_menu.close(false),
            _ => {}
        });

        // --- Хоткеи: навигация по тактам. Обработчик вешаем и на frame, и на
        // панель — у кого фокус, тот и получает клавиши (панель без a11y).
        // Клавиатура приходит как WindowEventData::Keyboard (см. virtual_list).
        {
            let doc_k = doc.clone();
            let spk_k = speaker.clone();
            let st_k = grid_state.clone();
            let f_k = frame.clone();
            let p_k = grid_panel.clone();
            frame.on_key_down(move |event| {
                handle_key(event, &doc_k, &spk_k, &st_k, &f_k, &p_k);
            });
        }
        {
            let doc_k = doc.clone();
            let spk_k = speaker.clone();
            let st_k = grid_state.clone();
            let f_k = frame.clone();
            let p_k = grid_panel.clone();
            grid_panel.on_key_down(move |event| {
                handle_key(event, &doc_k, &spk_k, &st_k, &f_k, &p_k);
            });
        }

        // --- Закрытие окна: подтверждение несохранённых изменений (slice 8) ---
        // Калька python `_on_close_window` (EVT_CLOSE): сюда приходит и крестик /
        // Alt+F4, и «Выход»/Ctrl+Q (меню выше шлёт frame.close(false)). Если есть
        // несохранённые правки — модальный вопрос Сохранить/Не сохранять/Отмена;
        // «Отмена» или неудача сохранения — veto (окно остаётся). Флаг `closing`
        // глушит повторный вопрос, когда после одобрения приходит ещё одно
        // close-событие (например от force-закрытия).
        let closing = Rc::new(Cell::new(false));
        {
            let doc_c = doc.clone();
            let spk_c = speaker.clone();
            let cf_c = current_file.clone();
            let f_c = frame.clone();
            let closing_c = closing.clone();
            frame.on_close(move |event| {
                if closing_c.get() {
                    event.skip(true);
                    return;
                }
                let (dirty, title) = {
                    let d = doc_c.borrow();
                    (d.dirty, d.cp.title.clone())
                };
                if dirty {
                    let message = format!(
                        "«{title}» содержит несохранённые изменения.\n\nСохранить перед закрытием?"
                    );
                    match ask_unsaved(&f_c, &message) {
                        UnsavedChoice::Save => {
                            // Ошибка/отмена сохранения (save_as) — закрывать нельзя.
                            if !save_current_or_as(&doc_c, &spk_c, &cf_c, &f_c) {
                                veto_close(&event);
                                return;
                            }
                        }
                        // «Не сохранять» — как python: ничего не сохраняем и закрываем.
                        UnsavedChoice::Discard => {}
                        UnsavedChoice::Cancel => {
                            veto_close(&event);
                            return;
                        }
                    }
                }
                closing_c.set(true);
                event.skip(true);
            });
        }

        frame.centre();
        frame.show(true);
    });
}
