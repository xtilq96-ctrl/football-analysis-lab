import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("collector", Path(__file__).with_name("collector.py"))
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def match(index: int, probability: float, league: str = "联赛A") -> dict:
    remaining = round((100 - probability) / 2, 2)
    return {
        "matchId": str(index), "businessDate": "2026-09-10", "officialNumber": f"周四{index:03d}",
        "league": league, "home": f"主队{index}", "away": f"客队{index}",
        "had": {"h": "1.80", "d": "3.80", "a": "4.20"},
        "analysis": {
            "prediction": "主胜", "confidence": probability, "risk": "低风险", "marketMargin": 5,
            "probabilities": {"home": probability, "draw": remaining, "away": remaining},
            "marketProbabilities": {"home": probability - 2, "draw": remaining + 1, "away": remaining + 1},
        },
        "analysisSchedule": {"phase": "持续更新", "isLocked": False},
    }


class DynamicRecommendationTests(unittest.TestCase):
    def test_returns_no_pick_when_fewer_than_two_solid_matches(self) -> None:
        recommendations, decisions = collector.build_recommendations([match(1, 51), match(2, 46)], ["2026-09-10"])
        self.assertEqual(recommendations["2026-09-10"], [])
        self.assertEqual(decisions["2026-09-10"]["status"], "no_pick")

    def test_selects_three_legs_when_three_strong_matches_qualify(self) -> None:
        matches = [match(1, 66, "联赛A"), match(2, 62, "联赛B"), match(3, 58, "联赛C")]
        recommendations, decisions = collector.build_recommendations(matches, ["2026-09-10"])
        self.assertEqual(decisions["2026-09-10"]["legCount"], 3)
        self.assertEqual(recommendations["2026-09-10"][0]["type"], "3串1")

    def test_selects_four_legs_only_when_joint_probability_qualifies(self) -> None:
        matches = [match(1, 66, "联赛A"), match(2, 64, "联赛B"), match(3, 62, "联赛C"), match(4, 60, "联赛D")]
        recommendations, decisions = collector.build_recommendations(matches, ["2026-09-10"])
        self.assertEqual(decisions["2026-09-10"]["legCount"], 4)
        self.assertEqual(len(recommendations["2026-09-10"][0]["legs"]), 4)


if __name__ == "__main__":
    unittest.main()
