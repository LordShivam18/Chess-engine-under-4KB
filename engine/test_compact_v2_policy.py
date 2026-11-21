"""V2-only node-policy assertions; does not alter the V1 compact suite."""
import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("compact_v2.py")
SPEC = importlib.util.spec_from_file_location("compact_v2_policy_subject", SOURCE)
compact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compact)

class TestV2NodePolicy(unittest.TestCase):
    def assert_tier(self, opponent, base):
        self.assertEqual(compact.lim(opponent, 60), base)
        self.assertEqual(compact.lim(opponent, 61), base * 3 // 4)
        self.assertEqual(compact.lim(opponent, 100), base * 3 // 4)
        self.assertEqual(compact.lim(opponent, 101), base // 2)

    def test_depth_tiers_and_thresholds(self):
        self.assert_tier("depth-2", 18000)
        self.assert_tier("depth-3", 30000)
        self.assert_tier("depth-4", 18000)

    def test_nodes_tiers_and_thresholds(self):
        for opponent in ("nodes-100k", "nodes-250k", "nodes-500k",
                         "nodes-1M", "nodes-2M", "nodes-750k"):
            with self.subTest(opponent=opponent):
                self.assert_tier(opponent, 30000)

    def test_invalid_identifiers_remain_rejected(self):
        for opponent in ("depthish-2", "nodes-fast"):
            with self.subTest(opponent=opponent):
                with self.assertRaises(ValueError):
                    compact.lim(opponent, 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
