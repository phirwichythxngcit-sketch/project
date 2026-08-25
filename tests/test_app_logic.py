import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path


def load_app():
    streamlit = types.ModuleType("streamlit")
    streamlit.cache_data = lambda **_kwargs: lambda func: func
    streamlit.session_state = {}
    streamlit.secrets = {}
    sys.modules["streamlit"] = streamlit
    sys.modules.setdefault("pandas", types.ModuleType("pandas"))
    plotly = types.ModuleType("plotly")
    plotly_express = types.ModuleType("plotly.express")
    sys.modules.setdefault("plotly", plotly)
    sys.modules.setdefault("plotly.express", plotly_express)

    path = Path(__file__).resolve().parents[1] / "app.py"
    spec = importlib.util.spec_from_file_location("app_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


app = load_app()


class SurveyNavigationTests(unittest.TestCase):
    def test_saved_list_answers_are_available_after_back_navigation(self):
        answers = [5, 4, 3]
        self.assertEqual(app.saved_answer_at(answers, 1), 4)
        self.assertIsNone(app.saved_answer_at(answers, 3))


class MixedScopeTests(unittest.TestCase):
    def setUp(self):
        self.architecture = next(
            faculty for faculty in app.FACULTIES
            if faculty["name"] == "สถาปัตยกรรมศาสตร์"
        )

    def test_non_dominant_ni_does_not_satisfy_dominant_route(self):
        strengths = {"Ti": 0, "Te": 0, "Fe": 0, "Fi": 0,
                     "Se": 0, "Si": 0, "Ne": 100, "Ni": 70}
        self.assertEqual(app.mbti_score(self.architecture, strengths), 0)

    def test_da_route_remains_available_for_ti(self):
        strengths = {"Ti": 80, "Te": 0, "Fe": 0, "Fi": 0,
                     "Se": 0, "Si": 0, "Ne": 100, "Ni": 70}
        self.assertEqual(app.mbti_score(self.architecture, strengths), 80)


class AdminHistoryAccessTests(unittest.TestCase):
    def setUp(self):
        self.original_secrets = app.st.secrets
        app.st.secrets = {"ADMIN_PASSWORD": "strong-test-password"}

    def tearDown(self):
        app.st.secrets = self.original_secrets

    def test_correct_password_authenticates_admin(self):
        self.assertTrue(app.is_admin_password("strong-test-password"))

    def test_wrong_password_cannot_authenticate_admin(self):
        self.assertFalse(app.is_admin_password("incorrect-password"))


class StackSimilarityTests(unittest.TestCase):
    def test_exact_stack_is_100_percent(self):
        self.assertEqual(app.stack_similarity(
            ["Ti", "Ne", "Si", "Fe"], ["Ti", "Ne", "Si", "Fe"]), 1.0)

    def test_only_first_position_match_is_40_percent(self):
        self.assertEqual(app.stack_similarity(
            ["Ti", "Te", "Fe", "Fi"], ["Ti", "Ne", "Si", "Fe"]), 0.4)

    def test_no_position_matches_is_zero_percent(self):
        self.assertEqual(app.stack_similarity(
            ["Te", "Fe", "Fi", "Se"], ["Ti", "Ne", "Si", "Fe"]), 0.0)


class InterestQuestionParsingTests(unittest.TestCase):
    def test_interest_questions_are_loaded_from_the_new_source_file(self):
        source = app.DATA_DIR / "ความชอบ2.txt"
        survey = app.parse_interest_questions(source.stat().st_mtime_ns)

        self.assertEqual(len(survey), 5)
        self.assertEqual(len(survey["M"]["questions"]), 20)
        self.assertEqual(
            survey["M"]["questions"][0],
            "เวลาเจอโจทย์เลขที่ยากมากๆ คุณรู้สึกอยากลองแก้ไปเรื่อยๆ จนกว่าจะได้คำตอบ",
        )


class FacultyRankingTests(unittest.TestCase):
    def setUp(self):
        self.original_faculties = app.FACULTIES
        app.FACULTIES = [
            {
                "name": "ก คณะที่เกินเกณฑ์น้อยกว่า",
                "group": "ทดสอบ",
                "functions": ["Ti"],
                "conditions": [{"cat": "M", "min": 50}],
                "budget": {},
            },
            {
                "name": "ฮ คณะที่เกินเกณฑ์มากกว่า",
                "group": "ทดสอบ",
                "functions": ["Ti"],
                "conditions": [{"cat": "M", "min": 20}],
                "budget": {},
            },
        ]
        self.strengths = {"Ti": 100, "Te": 0, "Fe": 0, "Fi": 0,
                          "Se": 0, "Si": 0, "Ne": 0, "Ni": 0}
        self.cat_scores = {"M": 100, "S": 0, "L": 0, "H": 0, "A": 0}

    def tearDown(self):
        app.FACULTIES = self.original_faculties

    def test_display_score_stays_capped_while_ranking_uses_uncapped_score(self):
        rows = app.rank_faculties(self.strengths, self.cat_scores)

        self.assertEqual([row["match"] for row in rows], [100.0, 100.0])
        self.assertEqual(rows[0]["name"], "ฮ คณะที่เกินเกณฑ์มากกว่า")
        self.assertGreater(rows[0]["sortScore"], rows[1]["sortScore"])

    def test_equal_sort_scores_are_ordered_by_faculty_name(self):
        app.FACULTIES[1]["conditions"] = [{"cat": "M", "min": 50}]

        rows = app.rank_faculties(self.strengths, self.cat_scores)

        self.assertEqual(
            [row["name"] for row in rows],
            ["ก คณะที่เกินเกณฑ์น้อยกว่า", "ฮ คณะที่เกินเกณฑ์มากกว่า"],
        )

    def test_ranked_rows_do_not_include_university_examples(self):
        rows = app.rank_faculties(self.strengths, self.cat_scores)

        self.assertTrue(all("uni" not in row for row in rows))


    def test_display_match_percentage_is_the_primary_ranking_order(self):
        app.FACULTIES = [
            {
                "name": "ก Match 100 แต้มรอง",
                "group": "ทดสอบ",
                "functions": ["Ti"],
                "conditions": [{"cat": "M", "min": 100}],
                "budget": {},
            },
            {
                "name": "ข Match 91 แต่เกินเกณฑ์มาก",
                "group": "ทดสอบ",
                "functions": ["Te"],
                "conditions": [{"cat": "M", "min": 20}],
                "budget": {},
            },
            {
                "name": "ค Match 100 แต้มรองสูง",
                "group": "ทดสอบ",
                "functions": ["Ti"],
                "conditions": [{"cat": "M", "min": 20}],
                "budget": {},
            },
        ]
        strengths = {"Ti": 100, "Te": 70, "Fe": 0, "Fi": 0,
                     "Se": 0, "Si": 0, "Ne": 0, "Ni": 0}
        cat_scores = {"M": 100, "S": 0, "L": 0, "H": 0, "A": 0}

        rows = app.rank_faculties(strengths, cat_scores)

        self.assertEqual([row["match"] for row in rows], [100.0, 100.0, 91.0])
        self.assertEqual(
            [row["name"] for row in rows],
            ["ค Match 100 แต้มรองสูง", "ก Match 100 แต้มรอง",
             "ข Match 91 แต่เกินเกณฑ์มาก"],
        )

    def test_real_faculty_rankings_are_non_increasing_by_display_match(self):
        sample_profiles = [
            ({"Ti": 100, "Te": 70, "Fe": 40, "Fi": 30,
              "Se": 60, "Si": 50, "Ne": 80, "Ni": 20},
             {"M": 100, "S": 100, "L": 100, "H": 100, "A": 100}),
            ({"Ti": 35, "Te": 95, "Fe": 55, "Fi": 45,
              "Se": 75, "Si": 65, "Ne": 85, "Ni": 25},
             {"M": 75, "S": 90, "L": 65, "H": 80, "A": 70}),
            ({"Ti": 60, "Te": 40, "Fe": 90, "Fi": 80,
              "Se": 30, "Si": 50, "Ne": 70, "Ni": 100},
             {"M": 55, "S": 60, "L": 95, "H": 100, "A": 85}),
        ]

        for strengths, cat_scores in sample_profiles:
            with self.subTest(strengths=strengths, cat_scores=cat_scores):
                rows = app.rank_faculties(strengths, cat_scores)
                self.assertEqual(len(rows), len(app.FACULTIES))
                self.assertEqual(
                    rows,
                    sorted(rows, key=lambda row: (
                        -row["match"], -row["sortScore"], row["name"])),
                )
                self.assertEqual(
                    rows[:10],
                    sorted(rows[:10], key=lambda row: (
                        -row["match"], -row["sortScore"], row["name"])),
                )


class FundingTierFilteringTests(unittest.TestCase):
    def setUp(self):
        self.strengths = {"Ti": 100, "Te": 0, "Fe": 0, "Fi": 0,
                          "Se": 0, "Si": 0, "Ne": 0, "Ni": 0}
        self.cat_scores = {"M": 100, "S": 100, "L": 100, "H": 100, "A": 100}

    def test_every_faculty_is_explicitly_assigned_to_one_funding_group(self):
        unassigned = [
            faculty["name"] for faculty in app.FACULTIES
            if app.funding_tier_for_faculty(faculty) is None
        ]
        self.assertEqual(unassigned, [])

    def test_low_funding_excludes_the_faculties_in_the_reported_bug(self):
        rows = app.rank_faculties(self.strengths, self.cat_scores, "B1")
        names = {row["name"] for row in rows}

        self.assertIn("นิติศาสตร์", names)
        self.assertNotIn("ทันตแพทยศาสตร์", names)
        self.assertNotIn("ทัศนมาตรศาสตร์ (Optometry)", names)
        self.assertNotIn("ธรณีวิทยา", names)
        self.assertTrue(all(
            app.funding_tier_for_faculty(row["_fac"]) == "B1" for row in rows
        ))

    def test_high_funding_includes_every_affordable_tier(self):
        rows = app.rank_faculties(self.strengths, self.cat_scores, "B3")
        names = {row["name"] for row in rows}

        self.assertIn("ทันตแพทยศาสตร์", names)
        self.assertIn("วิศวกรรมเครื่องกล", names)
        self.assertIn("นิติศาสตร์", names)

    def test_medium_funding_includes_medium_and_low_but_not_high(self):
        rows = app.rank_faculties(self.strengths, self.cat_scores, "B2")
        names = {row["name"] for row in rows}

        self.assertIn("วิศวกรรมเครื่องกล", names)
        self.assertIn("นิติศาสตร์", names)
        self.assertNotIn("ทันตแพทยศาสตร์", names)

    def test_display_orders_affordable_tiers_highest_first(self):
        rows = app.rank_faculties(self.strengths, self.cat_scores, "B3")
        displayed = app.order_rows_by_funding_tier(rows, "B3")
        tiers = [app.funding_tier_for_faculty(row["_fac"]) for row in displayed]

        self.assertEqual(tiers, sorted(tiers, reverse=True))
        for tier in app.affordable_funding_tiers("B3"):
            tier_rows = [row for row in displayed
                         if app.funding_tier_for_faculty(row["_fac"]) == tier]
            self.assertEqual(
                tier_rows,
                sorted(tier_rows, key=lambda row: (
                    -row["match"], -row["sortScore"], row["name"])),
            )


class RankTableSortScoreDisplayTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"name": "ก", "match": 100.0, "mbtiScore": 100, "subjScore": 100,
             "sortScore": 181.84, "reason": "-"},
            {"name": "ข", "match": 100.0, "mbtiScore": 100, "subjScore": 100,
             "sortScore": 181.81, "reason": "-"},
            {"name": "ค", "match": 90.0, "mbtiScore": 90, "subjScore": 90,
             "sortScore": 90.04, "reason": "-"},
            {"name": "ง", "match": 80.0, "mbtiScore": 80, "subjScore": 80,
             "sortScore": 80.0, "reason": "-"},
            {"name": "จ", "match": 80.0, "mbtiScore": 80, "subjScore": 80,
             "sortScore": 79.96, "reason": "-"},
        ]

    def test_rendered_scores_match_each_rows_sort_score(self):
        rendered = []
        previous_markdown = getattr(app.st, "markdown", None)
        app.st.markdown = lambda text, **_kwargs: rendered.append(text)
        try:
            app.render_rank_table(self.rows)
        finally:
            if previous_markdown is None:
                del app.st.markdown
            else:
                app.st.markdown = previous_markdown

        tbody = re.search(r"<tbody>(.*?)</tbody>", rendered[0]).group(1)
        body_rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody)
        self.assertEqual(len(body_rows), len(self.rows))
        for row, expected in zip(body_rows, self.rows):
            self.assertIn(f"คะแนนจัดอันดับ: {round(expected['sortScore'], 1)}", row)
        self.assertNotIn("จัดลำดับย่อยจากคะแนนละเอียดกว่า", rendered[0])
        self.assertIn("เมื่อ Match % เท่ากัน", rendered[0])
        self.assertNotIn("เหตุผล", rendered[0])


class ZeroToFiveScaleTests(unittest.TestCase):
    def test_mbti_raw_score_zero_normalizes_to_zero_percent(self):
        raw_scores = {function: 0 for function in app.FN_ORDER}
        self.assertEqual(
            app.strengths_from_raw(raw_scores),
            {function: 0.0 for function in app.FN_ORDER},
        )

    def test_mbti_raw_score_fifty_normalizes_to_one_hundred_percent(self):
        raw_scores = {function: 50 for function in app.FN_ORDER}
        self.assertEqual(
            app.strengths_from_raw(raw_scores),
            {function: 100.0 for function in app.FN_ORDER},
        )

    def test_zero_to_five_scale_has_six_ordered_choices(self):
        self.assertEqual(app.SCALE_0_5, ["0", "1", "2", "3", "4", "5"])

    def test_zero_is_a_valid_forced_choice_response(self):
        self.assertEqual(app.SCALE_LABELS[0], "ไม่เห็นด้วยอย่างยิ่ง")
        self.assertEqual(app.SCALE_LABELS[5], "เห็นด้วยอย่างยิ่ง")


if __name__ == "__main__":
    unittest.main()
