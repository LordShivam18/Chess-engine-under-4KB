<div align="center">

# ♟️ TinyChess

### A complete chess engine in **3,873 bytes** of Python.

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Size](https://img.shields.io/badge/engine-3%2C873%20bytes-2ea44f)](#the-size-budget)
[![Dependencies](https://img.shields.io/badge/dependencies-none-blue)](#quick-start)
[![Deterministic](https://img.shields.io/badge/search-deterministic-8a2be2)](#design-principles)
[![License](https://img.shields.io/badge/license-MIT-yellow)](#license)

**One file. Standard library only. Every move reproducible.**

</div>

---

TinyChess is a full chess engine compressed into a single Python file. It generates legal moves, searches with alpha-beta and quiescence, keeps a transposition table, evaluates positions with material and piece-square tables, and plays complete games — all inside a hard **4,096-byte** budget.

It does not read a clock, call a model, load a book, or depend on another file. The shipped engine is a self-extracting LZMA payload: the decompressor and the engine are the same file.

```text
  a b c d e f g h
8 ♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜
7 ♟ ♟ ♟ ♟ ♟ ♟ ♟ ♟
6 · · · · · · · ·
5 · · · · · · · ·
4 · · · · · · · ·
3 · · · · · · · ·
2 ♙ ♙ ♙ ♙ ♙ ♙ ♙ ♙
1 ♖ ♘ ♗ ♕ ♔ ♗ ♘ ♖
```

## At a glance

| Property | Detail |
| --- | --- |
| Language | Python 3.13 |
| Dependencies | None — standard library only |
| Packed engine | **3,873 bytes** |
| Size limit | 4,096 bytes |
| Headroom | 223 bytes |
| Board | 10×12 mailbox, 120 squares |
| Search | Iterative deepening negamax + alpha-beta |
| Extensions | Quiescence, transposition table, killers, history |
| Evaluation | Material + piece-square tables |
| Determinism | Fixed node budget, no wall clock, no randomness |

## Highlights

- **Complete move generation** — castling, en passant, all four promotions, checks, pins, mate and stalemate.
- **A real search** — iterative deepening, fail-soft alpha-beta, quiescence search, a 64-bit Zobrist transposition table, killer moves and history heuristics.
- **A compact evaluation** — classic material values plus piece-square tables, mirrored for Black and scored from the side to move.
- **Deterministic by design** — the same position and node budget always produce the same move. Nothing depends on timing or unseeded randomness.
- **Self-contained** — the payload, lookup tables and decompressor live in one file. No data files, no imports from the repository.
- **Tested** — independent suites cover perft counts, rule edge cases, make/unmake state, and search-budget behaviour.

## Under the hood

### Board representation

The board is a **10×12 mailbox**: a 10-file by 12-rank array with a one-file border and a two-rank border. Real squares use `(rank + 2) * 10 + (file + 1)`, so `a1 == 21` and `h8 == 98`. The sentinel border means move generation never needs a separate bounds check.

Pieces are encoded as `type | colour`, with White as `0` and Black as `8`. One bit tests the colour, one mask extracts the piece type, and both sides share the same movement code.

### Move generation

Moves are generated pseudo-legally from precomputed knight, king and sliding-ray tables, then validated by making the move and asking whether the king is attacked. This catches pins and illegal check evasions without a separate pin-detection pass. `push()` and `pop()` restore every part of the state: board, side to move, castling rights, en passant square and halfmove clock.

### Search

The engine deepens one ply at a time and keeps the best move from the last completed iteration. Each iteration is a fail-soft negamax search with alpha-beta pruning.

- **Quiescence** searches captures, promotions and en passant captures at leaf nodes. In check it searches every legal evasion and never uses a stand-pat score.
- **Mate scores** are `99999 - ply`, so the search prefers faster mates and slower losses. Mate scores are not stored in the table.
- **Transposition table** entries use 64-bit Zobrist keys and carry exact, lower-bound or upper-bound flags.
- **Move ordering** is transposition move first, then MVV-LVA captures, promotions, en passant, killers and history.
- **Node budgets** stop the current iteration cleanly; the last completed best move stands. Budgets shrink as the game gets longer, keeping the search predictable.

### Evaluation

Evaluation is deliberately small and fast: pawn `100`, knight `320`, bishop `330`, rook `500`, queen `900`, plus a piece-square table for every piece. Black's table is mirrored, and the score is returned relative to the side to move.

### Size engineering

The readable engine is about 12 KB. The shipped file is **3,873 bytes**:

- the source is packed with LZMA and unpacked at startup;
- piece-square tables are stored as one base85 string;
- move lists use compact tuples instead of objects;
- names, constants and control flow are tuned for both speed and byte count.

Every byte is part of the engine, including the unpacker. There is no hidden data file and no second source file.

## The size budget

| Item | Bytes |
| --- | ---: |
| Packed engine | 3,873 |
| Hard limit | 4,096 |
| Remaining | 223 |

The engine is valid Python 3.13 and uses only `base64`, `json`, `lzma`, `os`, `sys` and `urllib` from the standard library.

## Quick start

The readable source lives in `engine/`. A quick look at legal move generation:

```python
from engine.compact import Pos, uci

start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
position = Pos(start)

print(len(position.legal()), "legal moves")
print(uci(position.legal()[0]))
```

Run the test suites:

```text
python engine/test_engine.py
python engine/test_compact.py
python engine/test_compact_v2_policy.py
```

`bot/main.py` is the packed engine entry point. It expects the host to provide the game server address in the environment, then plays through JSON/HTTP until the game is over.

## Project layout

```text
engine/     readable engine source, tests and design notes
bot/        packed single-file engine
starter/    minimal reference implementation
.github/    continuous integration
```

## Design principles

> Correctness before cleverness. Determinism before convenience. Every byte must earn its place.

- **No clock in the search.** A fixed node budget makes games reproducible.
- **No external state.** The engine may read its own bytes, but no other repository file.
- **No hidden dependencies.** Standard library only, no install step, no native code.
- **Small, measured changes.** Every optimisation is checked against the size cap and the test suites.

## Limitations

TinyChess is intentionally minimal. Its evaluation has no mobility, king-safety, pawn-structure or space terms. It has no opening book and no endgame tablebase. Outside check, quiescence considers only forcing captures and promotions, not quiet checks. It is single-threaded and budgets nodes rather than time.

Those limits are the point: the engine is a study in how much chess can fit into four kilobytes.

## License

Released under the **MIT License**. Use it, modify it, share it.
