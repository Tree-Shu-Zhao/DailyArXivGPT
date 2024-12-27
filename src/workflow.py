import json
import os

from loguru import logger
from flask import jsonify

from .crawler import ArXivCrawler
from .paper_reader import PaperReader


class Workflow:
    def __init__(self, cfg):
        self.crawler = ArXivCrawler(cfg.crawler.CATEGORIES)
        self.reader = PaperReader(cfg.reader.LLM_MODEL, cfg.reader.RELEVANCE_THRESHOLD)
        self.output_dir = cfg.OUTPUT_DIR

    def run(self):
        # Check if we have today's data
        year, month, day = self.crawler.get_date()
        filepath = os.path.join(self.output_dir, f"{year}-{month}-{day}.json")
        if not os.path.exists(filepath):
            # If not, run the crawler
            logger.info("Start crawling...")
            papers = self.crawler.run()
            if papers is None:
                logger.error("Failed to fetch data from ArXiv.")
                return jsonify({'error': 'Something wrong during parsing!'}), 400
            logger.info(f"Crawling done! Save the data to {filepath}.")
            with open(filepath, "w") as f:
                json.dump(papers, f)
        else:
            logger.info(f"Found data file {filepath}! Load it.")

        with open(filepath, "r") as f:
            papers = json.load(f)

        relevant_filepath = os.path.join(self.output_dir, f"{year}-{month}-{day}-relevant.json")
        if not os.path.exists(relevant_filepath):
            # Process the papers and get the relevant ones
            relevant_papers = self.reader.run(papers)
            if len(relevant_papers) == 0:
                logger.info("No relevant papers found.")
                return jsonify({'error': 'No relevant papers found.'}), 400

            # Sort the papers by relevance score
            relevant_papers.sort(key=lambda x: x.relevance_score, reverse=True)
            with open(relevant_filepath, "w") as f:
                json.dump(relevant_papers, f)
        else:
            logger.info(f"Found relevant data file {relevant_filepath}! Load it.")
        with open(relevant_filepath, "r") as f:
            relevant_papers = json.load(f)
        
        return jsonify({'papers': relevant_papers})
