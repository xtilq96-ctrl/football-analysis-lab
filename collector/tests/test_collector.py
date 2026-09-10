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
                        "homeTeamCode": "ULS",
                        "awayTeamCode": "SEO",
                        "homeTeamAbbEnName": "Ulsan",
                        "awayTeamAbbEnName": "Seoul",
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
        recommendations, _decisions = collector.build_recommendations([first, second], ["2026-09-08"])
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

    def test_settlement_uses_the_immutable_locked_prediction(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = collector.connect_database(Path(directory) / "test.sqlite3")
            collector.save_matches(
                connection, collector.flatten_matches(SAMPLE), "2026-09-08T08:00:00+00:00"
            )
            current = json.loads(connection.execute(
                "SELECT payload FROM current_matches WHERE match_id='2041345'"
            ).fetchone()[0])
            locked_analysis = dict(current["analysis"])
            locked_analysis.update({"prediction": "主胜", "modelVersion": "locked-test"})
            connection.execute(
                "INSERT INTO locked_predictions(match_id,payload,locked_at) VALUES (?,?,?)",
                ("2041345", json.dumps({"analysis": locked_analysis}), "2026-09-08T08:30:00+00:00"),
            )
            collector.settle_match_results(connection, [{
                "matchId": 2041345, "matchResultStatus": "2",
                "sectionsNo1": "1:0", "sectionsNo999": "2:0",
            }], "2026-09-08T10:00:00+00:00")
            row = connection.execute(
                "SELECT predicted_outcome,outcome_hit FROM prediction_settlements"
            ).fetchone()
            self.assertEqual(row, ("主胜", 1))
            connection.close()

    def test_early_match_uses_its_own_deadline(self):
        match = collector.normalized(
            collector.flatten_matches(SAMPLE)[0], "2026-09-08T02:00:00+00:00"
        )
        now = collector.datetime(2026, 9, 8, 17, 15, tzinfo=collector.SHANGHAI)
        schedule = collector.analysis_schedule(match, now)
        self.assertTrue(schedule["isEarlyMatch"])
        self.assertEqual(schedule["phase"], "最终分析")
        self.assertEqual(schedule["finalAnalysisAt"][11:16], "17:00")

    def test_matches_api_fixture_and_builds_recent_form(self):
        match = collector.normalized(
            collector.flatten_matches(SAMPLE)[0], "2026-09-08T02:00:00+00:00"
        )
        kickoff = collector.parse_kickoff(match)
        fixture = {
            "fixture": {"id": 99, "timestamp": int(kickoff.timestamp()), "status": {"short": "NS"}},
            "teams": {
                "home": {"id": 1, "name": "Ulsan HD"},
                "away": {"id": 2, "name": "FC Seoul"},
            },
            "goals": {"home": None, "away": None},
        }
        selected, confidence = collector.match_api_fixture(match, [fixture])
        self.assertEqual(selected["fixture"]["id"], 99)
        self.assertGreaterEqual(confidence, 0.72)

        history = []
        for index, score in enumerate([(2, 0), (1, 1), (0, 1), (3, 0), (1, 0)]):
            history.append({
                "fixture": {
                    "timestamp": int((kickoff - collector.timedelta(days=index + 4)).timestamp()),
                    "status": {"short": "FT"},
                },
                "teams": {"home": {"id": 1}, "away": {"id": 10 + index}},
                "goals": {"home": score[0], "away": score[1]},
            })
        summary = collector.team_form_summary(history, 1, "home", kickoff)
        self.assertEqual(summary["matches"], 5)
        self.assertEqual(summary["wins"], 3)
        self.assertEqual(summary["cleanSheetRate"], 60.0)

    def test_fundamentals_adjust_market_probability(self):
        base = collector.market_analysis(collector.flatten_matches(SAMPLE)[0])
        fundamentals = {
            "status": "ready",
            "home": {
                "form": {"matches": 5, "pointsPerGame": 2.4, "goalsForPerGame": 2.0,
                         "goalsAgainstPerGame": 0.6, "cleanSheetRate": 60, "restDays": 6,
                         "venue": {"matches": 5, "pointsPerGame": 2.6,
                                   "goalsForPerGame": 2.2, "goalsAgainstPerGame": 0.4}},
                "absences": {"injuries": 0, "suspensions": 0},
            },
            "away": {
                "form": {"matches": 5, "pointsPerGame": 0.8, "goalsForPerGame": 0.8,
                         "goalsAgainstPerGame": 1.8, "cleanSheetRate": 20, "restDays": 3,
                         "venue": {"matches": 4, "pointsPerGame": 0.5,
                                   "goalsForPerGame": 0.5, "goalsAgainstPerGame": 2.0}},
                "absences": {"injuries": 2, "suspensions": 1},
            },
        }
        adjusted = collector.blend_fundamentals(base, fundamentals)
        self.assertEqual(adjusted["modelVersion"], "v2-market-fundamentals")
        self.assertGreater(adjusted["probabilities"]["home"], base["probabilities"]["home"])

    def test_candidate_model_stays_between_market_and_fundamental_model(self):
        base = collector.market_analysis(collector.flatten_matches(SAMPLE)[0])
        primary = json.loads(json.dumps(base, ensure_ascii=False))
        primary["probabilities"] = {"home": 18.0, "draw": 22.0, "away": 60.0}
        candidate = collector.calibrated_candidate(base, primary)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["modelVersion"], collector.SHADOW_MODEL_VERSION)
        self.assertGreater(candidate["probabilities"]["away"], base["probabilities"]["away"])
        self.assertLess(candidate["probabilities"]["away"], primary["probabilities"]["away"])

    def test_model_upgrade_waits_for_enough_paired_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = collector.connect_database(Path(directory) / "test.sqlite3")
            summary = collector.model_governance_summary(connection)
            self.assertEqual(summary["decision"], "collecting")
            self.assertFalse(summary["gates"]["enoughSamples"])
            connection.close()

    def test_builds_form_from_official_sporttery_history(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = collector.connect_database(Path(directory) / "test.sqlite3")
            results = []
            for index, score in enumerate([(2, 0), (1, 1), (0, 1), (3, 0), (1, 0)]):
                results.append({
                    "matchId": 9000 + index,
                    "matchDate": f"2026-08-{30 - index:02d}",
                    "matchResultStatus": "2",
                    "sectionsNo999": f"{score[0]}:{score[1]}",
                    "homeTeamId": 1192,
                    "awayTeamId": 8000 + index,
                    "allHomeTeam": "江原FC",
                    "allAwayTeam": f"对手{index}",
                    "leagueId": 48,
                    "leagueName": "韩国职业联赛",
                })
            saved = collector.save_official_history(
                connection, results, "2026-09-01T00:00:00+00:00"
            )
            self.assertEqual(saved, 5)
            summary = collector.official_history_form_summary(
                connection,
                1192,
                "home",
                collector.datetime(2026, 9, 8, 18, 30, tzinfo=collector.SHANGHAI),
            )
            self.assertEqual(summary["matches"], 5)
            self.assertEqual(summary["wins"], 3)
            self.assertEqual(summary["cleanSheetRate"], 60.0)
            self.assertEqual(summary["restDays"], 9)
            connection.close()


if __name__ == "__main__":
    unittest.main()
