# irealwx — переписывание irealstudio на Rust

Статус: **этап 1 (порт чистого ядра) закрыт, идёт этап 2 (wxDragon GUI)**. Ядро: irealb-кодек сверен с python-эталоном; гармония (`core/src/chords/`) полностью портирована — распознавание аккордов, модель, ireal-перевод, транспонирование, вокализация в MIDI, `ChordProgression` (секции, вольты/повторы, виртуальная навигация, N.C., транспонирование прогрессии), **экспорт-грамматика** (`core/src/chords/export.rs`), **озвучка аккордов по-русски** (`core/src/chords/spoken.rs`) и **JSON-персистентность** (`core/src/chords/persist.rs`, 6 сценариев байтово против python, без serde). GUI: **slice 1 (ui-shell) готов к сборке** — окно + нативное альт-меню + рисованная панель тактов (`on_paint`) + навигация стрелками с озвучкой через NVDA ControllerClient; чистая логика документа в `ui/src/lib.rs` (тесты в контейнере), wxDragon-оболочка в `ui/src/main.rs`. Целевая сборка — **Windows** (там NVDA читает нативное Win32-меню), но сам wxDragon кроссплатформенный (Windows/macOS/Linux-GTK), окно пишется обычным wx-кодом.

## Зачем

irealstudio — ~13k строк wxPython-приложения Дениза для игры цифровок (Mille Bornes-стайл аккордовые сетки, доступность для незрячих). Переносим на Rust: один exe без Python, нативный wx-менюбар, скринридер-речь.

## Раскладка по крейтам — чинить каждый слой отдельно

| Крейт | Роль | Аналог в irealstudio | Где собирается |
|---|---|---|---|
| `core` | Чистая логика: irealb-кодек, гармония, модель | `irealb.py`, `chords.py` | любой хост |
| `audio` | Метроном/клик (cpal) | `sound.py` | Windows |
| `midi` | MIDI-выход (midir) | `midi_handler.py` | Windows |
| `speech` | Речь в скринридер (NVDA ControllerClient) | `accessible_output3` в `main.py` | Windows (no-op иначе) |
| `ui` | wxDragon GUI: окно, альт-меню, панель тактов, форма цифровки | `main.py`, `app_menu.py`, `dialogs.py`, `app_keys.py` | Windows — целевая (wxDragon кроссплатформенный: Win/macOS/Linux-GTK) |

`cargo test` гоняет default-members (core/audio/midi/speech) на любом хосте — без wx.
Крейт `ui` тянет wxDragon; сборка цели — **Windows** (`cargo build -p irealwx_ui`).
wxDragon не «только Windows»: это кроссплатформенная обёртка wxWidgets
(официально Windows/macOS/Linux-GTK), и окно в `ui/src/main.rs` — обычный
wx-код без Win32-специфики: под GTK/Cocoa он соберётся, поменяется лишь слой
речи (в `speech` под не-Windows no-op). В `Cargo.toml` зависимость wxdragon
стоит под `cfg(windows)` не по принципу, а чтобы контейнерные тесты чистых
крейтов не пересобирали wxWidgets (CMake, 10–30 мин) на каждый прогон.
Собранный exe сам находит `nvdaControllerClient.dll` (рядом с exe / в каталогах
NVDA / в PATH) — речь работает без доустановки.

## Slice 1 (ui-shell) — что собрать и проверить на Windows

Ветка `rust`, папка `workspace/irealwx/`. В **«x64 Native Tools Command
Prompt for VS 2022»**:

```sh
cargo build -p irealwx_ui
target\debug\irealwx_ui.exe
```

Ожидаемое поведение (демо — Rhythm Changes, 12 тактов, секции *A/*B):

- **Alt** открывает нативное меню: **Файл** (Новая цифровка Ctrl+N / Выход),
  **Песня** (Озвучить такт F5 / Озвучить всю цифровку F6 / В начало / В конец),
  **Справка** (О программе). NVDA читает пункты и их help.
- **Стрелки ←/→** — по тактам, **Home/End** — первый/последний такт,
  **Alt+←/Alt+→** — прыжок по секциям; каждый переход озвучивается
  («такт 3, си-бемоль минор септ, …») и подсвечивает ячейку на сетке.
- Панель тактов рисуется в `on_paint` (визуально), в дерево a11y не попадает.

Если NVDA не запущена — программа не падает, речь просто молчит (статус-строка
показывает такт). wxDragon впервые собирает wxWidgets 3.3.3 долго (10–30 мин,
нужны Ninja/CMake) — это один раз.


## Модель доступности (решение Дениза)

- Главное окно без a11y-контролов; весь ввод через альт-меню (нативный HMENU) + хоткеи.
- Аккордовая сетка рисуется в `on_paint` — только видна, в дерево доступности не попадает.
- Навигация стрелками по тактам озвучивается через `speech` (не a11y-событиями).
- Обычные wx-контролы — только в форме создания цифровки.

## Сверка порта с python-эталоном

`core` держит golden-тесты против `irealstudio/` (python-эталона); любое
расхождение порта с эталоном — красный тест:

- `golden_songs.rs` — decode + обратный encode irealb (2 реальные песни iReal Pro).
- `chords_golden.rs` — 345 векторов: распознавание, ireal-перевод, транспонирование,
  вокализация, ноты тональностей.
- `progression_golden.rs` — 5 сценариев `ChordProgression` (volta/plain/replace/
  transpose): структура + свип навигации по 22 тактам + 4 экспорт-URL
  (`to_ireal_url`/`to_irealb_url`, кодированный и сырой) побайтово против
  python (`pyrealpro.py` + `irealb.py`).
- `spoken_golden.rs` — 485 кейсов озвучки аккордов: `chord_name_to_spoken`
  против chords.py под ru-каталогом irealstudio (ровно то, что слышит
  пользователь). ru-переводы фраз вендорены в `core/src/chords/spoken_i18n.rs`.
- `json_golden.rs` — 6 сценариев `to_json`/`from_json` побайтово против
  chords.py (`json.dumps(indent=2, ensure_ascii)`): кириллица/«ёлочки»,
  emoji (суррогатная пара), управляющие символы, пустые контейнеры, вольты,
  транспонирование (мутация key), многотактовый порядок, дубли N.C.
  Парсер и принтер — ручные (`core/src/chords/persist.rs`), без serde.

Генераторы: `core/tests/gen_*_golden.py` (запуск из папки тестов при эталоне
`irealstudio/` рядом с workspace).

## Как тестировать (контейнер без C-компилятора)

Rust-тулчейн лежит в `workspace/.rustup`/`workspace/.cargo`. Сборка под
`x86_64-unknown-linux-musl` линкуется через lld-shim из rust-тулчейна:

```sh
export RUSTUP_HOME=$PWD/.rustup CARGO_HOME=$PWD/.cargo PATH=$PWD/.cargo/bin:$PATH
TC=$(ls -d .rustup/toolchains/*/ | head -1)
export CARGO_TARGET_DIR=$PWD/irealwx/target
RUSTFLAGS="-C linker=${TC}lib/rustlib/x86_64-unknown-linux-gnu/bin/gcc-ld/ld.lld" \
  cargo test --target x86_64-unknown-linux-musl
```
