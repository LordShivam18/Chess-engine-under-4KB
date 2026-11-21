"""Independent tests for the compact engine.

Run with: python engine/test_compact.py
"""

import http.server
import json
import os
import random
import subprocess
import sys
import threading
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import compact
import engine

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
POS3 = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"
POS4 = "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1"
POS5 = "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8"
POS6 = "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10"
PROMOTION = "n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1"
CASTLE = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
CASTLE_BLACK = "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1"
CASTLE_K_CHECK = "4kr2/8/8/8/8/8/8/4K2R w K - 0 1"
CASTLE_Q_CHECK = "3rkr2/8/8/8/8/8/8/R3K2R w KQ - 0 1"
EP = "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3"
EP_PIN = "8/8/8/8/k2Pp2Q/8/8/4K3 b - d3 0 1"
PROMO_FEN = "1n6/P7/8/8/8/8/7p/4K2k w - - 0 1"
PROMO_CAPTURE = "1r6/P7/8/8/8/8/7p/4K2k w - - 0 1"
CHECKMATE = "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1"
STALEMATE = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"

FENS = (
    START, KIWIPETE, POS3, POS4, POS5, POS6, CASTLE, CASTLE_BLACK,
    CASTLE_K_CHECK, CASTLE_Q_CHECK, EP, EP_PIN, PROMO_FEN, PROMO_CAPTURE,
    CHECKMATE, STALEMATE,
)

PERFT_CASES = (
    ("start", START, ((1, 20), (2, 400), (3, 8902), (4, 197281), (5, 4865609))),
    ("kiwipete", KIWIPETE, ((1, 48), (2, 2039), (3, 97862), (4, 4085603))),
    ("position-3", POS3, ((1, 14), (2, 191), (3, 2812), (4, 43238), (5, 674624))),
    ("position-4", POS4, ((1, 6), (2, 264), (3, 9467), (4, 422333))),
    ("position-5", POS5, ((1, 44), (2, 1486), (3, 62379), (4, 2103487))),
    ("position-6", POS6, ((1, 46), (2, 2079), (3, 89890), (4, 3894594))),
    ("promotion", PROMOTION, ((1, 24), (2, 496))),
)


def phase1_legal(fen):
    return engine.Position.from_fen(fen).legal_moves()


CP = {v: k for k, v in compact.PC.items()}


def to_fen(pos):
    rows = []
    for rank in range(7, -1, -1):
        row = []
        empty = 0
        for file in range(8):
            piece = pos.b[(rank + 2) * 10 + file + 1]
            if piece:
                if empty:
                    row.append(str(empty))
                    empty = 0
                row.append(CP[piece])
            else:
                empty += 1
        if empty:
            row.append(str(empty))
        rows.append("".join(row))
    castling = "".join(
        ch for bit, ch in ((1, "K"), (2, "Q"), (4, "k"), (8, "q")) if pos.c & bit
    ) or "-"
    ep = "-" if not pos.e else compact.nm(pos.e)
    side = "w" if pos.s == compact.W else "b"
    return f"{'/'.join(rows)} {side} {castling} {ep} {pos.h} {pos.m}"


def compact_legal(fen_text):
    return compact.Pos(fen_text).legal()


def perft(pos, depth):
    if depth == 0:
        return 1
    moves = pos.legal()
    if depth == 1:
        return len(moves)
    total = 0
    for move in moves:
        pos.push(move)
        total += perft(pos, depth - 1)
        pos.pop()
    return total


class TestRulesCore(unittest.TestCase):
    def test_legal_move_order_matches_phase1(self):
        for fen in FENS:
            expected = [str(m) for m in phase1_legal(fen)]
            actual = [compact.uci(m) for m in compact_legal(fen)]
            self.assertEqual(actual, expected, fen)

    def test_make_unmake_restores_state(self):
        for fen in FENS:
            pos = compact.Pos(fen)
            before = to_fen(pos)
            for move in pos.legal():
                pos.push(move)
                pos.pop()
                self.assertEqual(to_fen(pos), before, f"{fen} {compact.uci(move)}")

    def test_random_walk_matches_phase1(self):
        rng = random.Random(1234)
        for start in (START, KIWIPETE, POS5):
            a = engine.Position.from_fen(start)
            b = compact.Pos(start)
            for ply in range(60):
                am = a.legal_moves()
                bm = b.legal()
                self.assertEqual(
                    [str(m) for m in am],
                    [compact.uci(m) for m in bm],
                    f"{start} ply {ply}",
                )
                if not am:
                    break
                chosen = rng.choice(am)
                text = str(chosen)
                a.make_move(chosen)
                b.push(next(m for m in bm if compact.uci(m) == text))
                self.assertEqual(a.to_fen(), to_fen(b), f"{start} ply {ply} {text}")

    def test_castling_moves(self):
        white = {compact.uci(m) for m in compact_legal(CASTLE)}
        black = {compact.uci(m) for m in compact_legal(CASTLE_BLACK)}
        self.assertIn("e1g1", white)
        self.assertIn("e1c1", white)
        self.assertIn("e8g8", black)
        self.assertIn("e8c8", black)
        self.assertNotIn("e1g1", {compact.uci(m) for m in compact_legal(CASTLE_K_CHECK)})
        self.assertNotIn("e1c1", {compact.uci(m) for m in compact_legal(CASTLE_Q_CHECK)})

    def test_en_passant_moves(self):
        moves = {compact.uci(m) for m in compact_legal(EP)}
        self.assertIn("e5d6", moves)
        pinned = {compact.uci(m) for m in compact_legal(EP_PIN)}
        self.assertNotIn("e4d3", pinned)

    def test_promotion_moves(self):
        moves = {compact.uci(m) for m in compact_legal(PROMO_FEN)}
        for suffix in ("q", "r", "b", "n"):
            self.assertIn("a7a8" + suffix, moves)
        captures = {compact.uci(m) for m in compact_legal(PROMO_CAPTURE)}
        for suffix in ("q", "r", "b", "n"):
            self.assertIn("a7b8" + suffix, captures)

    def test_checkmate_and_stalemate(self):
        mate = compact.Pos(CHECKMATE)
        stale = compact.Pos(STALEMATE)
        self.assertTrue(mate.chk())
        self.assertEqual(mate.legal(), [])
        self.assertFalse(stale.chk())
        self.assertEqual(stale.legal(), [])


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.old_limit = compact.LIMIT
        compact.LIMIT = 20000

    def tearDown(self):
        compact.LIMIT = self.old_limit

    def choose(self, fen):
        legal = [compact.uci(m) for m in compact.Pos(fen).legal()]
        move = compact.choose(fen, legal)
        self.assertIn(move, legal)
        return move

    def test_mate_in_one(self):
        self.assertEqual(self.choose("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1"), "e1e8")

    def test_capture_hanging_queen(self):
        self.assertEqual(self.choose("4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"), "e1e2")

    def test_promotion(self):
        move = self.choose("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        self.assertEqual(move[:4], "a7a8")
        self.assertEqual(move[4], "q")

    def test_mate_avoidance_is_legal(self):
        fen = "4k3/8/8/8/8/8/8/4K2r w - - 0 1"
        legal = [compact.uci(m) for m in compact.Pos(fen).legal()]
        move = compact.choose(fen, legal)
        self.assertIn(move, legal)
        pos = compact.Pos(fen)
        pos.push(next(m for m in pos.legal() if compact.uci(m) == move))
        self.assertFalse(pos.chk())

    def test_repeatable(self):
        fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
        legal = [compact.uci(m) for m in compact.Pos(fen).legal()]
        first = compact.choose(fen, legal)
        first_nodes = compact.NODES
        for _ in range(2):
            self.assertEqual(compact.choose(fen, legal), first)
            self.assertEqual(compact.NODES, first_nodes)

    def test_node_limit(self):
        compact.LIMIT = 3000
        fen = KIWIPETE
        legal = [compact.uci(m) for m in compact.Pos(fen).legal()]
        move = compact.choose(fen, legal)
        self.assertIn(move, legal)
        self.assertLessEqual(compact.NODES, 3000)

    def test_low_node_abort_keeps_first_legal_move(self):
        compact.LIMIT = 1
        legal = [compact.uci(m) for m in compact.Pos(START).legal()]
        self.assertEqual(compact.choose(START, legal), legal[0])
        self.assertTrue(compact.ABORT)
        self.assertLessEqual(compact.NODES, compact.LIMIT)

    def test_abort_keeps_last_completed_iteration(self):
        legal = [compact.uci(m) for m in compact.Pos(START).legal()]
        old_root = compact.root
        completed = []

        def record(*args):
            result = old_root(*args)
            if result is not None:
                completed.append(result[0])
            return result

        try:
            compact.root = record
            compact.LIMIT = 50
            chosen = compact.choose(START, legal)
            self.assertTrue(compact.ABORT)
            self.assertTrue(completed)
            self.assertEqual(chosen, compact.uci(completed[-1]))
        finally:
            compact.root = old_root

    def test_qsearch_cutoff_resolves_check_and_scores_mate(self):
        saved = compact.POS, compact.NODES, compact.LIMIT, compact.ABORT, compact.ev
        try:
            compact.POS = compact.Pos(CHECKMATE)
            compact.NODES = 0
            compact.LIMIT = 100
            compact.ABORT = False
            self.assertEqual(compact.qs(-compact.MATE, compact.MATE, 12), -compact.MATE + 12)

            compact.POS = compact.Pos("4k3/8/8/8/8/8/8/4K2r w - - 0 1")
            original_ev = compact.ev

            def guarded_ev():
                self.assertFalse(compact.POS.chk(), "qsearch must not stand pat in check")
                return original_ev()

            compact.ev = guarded_ev
            compact.NODES = 0
            self.assertFalse(compact.ABORT)
            compact.qs(-compact.MATE, compact.MATE, 12)
            self.assertFalse(compact.ABORT)
        finally:
            compact.POS, compact.NODES, compact.LIMIT, compact.ABORT, compact.ev = saved

    def test_halfmove_clock_is_in_transposition_key(self):
        saved = compact.POS
        try:
            compact.POS = compact.Pos("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
            fresh_key = compact.hsh()
            compact.POS = compact.Pos("4k3/8/8/8/8/8/8/4K3 w - - 99 1")
            late_key = compact.hsh()
            self.assertNotEqual(fresh_key, late_key)
        finally:
            compact.POS = saved

    def test_mate_score_has_ply_distance(self):
        saved = compact.POS, compact.NODES, compact.LIMIT, compact.ABORT, dict(compact.TT)
        try:
            compact.POS = compact.Pos(CHECKMATE)
            compact.NODES = 0
            compact.LIMIT = 100
            compact.ABORT = False
            compact.TT.clear()
            self.assertEqual(compact.nega(1, -compact.MATE, compact.MATE, 7), -compact.MATE + 7)
        finally:
            compact.POS, compact.NODES, compact.LIMIT, compact.ABORT, old_tt = saved
            compact.TT.clear()
            compact.TT.update(old_tt)

    def test_worst_case_runtime(self):
        compact.LIMIT = 50000
        fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        legal = [compact.uci(m) for m in compact.Pos(fen).legal()]
        started = time.perf_counter()
        move = compact.choose(fen, legal)
        elapsed = time.perf_counter() - started
        print(f"worst-case search: {move} nodes={compact.NODES} time={elapsed:.2f}s", flush=True)
        self.assertIn(move, legal)
        self.assertLess(elapsed, 15.0)


class MockHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        state = self.server.state
        if self.path == "/game":
            state["game_calls"] += 1
            if state.get("resign_mode"):
                if state["game_calls"] == 1:
                    response = {
                        "game": 1, "status": "your_move",
                        "fen": START, "legal_moves": [], "opponent": "depth-2", "plies": 8,
                    }
                else:
                    response = {
                        "game": 1, "status": "done", "outcome": "resign",
                        "reason": "mock", "wins": 0, "draws": 0, "losses": 1,
                    }
            elif state["game_calls"] == 1:
                response = {
                    "game": 1, "status": "your_move",
                    "fen": state.get("fen", START), "legal_moves": state["legal"],
                    "opponent": state["opponent"], "plies": state["plies"],
                }
            else:
                response = {
                    "game": 1, "status": "done", "outcome": "win",
                    "reason": "mock", "wins": 1, "draws": 0, "losses": 0,
                }
        elif self.path == "/move":
            state["moves"].append(body.get("move"))
            response = {
                "game": 1, "status": "done", "outcome": "win",
                "reason": "mock", "wins": 1, "draws": 0, "losses": 0,
            }
        elif self.path == "/resign":
            state["resigned"] = True
            response = {
                "game": 1, "status": "done", "outcome": "resign",
                "reason": "mock", "wins": 0, "draws": 0, "losses": 1,
            }
        else:
            self.send_error(404)
            return
        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class TestHTTP(unittest.TestCase):
    def run_engine(self, resign_mode=False, opponent="depth-2", plies=8, fen=START, entry="compact.py"):
        state = {
            "game_calls": 0,
            "moves": [],
            "resigned": False,
            "resign_mode": resign_mode,
            "opponent": opponent,
            "plies": plies,
            "fen": fen,
            "legal": [str(m) for m in engine.Position.from_fen(START).legal_moves()],
        }
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
        server.state = state
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = os.environ.copy()
            env["MAKEFUN_ENV_URL"] = f"http://127.0.0.1:{server.server_address[1]}"
            env["PYTHONHASHSEED"] = "0"
            result = subprocess.run(
                [sys.executable, "-P", "-s", os.path.join(_HERE, entry)],
                env=env, capture_output=True, text=True, timeout=90,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        return result, state

    def test_game_and_move(self):
        result, state = self.run_engine()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(state["moves"]), 1, result.stderr)
        self.assertIn(state["moves"][0], state["legal"])

    def test_resign_when_no_legal_moves(self):
        result, state = self.run_engine(resign_mode=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(state["resigned"], result.stderr)
        self.assertEqual(state["moves"], [])

    def test_search_exception_uses_environment_first_legal_move(self):
        result, state = self.run_engine(opponent="nodes-2M", plies=101, fen="not a fen")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(state["moves"], [state["legal"][0]])
        self.assertFalse(state["resigned"])

    def test_packed_python313_game_and_move(self):
        result, state = self.run_engine(opponent="nodes-500k", plies=61,
                                        entry=os.path.join("..", "bot", "main.py"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(state["moves"]), 1, result.stderr)
        self.assertIn(state["moves"][0], state["legal"])


class TestNodePolicy(unittest.TestCase):
    def test_all_tiers_and_ply_branches(self):
        for opponent, base in (("depth-2", 18000), ("depth-3", 18000), ("depth-4", 18000), ("depth-99", 18000),
                               ("nodes-100k", 30000), ("nodes-250k", 30000),
                               ("nodes-500k", 30000), ("nodes-1M", 30000), ("nodes-2M", 30000), ("nodes-750k", 30000)):
            with self.subTest(opponent=opponent):
                self.assertEqual(compact.lim(opponent, 60), base)
                self.assertEqual(compact.lim(opponent, 61), base * 3 // 4)
                self.assertEqual(compact.lim(opponent, 100), base * 3 // 4)
                self.assertEqual(compact.lim(opponent, 101), base // 2)

    def test_unknown_opponent_is_rejected(self):
        with self.assertRaises(ValueError):
            compact.lim("depthish-2", 0)
        with self.assertRaises(ValueError):
            compact.lim("nodes-fast", 0)


class TestDeterminism(unittest.TestCase):
    def test_hash_seed_independence(self):
        script = r"""
import sys
sys.path.insert(0, sys.argv[1])
import compact
compact.LIMIT = 4000
cases = [
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
]
for fen in cases:
    legal = [compact.uci(m) for m in compact.Pos(fen).legal()]
    print(compact.choose(fen, legal))
"""
        outputs = []
        for seed in ("0", "1", "42", "12345"):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            result = subprocess.run(
                [sys.executable, "-c", script, _HERE],
                env=env, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
        for output in outputs[1:]:
            self.assertEqual(output, outputs[0])


class TestPerft(unittest.TestCase):
    def test_phase1_perft_suite(self):
        for name, fen, cases in PERFT_CASES:
            pos = compact.Pos(fen)
            for depth, expected in cases:
                started = time.perf_counter()
                actual = perft(pos, depth)
                elapsed = time.perf_counter() - started
                print(f"compact perft {name:12} depth {depth}: {actual:>9d} "
                      f"(expected {expected:>9d}) {elapsed:7.2f}s", flush=True)
                self.assertEqual(actual, expected, f"{name} perft({depth})")
                self.assertEqual(to_fen(pos), fen, f"{name} perft({depth}) restored")


if __name__ == "__main__":
    unittest.main(verbosity=2)
