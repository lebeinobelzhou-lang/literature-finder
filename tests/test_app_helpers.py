import unittest

import app


class AppHelperTests(unittest.TestCase):
    def test_inverted_index_to_text_orders_words_by_position(self):
        abstract = {"world": [1], "hello": [0], "again": [2]}

        self.assertEqual(app.inverted_index_to_text(abstract), "hello world again")

    def test_parse_openalex_work_keeps_legal_access_links(self):
        work = {
            "display_name": "Accessible Autism Research",
            "publication_year": 2024,
            "doi": "https://doi.org/10.1234/example",
            "cited_by_count": 42,
            "abstract_inverted_index": {"Autism": [0], "research": [1]},
            "authorships": [
                {"author": {"display_name": "Ada Author"}},
                {"author": {"display_name": "Ben Writer"}},
            ],
            "primary_location": {
                "landing_page_url": "https://publisher.example/article",
                "source": {"display_name": "Journal of Examples"},
            },
            "open_access": {"oa_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/"},
        }

        result = app.parse_openalex_work(work, "autism")

        self.assertEqual(result["title"], "Accessible Autism Research")
        self.assertEqual(result["authors"], "Ada Author, Ben Writer")
        self.assertEqual(result["year"], 2024)
        self.assertEqual(result["venue"], "Journal of Examples")
        self.assertEqual(result["citation_count"], 42)
        self.assertEqual(result["abstract"], "Autism research")
        self.assertEqual(result["doi"], "10.1234/example")
        self.assertEqual(result["publisher_url"], "https://publisher.example/article")
        self.assertEqual(result["openalex_oa_url"], "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/")
        self.assertEqual(result["access_status"], "Open access found")
        self.assertEqual(result["best_access_url"], "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/")
        self.assertEqual(result["matched_keyword"], "autism")

    def test_add_access_fields_prefers_unpaywall_then_openalex_then_publisher_then_doi(self):
        rows = [
            {
                "title": "Unpaywall",
                "doi": "10.1/unpaywall",
                "publisher_url": "https://publisher.example/unpaywall",
                "openalex_oa_url": "https://openalex.example/unpaywall",
                "unpaywall_oa_url": "https://unpaywall.example/unpaywall",
            },
            {
                "title": "OpenAlex",
                "doi": "10.1/openalex",
                "publisher_url": "https://publisher.example/openalex",
                "openalex_oa_url": "https://openalex.example/openalex",
                "unpaywall_oa_url": "",
            },
            {
                "title": "Publisher",
                "doi": "10.1/publisher",
                "publisher_url": "https://publisher.example/publisher",
                "openalex_oa_url": "",
                "unpaywall_oa_url": "",
            },
            {
                "title": "DOI",
                "doi": "10.1/doi",
                "publisher_url": "",
                "openalex_oa_url": "",
                "unpaywall_oa_url": "",
            },
            {
                "title": "None",
                "doi": "",
                "publisher_url": "",
                "openalex_oa_url": "",
                "unpaywall_oa_url": "",
            },
        ]

        enriched = [app.add_access_fields(row.copy()) for row in rows]

        self.assertEqual(enriched[0]["access_status"], "Open access found")
        self.assertEqual(enriched[0]["best_access_url"], "https://unpaywall.example/unpaywall")
        self.assertEqual(enriched[1]["access_status"], "Open access found")
        self.assertEqual(enriched[1]["best_access_url"], "https://openalex.example/openalex")
        self.assertEqual(enriched[2]["access_status"], "DOI/publisher only")
        self.assertEqual(enriched[2]["best_access_url"], "https://publisher.example/publisher")
        self.assertEqual(enriched[3]["access_status"], "DOI/publisher only")
        self.assertEqual(enriched[3]["best_access_url"], "https://doi.org/10.1/doi")
        self.assertEqual(enriched[4]["access_status"], "No access link found")
        self.assertEqual(enriched[4]["best_access_url"], "")

    def test_filter_results_applies_year_and_abstract_requirements(self):
        rows = [
            {"title": "Old", "year": 2015, "abstract": "has abstract", "citation_count": 1},
            {"title": "No Abstract", "year": 2022, "abstract": "", "citation_count": 2},
            {"title": "Current", "year": 2023, "abstract": "has abstract", "citation_count": 3},
        ]

        filtered = app.filter_results(rows, minimum_year=2020, maximum_year=2024, require_abstract=True)

        self.assertEqual([row["title"] for row in filtered], ["Current"])

    def test_sort_results_supports_citation_count_and_year(self):
        rows = [
            {"title": "A", "year": 2020, "citation_count": 5, "relevance_score": 1},
            {"title": "B", "year": 2023, "citation_count": 2, "relevance_score": 2},
            {"title": "C", "year": 2021, "citation_count": 9, "relevance_score": 3},
        ]

        by_citations = app.sort_results(rows, "citation count")
        by_year = app.sort_results(rows, "year")

        self.assertEqual([row["title"] for row in by_citations], ["C", "A", "B"])
        self.assertEqual([row["title"] for row in by_year], ["B", "C", "A"])

    def test_results_to_markdown_includes_access_links(self):
        rows = [
            {
                "title": "A Paper",
                "authors": "A. Author",
                "year": 2024,
                "venue": "Example Journal",
                "citation_count": 7,
                "abstract": "Short abstract.",
                "doi": "10.1234/example",
                "publisher_url": "https://publisher.example/article",
                "openalex_oa_url": "https://open.example/full-text",
                "unpaywall_oa_url": "https://oa.example/full-text",
                "matched_keyword": "autism",
            }
        ]

        markdown = app.results_to_markdown(rows)

        self.assertIn("# Literature Finder Results", markdown)
        self.assertIn("https://doi.org/10.1234/example", markdown)
        self.assertIn("https://publisher.example/article", markdown)
        self.assertIn("https://open.example/full-text", markdown)
        self.assertIn("https://oa.example/full-text", markdown)
        self.assertIn("Open access found", markdown)


if __name__ == "__main__":
    unittest.main()
