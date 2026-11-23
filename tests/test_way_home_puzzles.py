"""Check both localized boards and the supported controls of every puzzle."""

import json
from pathlib import Path
import unittest

from services.adventure_puzzle import run_puzzle

CASES = json.loads(Path(__file__).with_name("way_home_cases.json").read_text(encoding="utf-8"))


def puzzle_row(case, moves=()):
    return {
        "region": case["region"],
        "gate": case["gate"],
        "attempt_count": case["variant"] + 1,
        "moves": list(moves),
    }


class WayHomePuzzles(unittest.TestCase):
    def test_every_puzzle_has_a_correct_answer_and_rejects_a_blank_submission(self):
        self.assertEqual(len({(c["region"], c["gate"], c["variant"]) for c in CASES}), 120)
        for case in CASES:
            with self.subTest(region=case["region"], gate=case["gate"], variant=case["variant"]):
                self.assertEqual(run_puzzle(puzzle_row(case), "submit", "ko"), {"correct": False})
                solved = puzzle_row(case, case["moves"])
                self.assertEqual(run_puzzle(solved, "submit", "ko", answer=case["answer"]), {"correct": True})

    def test_both_language_boards_return_only_inert_controls_and_clues(self):
        for case in CASES:
            for lang in ("ko", "en"):
                with self.subTest(region=case["region"], gate=case["gate"], variant=case["variant"], lang=lang):
                    board = run_puzzle(puzzle_row(case), "read", lang)
                    self.assertEqual(set(board), {"title", "instruction", "board", "clues"})
                    self.assertTrue(board["board"])
                    self.assertNotIn("onclick", json.dumps(board["board"]))
                    self.assertNotIn("undefined", board["instruction"])

    def test_unknown_control_is_rejected(self):
        self.assertEqual(
            run_puzzle(puzzle_row(CASES[0]), "move", "en", move="jf_99"),
            {"invalid": True},
        )

    def test_invalid_text_cannot_make_a_text_puzzle_successful(self):
        case = next(c for c in CASES if c["answer"])
        self.assertEqual(run_puzzle(puzzle_row(case), "submit", "en", answer="incorrect"), {"correct": False})


if __name__ == "__main__":
    unittest.main()
