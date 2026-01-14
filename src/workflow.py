import json
import os
import shutil

from loguru import logger
from datetime import datetime

from .crawler import ArXivCrawler
from .paper import Paper
from .paper_reader import PaperReader


class Workflow:
    def __init__(self, cfg):
        self.output_dir = cfg["output_dir"]
        self.crawler = ArXivCrawler(cfg["crawler"]["categories"])

        # Substitute research_interests placeholder in prompts
        research_interests = cfg.get("research_interests", "")
        system_prompt = cfg["system_prompt"].replace("{research_interests}", research_interests)
        key_contributions_prompt = cfg.get("key_contributions_prompt", "")
        if key_contributions_prompt:
            key_contributions_prompt = key_contributions_prompt.replace("{research_interests}", research_interests)

        self.reader = PaperReader(
            system_prompt=system_prompt,
            llm_model=cfg["reader"]["llm_model"],
            relevance_threshold=cfg["reader"]["relevance_threshold"],
            output_dir=self.output_dir,
            num_threads=cfg["reader"].get("num_threads", 32),
            key_contributions_prompt=key_contributions_prompt,
        )

    def run(self):
        os.makedirs(self.output_dir, exist_ok=True)
        # Check if we have today's data
        year, month, day = self.crawler.get_date()
        filepath = os.path.join(self.output_dir, f"{year}-{month}-{day}.json")
        logger.info(f"Date: {year}-{month}-{day}")

        # arXiv rss is weird, sometimes the content of the feed is not updated but the date is updated
        current_date = datetime.now()
        sys_year = current_date.year
        sys_month = current_date.month
        sys_day = current_date.day
        if sys_year != year or sys_month != month or sys_day != day:
            logger.error("The date of feed is not equal to the system date.")
            return []

        if not os.path.exists(filepath) or os.path.getsize(filepath) <= 5:
            # If not, run the crawler
            # We use os.path.getsize(filepath) <= 5, because sometimes the release of the rss feed is delayed
            # For example, if we refresh the page at 12:30, the rss feed might not be available until 02:00
            logger.info("Start crawling...")
            papers = self.crawler.run()
            if papers is None or len(papers) == 0:
                logger.error("Failed to fetch data from ArXiv.")
                return []
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
            # Sort relevant papers by relevance score
            relevant_papers.sort(key=lambda x: x.relevance_score, reverse=True)
            logger.info(f"Loaded {len(relevant_papers)} relevant papers.")
        
        return [relevant_paper.to_dict() for relevant_paper in relevant_papers]
