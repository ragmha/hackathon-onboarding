"""Original condensed lettering with a half-cell-offset outline shadow."""

TITLE = "HACKATHON"
DEFAULT_CAPTION = "LET'S BUILD"
BLOCKS = " \u2598\u259d\u2580\u2596\u258c\u259e\u259b\u2597\u259a\u2590\u259c\u2584\u2599\u259f\u2588"
LINES = " \u2575\u2576\u2514\u2577\u2502\u250c\u251c\u2574\u2518\u2500\u2534\u2510\u2524\u252c\u253c"
ALLOWED_GLYPHS = frozenset(BLOCKS + LINES)

FONT = {
    "H": (
        "111000111", "111000111", "111000111", "111000111", "111111111",
        "111111111", "111000111", "111000111", "111000111", "111000111",
    ),
    "A": (
        "001111100", "001111100", "111000111", "111000111", "111111111",
        "111111111", "111000111", "111000111", "111000111", "111000111",
    ),
    "C": (
        "001111111", "001111111", "111000000", "111000000", "111000000",
        "111000000", "111000000", "111000000", "001111111", "001111111",
    ),
    "K": (
        "111000111", "111000111", "111011100", "111011100", "111110000",
        "111110000", "111011100", "111011100", "111000111", "111000111",
    ),
    "T": (
        "111111111", "111111111", "000111000", "000111000", "000111000",
        "000111000", "000111000", "000111000", "000111000", "000111000",
    ),
    "O": (
        "001111100", "001111100", "111000111", "111000111", "111000111",
        "111000111", "111000111", "111000111", "001111100", "001111100",
    ),
    "N": (
        "111000111", "111000111", "111100111", "111100111", "111011111",
        "111011111", "111001111", "111001111", "111000111", "111000111",
    ),
}

COMPACT_FONT = {
    letter: tuple("".join(pixel for x, pixel in enumerate(row) if x not in (1, 7)) for row in rows)
    for letter, rows in FONT.items()
}


def ascii_glyph(char: str) -> str:
    if char in BLOCKS:
        return " " if char == " " else "#"
    if char in ("\u2500", "\u2574", "\u2576"):
        return "-"
    if char in ("\u2502", "\u2575", "\u2577"):
        return "|"
    return "+"


def outlined_wordmark(text: str, compact: bool = False) -> tuple[str, ...]:
    if not text or any(letter not in FONT for letter in text):
        raise ValueError("The block font supports only H, A, C, K, T, O, and N.")
    font = COMPACT_FONT if compact else FONT
    pixels = ["".join(font[letter][y] + "0" for letter in text) for y in range(10)]
    width, height = len(pixels[0]) // 2, len(pixels) // 2
    ink = [
        [
            BLOCKS[sum(
                1 << (dy * 2 + dx)
                for dy in range(2) for dx in range(2)
                if pixels[y * 2 + dy][x * 2 + dx] == "1"
            )]
            for x in range(width)
        ]
        for y in range(height)
    ]
    strokes = [[0] * (width + 1) for _ in range(height + 1)]

    def filled(x: int, y: int) -> bool:
        return 0 <= x < width and 0 <= y < height and ink[y][x] != " "

    # Box-drawing nodes sit at cell centers, offset from the ink's cell edges.
    for y in range(height):
        for x in range(width):
            if not filled(x, y):
                continue
            if not filled(x, y - 1):
                strokes[y][x] |= 2
                strokes[y][x + 1] |= 8
            if not filled(x, y + 1):
                strokes[y + 1][x] |= 2
                strokes[y + 1][x + 1] |= 8
            if not filled(x - 1, y):
                strokes[y][x] |= 4
                strokes[y + 1][x] |= 1
            if not filled(x + 1, y):
                strokes[y][x + 1] |= 4
                strokes[y + 1][x + 1] |= 1
    rows = [[LINES[mask] for mask in row] for row in strokes]
    for y, row in enumerate(ink):
        for x, char in enumerate(row):
            if char != " ":
                rows[y][x] = char
    return tuple("".join(row) for row in rows)


WORDMARK = outlined_wordmark(TITLE)
WORDMARK_WIDTH, WORDMARK_HEIGHT = len(WORDMARK[0]), len(WORDMARK)
COMPACT_WORDMARK = outlined_wordmark(TITLE, compact=True)
COMPACT_WORDMARK_WIDTH = len(COMPACT_WORDMARK[0])
