"""TinyChess Phase 1 chess core.

This module is an original, dependency-free implementation of the rules of
chess on a 10x12 mailbox board.  It deliberately contains no search or
evaluation; those belong to Phase 2.

The 10x12 board has a two-rank border above and below and a one-file border
left and right.  A real square is addressed by

    (rank + 2) * 10 + (file + 1)

with a1 == 21 and h8 == 98.  File and rank indices in this module are
zero-based (a1 -> file 0, rank 0).

Colours are 0 (white) and 8 (black); a piece is ``type | colour``.  Sharing
the piece encoding this way lets both colours use the same movement code and
turns a colour test into one bit mask.

The public surface is:

* :class:`Position` -- FEN parsing/rendering, legal move generation,
  make/unmake, attack and game-state queries, UCI parsing, and perft.
* :class:`Move` -- an immutable move with UCI rendering.
* :func:`parse_square` / :func:`square_name` -- square conversions.

Invalid FENs and illegal moves raise :class:`ValueError`; they are never
silently ignored.

Run the independent tests with::

    python engine/test_engine.py
"""

from __future__ import annotations

from collections import namedtuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WHITE = 0
BLACK = 8

EMPTY = 0
OFF_BOARD = -1

PAWN = 1
KNIGHT = 2
BISHOP = 3
ROOK = 4
QUEEN = 5
KING = 6

W_PAWN = PAWN | WHITE
W_KNIGHT = KNIGHT | WHITE
W_BISHOP = BISHOP | WHITE
W_ROOK = ROOK | WHITE
W_QUEEN = QUEEN | WHITE
W_KING = KING | WHITE

B_PAWN = PAWN | BLACK
B_KNIGHT = KNIGHT | BLACK
B_BISHOP = BISHOP | BLACK
B_ROOK = ROOK | BLACK
B_QUEEN = QUEEN | BLACK
B_KING = KING | BLACK

# Castling-rights bits.
CASTLE_WK = 1
CASTLE_WQ = 2
CASTLE_BK = 4
CASTLE_BQ = 8
CASTLE_ALL = CASTLE_WK | CASTLE_WQ | CASTLE_BK | CASTLE_BQ

# Move flags.  A promotion is identified by Move.promotion; it still uses
# FLAG_NORMAL because it is an ordinary one-square pawn move otherwise.
FLAG_NORMAL = 0
FLAG_DOUBLE_PUSH = 1
FLAG_EN_PASSANT = 2
FLAG_CASTLE_KING = 3
FLAG_CASTLE_QUEEN = 4

PROMOTION_ORDER = (QUEEN, ROOK, BISHOP, KNIGHT)

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

FILES = "abcdefgh"
_FILE_TO_INDEX = {name: index for index, name in enumerate(FILES)}

_CHAR_TO_PIECE = {
    "P": W_PAWN,
    "N": W_KNIGHT,
    "B": W_BISHOP,
    "R": W_ROOK,
    "Q": W_QUEEN,
    "K": W_KING,
    "p": B_PAWN,
    "n": B_KNIGHT,
    "b": B_BISHOP,
    "r": B_ROOK,
    "q": B_QUEEN,
    "k": B_KING,
}
_PIECE_TO_CHAR = {piece: char for char, piece in _CHAR_TO_PIECE.items()}

_PROMOTION_TYPE_TO_CHAR = {
    KNIGHT: "n",
    BISHOP: "b",
    ROOK: "r",
    QUEEN: "q",
}
_PROMOTION_CHAR_TO_TYPE = {
    char: promotion for promotion, char in _PROMOTION_TYPE_TO_CHAR.items()
}

_CASTLE_CHAR_TO_BIT = {
    "K": CASTLE_WK,
    "Q": CASTLE_WQ,
    "k": CASTLE_BK,
    "q": CASTLE_BQ,
}

# Frequently used 120-board squares.
A1 = 21
B1 = 22
C1 = 23
D1 = 24
E1 = 25
F1 = 26
G1 = 27
H1 = 28

A8 = 91
B8 = 92
C8 = 93
D8 = 94
E8 = 95
F8 = 96
G8 = 97
H8 = 98

# ---------------------------------------------------------------------------
# Board geometry and precomputed movement tables
# ---------------------------------------------------------------------------


def _is_on_board(square: int) -> bool:
    """Whether ``square`` is one of the 64 real squares of the 10x12 board."""
    if not 0 <= square < 120:
        return False
    return 2 <= square // 10 <= 9 and 1 <= square % 10 <= 8


SQUARES = tuple(square for square in range(120) if _is_on_board(square))

# Fixed offset orders are part of the deterministic move-generation contract.
KNIGHT_OFFSETS = (-21, -19, -12, -8, 8, 12, 19, 21)
KING_OFFSETS = (-11, -10, -9, -1, 1, 9, 10, 11)
BISHOP_DIRECTIONS = (-11, -9, 9, 11)
ROOK_DIRECTIONS = (-10, -1, 1, 10)


def _build_leaper_table(offsets):
    table = []
    for square in range(120):
        targets = []
        if _is_on_board(square):
            for offset in offsets:
                target = square + offset
                if _is_on_board(target):
                    targets.append(target)
        table.append(tuple(targets))
    return tuple(table)


def _build_ray_table(directions):
    table = []
    for square in range(120):
        rays = []
        if _is_on_board(square):
            for direction in directions:
                ray = []
                target = square + direction
                while _is_on_board(target):
                    ray.append(target)
                    target += direction
                rays.append(tuple(ray))
        table.append(tuple(rays))
    return tuple(table)


KNIGHT_TARGETS = _build_leaper_table(KNIGHT_OFFSETS)
KING_TARGETS = _build_leaper_table(KING_OFFSETS)
BISHOP_RAYS = _build_ray_table(BISHOP_DIRECTIONS)
ROOK_RAYS = _build_ray_table(ROOK_DIRECTIONS)
QUEEN_RAYS = tuple(
    BISHOP_RAYS[square] + ROOK_RAYS[square] for square in range(120)
)


def rank_index(square: int) -> int:
    """Zero-based rank of a 120-board square (a1=0 ... h8=7)."""
    return square // 10 - 2


def file_index(square: int) -> int:
    """Zero-based file of a 120-board square (a=0 ... h=7)."""
    return square % 10 - 1


def square_name(square: int) -> str:
    """Convert a 120-board square to its lowercase coordinate name."""
    if not _is_on_board(square):
        raise ValueError(f"not a board square: {square}")
    return FILES[file_index(square)] + str(rank_index(square) + 1)


def parse_square(name: str) -> int:
    """Convert a coordinate such as ``e4`` to its 120-board square."""
    if not isinstance(name, str) or len(name) != 2:
        raise ValueError(f"not a square name: {name!r}")
    file_char, rank_char = name[0], name[1]
    if file_char not in _FILE_TO_INDEX or rank_char not in "12345678":
        raise ValueError(f"not a square name: {name!r}")
    return (int(rank_char) - 1 + 2) * 10 + (_FILE_TO_INDEX[file_char] + 1)


# ---------------------------------------------------------------------------
# Moves
# ---------------------------------------------------------------------------


class Move(namedtuple("_Move", "from_sq to_sq promotion flag")):
    """An immutable move.

    ``promotion`` is 0 or one of PAWN..QUEEN (only KNIGHT..QUEEN are used).
    Castling moves use standard king-to-destination coordinates, so White
    kingside castling is e1g1, not e1h1.
    """

    __slots__ = ()

    def uci(self) -> str:
        text = square_name(self.from_sq) + square_name(self.to_sq)
        if self.promotion:
            text += _PROMOTION_TYPE_TO_CHAR[self.promotion]
        return text

    def __str__(self) -> str:
        return self.uci()


def _append_promotions(moves, from_sq, to_sq):
    """Append the four promotion choices in deterministic Q, R, B, N order."""
    for promotion in PROMOTION_ORDER:
        moves.append(Move(from_sq, to_sq, promotion, FLAG_NORMAL))


# ---------------------------------------------------------------------------
# Attack detection
# ---------------------------------------------------------------------------


def _is_attacked(board, square: int, by_color: int) -> bool:
    """Whether ``square`` is attacked by any piece of ``by_color``.

    ``board`` is a 120-entry mailbox with OFF_BOARD in the guard band.  Pawn
    lookups stay inside the array because every real square is at least 21 and
    at most 98.
    """
    if by_color == WHITE:
        if board[square - 9] == W_PAWN or board[square - 11] == W_PAWN:
            return True
    else:
        if board[square + 9] == B_PAWN or board[square + 11] == B_PAWN:
            return True

    for target in KNIGHT_TARGETS[square]:
        if board[target] == (KNIGHT | by_color):
            return True

    for target in KING_TARGETS[square]:
        if board[target] == (KING | by_color):
            return True

    for ray in BISHOP_RAYS[square]:
        for target in ray:
            piece = board[target]
            if piece != EMPTY:
                if piece == (BISHOP | by_color) or piece == (QUEEN | by_color):
                    return True
                break

    for ray in ROOK_RAYS[square]:
        for target in ray:
            piece = board[target]
            if piece != EMPTY:
                if piece == (ROOK | by_color) or piece == (QUEEN | by_color):
                    return True
                break

    return False


def _validate_en_passant_square(board, ep_square: int, side_to_move: int) -> None:
    """Validate the geometry promised by a FEN en passant target square.

    An en passant target is only meaningful when the side that just moved
    double-pushed a pawn.  The target itself must be empty, the pushed pawn
    must stand directly behind it, and its original square must be empty.
    """
    if side_to_move == BLACK:
        # White has just double-pushed: the target is on rank 3, the white
        # pawn is on rank 4, and it came from rank 2.
        if rank_index(ep_square) != 2:
            raise ValueError("en passant target has the wrong rank")
        pawn_square = ep_square + 10
        origin_square = ep_square - 10
        expected_pawn = W_PAWN
    else:
        # Black has just double-pushed: the target is on rank 6, the black
        # pawn is on rank 5, and it came from rank 7.
        if rank_index(ep_square) != 5:
            raise ValueError("en passant target has the wrong rank")
        pawn_square = ep_square - 10
        origin_square = ep_square + 10
        expected_pawn = B_PAWN

    if board[ep_square] != EMPTY:
        raise ValueError("en passant target square is occupied")
    if board[pawn_square] != expected_pawn:
        raise ValueError("en passant target has no double-pushed pawn behind it")
    if board[origin_square] != EMPTY:
        raise ValueError("en passant pawn's origin square is occupied")


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------


class Position:
    """A complete chess position with legal move generation and perft."""

    __slots__ = (
        "board",
        "side_to_move",
        "castling",
        "ep_square",
        "halfmove_clock",
        "fullmove_number",
        "king_sq",
        "_stack",
    )

    def __init__(self, fen: str):
        """Build a position from a complete six-field FEN."""
        self.board = [OFF_BOARD] * 120
        for square in SQUARES:
            self.board[square] = EMPTY
        self.side_to_move = WHITE
        self.castling = 0
        self.ep_square = None
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self.king_sq = [-1, -1]  # indexed by colour >> 3
        self._stack = []
        self._load_fen(fen)

    # -- FEN ---------------------------------------------------------------

    @classmethod
    def from_fen(cls, fen: str) -> "Position":
        """Build a position from a complete six-field FEN."""
        return cls(fen)

    def _load_fen(self, fen: str) -> None:
        if not isinstance(fen, str):
            raise TypeError("FEN must be a string")
        fields = fen.split()
        scene = f"FEN {fen!r}"
        if len(fields) != 6:
            raise ValueError(f"{scene}: expected 6 fields, got {len(fields)}")

        placement, side_field, castling_field, ep_field, halfmove_field, fullmove_field = fields
        board = [OFF_BOARD] * 120
        for square in SQUARES:
            board[square] = EMPTY

        rank_rows = placement.split("/")
        if len(rank_rows) != 8:
            raise ValueError(f"{scene}: placement must have 8 ranks")
        for row_index, row_text in enumerate(rank_rows):
            file = 0
            for char in row_text:
                if "1" <= char <= "8":
                    file += ord(char) - ord("0")
                    if file > 8:
                        raise ValueError(f"{scene}: rank {8 - row_index} has more than 8 files")
                    continue
                piece = _CHAR_TO_PIECE.get(char)
                if piece is None:
                    raise ValueError(f"{scene}: invalid piece character {char!r}")
                if file >= 8:
                    raise ValueError(f"{scene}: rank {8 - row_index} has more than 8 files")
                square = (7 - row_index + 2) * 10 + (file + 1)
                board[square] = piece
                file += 1
            if file != 8:
                raise ValueError(f"{scene}: rank {8 - row_index} has {file} files, not 8")

        kings = [[], []]  # white, black
        piece_counts = [0, 0]
        pawn_counts = [0, 0]
        for square in SQUARES:
            piece = board[square]
            if piece == EMPTY:
                continue
            colour_index = 1 if piece & BLACK else 0
            piece_type = piece & 7
            piece_counts[colour_index] += 1
            if piece_type == KING:
                kings[colour_index].append(square)
            elif piece_type == PAWN:
                pawn_counts[colour_index] += 1
                if rank_index(square) in (0, 7):
                    raise ValueError(f"{scene}: pawn on the first or last rank")
        if len(kings[0]) != 1 or len(kings[1]) != 1:
            raise ValueError(f"{scene}: each side must have exactly one king")
        if piece_counts[0] > 16 or piece_counts[1] > 16:
            raise ValueError(f"{scene}: a side has more than 16 pieces")
        if pawn_counts[0] > 8 or pawn_counts[1] > 8:
            raise ValueError(f"{scene}: a side has more than 8 pawns")
        if kings[1][0] in KING_TARGETS[kings[0][0]]:
            raise ValueError(f"{scene}: kings are adjacent")

        if side_field == "w":
            side_to_move = WHITE
        elif side_field == "b":
            side_to_move = BLACK
        else:
            raise ValueError(f"{scene}: side to move must be 'w' or 'b'")

        castling = 0
        if castling_field != "-":
            for char in castling_field:
                bit = _CASTLE_CHAR_TO_BIT.get(char)
                if bit is None:
                    raise ValueError(f"{scene}: invalid castling field {castling_field!r}")
                if castling & bit:
                    raise ValueError(f"{scene}: duplicate castling right {char!r}")
                castling |= bit
            if castling & CASTLE_WK and (board[E1] != W_KING or board[H1] != W_ROOK):
                raise ValueError(f"{scene}: White kingside castling right has no king/rook")
            if castling & CASTLE_WQ and (board[E1] != W_KING or board[A1] != W_ROOK):
                raise ValueError(f"{scene}: White queenside castling right has no king/rook")
            if castling & CASTLE_BK and (board[E8] != B_KING or board[H8] != B_ROOK):
                raise ValueError(f"{scene}: Black kingside castling right has no king/rook")
            if castling & CASTLE_BQ and (board[E8] != B_KING or board[A8] != B_ROOK):
                raise ValueError(f"{scene}: Black queenside castling right has no king/rook")

        if ep_field == "-":
            ep_square = None
        else:
            try:
                ep_square = parse_square(ep_field)
            except ValueError as exc:
                raise ValueError(f"{scene}: invalid en passant square: {exc}") from None
            try:
                _validate_en_passant_square(board, ep_square, side_to_move)
            except ValueError as exc:
                raise ValueError(f"{scene}: {exc}") from None

        if not (halfmove_field.isascii() and halfmove_field.isdigit()):
            raise ValueError(f"{scene}: halfmove clock must be a non-negative integer")
        if not (fullmove_field.isascii() and fullmove_field.isdigit()):
            raise ValueError(f"{scene}: fullmove number must be a positive integer")
        halfmove_clock = int(halfmove_field)
        fullmove_number = int(fullmove_field)
        if fullmove_number < 1:
            raise ValueError(f"{scene}: fullmove number must be at least 1")
        if ep_square is not None and halfmove_clock != 0:
            raise ValueError(f"{scene}: an en passant target requires a zero halfmove clock")

        side_not_to_move = side_to_move ^ BLACK
        if _is_attacked(board, kings[side_not_to_move >> 3][0], side_to_move):
            raise ValueError(f"{scene}: the side not to move is in check")

        self.board = board
        self.side_to_move = side_to_move
        self.castling = castling
        self.ep_square = ep_square
        self.halfmove_clock = halfmove_clock
        self.fullmove_number = fullmove_number
        self.king_sq = [kings[0][0], kings[1][0]]
        self._stack = []

    def to_fen(self) -> str:
        """Render the position as a complete six-field FEN."""
        rows = []
        for rank in range(7, -1, -1):
            row = []
            empty_run = 0
            for file in range(8):
                piece = self.board[(rank + 2) * 10 + (file + 1)]
                if piece == EMPTY:
                    empty_run += 1
                    continue
                if empty_run:
                    row.append(str(empty_run))
                    empty_run = 0
                row.append(_PIECE_TO_CHAR[piece])
            if empty_run:
                row.append(str(empty_run))
            rows.append("".join(row))

        castling = ""
        if self.castling & CASTLE_WK:
            castling += "K"
        if self.castling & CASTLE_WQ:
            castling += "Q"
        if self.castling & CASTLE_BK:
            castling += "k"
        if self.castling & CASTLE_BQ:
            castling += "q"
        if not castling:
            castling = "-"

        ep_text = "-" if self.ep_square is None else square_name(self.ep_square)
        side_text = "w" if self.side_to_move == WHITE else "b"
        return (
            f"{'/'.join(rows)} {side_text} {castling} {ep_text} "
            f"{self.halfmove_clock} {self.fullmove_number}"
        )

    def __repr__(self) -> str:
        return f"Position.from_fen({self.to_fen()!r})"

    # -- Queries -----------------------------------------------------------

    def is_attacked(self, square: int, by_color: int) -> bool:
        """Whether ``square`` is attacked by ``by_color``."""
        if not _is_on_board(square):
            raise ValueError(f"not a board square: {square}")
        if by_color not in (WHITE, BLACK):
            raise ValueError(f"invalid colour: {by_color!r}")
        return _is_attacked(self.board, square, by_color)

    def in_check(self, color: int | None = None) -> bool:
        """Whether ``color`` (default: the side to move) is in check."""
        if color is None:
            color = self.side_to_move
        if color not in (WHITE, BLACK):
            raise ValueError(f"invalid colour: {color!r}")
        return _is_attacked(self.board, self.king_sq[color >> 3], color ^ BLACK)

    def is_checkmate(self) -> bool:
        return self.in_check() and not self.legal_moves()

    def is_stalemate(self) -> bool:
        return not self.in_check() and not self.legal_moves()

    # -- Move generation ---------------------------------------------------

    def _pseudo_legal_moves(self) -> list[Move]:
        """Generate pseudo-legal moves in a fixed, deterministic order.

        Squares are scanned from a1 to h8.  Within a square, leapers use the
        fixed offset order above, sliders use the fixed ray order, pawns try
        the single push, double push, then the two capture directions, and
        promotions are emitted Q, R, B, N.  Castling is appended after the
        king's ordinary moves.  Legality (own-king safety) is filtered by
        :meth:`legal_moves`.
        """
        board = self.board
        us = self.side_to_move
        them = us ^ BLACK
        castling = self.castling
        ep_square = self.ep_square
        moves: list[Move] = []

        for square in SQUARES:
            piece = board[square]
            if piece == EMPTY or (piece & BLACK) != us:
                continue
            piece_type = piece & 7

            if piece_type == PAWN:
                if us == WHITE:
                    rank = rank_index(square)
                    one = square + 10
                    if board[one] == EMPTY:
                        if rank == 6:
                            _append_promotions(moves, square, one)
                        else:
                            moves.append(Move(square, one, 0, FLAG_NORMAL))
                            if rank == 1 and board[one + 10] == EMPTY:
                                moves.append(Move(square, one + 10, 0, FLAG_DOUBLE_PUSH))
                    for step in (9, 11):
                        target_square = square + step
                        target = board[target_square]
                        if target > 0 and (target & BLACK) == them:
                            if rank == 6:
                                _append_promotions(moves, square, target_square)
                            else:
                                moves.append(Move(square, target_square, 0, FLAG_NORMAL))
                        elif target_square == ep_square:
                            moves.append(Move(square, target_square, 0, FLAG_EN_PASSANT))
                else:
                    rank = rank_index(square)
                    one = square - 10
                    if board[one] == EMPTY:
                        if rank == 1:
                            _append_promotions(moves, square, one)
                        else:
                            moves.append(Move(square, one, 0, FLAG_NORMAL))
                            if rank == 6 and board[one - 10] == EMPTY:
                                moves.append(Move(square, one - 10, 0, FLAG_DOUBLE_PUSH))
                    for step in (-9, -11):
                        target_square = square + step
                        target = board[target_square]
                        if target > 0 and (target & BLACK) == them:
                            if rank == 1:
                                _append_promotions(moves, square, target_square)
                            else:
                                moves.append(Move(square, target_square, 0, FLAG_NORMAL))
                        elif target_square == ep_square:
                            moves.append(Move(square, target_square, 0, FLAG_EN_PASSANT))

            elif piece_type == KNIGHT:
                for target_square in KNIGHT_TARGETS[square]:
                    target = board[target_square]
                    if target == EMPTY:
                        moves.append(Move(square, target_square, 0, FLAG_NORMAL))
                    elif target > 0 and (target & BLACK) == them:
                        moves.append(Move(square, target_square, 0, FLAG_NORMAL))

            elif piece_type in (BISHOP, ROOK, QUEEN):
                if piece_type == BISHOP:
                    rays = BISHOP_RAYS[square]
                elif piece_type == ROOK:
                    rays = ROOK_RAYS[square]
                else:
                    rays = QUEEN_RAYS[square]
                for ray in rays:
                    for target_square in ray:
                        target = board[target_square]
                        if target == EMPTY:
                            moves.append(Move(square, target_square, 0, FLAG_NORMAL))
                            continue
                        if target > 0 and (target & BLACK) == them:
                            moves.append(Move(square, target_square, 0, FLAG_NORMAL))
                        break

            elif piece_type == KING:
                for target_square in KING_TARGETS[square]:
                    target = board[target_square]
                    if target == EMPTY:
                        moves.append(Move(square, target_square, 0, FLAG_NORMAL))
                    elif target > 0 and (target & BLACK) == them:
                        moves.append(Move(square, target_square, 0, FLAG_NORMAL))

                if us == WHITE and square == E1:
                    if (
                        castling & CASTLE_WK
                        and board[F1] == EMPTY
                        and board[G1] == EMPTY
                        and board[H1] == W_ROOK
                        and not _is_attacked(board, E1, them)
                        and not _is_attacked(board, F1, them)
                        and not _is_attacked(board, G1, them)
                    ):
                        moves.append(Move(E1, G1, 0, FLAG_CASTLE_KING))
                    if (
                        castling & CASTLE_WQ
                        and board[D1] == EMPTY
                        and board[C1] == EMPTY
                        and board[B1] == EMPTY
                        and board[A1] == W_ROOK
                        and not _is_attacked(board, E1, them)
                        and not _is_attacked(board, D1, them)
                        and not _is_attacked(board, C1, them)
                    ):
                        moves.append(Move(E1, C1, 0, FLAG_CASTLE_QUEEN))
                elif us == BLACK and square == E8:
                    if (
                        castling & CASTLE_BK
                        and board[F8] == EMPTY
                        and board[G8] == EMPTY
                        and board[H8] == B_ROOK
                        and not _is_attacked(board, E8, them)
                        and not _is_attacked(board, F8, them)
                        and not _is_attacked(board, G8, them)
                    ):
                        moves.append(Move(E8, G8, 0, FLAG_CASTLE_KING))
                    if (
                        castling & CASTLE_BQ
                        and board[D8] == EMPTY
                        and board[C8] == EMPTY
                        and board[B8] == EMPTY
                        and board[A8] == B_ROOK
                        and not _is_attacked(board, E8, them)
                        and not _is_attacked(board, D8, them)
                        and not _is_attacked(board, C8, them)
                    ):
                        moves.append(Move(E8, C8, 0, FLAG_CASTLE_QUEEN))

        return moves

    def legal_moves(self) -> list[Move]:
        """Every legal move of the side to move, in deterministic order."""
        us = self.side_to_move
        them = us ^ BLACK
        king_index = us >> 3
        legal: list[Move] = []
        for move in self._pseudo_legal_moves():
            self._push(move)
            if not _is_attacked(self.board, self.king_sq[king_index], them):
                legal.append(move)
            self._pop()
        return legal

    # -- Make / unmake -----------------------------------------------------

    def make_move(self, move: Move) -> None:
        """Make ``move`` after confirming it is legal for this position.

        The move is validated against :meth:`legal_moves`; an illegal or
        malformed move raises :class:`ValueError` and leaves the position
        untouched.  Use :meth:`unmake_move` to take the move back.
        """
        if not isinstance(move, Move):
            raise TypeError(f"expected a Move, got {type(move).__name__}")
        if move not in self.legal_moves():
            raise ValueError(f"illegal move {move!r} in position {self.to_fen()!r}")
        self._push(move)

    def unmake_move(self) -> Move:
        """Take back the last made move, restoring the position exactly."""
        if not self._stack:
            raise ValueError("cannot unmake: no move has been made")
        return self._pop()

    def _push(self, move: Move) -> None:
        """Apply a move that the caller knows is legal for this position."""
        board = self.board
        us = self.side_to_move
        from_sq = move.from_sq
        to_sq = move.to_sq
        flag = move.flag
        piece = board[from_sq]

        captured_square = to_sq
        if flag == FLAG_EN_PASSANT:
            captured_square = to_sq - 10 if us == WHITE else to_sq + 10
        captured = board[captured_square]

        self._stack.append(
            (
                move,
                piece,
                captured,
                captured_square,
                self.castling,
                self.ep_square,
                self.halfmove_clock,
                self.fullmove_number,
                self.side_to_move,
                self.king_sq[0],
                self.king_sq[1],
            )
        )

        board[from_sq] = EMPTY
        if captured != EMPTY:
            board[captured_square] = EMPTY
        if move.promotion:
            board[to_sq] = move.promotion | us
        else:
            board[to_sq] = piece

        if flag == FLAG_CASTLE_KING:
            if us == WHITE:
                board[F1] = board[H1]
                board[H1] = EMPTY
            else:
                board[F8] = board[H8]
                board[H8] = EMPTY
        elif flag == FLAG_CASTLE_QUEEN:
            if us == WHITE:
                board[D1] = board[A1]
                board[A1] = EMPTY
            else:
                board[D8] = board[A8]
                board[A8] = EMPTY

        if (piece & 7) == KING:
            self.king_sq[us >> 3] = to_sq

        castling = self.castling
        if (piece & 7) == KING:
            castling &= ~(CASTLE_WK | CASTLE_WQ) if us == WHITE else ~(CASTLE_BK | CASTLE_BQ)
        if from_sq == H1:
            castling &= ~CASTLE_WK
        elif from_sq == A1:
            castling &= ~CASTLE_WQ
        elif from_sq == H8:
            castling &= ~CASTLE_BK
        elif from_sq == A8:
            castling &= ~CASTLE_BQ
        if captured_square == H1:
            castling &= ~CASTLE_WK
        elif captured_square == A1:
            castling &= ~CASTLE_WQ
        elif captured_square == H8:
            castling &= ~CASTLE_BK
        elif captured_square == A8:
            castling &= ~CASTLE_BQ
        self.castling = castling

        if flag == FLAG_DOUBLE_PUSH:
            self.ep_square = (from_sq + to_sq) // 2
        else:
            self.ep_square = None

        if (piece & 7) == PAWN or captured != EMPTY:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1
        if us == BLACK:
            self.fullmove_number += 1
        self.side_to_move = us ^ BLACK

    def _pop(self) -> Move:
        """Undo the most recent move, restoring every part of the state."""
        (
            move,
            piece,
            captured,
            captured_square,
            castling,
            ep_square,
            halfmove_clock,
            fullmove_number,
            side_to_move,
            white_king,
            black_king,
        ) = self._stack.pop()

        board = self.board
        from_sq = move.from_sq
        to_sq = move.to_sq

        board[from_sq] = piece
        board[to_sq] = EMPTY
        if captured != EMPTY:
            board[captured_square] = captured

        if move.flag == FLAG_CASTLE_KING:
            if side_to_move == WHITE:
                board[H1] = board[F1]
                board[F1] = EMPTY
            else:
                board[H8] = board[F8]
                board[F8] = EMPTY
        elif move.flag == FLAG_CASTLE_QUEEN:
            if side_to_move == WHITE:
                board[A1] = board[D1]
                board[D1] = EMPTY
            else:
                board[A8] = board[D8]
                board[D8] = EMPTY

        self.side_to_move = side_to_move
        self.castling = castling
        self.ep_square = ep_square
        self.halfmove_clock = halfmove_clock
        self.fullmove_number = fullmove_number
        self.king_sq[0] = white_king
        self.king_sq[1] = black_king
        return move

    # -- UCI ---------------------------------------------------------------

    def parse_uci_move(self, text: str) -> Move:
        """Return the legal move named by a UCI string.

        The string must name a legal move at the root of this position.  A
        promotion requires its piece letter.  Castling uses standard
        king-to-destination notation (e1g1, e1c1, e8g8, e8c8).
        """
        if not isinstance(text, str):
            raise TypeError("UCI move must be a string")
        normalized = text.strip().lower()
        if len(normalized) not in (4, 5):
            raise ValueError(f"not a UCI move: {text!r}")
        from_sq = parse_square(normalized[:2])
        to_sq = parse_square(normalized[2:4])
        promotion = 0
        if len(normalized) == 5:
            promotion = _PROMOTION_CHAR_TO_TYPE.get(normalized[4], 0)
            if promotion == 0:
                raise ValueError(f"not a UCI move: {text!r}")

        matches = [
            move
            for move in self.legal_moves()
            if move.from_sq == from_sq
            and move.to_sq == to_sq
            and move.promotion == promotion
        ]
        if len(matches) != 1:
            raise ValueError(f"illegal UCI move {text!r} in position {self.to_fen()!r}")
        return matches[0]

    # -- Perft -------------------------------------------------------------

    def perft(self, depth: int) -> int:
        """Count legal move sequences of exactly ``depth`` plies.

        The position is left exactly as it was found.
        """
        if not isinstance(depth, int) or isinstance(depth, bool):
            raise TypeError("perft depth must be an integer")
        if depth < 0:
            raise ValueError("perft depth must be non-negative")
        return self._perft(depth)

    def _perft(self, depth: int) -> int:
        if depth == 0:
            return 1
        moves = self.legal_moves()
        if depth == 1:
            return len(moves)
        total = 0
        for move in moves:
            self._push(move)
            total += self._perft(depth - 1)
            self._pop()
        return total
