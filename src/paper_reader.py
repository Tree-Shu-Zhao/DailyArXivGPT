import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
from pydantic import BaseModel


class PaperReader:
    def __init__(self, system_prompt, llm_model="gpt-4o", relevance_threshold=7, output_dir="data", num_threads=32):
        self.openai_client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        self.system_prompt = system_prompt
        self.llm_model = llm_model
        self.threshold = relevance_threshold
        self.output_dir = os.path.join(output_dir, "processed")
        self.num_threads = num_threads
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self, papers):
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = {executor.submit(self._process_paper, paper): paper for paper in papers}
            for future in as_completed(futures):
                paper = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"Error processing paper '{paper.title}': {e}")

    def _process_paper(self, paper):
        # Skip if the paper already be processed
        paper_id = self.create_paper_id(paper.to_dict())
        filepath = os.path.join(self.output_dir, f"{paper_id}.json")
        if os.path.exists(filepath):
            return

        paper.title = paper.title.strip()
        paper.abstract = paper.abstract.split("Abstract:")[1].strip()

        # Rate the relevance of the paper
        relevance_output = self.rate_relevance(paper.title, paper.abstract)
        paper.relevance_score = relevance_output.score
        paper.relevance_reasons = relevance_output.reasons

        # Save the paper to the output directory
        with open(filepath, "w") as f:
            json.dump(paper.to_dict(), f, indent=2)
    
    def rate_relevance(self, title, abstract):
        chat_completion = self.openai_client.beta.chat.completions.parse(
            messages=[
                { "role": "system", "content": self.system_prompt},
                { "role": "user", "content": f"Title: {title}\nAbstract: {abstract}"}
            ],
            model=self.llm_model,
            response_format=RelevanceOutput,
        )
        return chat_completion.choices[0].message.parsed

    def create_paper_id(self, paper_metadata):
        """
        Creates a unique, deterministic identifier for a paper based on its metadata.
        
        Args:
            paper_metadata: Dictionary containing paper metadata like title, authors, doi, etc.
            
        Returns:
            A unique string identifier for the paper
        """
        # Sort the metadata to ensure deterministic hashing
        sorted_metadata = json.dumps(paper_metadata, sort_keys=True)
        
        # Create SHA-256 hash
        paper_hash = hashlib.sha256(sorted_metadata.encode()).hexdigest()
        
        # Take first 12 characters for a shorter but still unique ID
        return paper_hash[:12]


class RelevanceOutput(BaseModel):
    score: int
    reasons: str