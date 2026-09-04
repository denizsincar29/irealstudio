// irealwx — этап 2: живое ядро в окне wxDragon (Windows).
//
// А11y-модель (решение Дениза): главное окно БЕЗ a11y-контролов. Весь ввод —
// через альт-меню (нативный HMENU) и хоткеи; панель тактов рисуется в on_paint
// (только видна, в дерево доступности не попадает); навигация озвучивается
// через irealwx_speech (NVDA ControllerClient) и дублируется в статус-строку.
// Обычные wx-контролы — только в формах: «Новая цифровка» (Ctrl+N) и файловые
// диалоги открыть/сохранить .ips (Ctrl+O / Ctrl+S).
//
// Сборка на любом хосте с тулчейном wxDragon (см. README): cargo build -p irealwx_ui.
// Целевая платформа проекта — Windows (NVDA); сам wx-код кроссплатформенный.
// Данные — Doc из lib.rs (демо-цифровка поверх ChordProgression core).

use std::cell::RefCell;
use std::fs;
use std::path::{Path, PathBuf};
use std::rc::Rc;

use wxdragon::dc::{AutoBufferedPaintDC, BrushStyle, PenStyle};
use wxdragon::event::WindowEventData;
use wxdragon::keycode::{WXK_END, WXK_HOME, WXK_LEFT, WXK_RIGHT};
use wxdragon::prelude::*;

use irealwx_speech::{default_speak, Speak};
use irealwx_ui::{BPM_MAX, BPM_MIN, Doc, NewChart};

// --- ID пунктов меню (кроме ID_EXIT/ID_ABOUT из прелюда) ---
const ID_NEW: i32 = 1001;
const ID_OPEN: i32 = 1002;
const ID_SAVE: i32 = 1003;
const ID_SAVE_AS: i32 = 1004;
const ID_SPEAK: i32 = 2001;
const ID_SPEAK_ALL: i32 = 2002;
const ID_GOTO_START: i32 = 2003;
const ID_GOTO_END: i32 = 2004;

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
    let cw = (w / cols).max(1);
    let row_h = 64;

    for (idx, text) in st.cells.iter().enumerate() {
        let measure = idx as i32 + 1;
        let r = idx / cols;
        let c = idx % cols;
        let x = c * cw;
        let y = r * row_h;
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
                spk.borrow().speak(&format!("Сохранено: {name}"));
                frame.set_status_text(&format!("Сохранено: {name}"), 0);
            }
            Err(e) => {
                spk.borrow().speak(&format!("Не удалось сохранить: {e}"));
            }
        }
    }
}

// --- Форма «Новая цифровка» (Ctrl+N) ---
//
// Калька python `_NewProjectDlg` (dialogs.py:240) в реальный wxDialog: NVDA
// объявляет его как диалог, табы идут по порядку создания контролов (как в
// wxPython-версии). Поля формы собирают `NewChart`, дальше его строит
// `Doc::new_chart` в lib (тот же путь, что python `new_project`).

/// 12 хроматических корней — порядок python `KEY_ROOT_NOTES` (dialogs.py:27).
const KEY_ROOTS: [&str; 12] = [
    "C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B",
];

/// iReal-имя минора по корню — python `_MINOR_KEY_MAP` (dialogs.py:31):
/// часть корней в миноре пишется с диезами (Db → C#-, Gb → F#-, …).
const ROOT_MINOR: [(&str, &str); 12] = [
    ("C", "C-"),
    ("Db", "C#-"),
    ("D", "D-"),
    ("Eb", "Eb-"),
    ("E", "E-"),
    ("F", "F-"),
    ("Gb", "F#-"),
    ("G", "G-"),
    ("Ab", "G#-"),
    ("A", "A-"),
    ("Bb", "Bb-"),
    ("B", "B-"),
];

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
fn add_labeled_row<W: WxWidget>(col: &BoxSizer, panel: &Panel, label: &str, ctrl: &W) {
    let row = BoxSizer::builder(Orientation::Horizontal).build();
    let lab = StaticText::builder(panel).with_label(label).build();
    row.add(&lab, 0, SizerFlag::AlignCenterVertical | SizerFlag::Right, 8);
    row.add(ctrl, 1, SizerFlag::Expand | SizerFlag::AlignCenterVertical, 0);
    col.add_sizer(&row, 0, SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Top, 4);
}

/// iReal-ключ из корня и лада — как python `root_mode_to_key` (dialogs.py:54).
fn key_from_root_mode(root: &str, minor: bool) -> String {
    if minor {
        ROOT_MINOR
            .iter()
            .find(|(r, _)| *r == root)
            .map(|(_, k)| k.to_string())
            .unwrap_or_else(|| format!("{root}-"))
    } else {
        root.to_string()
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
    col.add_sizer(
        &buttons,
        0,
        SizerFlag::AlignRight | SizerFlag::Left | SizerFlag::Right | SizerFlag::Top | SizerFlag::Bottom,
        8,
    );

    panel.set_sizer(col, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer_and_fit(dialog_sizer, true);

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
        let ctrl = key.ctrl_down();
        let mut d = doc.borrow_mut();
        let mut changed = false;
        match code {
            WXK_LEFT if !alt && !ctrl => {
                d.go_left();
                changed = true;
            }
            WXK_RIGHT if !alt && !ctrl => {
                d.go_right();
                changed = true;
            }
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
                changed = true;
            }
            WXK_END => {
                d.cursor = d.last_measure();
                changed = true;
            }
            _ => {}
        }
        if changed {
            sync_grid(&d, state, panel);
            announce(&d, &*speaker.borrow(), frame);
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
            .with_title("irealstudio — Rust (форма Ctrl+N, открыть/сохранить .ips)")
            .with_size(Size::new(920, 640))
            .build();

        // --- Менюбар ---
        let file_menu = Menu::builder()
            .append_item(ID_NEW, "&Новая цифровка…\tCtrl+N", "Создать новую цифровку")
            .append_separator()
            .append_item(ID_OPEN, "&Открыть…\tCtrl+O", "Открыть цифровку из файла .ips")
            .append_item(ID_SAVE, "&Сохранить\tCtrl+S", "Сохранить цифровку в файл .ips")
            .append_item(ID_SAVE_AS, "Сохранить &как…", "Сохранить цифровку в новый файл")
            .append_separator()
            .append_item(ID_EXIT, "&Выход", "Закрыть программу")
            .build();

        let song_menu = Menu::builder()
            .append_item(ID_SPEAK, "Озвучить &такт\tF5", "Прочитать текущий такт")
            .append_item(
                ID_SPEAK_ALL,
                "Озвучить &всю цифровку\tF6",
                "Прочитать цифровку целиком",
            )
            .append_separator()
            .append_item(ID_GOTO_START, "В &начало\tHome", "Первый такт")
            .append_item(ID_GOTO_END, "В &конец\tEnd", "Последний такт")
            .build();

        let help_menu = Menu::builder()
            .append_item(ID_ABOUT, "О &программе", "Информация о сборке")
            .build();

        let menu_bar = MenuBar::builder()
            .append(file_menu, "&Файл")
            .append(song_menu, "&Песня")
            .append(help_menu, "&Справка")
            .build();
        frame.set_menu_bar(menu_bar);

        StatusBar::builder(&frame)
            .with_fields_count(1)
            .add_initial_text(
                0,
                "irealstudio (Rust). Ctrl+N — новая цифровка, Ctrl+O — открыть, Ctrl+S — сохранить. Стрелки — по тактам, Alt+стрелки — по секциям.",
            )
            .build();

        // --- Панель тактов (рисованная, без a11y-контролов) ---
        let (grid_panel, grid_state) = make_grid(&frame, &doc.borrow());

        let root = BoxSizer::builder(Orientation::Vertical).build();
        root.add(&grid_panel, 1, SizerFlag::Expand | SizerFlag::All, 0);
        frame.set_sizer(root, true);

        // --- События меню ---
        let doc_menu = doc.clone();
        let spk_menu = speaker.clone();
        let state_menu = grid_state.clone();
        let frame_menu = frame.clone();
        let panel_menu = grid_panel.clone();
        let current_menu = current_file.clone();
        frame.on_menu_selected(move |event| match event.get_id() {
            ID_NEW => {
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
                // Клонируем путь из Ref явно (у RefCell::Ref свой Clone —
                // голый .clone() склонировал бы обёртку, а не Option).
                let cur = {
                    let cf = current_menu.borrow();
                    (*cf).clone()
                };
                if let Some(path) = cur {
                    // Текущий файл есть — пишем прямо в него (как python save()).
                    let name = path
                        .file_name()
                        .map(|s| s.to_string_lossy().into_owned())
                        .unwrap_or_default();
                    let res = {
                        let d = doc_menu.borrow();
                        write_to_path(&path, &d)
                    };
                    match res {
                        Ok(()) => {
                            spk_menu.borrow().speak(&format!("Сохранено: {name}"));
                            frame_menu.set_status_text(&format!("Сохранено: {name}"), 0);
                        }
                        Err(e) => {
                            spk_menu
                                .borrow()
                                .speak(&format!("Не удалось сохранить: {e}"));
                        }
                    }
                } else {
                    // Файла ещё нет — как python save() → save_as().
                    save_as_progression(
                        &doc_menu,
                        &spk_menu,
                        &current_menu,
                        &frame_menu,
                    );
                }
            }
            ID_SAVE_AS => {
                save_as_progression(&doc_menu, &spk_menu, &current_menu, &frame_menu);
            }
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
            ID_GOTO_START => {
                let mut d = doc_menu.borrow_mut();
                d.cursor = 1;
                let dref = &*d;
                sync_grid(dref, &state_menu, &panel_menu);
                announce(dref, &*spk_menu.borrow(), &frame_menu);
            }
            ID_GOTO_END => {
                let mut d = doc_menu.borrow_mut();
                d.cursor = d.last_measure();
                let dref = &*d;
                sync_grid(dref, &state_menu, &panel_menu);
                announce(dref, &*spk_menu.borrow(), &frame_menu);
            }
            ID_ABOUT => {
                frame_menu.set_status_text(
                    "irealstudio (Rust) — wxDragon 0.9.21 / wxWidgets 3.3.3",
                    0,
                )
            }
            ID_EXIT => frame_menu.close(true),
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

        frame.centre();
        frame.show(true);
    });
}
