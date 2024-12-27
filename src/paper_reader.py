import os

from openai import OpenAI
from pydantic import BaseModel

from .prompt import RELEVANCE_SCORE_PROMPT


class PaperReader:
    def __init__(self, llm_model="gpt-4o", relevance_threshold=7):
        self.openai_client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        self.llm_model = llm_model
        self.threshold = relevance_threshold

    def run(self, papers):
        relevant_papers = []
        for paper in papers:
            # Preprocess, remove some unnecessary content, like blank, html tags, etc.
            paper.title = self._remove_last_bracket_content(paper.title).strip()
            paper.description = self._replace_new_line_with_space(self._remove_p_tag(paper.description)).strip()

            # Rate the relevance of the paper
            relevance_output = self._rate_relevance(paper.title, paper.description)
            paper.relevance_score = relevance_output.score
            paper.relevance_reasons = relevance_output.reasons
            if relevance_output.score >= self.threshold:
                relevant_papers.append(paper)
        return relevant_papers
    
    def _rate_relevance(self, title, abstract):
        chat_completion = self.openai_client.beta.chat.completions.parse(
            messages=[
                { "role": "system", "content": RELEVANCE_SCORE_PROMPT},
                { "role": "user", "content": f"Title: {title}\nAbstract: {abstract}"}
            ],
            model=self.llm_model,
            response_format=RelevanceOutput,
        )
        return chat_completion.choices[0].message.parsed

    def _remove_last_bracket_content(self, text):
        return text[:text.rindex('(')]
    
    def _remove_p_tag(self, text):
        return text.replace("<p>", "").replace("</p>", "")
    
    def _replace_new_line_with_space(self, text):
        return text.replace("\n", " ")


class RelevanceOutput(BaseModel):
    score: int
    reasons: str