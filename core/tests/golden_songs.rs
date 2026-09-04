// Автогенерация: python-эталон irealstudio (irealb.py) + реальные URL из iReal Pro.
// Эталон decode/encode для сверки Rust-кодека. Не редактировать руками.
pub struct GoldenSong {
    pub url: &'static str, pub title: &'static str, pub composer: &'static str,
    pub a2: &'static str, pub style: &'static str, pub key: &'static str,
    pub actual_key: &'static str, pub actual_style: &'static str,
    pub tempo: i32, pub repeats: i32, pub chords: &'static str, pub record: &'static str,
}
pub const ALL: &[GoldenSong] = &[
    GoldenSong {
        url: r#"irealb://You're%20Still%20The%20One%3DTwain%20Shania%3D%3DRock%20Ballad%3DC%3D%3D1r34LbKcu7L%23F/D4DLZD%7D%20AZLGZL%23F/DZLAD*%7B%0A%7D%20AZLGZL%23F/%0A%7CDLZ4Ti*%7BDZLAZLZSDLGZLDB*%7B%0A%5D%20AZLALZGZLDZLAZLAZLGZLZE-LAZLGZ%23F/DZALZN1%5D%20%3EadoC%20la%20.S.%3CD%20A2N%7CQyXQyX%7D%20G%0A%5BQDLZLGZLLZGLZfA%20Z%20%3D%3D155%3D0"#,
        title: r#"You're Still The One"#,
        composer: r#"Twain Shania"#,
        a2: r#""#,
        style: r#"Rock Ballad"#,
        key: r#"C"#,
        actual_key: r#""#,
        actual_style: r#""#,
        tempo: 155, repeats: 0,
        chords: r#"{*iT44D |D/F# |G |A }
{*AD |D/F# |G |A }
|D |D/F# |G |A |SD |G |A |A |D |G |A |A ]
{*BD |G |E- |A |D |G |A |N1G }      |N2A <D.S. al Coda> ]
[QD |D/F# |G |fA Z "#,
        record: r#"You're Still The One=Twain Shania==Rock Ballad=C==1r34LbKcu7L#F/D4DLZD} AZLGZL#F/DZLAD*{
} AZLGZL#F/
|DLZ4Ti*{DZLAZLZSDLGZLDB*{
] AZLALZGZLDZLAZLAZLGZLZE-LAZLGZ#F/DZALZN1] >adoC la .S.<D A2N|QyXQyX} G
[QDLZLGZLLZGLZfA Z ==155=0"#,
    },
    GoldenSong {
        url: r#"irealb://Ik%20Zie%20Jou%3DTrudie%20van%20den%20Bos%3D%3DMedium%20Swing%3DC%3D%3D1r34LbKcu7KQyXG-XyQK3%3Cx%7CF%7Cx%7C-A%7B%7D%3Ex%3C4%20lcKQyX-BZL%20lcx%3E%20%7D%7CA43T%7Bcl%20LZ%20x%20LZ%20x%20%20%5D%20%3DPop-Slow%20Rock%3D180%3D3"#,
        title: r#"Ik Zie Jou"#,
        composer: r#"Trudie van den Bos"#,
        a2: r#""#,
        style: r#"Medium Swing"#,
        key: r#"C"#,
        actual_key: r#""#,
        actual_style: r#"Pop-Slow Rock"#,
        tempo: 180, repeats: 3,
        chords: r#"{T34A-   | x  |B-   | x <4x>}{A-|x|F|x<3x> }|G   | x  | x  | x  ] "#,
        record: r#"Ik Zie Jou=Trudie van den Bos==Medium Swing=C==1r34LbKcu7KQyXG-XyQK3<x|F|x|-A{}>x<4 lcKQyX-BZL lcx> }|A43T{cl LZ x LZ x  ] =Pop-Slow Rock=180=3"#,
    },
];
