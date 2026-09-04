//! iReal Pro «irealb» (new) format codec — Rust-порт модуля `irealb.py`
//! из irealstudio.
//!
//! Современный формат шеринга iReal Pro выглядит как `irealb://...` и несёт
//! метаданные, которых нет в классическом читаемом `irealbook://`: BPM
//! (`actual_tempo`), переопределение стиля (`actual_style`), число повторов
//! и опциональную тональность транспонирования (`actual_key`).
//!
//! Скрыты только сами аккорды, и это не шифрование: фиксированная обфускация
//! без ключа (магический префикс, три подмены токенов и сам-себе-обратная
//! перестановка байтов). Эталон реализации — `Data::iRealPro`
//! (https://github.com/sciurius/perl-Data-iRealPro); здесь — независимый,
//! без зависимостей порт. Поведение сверено с python-эталоном irealstudio
//! золотыми векторами в `tests/`.
//!
//! Раскладка payload'а `irealb://` (после percent-декодирования)::
//!
//! ```text
//! irealb://<song>===<song>===...===<PlaylistName>     (плейлист)
//! ```
//!
//! где песня — запись из 10 полей::
//!
//! ```text
//! <Title>=<Composer>=<a2>=<Style>=<Key>=<ActualKey>=<chords>=<ActualStyle>=<Tempo>=<Repeats>
//! ```
//!
//! `<chords>` начинается с магической строки `1r34LbKcu7`. Payload из одной
//! песни без имени плейлиста открывается в iReal Pro сразу; несколько песен
//! (или явное имя) предлагаются плейлистом.

use std::fmt;

/// Магический префикс obfuscated-аккордов.
pub const MAGIC: &str = "1r34LbKcu7";

/// Обфускация — симметричная перестановка блоками по 50 символов.
const HUSSLE_BLOCK: usize = 50;

/// Подмены токенов аккорд-данных (порядок важен!).
const ENC_SUBS: &[(&str, &str)] = &[
    ("   ", "XyQ"), // 3 пробела  -> XyQ
    (" |", "LZ"),   // пробел+бар -> LZ
    ("| x", "Kcl"), // бар+x      -> Kcl
];

/// Ошибка формата irealb.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IrealbError(pub String);

impl fmt::Display for IrealbError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for IrealbError {}

fn err<T>(msg: impl Into<String>) -> Result<T, IrealbError> {
    Err(IrealbError(msg.into()))
}

/// Применить симметричный байт-скрэмбл (используется и на encode, и на decode).
///
/// Строка обрабатывается сегментами по 50 символов; каждый сегмент выдаётся
/// как семь переставленных (частично развёрнутых) кусков. Перестановка —
/// собственная инверсия, поэтому функция одна на оба направления.
fn hussle(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(chars.len());
    let mut i = 0;
    while chars.len() - i > HUSSLE_BLOCK {
        let seg = &chars[i..i + HUSSLE_BLOCK];
        i += HUSSLE_BLOCK;
        if chars.len() - i < 2 {
            // Perl-эталон оставляет короткий остаток в конце нетронутым.
            out.extend(seg);
            continue;
        }
        out.extend(seg[45..50].iter().rev());
        out.extend(&seg[5..10]);
        out.extend(seg[26..40].iter().rev());
        out.extend(&seg[24..26]);
        out.extend(seg[10..24].iter().rev());
        out.extend(&seg[40..45]);
        out.extend(seg[0..5].iter().rev());
    }
    out.extend(chars[i..].iter());
    out
}

/// Закодировать читаемые аккорд-данные в скрытую форму (с магическим префиксом).
pub fn obfuscate(chord_data: &str) -> String {
    let mut t = chord_data.to_string();
    for (plain, coded) in ENC_SUBS {
        t = t.replace(plain, coded);
    }
    let mut out = String::with_capacity(MAGIC.len() + t.len());
    out.push_str(MAGIC);
    out.push_str(&hussle(&t));
    out
}

/// Восстановить читаемые аккорд-данные из обфусцированной строки.
pub fn deobfuscate(text: &str) -> Result<String, IrealbError> {
    if !text.starts_with(MAGIC) {
        return err(format!(
            "not an iRealPro obfuscated chord blob (missing magic prefix)"
        ));
    }
    let mut t = hussle(&text[MAGIC.len()..]);
    for (plain, coded) in ENC_SUBS {
        t = t.replace(coded, plain);
    }
    Ok(t)
}

// ---------------------------------------------------------------------------
// Percent-encode/decode (совместимо с urllib.quote / unquote)
// ---------------------------------------------------------------------------

/// Символы, которые остаются нетронутыми при кодировании.
/// urllib.parse.quote держит `~` всегда-safe отдельно от списка safe; python-модуль
/// irealb.py передаёт safe = `-_.A-Za-z*/'` (диапазоны не раскрываются), а `~` в него
/// не входит, но quote оставляет сырым. Поэтому здесь `~` тоже safe.
fn is_safe(b: u8) -> bool {
    b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.' | b'*' | b'/' | b'\'' | b'~')
}

/// Percent-кодирование UTF-8 строки; повторяет `url_encode` python-модуля
/// (quote(safe="-_.A-Za-z*/'") + всегда-safe `~`). Шестнадцатеричные цифры — заглавные.
pub fn url_encode(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for &b in text.as_bytes() {
        if is_safe(b) {
            out.push(b as char);
        } else {
            out.push('%');
            out.push_str(&format!("{b:02X}"));
        }
    }
    out
}

/// Percent-декодирование (аналог urllib.unquote; `+` НЕ превращается в пробел).
fn url_decode(text: &str) -> Result<String, IrealbError> {
    let bytes = text.as_bytes();
    let mut decoded: Vec<u8> = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        let b = bytes[i];
        if b == b'%' {
            if i + 2 >= bytes.len() {
                return err("bad percent-encoding: truncated escape");
            }
            let hi = (bytes[i + 1] as char).to_digit(16);
            let lo = (bytes[i + 2] as char).to_digit(16);
            match (hi, lo) {
                (Some(h), Some(l)) => {
                    decoded.push((h * 16 + l) as u8);
                    i += 3;
                }
                _ => return err("bad percent-encoding: invalid hex digit"),
            }
        } else {
            decoded.push(b);
            i += 1;
        }
    }
    String::from_utf8(decoded).map_err(|_| IrealbError("bad percent-encoding: invalid UTF-8".into()))
}

// ---------------------------------------------------------------------------
// Песня
// ---------------------------------------------------------------------------

/// Одна песня в новом формате iReal Pro.
///
/// `chords` хранит *читаемые* аккорд-данные; поля метаданных соответствуют
/// десяти `=`-полям формата.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Song {
    pub title: String,
    pub composer: String,
    pub a2: String,
    pub style: String,
    pub key: String,
    pub actual_key: String,
    pub chords: String,
    pub actual_style: String,
    pub tempo: i32,
    pub repeats: i32,
}

impl Song {
    /// Новая песня со значениями по умолчанию, как в python-конструкторе.
    pub fn new(title: impl Into<String>) -> Self {
        Song {
            title: title.into(),
            composer: "Unknown".into(),
            a2: String::new(),
            style: "Medium Swing".into(),
            key: "C".into(),
            actual_key: String::new(),
            chords: String::new(),
            actual_style: String::new(),
            tempo: 0,
            repeats: 0,
        }
    }

    /// Запись из десяти `=`-полей (аккорд-данные обфусцированы).
    pub fn to_field_record(&self) -> String {
        [
            self.title.clone(),
            self.composer.clone(),
            self.a2.clone(),
            self.style.clone(),
            self.key.clone(),
            self.actual_key.clone(),
            obfuscate(&self.chords),
            self.actual_style.clone(),
            self.tempo.to_string(),
            self.repeats.to_string(),
        ]
        .join("=")
    }
}

impl Default for Song {
    fn default() -> Self {
        Song::new("")
    }
}

// ---------------------------------------------------------------------------
// Кодирование
// ---------------------------------------------------------------------------

/// Payload одной песни (без имени плейлиста) для `irealb://`.
pub fn encode_song(song: &Song) -> String {
    song.to_field_record()
}

/// Полный URL `irealb://` из одной или нескольких песен.
///
/// Одна песня без *playlist_name* даёт payload, который открывается сразу;
/// всё остальное — как плейлист.
pub fn build_url(songs: &[Song], playlist_name: Option<&str>) -> String {
    let payload: Vec<String> = songs.iter().map(Song::to_field_record).collect();
    let mut joined = payload.join("===");
    if let Some(name) = playlist_name {
        if !name.is_empty() {
            joined.push_str("===");
            joined.push_str(name);
        }
    }
    let mut out = String::from("irealb://");
    out.push_str(&url_encode(&joined));
    out
}

// ---------------------------------------------------------------------------
// Декодирование
// ---------------------------------------------------------------------------

fn parse_int(field: &str) -> Result<i32, IrealbError> {
    if field.is_empty() {
        return Ok(0);
    }
    field
        .parse::<i32>()
        .map_err(|_| IrealbError(format!("bad iRealPro numeric field: '{field}'")))
}

/// Из десяти полей irealpro-записи.
fn song_from_irealpro_fields(fields: &[&str]) -> Result<Song, IrealbError> {
    if fields.len() != 10 {
        return err(format!(
            "bad iRealPro song record: expected 10 fields, got {}",
            fields.len()
        ));
    }
    let raw = fields[6];
    let mut song = Song {
        title: fields[0].to_string(),
        composer: fields[1].to_string(),
        a2: fields[2].to_string(),
        style: fields[3].to_string(),
        key: fields[4].to_string(),
        actual_key: fields[5].to_string(),
        chords: String::new(),
        actual_style: fields[7].to_string(),
        tempo: parse_int(fields[8])?,
        repeats: parse_int(fields[9])?,
    };
    song.chords = deobfuscate(raw)?;
    Ok(song)
}

/// Из шести полей классической irealbook-записи.
///
/// Классическая читаемая запись: `Title=Composer=Style=<a3>=Key=<chord data>`.
/// iReal Pro пишет запись как `...=Style=Key=n=<data>` — sentinel 'n' попадает
/// в слот *key*, его надо переставить обратно.
fn song_from_irealbook_fields(fields: &[&str]) -> Result<Song, IrealbError> {
    if fields.len() != 6 {
        return err(format!(
            "bad irealbook record: expected 6 fields, got {}",
            fields.len()
        ));
    }
    let (title, composer, style, a3, mut key, raw) = (
        fields[0],
        fields[1],
        fields[2],
        fields[3],
        fields[4],
        fields[5],
    );
    if key == "n" {
        key = a3;
    }
    Ok(Song {
        title: title.to_string(),
        composer: composer.to_string(),
        a2: String::new(),
        style: style.to_string(),
        key: key.to_string(),
        actual_key: String::new(),
        chords: raw.to_string(),
        actual_style: String::new(),
        tempo: 0,
        repeats: 0,
    })
}

/// Разобрать сырой (percent-декодированный, без `irealb://`) payload в песни.
///
/// Принимает и современные `irealpro`-записи, и классические читаемые
/// `irealbook`-записи.
pub fn decode_payload(data: &str) -> Result<Vec<Song>, IrealbError> {
    // Payload плейлиста: song===song===...===Name ; у одиночной песни '===' нет.
    let mut parts: Vec<&str> = data.split("===").collect();
    if parts.len() > 1 {
        parts.pop(); // отбрасываем хвостовое имя плейлиста
    }
    let mut songs = Vec::with_capacity(parts.len());
    for part in parts {
        let fields: Vec<&str> = part.split('=').collect();
        match fields.len() {
            10 => songs.push(song_from_irealpro_fields(&fields)?),
            6 => songs.push(song_from_irealbook_fields(&fields)?),
            n => {
                return err(format!(
                    "unsupported iRealPro record with {n} fields"
                ))
            }
        }
    }
    Ok(songs)
}

/// Извлечь и разобрать песни из URL `irealb://` / `irealbook://`.
///
/// Терпит окружающий HTML/текст и переводы строк — как эталонный парсер.
pub fn decode_url(text: &str) -> Result<Vec<Song>, IrealbError> {
    let cleaned: String = text.chars().filter(|&c| c != '\r' && c != '\n').collect();
    let find = |token: &str| -> Option<usize> { cleaned.find(token) };
    let irealb_pos = find("irealb://");
    let irealbook_pos = find("irealbook://");
    let (start, token_len) = match (irealb_pos, irealbook_pos) {
        (Some(a), Some(b)) if a <= b => (a, "irealb://".len()),
        (Some(_), Some(b)) => (b, "irealbook://".len()),
        (Some(a), None) => (a, "irealb://".len()),
        (None, Some(b)) => (b, "irealbook://".len()),
        (None, None) => return err("no irealb:// or irealbook:// URL found"),
    };
    let payload = url_decode(&cleaned[start + token_len..])?;
    decode_payload(&payload)
}

// ---------------------------------------------------------------------------
// Интеграционные хелперы irealstudio
// ---------------------------------------------------------------------------

/// Параметры конвертации классического читаемого URL в новый формат.
#[derive(Debug, Clone)]
pub struct ModernizeParams {
    pub tempo: i32,
    pub actual_style: String,
    pub actual_key: String,
    pub repeats: i32,
    pub urlencode: bool,
}

impl Default for ModernizeParams {
    fn default() -> Self {
        ModernizeParams {
            tempo: 120,
            actual_style: String::new(),
            actual_key: String::new(),
            repeats: 0,
            urlencode: true,
        }
    }
}

/// Преобразовать классический читаемый `irealbook://` URL в новый формат.
///
/// Используется irealstudio для эмиссии современного формата, оставаясь на
/// проверенном построителе аккорд-данных: читаемый URL уже несёт
/// title/composer/style/key/chords, а дополнительные метаданные (прежде всего
/// BPM) приходят от вызывающего кода.
pub fn irealbook_to_irealb(
    readable_irealbook_url: &str,
    params: &ModernizeParams,
) -> Result<String, IrealbError> {
    let songs = decode_url(readable_irealbook_url)?;
    if songs.len() != 1 {
        return err("irealbook_to_irealb expects a single-song URL");
    }
    let mut song = songs.into_iter().next().unwrap();
    song.tempo = params.tempo.max(0);
    song.actual_style = params.actual_style.clone();
    song.actual_key = params.actual_key.clone();
    song.repeats = params.repeats.max(0);
    let payload = song.to_field_record();
    let mut out = String::from("irealb://");
    if params.urlencode {
        out.push_str(&url_encode(&payload));
    } else {
        out.push_str(&payload);
    }
    Ok(out)
}

// ---------------------------------------------------------------------------
// Тесты
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hussle_is_self_inverse() {
        let samples = [
            "",
            "a",
            "C7 F7 Bb^7 |Cm7 F7|",
            &"x".repeat(49),
            &"x".repeat(50),
            &"x".repeat(51),
            &"x".repeat(149),
        ];
        for s in samples {
            assert_eq!(hussle(&hussle(s)), s, "hussle not self-inverse for len {}", s.len());
        }
    }

    #[test]
    fn obfuscate_starts_with_magic() {
        let blob = obfuscate("|D |D/F# |G |A");
        assert!(blob.starts_with(MAGIC));
        assert_eq!(deobfuscate(&blob).unwrap(), "|D |D/F# |G |A");
    }

    #[test]
    fn deobfuscate_rejects_bad_magic() {
        let e = deobfuscate("nope").unwrap_err();
        assert!(e.0.contains("magic prefix"), "{e}");
    }

    #[test]
    fn url_encoding_matches_python_safe_set() {
        // эталон из python: quote(s.encode('utf-8'), safe="-_.A-Za-z*/'")
        let s = "Rock Ballad*C/D'F# x~,!:()";
        let want = "Rock%20Ballad*C/D'F%23%20x~%2C%21%3A%28%29";
        assert_eq!(url_encode(s), want);
        assert_eq!(url_decode(&url_encode(s)).unwrap(), s);
        // '+' не превращается в пробел (как urllib.unquote).
        assert_eq!(url_decode("a+b").unwrap(), "a+b");
    }

    #[test]
    fn roundtrip_song() {
        let song = Song {
            title: "Autumn Leaves".into(),
            chords: "[A]|Cm7 |F7 |Bb^7 |Eb^7 |Am7-5 |D7 |G- |G7 |".into(),
            tempo: 120,
            ..Song::new("")
        };
        let url = build_url(&[song.clone()], None);
        assert!(url.starts_with("irealb://"));
        let decoded = decode_url(&url).unwrap();
        assert_eq!(decoded.len(), 1);
        assert_eq!(decoded[0].chords, song.chords);
        assert_eq!(decoded[0].tempo, 120);
        assert_eq!(decoded[0].to_field_record(), song.to_field_record());
    }

    #[test]
    fn decode_classic_irealbook_record() {
        // Классическая 6-полевая читаемая запись: аккорды не скрыты.
        let payload = "Autumn Leaves=Kosma=Medium Swing=AABA=C=Cm7|F7|Bb^7";
        let songs = decode_payload(payload).unwrap();
        assert_eq!(songs.len(), 1);
        assert_eq!(songs[0].title, "Autumn Leaves");
        assert_eq!(songs[0].composer, "Kosma");
        assert_eq!(songs[0].style, "Medium Swing");
        assert_eq!(songs[0].key, "C");
        assert_eq!(songs[0].chords, "Cm7|F7|Bb^7");
    }

    #[test]
    fn decode_classic_irealbook_with_sentinel_n() {
        // Запись, где iReal Pro вставил sentinel 'n' в слот key.
        let payload = "Blue Bossa=Kenny Dorham=Medium Swing=n=C=Cm7|Fm7";
        let songs = decode_payload(payload).unwrap();
        assert_eq!(songs[0].key, "C");
        assert_eq!(songs[0].chords, "Cm7|Fm7");
    }

    #[test]
    fn decode_payload_rejects_unknown_field_count() {
        assert!(decode_payload("a=b=c").is_err());
        assert!(decode_payload("a=b=c=d=e=f=g=h").is_err());
    }
}
