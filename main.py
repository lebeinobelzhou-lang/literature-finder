import argparse
import csv
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
OPENALEX_URL = "https://api.openalex.org/works"


@dataclass
class Paper:
    title: str
    authors: str = ""
    year: Optional[int] = None
    journal_or_venue: str = ""
    doi: str = ""
    url: str = ""
    citation_count: int = 0
    abstract: str = ""
    source_api: str = ""
    matched_keyword: str = ""
    relevance_score: int = 0
    rank_score: float = 0.0
    sources: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)


def read_keywords(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as file:
        keywords = []
        for line in file:
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#"):
                keywords.append(cleaned)
        return keywords


def normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def normalize_doi(doi: str) -> str:
    doi = doi.strip().lower()
    doi = doi.replace("https://doi.org/", "")
    doi = doi.replace("http://doi.org/", "")
    doi = doi.replace("doi:", "")
    return doi.strip()


def safe_get(
    url: str,
    params: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    rate_limit_message: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    try:
        import requests
    except ImportError:
        raise SystemExit(
            "The 'requests' package is not installed. Run: python3 -m pip install -r requirements.txt"
        )

    try:
        response = requests.get(url, params=params, headers=headers or {}, timeout=30)
        if response.status_code == 429:
            print(rate_limit_message or f"Rate limit reached for {url}. Skipping this request.")
            return None
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        print(f"API request failed for {url}: {error}")
        return None


def search_semantic_scholar(keyword: str, limit: int, pause_seconds: float) -> List[Paper]:
    fields = ",".join(
        [
            "title",
            "authors",
            "year",
            "venue",
            "publicationVenue",
            "citationCount",
            "abstract",
            "externalIds",
            "url",
        ]
    )
    params = {"query": keyword, "limit": limit, "fields": fields}
    headers = {}
    api_key = os.getenv("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    data = safe_get(
        SEMANTIC_SCHOLAR_URL,
        params=params,
        headers=headers,
        rate_limit_message=f"Semantic Scholar rate limit reached for keyword '{keyword}'. Skipping Semantic Scholar for this keyword.",
    )
    time.sleep(pause_seconds)
    if not data:
        return []

    papers = []
    for item in data.get("data", []):
        title = (item.get("title") or "").strip()
        if not title:
            continue
        external_ids = item.get("externalIds") or {}
        publication_venue = item.get("publicationVenue") or {}
        authors = item.get("authors") or []
        papers.append(
            Paper(
                title=title,
                authors=", ".join(author.get("name", "") for author in authors if author.get("name")),
                year=item.get("year"),
                journal_or_venue=publication_venue.get("name") or item.get("venue") or "",
                doi=normalize_doi(external_ids.get("DOI") or ""),
                url=item.get("url") or "",
                citation_count=int(item.get("citationCount") or 0),
                abstract=item.get("abstract") or "",
                source_api="Semantic Scholar",
                matched_keyword=keyword,
            )
        )
    return papers


def inverted_index_to_text(index: Optional[Dict[str, List[int]]]) -> str:
    if not index:
        return ""
    positioned_words = []
    for word, positions in index.items():
        for position in positions:
            positioned_words.append((position, word))
    positioned_words.sort()
    return " ".join(word for _, word in positioned_words)


def search_openalex(keyword: str, limit: int, pause_seconds: float) -> List[Paper]:
    params = {
        "search": keyword,
        "per-page": limit,
        "select": "title,display_name,authorships,publication_year,primary_location,doi,cited_by_count,abstract_inverted_index",
    }
    mailto = os.getenv("OPENALEX_MAILTO")
    if mailto:
        params["mailto"] = mailto

    data = safe_get(OPENALEX_URL, params=params)
    time.sleep(pause_seconds)
    if not data:
        return []

    papers = []
    for item in data.get("results", []):
        title = (item.get("title") or item.get("display_name") or "").strip()
        if not title:
            continue
        authors = []
        for authorship in item.get("authorships") or []:
            author = authorship.get("author") or {}
            if author.get("display_name"):
                authors.append(author["display_name"])

        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        landing_page_url = primary_location.get("landing_page_url") or ""
        openalex_doi = normalize_doi(item.get("doi") or "")

        papers.append(
            Paper(
                title=title,
                authors=", ".join(authors),
                year=item.get("publication_year"),
                journal_or_venue=source.get("display_name") or "",
                doi=openalex_doi,
                url=landing_page_url or (f"https://doi.org/{openalex_doi}" if openalex_doi else ""),
                citation_count=int(item.get("cited_by_count") or 0),
                abstract=inverted_index_to_text(item.get("abstract_inverted_index")),
                source_api="OpenAlex",
                matched_keyword=keyword,
            )
        )
    return papers


def relevance_score(paper: Paper, keyword: str) -> int:
    words = [word.lower() for word in re.findall(r"[a-zA-Z0-9]+", keyword) if len(word) > 2]
    title = paper.title.lower()
    abstract = paper.abstract.lower()
    score = 0
    for word in words:
        if word in title:
            score += 4
        if word in abstract:
            score += 1
    if paper.abstract:
        score += 5
    return score


def merge_papers(existing: Paper, new: Paper) -> Paper:
    if not existing.abstract and new.abstract:
        existing.abstract = new.abstract
    if not existing.doi and new.doi:
        existing.doi = new.doi
    if not existing.url and new.url:
        existing.url = new.url
    if not existing.journal_or_venue and new.journal_or_venue:
        existing.journal_or_venue = new.journal_or_venue
    if not existing.authors and new.authors:
        existing.authors = new.authors
    if not existing.year and new.year:
        existing.year = new.year
    existing.citation_count = max(existing.citation_count, new.citation_count)
    existing.relevance_score = max(existing.relevance_score, new.relevance_score)
    if new.source_api not in existing.sources:
        existing.sources.append(new.source_api)
    if new.matched_keyword not in existing.matched_keywords:
        existing.matched_keywords.append(new.matched_keyword)
    existing.source_api = "; ".join(existing.sources)
    existing.matched_keyword = "; ".join(existing.matched_keywords)
    return existing


def deduplicate_papers(papers: Iterable[Paper]) -> List[Paper]:
    by_doi: Dict[str, Paper] = {}
    by_title: Dict[str, Paper] = {}

    for paper in papers:
        if not paper.title.strip():
            continue
        paper.doi = normalize_doi(paper.doi)
        paper.sources = [paper.source_api]
        paper.matched_keywords = [paper.matched_keyword]
        doi_key = paper.doi
        title_key = normalize_title(paper.title)

        if doi_key and doi_key in by_doi:
            merge_papers(by_doi[doi_key], paper)
            continue
        if title_key and title_key in by_title:
            merged = merge_papers(by_title[title_key], paper)
            if doi_key:
                by_doi[doi_key] = merged
            continue

        if doi_key:
            by_doi[doi_key] = paper
        if title_key:
            by_title[title_key] = paper

    return list({id(paper): paper for paper in list(by_doi.values()) + list(by_title.values())}.values())


def rank_papers(papers: List[Paper]) -> List[Paper]:
    for paper in papers:
        recency = 0
        if paper.year:
            recency = max(0, paper.year - 2000)
        paper.rank_score = (
            paper.relevance_score * 10
            + min(paper.citation_count, 1000) * 0.5
            + recency
            + (25 if paper.abstract else 0)
        )
    return sorted(papers, key=lambda paper: paper.rank_score, reverse=True)


def export_csv(papers: List[Paper], path: str) -> None:
    columns = [
        "title",
        "authors",
        "year",
        "journal_or_venue",
        "doi",
        "url",
        "citation_count",
        "abstract",
        "source_api",
        "matched_keyword",
        "relevance_score",
        "rank_score",
    ]
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for paper in papers:
            writer.writerow({column: getattr(paper, column) for column in columns})


def introduction_note(paper: Paper) -> str:
    text = f"{paper.title} {paper.abstract} {paper.matched_keyword}".lower()
    reasons = []
    if any(term in text for term in ["intersection", "race", "gender", "identity", "minority"]):
        reasons.append("It may support the section on intersectionality by showing how autistic experiences differ across social identities.")
    if any(term in text for term in ["college", "university", "student", "stem"]):
        reasons.append("It may help connect autism research to college pathways, STEM preparation, or early career transitions.")
    if any(term in text for term in ["interview", "hiring", "employment", "workplace", "job"]):
        reasons.append("It may provide evidence about employment barriers, hiring practices, or job interview demands.")
    if any(term in text for term in ["disclosure", "accommodation"]):
        reasons.append("It may help explain disclosure and accommodation decisions during recruitment or work.")
    if any(term in text for term in ["stigma", "bias", "masking", "camouflaging"]):
        reasons.append("It may support discussion of bias, stigma, masking, or impression management.")
    if any(term in text for term in ["mental health", "anxiety", "depression", "co-occurring", "comorbid"]):
        reasons.append("It may help describe co-occurring conditions and mental health concerns that shape interview and employment experiences.")

    if not reasons:
        reasons.append("It may provide background evidence for autism, education, employment, or research-gap framing.")
    if len(reasons) == 1:
        reasons.append("Review the abstract and methods to decide whether it belongs in the introduction or in a later literature review section.")
    return " ".join(reasons[:3])


def markdown_header() -> str:
    return """# Literature Search Results

## Possible Introduction Themes

### Intersectionality and autism
- Define intersectionality and explain why autistic students' experiences may differ by race, ethnicity, gender, disability, class, sexuality, and other identities.

### Autistic college students and STEM pathways
- Summarize research on autistic students in higher education, STEM participation, career preparation, and transition from college to work.

### Job interviews as barriers
- Discuss interviews as socially demanding selection tools that may disadvantage autistic applicants even when they have strong technical qualifications.

### Disclosure and accommodations
- Cover whether, when, and how autistic students disclose disability status and request accommodations during recruitment or interviewing.

### Bias, stigma, and masking
- Explain how stigma, implicit bias, camouflaging, and expectations about social communication can shape hiring outcomes.

### Co-occurring conditions and mental health
- Summarize common co-occurring conditions and mental health concerns that may affect college, interviewing, and employment.

### Research gap
- Identify what is still underexplored, especially intersectional experiences of autistic college students seeking STEM careers through job interviews.

"""


def export_markdown(papers: List[Paper], path: str) -> None:
    with open(path, "w", encoding="utf-8") as file:
        file.write(markdown_header())
        file.write("## Papers\n\n")
        for index, paper in enumerate(papers, start=1):
            authors = paper.authors or "Authors not listed"
            year = paper.year or "Year not listed"
            doi_or_url = f"https://doi.org/{paper.doi}" if paper.doi else paper.url or "DOI/URL not listed"
            abstract = paper.abstract or "No abstract available from the API results."
            file.write(f"### {index}. {paper.title}\n\n")
            file.write(f"- **Authors:** {authors}\n")
            file.write(f"- **Year:** {year}\n")
            file.write(f"- **Journal/Venue:** {paper.journal_or_venue or 'Not listed'}\n")
            file.write(f"- **DOI or URL:** {doi_or_url}\n")
            file.write(f"- **Citation count:** {paper.citation_count}\n")
            file.write(f"- **Source API:** {paper.source_api}\n")
            file.write(f"- **Matched keyword:** {paper.matched_keyword}\n\n")
            file.write(f"**Abstract:** {abstract}\n\n")
            file.write(f"**How this might help the introduction:** {introduction_note(paper)}\n\n")


def collect_papers(keywords: List[str], limit_per_api: int, pause_seconds: float, source: str) -> List[Paper]:
    all_papers: List[Paper] = []
    for keyword in keywords:
        print(f"Searching: {keyword}")
        keyword_papers: List[Paper] = []
        if source in ("all", "openalex"):
            keyword_papers.extend(search_openalex(keyword, limit_per_api, pause_seconds))
        if source in ("all", "semantic-scholar"):
            keyword_papers.extend(search_semantic_scholar(keyword, limit_per_api, pause_seconds))
        for paper in keyword_papers:
            paper.relevance_score = relevance_score(paper, keyword)
            all_papers.append(paper)
    unique_papers = deduplicate_papers(all_papers)
    return rank_papers(unique_papers)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search academic APIs for autism and STEM interview literature.")
    parser.add_argument("--keywords", default="keywords.txt", help="Path to the keywords file.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum results per API for each keyword.")
    parser.add_argument("--pause", type=float, default=2.5, help="Seconds to pause between API calls.")
    parser.add_argument(
        "--source",
        choices=["all", "openalex", "semantic-scholar"],
        default="all",
        help="API source to search. Use 'openalex' to avoid Semantic Scholar rate limits.",
    )
    parser.add_argument("--csv", default="literature_results_interview_targeted.csv", help="CSV output path.")
    parser.add_argument("--md", default="literature_results_interview_targeted.md", help="Markdown output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    keywords = read_keywords(args.keywords)
    if not keywords:
        raise SystemExit(f"No keywords found in {args.keywords}. Add one search phrase per line.")

    papers = collect_papers(keywords, args.limit, args.pause, args.source)
    export_csv(papers, args.csv)
    export_markdown(papers, args.md)
    print(f"\nDone. Saved {len(papers)} unique papers.")
    print(f"CSV: {args.csv}")
    print(f"Markdown: {args.md}")


if __name__ == "__main__":
    main()
