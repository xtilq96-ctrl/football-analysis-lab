import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "collector.py"
SPEC = importlib.util.spec_from_file_location("football_ai_collector", MODULE_PATH)
collector = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(collector)


SAMPLE = {
    "success": True,
    "errorCode": "0",
    "value": {
        "matchInfoList": [
            {
                "businessDate": "2026-09-08",
                "subMatchList": [
                    {
                        "matchId": 2041345,
                        "matchNum": 2001,
                        "matchNumStr": "周二001",
                        "matchWeek": "周二",
                        "matchDate": "2026-09-08",
                        "matchTime": "18:30:00",
                        "leagueAllName": "韩国职业联赛",
                        "homeTeamAllName": "蔚山现代",
                        "awayTeamAllName": "首尔FC",
                        "sellStatus": "1",
                        "had": {"h": "3.29", "d": "3.58", "a": "1.83"},
                        "hhad": {"h": "1.74", "d": "3.80", "a": "3.43", "goalLine": "+1"},
                    }
                ],
            }
        ]
    },
}


class CollectorTests(unittest.TestCase):
    def test_flattens_and_analyses_official_payload(self):
        matches = collector.flatten_matches(SAMPLE)
        self.assertEqual(len(matches), 1)
        item = collector.normalized(matches[0], "2026-09-08T08:00:00+00:00")
        self.assertEqual(item["officialNumber"], "周二001")
        self.assertEqual(item["analysis"]["prediction"], "客胜")
        self.assertAlmostEqual(sum(item["analysis"]["probabilities"].values()), 100, places=1)
        self.assertRegex(item["analysis"]["predictedScore"], r"^\d+-\d+$")
        predicted_home, predicted_away = map(int, item["analysis"]["predictedScore"].split("-"))
        self.assertLess(predicted_home, predicted_away)
        self.assertEqual(len(item["analysis"]["scoreProbabilities"]), 5)
        self.assertAlmostEqual(
            sum(item["analysis"]["totalGoalsProbabilities"].values()), 100, places=1
        )

    def test_deduplicates_the_same_match_from_multiple_pool_groups(self):
        duplicate = json.loads(json.dumps(SAMPLE, ensure_ascii=False))
        duplicate["value"]["matchInfoList"].append(
            json.loads(json.dumps(duplicate["value"]["matchInfoList"][0], ensure_ascii=False))
        )
        self.assertEqual(len(collector.flatten_matches(duplicate)), 1)

    def test_keeps_match_after_it_disappears_from_live_feed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.sqlite3"
            connection = collector.connect_database(path)
            matches = collector.flatten_matches(SAMPLE)
            collector.save_matches(connection, matches, "2026-09-08T08:00:00+00:00")
            count = connection.execute("SELECT COUNT(*) FROM current_matches").fetchone()[0]
            self.assertEqual(count, 1)
            collector.save_matches(connection, [], "2026-09-08T10:00:00+00:00")
            count = connection.execute("SELECT COUNT(*) FROM current_matches").fetchone()[0]
            self.assertEqual(count, 1)
            connection.close()

    def test_odds_history_only_adds_changed_prices(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = collector.connect_database(Path(directory) / "test.sqlite3")
            matches = collector.flatten_matches(SAMPLE)
            collector.save_matches(connection, matches, "2026-09-08T08:00:00+00:00")
            collector.save_matches(connection, matches, "2026-09-08T08:05:00+00:00")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM odds_history").fetchone()[0], 1)
            changed = json.loads(json.dumps(SAMPLE, ensure_ascii=False))
            changed["value"]["matchInfoList"][0]["subMatchList"][0]["had"]["h"] = "3.20"
            collector.save_matches(connection, collector.flatten_matches(changed), "2026-09-08T08:10:00+00:00")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM odds_history").fetchone()[0], 2)
            collector.save_matches(connection, matches, "2026-09-08T08:15:00+00:00")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM odds_history").fetchone()[0], 3)
            connection.close()

    def test_builds_two_leg_recommendations_without_reusing_a_match(self):
        sources = collector.flatten_matches(SAMPLE)
        first = collector.normalized(sources[0], "2026-09-08T08:00:00+00:00")
        second = json.loads(json.dumps(first, ensure_ascii=False))
        second.update({"matchId": "2041346", "officialNumber": "周二002", "matchNumber": 2002, "league": "欧洲冠军联赛"})
        recommendations = collector.build_recommendations([first, second], ["2026-09-08"])
        self.assertLessEqual(len(recommendations["2026-09-08"]), 1)
        if recommendations["2026-09-08"]:
            legs = recommendations["2026-09-08"][0]["legs"]
            self.assertNotEqual(legs[0]["matchId"], legs[1]["matchId"])

    def test_settles_predictions_against_official_full_time_score(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = collector.connect_database(Path(directory) / "test.sqlite3")
            collector.save_matches(
                connection, collector.flatten_matches(SAMPLE), "2026-09-08T08:00:00+00:00"
            )
            completed, settled = collector.settle_match_results(
                connection,
                [{
                    "matchId": 2041345,
                    "matchResultStatus": "2",
                    "sectionsNo1": "0:1",
                    "sectionsNo999": "0:2",
                    "winFlag": "A",
                }],
                "2026-09-08T10:00:00+00:00",
            )
            self.assertEqual((completed, settled), (1, 1))
            row = connection.execute(
                "SELECT actual_outcome,outcome_hit,actual_score FROM prediction_settlements"
            ).fetchone()
            self.assertEqual(row, ("客胜", 1, "0-2"))
            performance = collector.performance_summary(connection)
            self.assertEqual(performance["settledMatches"], 1)
            self.assertEqual(performance["outcomeHitRate"], 100.0)
            connection.close()


if __name__ == "__main__":
    unittest.main()
