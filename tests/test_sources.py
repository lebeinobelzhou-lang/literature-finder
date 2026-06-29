import unittest
from unittest.mock import Mock, patch

import main


class SourceSelectionTests(unittest.TestCase):
    def test_openalex_only_skips_semantic_scholar(self):
        with patch.object(main, "search_openalex", return_value=[]) as openalex, patch.object(
            main, "search_semantic_scholar", return_value=[]
        ) as semantic:
            main.collect_papers(["autism STEM"], limit_per_api=3, pause_seconds=0, source="openalex")

        openalex.assert_called_once_with("autism STEM", 3, 0)
        semantic.assert_not_called()

    def test_default_searches_openalex_before_semantic_scholar(self):
        calls = []

        def fake_openalex(*args):
            calls.append("openalex")
            return []

        def fake_semantic(*args):
            calls.append("semantic")
            return []

        with patch.object(main, "search_openalex", side_effect=fake_openalex), patch.object(
            main, "search_semantic_scholar", side_effect=fake_semantic
        ):
            main.collect_papers(["autism STEM"], limit_per_api=3, pause_seconds=0, source="all")

        self.assertEqual(calls, ["openalex", "semantic"])

    def test_safe_get_returns_none_without_retrying_on_rate_limit(self):
        response = Mock()
        response.status_code = 429

        with patch.dict("sys.modules", {"requests": Mock(get=Mock(return_value=response))}), patch.object(
            main.time, "sleep"
        ) as sleep:
            result = main.safe_get("https://example.test", params={})

        self.assertIsNone(result)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
