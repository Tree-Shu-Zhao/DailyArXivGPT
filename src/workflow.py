import json
import os
import shutil

from flask import jsonify
from loguru import logger

from .crawler import ArXivCrawler
from .paper import Paper
from .paper_reader import PaperReader


class Workflow:
    def __init__(self, cfg):
        self.output_dir = cfg["output_dir"]
        self.crawler = ArXivCrawler(cfg["crawler"]["categories"])
        self.reader = PaperReader(cfg["reader"]["llm_model"], cfg["reader"]["relevance_threshold"], self.output_dir)

    def run(self):
        os.makedirs(self.output_dir, exist_ok=True)
        # Check if we have today's data
        year, month, day = self.crawler.get_date()
        filepath = os.path.join(self.output_dir, f"{year}-{month}-{day}.json")
        logger.info(f"Date: {year}-{month}-{day}")
        if not os.path.exists(filepath):
            # If not, run the crawler
            logger.info("Start crawling...")
            papers = self.crawler.run()
            if papers is None:
                logger.error("Failed to fetch data from ArXiv.")
                return jsonify({'error': 'Something wrong during parsing!'}), 400
            logger.info(f"Crawling done! Save the data to {filepath}. #Paper: {len(papers)}")
            with open(filepath, "w") as f:
                json.dump([paper.to_dict() for paper in papers], f, indent=2)
        else:
            logger.info(f"Found data file {filepath}! Load it.")

        with open(filepath, "r") as f:
            data = json.load(f)
            papers = [Paper.from_dict(paper) for paper in data]
            logger.info(f"Loaded {len(papers)} papers.")

        relevant_filepath = os.path.join(self.output_dir, f"{year}-{month}-{day}-relevant.json")
        if not os.path.exists(relevant_filepath):
            # Process the papers and get the relevant ones
            logger.info("Start processing papers...")
            self.reader.run(papers)
            logger.info("Processing done!")

            # Gather all papers and relevant papers
            processed_paper_dir = os.path.join(self.output_dir, "processed")
            all_papers = []
            relevant_papers = []
            for processed_paper in os.listdir(processed_paper_dir):
                with open(os.path.join(processed_paper_dir, processed_paper), "r") as f:
                    paper = Paper.from_dict(json.load(f))
                    all_papers.append(paper)
                    if paper.relevance_score >= self.reader.threshold:
                        relevant_papers.append(paper)
            logger.info(f"Found {len(relevant_papers)} relevant papers.")

            with open(relevant_filepath.replace("-relevant.json", "-all-rate.json"), "w") as f:
                json.dump([all_paper.to_dict() for all_paper in all_papers], f, indent=2)

            if len(relevant_papers) == 0:
                logger.info("No relevant papers found.")
                # return jsonify({'error': 'No relevant papers found.'}), 400

            # Sort the papers by relevance score
            relevant_papers.sort(key=lambda x: x.relevance_score, reverse=True)
            with open(relevant_filepath, "w") as f:
                json.dump([relevant_paper.to_dict() for relevant_paper in relevant_papers], f, indent=2)

            # Remove the processed paper dir
            shutil.rmtree(processed_paper_dir)
            logger.info("Removed the processed paper directory.")
        else:
            logger.info(f"Found relevant data file {relevant_filepath}! Load it.")
        with open(relevant_filepath, "r") as f:
            data = json.load(f)
            relevant_papers = [Paper.from_dict(relevant_paper) for relevant_paper in data]
            logger.info(f"Loaded {len(relevant_papers)} relevant papers.")
        
        return jsonify({'papers': [relevant_paper.to_dict() for relevant_paper in relevant_papers]}), 200
