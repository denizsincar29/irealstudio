// irealwx — этап 2, slice 1: живое ядро в окне wxDragon (Windows).
//
// А11y-модель (решение Дениза): главное окно БЕЗ a11y-контролов. Весь ввод —
// через альт-меню (нативный HMENU) и хоткеи; панель тактов рисуется в on_paint
// (только видна, в дерево доступности не попадает); навигация озвучивается
// через irealwx_speech (NVDA ControllerClient) и дублируется в статус-строку.
//
// Сборка на любом хосте с тулчейном wxDragon (см. README): cargo build -p irealwx_ui.
// Целевая платформа проекта — Windows (NVDA); сам wx-код кроссплатформенный.
// Данные — Doc из lib.rs (демо-цифровка поверх ChordProgression core).

use std::cell::RefCell;
use std::rc::Rc;

use wxdragon::dc::{AutoBufferedPaintDC, BrushStyle, PenStyle};
use wxdragon::event::WindowEventData;
use wxdragon::keycode::{WXK_END, WXK_HOME, WXK_LEFT, WXK_RIGHT};
use wxdragon::prelude::*;

use irealwx_speech::{default_speak, Speak};
use irealwx_ui::Doc;

// --- ID пунктов меню (кроме ID_EXIT/ID_ABOUT из прелюда) ---
const ID_NEW: i32 = 1001;
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
        // --- Документ и озвучка (общие для меню и клавиатуры) ---
        let doc: Rc<RefCell<Doc>> = Rc::new(RefCell::new(Doc::new_demo()));
        let speaker: Rc<RefCell<Box<dyn Speak>>> =
            Rc::new(RefCell::new(default_speak()));

        // --- Главное окно ---
        let frame = Frame::builder()
            .with_title("irealstudio — Rust (slice 1: окно, меню, панель тактов)")
            .with_size(Size::new(920, 640))
            .build();

        // --- Менюбар ---
        let file_menu = Menu::builder()
            .append_item(ID_NEW, "&Новая цифровка…\tCtrl+N", "Сбросить к демо")
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
                "irealstudio (Rust). Стрелки — по тактам, Home/End — края, Alt+стрелки — по секциям.",
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
        frame.on_menu_selected(move |event| match event.get_id() {
            ID_NEW => {
                let mut d = doc_menu.borrow_mut();
                *d = Doc::new_demo();
                let dref = &*d;
                sync_grid(dref, &state_menu, &panel_menu);
                announce(dref, &*spk_menu.borrow(), &frame_menu);
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
                    "irealstudio (Rust), slice 1 — wxDragon 0.9.21 / wxWidgets 3.3.3",
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
