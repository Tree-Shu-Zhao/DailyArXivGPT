"""Fetch and parse daily AI news from TLDR Tech."""

import re
import urllib.request
import urllib.error
from datetime import date

from loguru import logger

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


# Sections to extract (in order)
SECTIONS = [
    "Headlines & Launches",
    "Deep Dives & Analysis",
    "Engineering & Research",
    "Miscellaneous",
    "Quick Links",
]


class NewsFetcher:
    """Fetches and parses AI news from TLDR Tech."""

    def __init__(self, url_template: str = "https://tldr.tech/ai/{date}"):
        """Initialize the news fetcher.

        Args:
            url_template: URL template with {date} placeholder for YYYY-MM-DD format
        """
        self.url_template = url_template

    def fetch(self, target_date: str = None) -> list[dict]:
        """Fetch AI news for the given date.

        Args:
            target_date: Date in YYYY-MM-DD format (default: today)

        Returns:
            List of news item dictionaries with title, url, summary, and section
            Returns empty list if news is not available (e.g., weekends)

        Raises:
            ImportError: If beautifulsoup4 is not installed
            Exception: If fetching or parsing fails unexpectedly
        """
        if BeautifulSoup is None:
            raise ImportError(
                "beautifulsoup4 is required. Install with: pip install beautifulsoup4"
            )

        if target_date is None:
            target_date = date.today().isoformat()

        url = self.url_template.format(date=target_date)
        logger.info(f"Fetching news from {url}")

        try:
            html_content = self._fetch_html(url)
            news_items = self._parse_news(html_content)

            if not news_items:
                logger.warning(
                    f"No news items found for {target_date} - page may be empty or unavailable (weekends?)"
                )
            else:
                logger.info(f"Fetched {len(news_items)} news items")

            return news_items

        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.warning(
                    f"News not available for {target_date} (404) - likely a weekend or holiday"
                )
                return []
            elif e.code == 403:
                logger.warning(f"Access forbidden (403) - possible rate limiting or blocking")
                return []
            else:
                logger.error(f"HTTP error {e.code} fetching news: {e}")
                raise

        except urllib.error.URLError as e:
            logger.error(f"Network error fetching news: {e}")
            raise

    def _fetch_html(self, url: str) -> str:
        """Fetch HTML content from URL."""
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DailyDigest/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8")

    def _clean_title(self, title: str) -> str:
        """Remove reading time suffix like '(2 minute read)' from title."""
        return re.sub(r"\s*\(\d+\s+minute\s+read\)\s*$", "", title).strip()

    def _parse_news(self, html_content: str) -> list[dict]:
        """Parse TLDR Tech HTML and extract news items."""
        soup = BeautifulSoup(html_content, "html.parser")
        news_items = []

        # Find all sections and match by header text
        for section in soup.find_all("section"):
            header = section.find("header")
            if not header:
                continue

            h3 = header.find("h3")
            if not h3:
                continue

            section_name = h3.get_text(strip=True)
            if section_name not in SECTIONS:
                continue

            articles = section.find_all("article")
            for article in articles:
                link = article.find("a", class_="font-bold")
                if not link:
                    continue

                title_elem = link.find("h3")
                if not title_elem:
                    continue

                raw_title = title_elem.get_text(strip=True)

                # Skip sponsor articles
                if "(Sponsor)" in raw_title:
                    continue

                title = self._clean_title(raw_title)
                url = link.get("href", "")

                # Extract summary from newsletter-html div
                summary_div = article.find("div", class_="newsletter-html")
                summary = summary_div.get_text(strip=True) if summary_div else ""

                if title and url:
                    news_items.append(
                        {
                            "title": title,
                            "url": url,
                            "summary": summary,
                            "section": section_name,
                        }
                    )

        return news_items
