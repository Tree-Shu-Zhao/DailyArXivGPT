import sys
from datetime import datetime

import feedparser
import requests
from loguru import logger

from .paper import Paper


class ArXivCrawler:
    def __init__(self, categories):
        # Categories
        # cs.CV: Computer Vision and Pattern Recognition
        # cs.CL: Computation and Language
        self.rss_urls = [f"http://export.arxiv.org/rss/{category}" for category in categories]
    
    def run(self):
        papers = []
        titles = set()
        for rss_url in self.rss_urls:
            # Fetch feed 
            feed = self.fetch(rss_url)
            if feed is None:
                return None
            
            for item in feed.entries:
                if item.title not in titles:
                    papers.append(Paper(item.title, item.link, item.abstract))
                    titles.add(item.title)
        return papers
    
    def get_date(self, rss_url="http://export.arxiv.org/rss/cs.CV"):
        feed = self.fetch(rss_url)
        if feed is None:
            return None
        year, month, day = self.parse_date(feed["feed"]["updated"])
        return year, month, day
    
    def fetch(self, rss_url):
        try:
            feed = feedparser.parse(requests.get(rss_url).content)
            return feed
        except:
            logger.error(f"Unexpected error: {sys.exc_info()[0]}")
            return None
    
    def parse_date(self, datetime_str):
        #parsed_date = datetime.fromisoformat(datetime_str) # ISO 8601
        parsed_date = datetime.strptime(datetime_str, "%a, %d %b %Y %H:%M:%S %z") # RFC 2822
        return parsed_date.year, parsed_date.month, parsed_date.day
