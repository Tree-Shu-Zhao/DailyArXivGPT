import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from pydantic import BaseModel


class PaperReader:
    def __init__(self, system_prompt, llm_model="gpt-4o", relevance_threshold=7, output_dir="data", num_threads=32, key_contributions_prompt=None):
        self.openai_client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        self.system_prompt = system_prompt
        self.key_contributions_prompt = key_contributions_prompt
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

        # If the relevance score is high, we need to extract the key technical contributions from the paper
        if paper.relevance_score >= self.threshold:
            key_contributions = self.extract_key_contributions(paper.title, paper.abstract, paper.link)
            paper.key_contributions = key_contributions
        else:
            paper.key_contributions = None

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
    
    def extract_key_contributions(self, title, abstract, link):
        html_link = link.replace("abs", "html")

        # Fetch HTML content
        try:
            response = requests.get(html_link, timeout=30)
            if response.status_code != 200:
                return None
        except requests.RequestException:
            return None

        # Parse and extract S1 section (Introduction)
        soup = BeautifulSoup(response.text, 'html.parser')
        section = soup.find('section', id='S1')
        if not section:
            return None

        # Remove citation tags
        for cite in section.find_all('cite'):
            cite.decompose()

        # Extract text paragraph by paragraph while maintaining document order
        paragraphs = []
        processed_lists = set()  # Track processed lists to avoid duplicates

        # Find all paragraph containers, but skip those inside list items
        for para_div in section.find_all('div', class_='ltx_para'):
            # Check if this div is inside a list item
            if para_div.find_parent('li'):
                continue

            # Get text from this paragraph, merging all sentences
            para_text = para_div.get_text(separator=' ', strip=True)
            if para_text:
                # Normalize whitespace
                para_text = ' '.join(para_text.split())
                paragraphs.append(para_text)

            # Check if this paragraph is followed by a list
            next_sibling = para_div.find_next_sibling()
            while next_sibling and next_sibling.name not in ['ul', 'ol', 'div']:
                next_sibling = next_sibling.find_next_sibling()

            if next_sibling and next_sibling.name in ['ul', 'ol'] and id(next_sibling) not in processed_lists:
                processed_lists.add(id(next_sibling))
                list_items = []
                for li in next_sibling.find_all('li', recursive=False):
                    # Get text from list item, normalizing whitespace
                    item_text = li.get_text(separator=' ', strip=True)
                    item_text = ' '.join(item_text.split())
                    if item_text:
                        list_items.append(f"• {item_text}")

                if list_items:
                    paragraphs.append('\n'.join(list_items))

        # If no paragraphs found, try finding all p tags
        if not paragraphs:
            for p in section.find_all('p'):
                para_text = p.get_text(separator=' ', strip=True)
                if para_text:
                    para_text = ' '.join(para_text.split())
                    paragraphs.append(para_text)

        # Join paragraphs with double newlines
        introduction = '\n\n'.join(paragraphs)

        # Call LLM with key contributions prompt
        if not self.key_contributions_prompt:
            return None

        chat_completion = self.openai_client.beta.chat.completions.parse(
            messages=[
                {"role": "system", "content": self.key_contributions_prompt},
                {"role": "user", "content": f"Title: {title}\nAbstract: {abstract}\nIntroduction: {introduction}"}
            ],
            model=self.llm_model,
            response_format=KeyContributionsOutput,
        )
        return chat_completion.choices[0].message.parsed.summary

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


class KeyContributionsOutput(BaseModel):
    summary: str