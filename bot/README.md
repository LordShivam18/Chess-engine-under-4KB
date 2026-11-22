<div align="center">

# ♟️ TinyChess

**A complete chess engine in 3,873 bytes of Python.**

</div>

`main.py` is the whole engine: one file, Python 3.13, standard library only. It reads no other file in this repository. It speaks JSON over HTTP with the game server, plays every position it is given, and exits when the game is over.

## Design

- **10×12 mailbox board** with sentinel borders, so move generation needs no bounds checks.
- **Compact pieces** encoded as `type | colour`; White is `0`, Black is `8`.
- **Legal move generation** by make/unmake and a king-attack test, covering castling, en passant, promotions, pins and check evasions.
- **Iterative deepening negamax** with fail-soft alpha-beta and quiescence search.
- **64-bit Zobrist transposition table** with exact, lower and upper bounds.
- **Move ordering** by transposition move, MVV-LVA captures, promotions, en passant, killers and history.
- **Material + piece-square evaluation**, mirrored for Black and relative to the side to move.
- **Fixed node budgets**, no wall clock and no unseeded randomness, so every move is reproducible.

## Size

| Item | Bytes |
| --- | ---: |
| Packed engine | 3,873 |
| Hard limit | 4,096 |
| Remaining | 223 |

The source is packed with LZMA and unpacked at startup. Piece-square tables are stored as a single base85 string. The unpacker, tables and engine are all part of the same file.

## Running

The host supplies the game server address in the environment. Run `main.py` with Python 3.13; no packages, build step or other repository files are needed.

## License

MIT.
