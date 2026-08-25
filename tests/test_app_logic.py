import importlib.util
import sys
import types
import unittest
from pathlib import Path


def load_app():
    streamlit = types.ModuleType("streamlit")
    streamlit.cache_data = lambda **_kwargs: lambda func: func
    streamlit.session_state = {}
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


if __name__ == "__main__":
    unittest.main()
