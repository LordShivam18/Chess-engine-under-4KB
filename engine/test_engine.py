"""Independent Phase 1 test suite for the TinyChess engine.

Run with::

    python engine/test_engine.py

The perft expectations are the published counts for the six standard Chess
Programming Wiki positions, plus the standard promotion-heavy position.  The
suite is independent of the engine implementation: it checks perft counts,
FEN and UCI round-trips, make/unmake state equality, and rule edge cases.
"""

import os
import random
import sys
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from engine import (  # noqa: E402
    BLACK,
    CASTLE_BK,
    CASTLE_BQ,
    CASTLE_WK,
    CASTLE_WQ,
    FLAG_DOUBLE_PUSH,
    FLAG_EN_PASSANT,
    FLAG_NORMAL,
    KING,
    KNIGHT,
    Move,
    PAWN,
    Position,
    QUEEN,
    ROOK,
    START_FEN,
    WHITE,
    parse_square,
    square_name,
)

# ---------------------------------------------------------------------------
# Shared positions
# ---------------------------------------------------------------------------

KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
POSITION_3 = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"
POSITION_4 = "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1"
POSITION_5 = "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8"
POSITION_6 = "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10"
PROMOTION_PERFT = "n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1"

CASTLE_FEN = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
CASTLE_FEN_BLACK = "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1"
EP_FEN = "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3"
EP_PIN_FEN = "8/8/8/8/k2Pp2Q/8/8/4K3 b - d3 0 1"
PROMOTION_FEN = "1n6/P7/8/8/8/8/7p/4K2k w - - 0 1"
CHECKMATE_FEN = "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1"
STALEMATE_FEN = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"

FEN_CORPUS = (
    START_FEN,
    KIWIPETE,
    POSITION_3,
    POSITION_4,
    POSITION_5,
    POSITION_6,
    CASTLE_FEN,
    EP_FEN,
    EP_PIN_FEN,
    PROMOTION_FEN,
)

PERFT_CASES = (
    ("start", START_FEN, ((1, 20), (2, 400), (3, 8902), (4, 197281), (5, 4865609))),
    ("kiwipete", KIWIPETE, ((1, 48), (2, 2039), (3, 97862), (4, 4085603))),
    ("position-3", POSITION_3, ((1, 14), (2, 191), (3, 2812), (4, 43238), (5, 674624))),
    ("position-4", POSITION_4, ((1, 6), (2, 264), (3, 9467), (4, 422333))),
    ("position-5", POSITION_5, ((1, 44), (2, 1486), (3, 62379), (4, 2103487))),
    ("position-6", POSITION_6, ((1, 46), (2, 2079), (3, 89890), (4, 3894594))),
)

START_LEGAL_UCI = [
    "b1a3",
    "b1c3",
    "g1f3",
    "g1h3",
    "a2a3",
    "a2a4",
    "b2b3",
    "b2b4",
    "c2c3",
    "c2c4",
    "d2d3",
    "d2d4",
    "e2e3",
    "e2e4",
    "f2f3",
    "f2f4",
    "g2g3",
    "g2g4",
    "h2h3",
    "h2h4",
]


def snapshot(position):
    """Every externally visible part of a Position, for exact comparisons."""
    return (
        tuple(position.board),
        position.side_to_move,
        position.castling,
        position.ep_square,
        position.halfmove_clock,
        position.fullmove_number,
        tuple(position.king_sq),
    )


def uci_list(position):
    return [move.uci() for move in position.legal_moves()]


def find_move(position, uci):
    for move in position.legal_moves():
        if move.uci() == uci:
            return move
    raise AssertionError(f"{uci} is not legal in {position.to_fen()}")


# ---------------------------------------------------------------------------
# FEN
# ---------------------------------------------------------------------------


class TestFen(unittest.TestCase):
    def test_fen_round_trip(self):
        for fen in FEN_CORPUS:
            with self.subTest(fen=fen):
                self.assertEqual(Position.from_fen(fen).to_fen(), fen)

    def test_fen_fields(self):
        position = Position.from_fen(KIWIPETE)
        self.assertEqual(position.side_to_move, WHITE)
        self.assertEqual(position.castling, CASTLE_WK | CASTLE_WQ | CASTLE_BK | CASTLE_BQ)
        self.assertIsNone(position.ep_square)
        self.assertEqual(position.halfmove_clock, 0)
        self.assertEqual(position.fullmove_number, 1)
        self.assertEqual(position.king_sq[0], parse_square("e1"))
        self.assertEqual(position.king_sq[1], parse_square("e8"))

    def test_fen_clocks_and_castling(self):
        position = Position.from_fen(POSITION_5)
        self.assertEqual(position.halfmove_clock, 1)
        self.assertEqual(position.fullmove_number, 8)
        self.assertEqual(position.castling, CASTLE_WK | CASTLE_WQ)

    def test_fen_after_double_push(self):
        position = Position.from_fen(START_FEN)
        position.make_move(find_move(position, "e2e4"))
        self.assertEqual(
            position.to_fen(),
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        )
        black_reply = find_move(position, "e7e5")
        position.make_move(black_reply)
        self.assertEqual(
            position.to_fen(),
            "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2",
        )

    def test_fen_round_trip_after_every_move(self):
        for fen in (START_FEN, KIWIPETE, EP_FEN):
            position = Position.from_fen(fen)
            for move in position.legal_moves():
                before = snapshot(position)
                position.make_move(move)
                fen_after = position.to_fen()
                reparsed = Position.from_fen(fen_after)
                self.assertEqual(reparsed.to_fen(), fen_after)
                self.assertEqual(snapshot(reparsed), snapshot(position))
                position.unmake_move()
                self.assertEqual(snapshot(position), before)

    def test_invalid_fens_are_rejected(self):
        invalid = {
            "empty": "",
            "five fields": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0",
            "extra field": "4k3/8/8/8/8/8/8/4K3 w - - 0 1 extra",
            "no kings": "8/8/8/8/8/8/8/8 w - - 0 1",
            "missing black king": "8/8/8/8/8/8/8/4K3 w - - 0 1",
            "two white kings": "4k3/8/8/8/8/8/8/4KK2 w - - 0 1",
            "short rank": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBN w KQkq - 0 1",
            "long rank": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNRR w KQkq - 0 1",
            "bad piece": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNX w KQkq - 0 1",
            "bad side": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x KQkq - 0 1",
            "bad castling": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KZ - 0 1",
            "duplicate castling": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KK - 0 1",
            "castling without rook": "4k3/8/8/8/8/8/8/4K3 w K - 0 1",
            "pawn on first rank": "4k3/8/8/8/8/8/8/P3K3 w - - 0 1",
            "pawn on last rank": "P3k3/8/8/8/8/8/8/4K3 w - - 0 1",
            "adjacent kings": "8/8/8/8/8/8/8/4Kk2 w - - 0 1",
            "side not to move in check": "4k3/8/8/8/8/8/4R3/4K3 w - - 0 1",
            "bad ep geometry": "4k3/8/8/8/8/8/8/4K3 w - e6 0 1",
            "bad ep rank": "4k3/8/8/8/8/8/8/4K3 w - e3 0 1",
            "bad ep name": "4k3/8/8/8/8/8/8/4K3 w - e9 0 1",
            "ep with nonzero clock": (
                "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 1 3"
            ),
            "negative halfmove": "4k3/8/8/8/8/8/8/4K3 w - - -1 1",
            "zero fullmove": "4k3/8/8/8/8/8/8/4K3 w - - 0 0",
            "nonnumeric halfmove": "4k3/8/8/8/8/8/8/4K3 w - - x 1",
            "nine white pawns": "4k3/8/8/8/8/8/PPPPPPPP/P3K3 w - - 0 1",
            "ranks not eight": "4k3/8/8/8/8/8/4K3 w - - 0 1",
        }
        for label, fen in invalid.items():
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    Position.from_fen(fen)

    def test_fen_type_errors(self):
        with self.assertRaises(TypeError):
            Position.from_fen(None)
        with self.assertRaises(TypeError):
            Position.from_fen(123)

    def test_side_to_move_in_check_is_a_valid_fen(self):
        position = Position.from_fen("4k3/8/8/8/8/8/4R3/4K3 b - - 0 1")
        self.assertTrue(position.in_check())
        self.assertFalse(position.in_check(WHITE))


# ---------------------------------------------------------------------------
# UCI
# ---------------------------------------------------------------------------


class TestUci(unittest.TestCase):
    def test_uci_round_trip(self):
        for fen in FEN_CORPUS:
            position = Position.from_fen(fen)
            for move in position.legal_moves():
                self.assertEqual(position.parse_uci_move(move.uci()), move)

    def test_start_uci_moves(self):
        position = Position.from_fen(START_FEN)
        self.assertEqual(
            position.parse_uci_move("e2e4"),
            Move(parse_square("e2"), parse_square("e4"), 0, FLAG_DOUBLE_PUSH),
        )
        self.assertEqual(position.parse_uci_move(" E2E4 ").uci(), "e2e4")

    def test_castling_uci_uses_king_destination(self):
        position = Position.from_fen(CASTLE_FEN)
        kingside = position.parse_uci_move("e1g1")
        queenside = position.parse_uci_move("e1c1")
        self.assertEqual(kingside.uci(), "e1g1")
        self.assertEqual(queenside.uci(), "e1c1")
        self.assertEqual(kingside.flag, 3)  # FLAG_CASTLE_KING
        self.assertEqual(queenside.flag, 4)  # FLAG_CASTLE_QUEEN
        with self.assertRaises(ValueError):
            position.parse_uci_move("e1h1")

        black = Position.from_fen(CASTLE_FEN_BLACK)
        self.assertEqual(black.parse_uci_move("e8g8").uci(), "e8g8")
        self.assertEqual(black.parse_uci_move("e8c8").uci(), "e8c8")
        with self.assertRaises(ValueError):
            black.parse_uci_move("e8a8")

    def test_promotion_uci(self):
        position = Position.from_fen(PROMOTION_FEN)
        expected = {
            "a7a8q": QUEEN,
            "a7a8r": ROOK,
            "a7a8b": 3,
            "a7a8n": KNIGHT,
        }
        for uci, piece_type in expected.items():
            self.assertEqual(position.parse_uci_move(uci).promotion, piece_type)
        with self.assertRaises(ValueError):
            position.parse_uci_move("a7a8")
        with self.assertRaises(ValueError):
            position.parse_uci_move("a7a8k")

    def test_illegal_and_malformed_uci_is_rejected(self):
        position = Position.from_fen(START_FEN)
        for text in ("e2e5", "e7e5", "e1g1", "", "e2e", "e2e4q", "z2e4", "e2e9"):
            with self.subTest(text):
                with self.assertRaises(ValueError):
                    position.parse_uci_move(text)
        with self.assertRaises(TypeError):
            position.parse_uci_move(1234)

    def test_root_legal_move_validation(self):
        position = Position.from_fen(START_FEN)
        before = snapshot(position)
        illegal = Move(parse_square("e2"), parse_square("e5"), 0, FLAG_NORMAL)
        with self.assertRaises(ValueError):
            position.make_move(illegal)
        self.assertEqual(snapshot(position), before)
        with self.assertRaises(TypeError):
            position.make_move("e2e4")
        self.assertEqual(snapshot(position), before)
        with self.assertRaises(ValueError):
            position.unmake_move()

        move = position.parse_uci_move("e2e4")
        position.make_move(move)
        self.assertEqual(position.side_to_move, BLACK)
        self.assertEqual(position.unmake_move(), move)
        self.assertEqual(snapshot(position), before)
        with self.assertRaises(ValueError):
            position.unmake_move()


# ---------------------------------------------------------------------------
# Move generation, make/unmake, determinism
# ---------------------------------------------------------------------------


class TestMoveGenerationAndUndo(unittest.TestCase):
    def test_start_position_exact_order(self):
        position = Position.from_fen(START_FEN)
        self.assertEqual(uci_list(position), START_LEGAL_UCI)

    def test_move_generation_is_deterministic(self):
        for fen in FEN_CORPUS:
            with self.subTest(fen=fen):
                first = uci_list(Position.from_fen(fen))
                second = uci_list(Position.from_fen(fen))
                self.assertEqual(first, second)
                position = Position.from_fen(fen)
                self.assertEqual(uci_list(position), uci_list(position))

    def test_all_moves_make_and_unmake_exactly(self):
        for fen in FEN_CORPUS:
            position = Position.from_fen(fen)
            for move in position.legal_moves():
                with self.subTest(fen=fen, uci=move.uci()):
                    before = snapshot(position)
                    stack_before = len(position._stack)
                    position.make_move(move)
                    self.assertEqual(len(position._stack), stack_before + 1)
                    position.unmake_move()
                    self.assertEqual(snapshot(position), before)
                    self.assertEqual(len(position._stack), stack_before)

    def test_random_walk_restores_every_state(self):
        rng = random.Random(20261121)
        position = Position.from_fen(START_FEN)
        snapshots = []
        for _ in range(120):
            moves = position.legal_moves()
            if not moves:
                break
            snapshots.append(snapshot(position))
            position.make_move(rng.choice(moves))

        self.assertGreater(len(snapshots), 60)
        while snapshots:
            expected = snapshots.pop()
            position.unmake_move()
            self.assertEqual(snapshot(position), expected)
        with self.assertRaises(ValueError):
            position.unmake_move()

    def test_perft_restores_position(self):
        position = Position.from_fen(KIWIPETE)
        before = snapshot(position)
        position.perft(2)
        self.assertEqual(snapshot(position), before)

    def test_attack_detection(self):
        position = Position.from_fen(START_FEN)
        self.assertTrue(position.is_attacked(parse_square("d3"), WHITE))
        self.assertTrue(position.is_attacked(parse_square("c3"), WHITE))
        self.assertFalse(position.is_attacked(parse_square("e4"), WHITE))
        self.assertTrue(position.is_attacked(parse_square("d6"), BLACK))
        self.assertFalse(position.is_attacked(parse_square("e5"), BLACK))

        sliding = Position.from_fen("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")
        self.assertTrue(sliding.is_attacked(parse_square("a8"), WHITE))
        self.assertFalse(sliding.is_attacked(parse_square("e8"), WHITE))

    def test_checkmate_and_stalemate(self):
        checkmate = Position.from_fen(CHECKMATE_FEN)
        self.assertTrue(checkmate.in_check())
        self.assertTrue(checkmate.is_checkmate())
        self.assertFalse(checkmate.is_stalemate())
        self.assertEqual(checkmate.legal_moves(), [])

        stalemate = Position.from_fen(STALEMATE_FEN)
        self.assertFalse(stalemate.in_check())
        self.assertTrue(stalemate.is_stalemate())
        self.assertFalse(stalemate.is_checkmate())
        self.assertEqual(stalemate.legal_moves(), [])

        start = Position.from_fen(START_FEN)
        self.assertFalse(start.is_checkmate())
        self.assertFalse(start.is_stalemate())


# ---------------------------------------------------------------------------
# Castling
# ---------------------------------------------------------------------------


class TestCastling(unittest.TestCase):
    def test_white_kingside_castling(self):
        position = Position.from_fen(CASTLE_FEN)
        move = find_move(position, "e1g1")
        self.assertEqual(move.flag, 3)  # FLAG_CASTLE_KING
        position.make_move(move)
        self.assertEqual(position.board[parse_square("g1")], KING | WHITE)
        self.assertEqual(position.board[parse_square("f1")], ROOK | WHITE)
        self.assertEqual(position.board[parse_square("e1")], 0)
        self.assertEqual(position.board[parse_square("h1")], 0)
        self.assertEqual(
            position.to_fen(),
            "r3k2r/8/8/8/8/8/8/R4RK1 b kq - 1 1",
        )

    def test_white_queenside_castling(self):
        position = Position.from_fen(CASTLE_FEN)
        move = find_move(position, "e1c1")
        self.assertEqual(move.flag, 4)  # FLAG_CASTLE_QUEEN
        position.make_move(move)
        self.assertEqual(position.board[parse_square("c1")], KING | WHITE)
        self.assertEqual(position.board[parse_square("d1")], ROOK | WHITE)
        self.assertEqual(position.board[parse_square("e1")], 0)
        self.assertEqual(position.board[parse_square("a1")], 0)
        self.assertEqual(
            position.to_fen(),
            "r3k2r/8/8/8/8/8/8/2KR3R b kq - 1 1",
        )

    def test_black_castling(self):
        kingside = Position.from_fen(CASTLE_FEN_BLACK)
        kingside.make_move(find_move(kingside, "e8g8"))
        self.assertEqual(
            kingside.to_fen(),
            "r4rk1/8/8/8/8/8/8/R3K2R w KQ - 1 2",
        )

        queenside = Position.from_fen(CASTLE_FEN_BLACK)
        queenside.make_move(find_move(queenside, "e8c8"))
        self.assertEqual(
            queenside.to_fen(),
            "2kr3r/8/8/8/8/8/8/R3K2R w KQ - 1 2",
        )

    def test_castling_is_not_generated_through_check(self):
        # The black rook on f8 attacks f1.
        position = Position.from_fen("r3kr2/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        moves = uci_list(position)
        self.assertNotIn("e1g1", moves)
        self.assertIn("e1c1", moves)

    def test_castling_is_not_generated_into_check(self):
        # The black rook on g8 attacks g1.
        position = Position.from_fen("r3k1r1/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        moves = uci_list(position)
        self.assertNotIn("e1g1", moves)
        self.assertIn("e1c1", moves)

    def test_castling_is_not_generated_out_of_check(self):
        # The black rook on e8 checks the white king on e1.
        position = Position.from_fen("1k2r3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        self.assertTrue(position.in_check())
        moves = uci_list(position)
        self.assertNotIn("e1g1", moves)
        self.assertNotIn("e1c1", moves)

    def test_queenside_castling_through_attacked_b1_is_legal(self):
        # b1 is attacked by the black rook on b8, but only the king's path
        # e1-d1-c1 must be safe; the rook may pass through b1.
        position = Position.from_fen("1r2k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        self.assertIn("e1c1", uci_list(position))

    def test_castling_is_blocked_by_a_piece(self):
        position = Position.from_fen("r3k2r/8/8/8/8/8/8/R3KB1R w KQkq - 0 1")
        moves = uci_list(position)
        self.assertNotIn("e1g1", moves)
        self.assertIn("e1c1", moves)

    def test_castling_rights_lost_after_rook_move(self):
        position = Position.from_fen(CASTLE_FEN)
        position.make_move(find_move(position, "h1h2"))
        self.assertEqual(position.castling, CASTLE_WQ | CASTLE_BK | CASTLE_BQ)
        self.assertEqual(
            position.to_fen(),
            "r3k2r/8/8/8/8/8/7R/R3K3 b Qkq - 1 1",
        )
        self.assertNotIn("e1g1", uci_list(position))

    def test_castling_rights_lost_after_king_move(self):
        position = Position.from_fen(CASTLE_FEN)
        position.make_move(find_move(position, "e1e2"))
        self.assertEqual(position.castling, CASTLE_BK | CASTLE_BQ)
        self.assertEqual(
            position.to_fen(),
            "r3k2r/8/8/8/8/8/4K3/R6R b kq - 1 1",
        )

    def test_castling_right_lost_when_rook_is_captured(self):
        position = Position.from_fen(CASTLE_FEN_BLACK)
        position.make_move(find_move(position, "a8a1"))
        self.assertEqual(position.castling, CASTLE_WK | CASTLE_BK)
        self.assertEqual(
            position.to_fen(),
            "4k2r/8/8/8/8/8/8/r3K2R w Kk - 0 2",
        )


# ---------------------------------------------------------------------------
# En passant
# ---------------------------------------------------------------------------


class TestEnPassant(unittest.TestCase):
    def test_en_passant_capture(self):
        position = Position.from_fen(EP_FEN)
        move = find_move(position, "e5d6")
        self.assertEqual(move.flag, FLAG_EN_PASSANT)
        before = snapshot(position)
        position.make_move(move)
        self.assertEqual(position.board[parse_square("d6")], PAWN | WHITE)
        self.assertEqual(position.board[parse_square("d5")], 0)
        self.assertIsNone(position.ep_square)
        self.assertEqual(position.halfmove_clock, 0)
        self.assertEqual(position.fullmove_number, 3)
        self.assertEqual(
            position.to_fen(),
            "rnbqkbnr/ppp1pppp/3P4/8/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 3",
        )
        position.unmake_move()
        self.assertEqual(snapshot(position), before)

    def test_en_passant_capture_exposing_own_king_is_illegal(self):
        # Capturing d3 en passant removes both the e4 pawn and the d4 pawn,
        # opening the fourth rank from the black king a4 to the white queen h4.
        position = Position.from_fen(EP_PIN_FEN)
        moves = uci_list(position)
        self.assertNotIn("e4d3", moves)
        self.assertIn("e4e3", moves)

    def test_en_passant_is_available_only_immediately(self):
        position = Position.from_fen(START_FEN)
        position.make_move(find_move(position, "e2e4"))
        self.assertEqual(position.ep_square, parse_square("e3"))
        position.make_move(find_move(position, "g8f6"))
        self.assertIsNone(position.ep_square)

    def test_non_double_push_clears_en_passant(self):
        position = Position.from_fen(EP_FEN)
        position.make_move(find_move(position, "g1f3"))
        self.assertIsNone(position.ep_square)
        self.assertIn(" - ", position.to_fen())

    def test_double_push_sets_en_passant_square(self):
        position = Position.from_fen(START_FEN)
        move = find_move(position, "e2e4")
        self.assertEqual(move.flag, 1)  # FLAG_DOUBLE_PUSH
        position.make_move(move)
        self.assertEqual(position.ep_square, parse_square("e3"))
        self.assertEqual(square_name(position.ep_square), "e3")


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------


class TestPromotion(unittest.TestCase):
    def test_white_push_promotions(self):
        expected_piece = {"q": QUEEN, "r": ROOK, "b": 3, "n": KNIGHT}
        for letter, piece_type in expected_piece.items():
            position = Position.from_fen(PROMOTION_FEN)
            move = find_move(position, f"a7a8{letter}")
            self.assertEqual(move.promotion, piece_type)
            position.make_move(move)
            self.assertEqual(position.board[parse_square("a8")], piece_type | WHITE)
            self.assertIsNone(position.ep_square)
            self.assertEqual(position.halfmove_clock, 0)
            position.unmake_move()

    def test_white_promotion_fen(self):
        position = Position.from_fen(PROMOTION_FEN)
        position.make_move(find_move(position, "a7a8q"))
        self.assertEqual(
            position.to_fen(),
            "Qn6/8/8/8/8/8/7p/4K2k b - - 0 1",
        )

    def test_white_capture_promotions(self):
        for letter in "qrbn":
            position = Position.from_fen(PROMOTION_FEN)
            move = find_move(position, f"a7b8{letter}")
            self.assertNotEqual(move.promotion, 0)
            position.make_move(move)
            self.assertEqual(position.board[parse_square("b8")] & BLACK, 0)
            self.assertEqual(position.board[parse_square("b8")] & 7, move.promotion)
            position.unmake_move()

    def test_white_capture_promotion_fen(self):
        position = Position.from_fen(PROMOTION_FEN)
        position.make_move(find_move(position, "a7b8q"))
        self.assertEqual(
            position.to_fen(),
            "1Q6/8/8/8/8/8/7p/4K2k b - - 0 1",
        )

    def test_black_promotion(self):
        position = Position.from_fen("4k3/8/8/8/8/8/p7/4K3 b - - 0 1")
        position.make_move(find_move(position, "a2a1q"))
        self.assertEqual(position.board[parse_square("a1")], QUEEN | BLACK)
        self.assertEqual(
            position.to_fen(),
            "4k3/8/8/8/8/8/8/q3K3 w - - 0 2",
        )

    def test_black_capture_promotion(self):
        position = Position.from_fen("4k3/8/8/8/8/8/p7/1N2K3 b - - 0 1")
        position.make_move(find_move(position, "a2b1q"))
        self.assertEqual(position.board[parse_square("b1")], QUEEN | BLACK)
        self.assertEqual(
            position.to_fen(),
            "4k3/8/8/8/8/8/8/1q2K3 w - - 0 2",
        )

    def test_promotion_resets_halfmove_clock(self):
        position = Position.from_fen("1n6/P7/8/8/8/8/7p/4K2k w - - 9 20")
        position.make_move(find_move(position, "a7a8q"))
        self.assertEqual(position.halfmove_clock, 0)
        self.assertEqual(
            position.to_fen(),
            "Qn6/8/8/8/8/8/7p/4K2k b - - 0 20",
        )


# ---------------------------------------------------------------------------
# Perft
# ---------------------------------------------------------------------------


class TestPerft(unittest.TestCase):
    def test_standard_perft_suite(self):
        for name, fen, cases in PERFT_CASES:
            position = Position.from_fen(fen)
            before = position.to_fen()
            for depth, expected in cases:
                start = time.perf_counter()
                actual = position.perft(depth)
                elapsed = time.perf_counter() - start
                print(
                    f"perft {name:11s} depth {depth}: {actual:>9d} "
                    f"(expected {expected:>9d}) {elapsed:8.2f}s",
                    flush=True,
                )
                self.assertEqual(
                    actual,
                    expected,
                    f"{name} perft({depth}): expected {expected}, got {actual}",
                )
                self.assertEqual(position.to_fen(), before)

    def test_promotion_heavy_perft(self):
        position = Position.from_fen(PROMOTION_PERFT)
        for depth, expected in ((1, 24), (2, 496)):
            start = time.perf_counter()
            actual = position.perft(depth)
            elapsed = time.perf_counter() - start
            print(
                f"perft promotion   depth {depth}: {actual:>9d} "
                f"(expected {expected:>9d}) {elapsed:8.2f}s",
                flush=True,
            )
            self.assertEqual(actual, expected)

    def test_castling_position_perft_one(self):
        position = Position.from_fen(CASTLE_FEN)
        self.assertEqual(position.perft(1), 26)

    def test_perft_depth_validation(self):
        position = Position.from_fen(START_FEN)
        self.assertEqual(position.perft(0), 1)
        with self.assertRaises(ValueError):
            position.perft(-1)
        with self.assertRaises(TypeError):
            position.perft(True)
        with self.assertRaises(TypeError):
            position.perft(1.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
