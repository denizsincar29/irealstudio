# irealwx — переписывание irealstudio на Rust

Статус: **этап 1 — порт чистого ядра**: irealb-кодек готов и сверен с python-эталоном; гармония (`core/src/chords/`) полностью портирована — распознавание аккордов, модель, ireal-перевод, транспонирование, вокализация в MIDI и `ChordProgression` (секции, вольты/повторы, виртуальная навигация, N.C., транспонирование прогрессии). Дальше: экспорт-грамматика pyrealpro (irealbook/ireal URL) и слой i18n. GUI/wxDragon — этап 2.

## Зачем

irealstudio — ~13k строк wxPython-приложения Дениза для игры цифровок (Mille Bornes-стайл аккордовые сетки, доступность для незрячих). Переносим на Rust: один exe без Python, нативный wx-менюбар, скринридер-речь.

## Раскладка по крейтам — чинить каждый слой отдельно

| Крейт | Роль | Аналог в irealstudio | Где собирается |
|---|---|---|---|
| `core` | Чистая логика: irealb-кодек, гармония, модель | `irealb.py`, `chords.py` | любой хост |
| `audio` | Метроном/клик (cpal) | `sound.py` | Windows |
| `midi` | MIDI-выход (midir) | `midi_handler.py` | Windows |
| `speech` | Речь в скринридер (NVDA ControllerClient) | `accessible_output3` в `main.py` | Windows (no-op иначе) |
| `ui` | wxDragon GUI: окно, альт-меню, панель тактов, форма цифровки | `main.py`, `app_menu.py`, `dialogs.py`, `app_keys.py` | Windows (wxDragon сам CMake-собирает wxWidgets) |

`cargo test` гоняет default-members (core/audio/midi/speech) на любом хосте.
`ui` тянет wxDragon → собирается на Windows: `cargo build -p irealwx_ui`.

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
  transpose): структура + свип навигации по 22 тактам.

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
