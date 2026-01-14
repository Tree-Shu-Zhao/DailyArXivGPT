"""Generate podcast script from papers and news using OpenAI API."""

import json
import os

from loguru import logger

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


PODCAST_NEWS_ANCHOR_PROMPT = """You are a podcast script writer for an AI research and news show called "{podcast_name}".

Your task is to create an engaging two-speaker podcast script with:
- HOST: Dr. Zhao, a professional news anchor who introduces topics and guides the conversation
- GUEST: Dr. Chen, an AI expert who presents the provided information in a conversational way

Guidelines:
- Target duration: approximately {duration} minutes when read aloud (roughly {word_count} words)
- IMPORTANT: Use ONLY the information provided in the summaries. Do NOT add extra analysis, speculation, or information not present in the source material.
- Your job is to REORGANIZE and REPHRASE the existing summaries into natural podcast dialogue, not to generate new insights.
- Start with a brief HOST greeting and GUEST introduction
- Cover items in order of importance/interest
- For research papers: HOST introduces the paper title, GUEST rephrases the provided summary in conversational language
- For news: HOST introduces the headline, GUEST rephrases the provided summary conversationally
- Keep transitions brief and natural
- End with a short wrap-up (1-2 exchanges)

CRITICAL OUTPUT FORMAT:
You MUST output valid JSON with this exact structure (no other text):
{{
  "segments": [
    {{"speaker": "host", "text": "Welcome to {podcast_name}..."}},
    {{"speaker": "guest", "text": "Thanks for having me..."}},
    ...
  ]
}}

Each segment should be a natural speaking turn (1-4 sentences). Alternate between host and guest naturally.
"""


class PodcastGenerator:
    """Generates podcast scripts from papers and news using OpenAI API."""

    def __init__(
        self,
        podcast_name: str = "AI Daily Digest",
        target_duration_minutes: int = 10,
        llm_model: str = "gpt-5.2",
        max_tokens: int = 8000,
        temperature: float = 0.7,
        translate_to_chinese: bool = True,
    ):
        """Initialize the podcast generator.

        Args:
            podcast_name: Name of the podcast
            target_duration_minutes: Target podcast duration in minutes
            llm_model: OpenAI model to use
            max_tokens: Maximum tokens for completion
            temperature: Temperature for generation
            translate_to_chinese: Whether to translate script to Chinese for TTS

        Raises:
            ImportError: If openai package is not installed
            ValueError: If OPENAI_API_KEY is not set
        """
        if OpenAI is None:
            raise ImportError(
                "openai package is required. Install with: pip install openai"
            )

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.podcast_name = podcast_name
        self.duration = target_duration_minutes
        self.llm_model = llm_model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.translate = translate_to_chinese

    def generate(self, papers: list[dict], news: list[dict]) -> dict:
        """Generate podcast script from papers and news.

        Args:
            papers: List of paper dicts with 'title' and 'summary' (or 'key_contributions')
            news: List of news dicts with 'title', 'summary', 'section'

        Returns:
            Dict with 'segments' list containing speaker/text pairs

        Raises:
            ValueError: If both papers and news are empty (to avoid wasting tokens)
        """
        # Guard against empty content to avoid wasting tokens
        if not papers and not news:
            raise ValueError(
                "Cannot generate podcast with no papers and no news. "
                "This would waste API tokens with empty content."
            )

        # Approximate words for target duration (150 words per minute)
        word_count = self.duration * 150

        # Build the user prompt with papers and news
        user_prompt = ""

        if papers:
            user_prompt += "## Research Papers\n\n"
            for paper in papers:
                user_prompt += f"**{paper.get('title', '')}**\n"
                # Try 'summary' first, fall back to 'key_contributions'
                summary = paper.get("summary") or paper.get("key_contributions", "")
                user_prompt += f"{summary}\n\n"
        else:
            logger.info("No papers available for podcast generation")

        if news:
            user_prompt += "\n## AI News\n\n"
            for item in news:
                user_prompt += f"**[{item.get('section', 'News')}] {item.get('title', '')}**\n"
                user_prompt += f"{item.get('summary', '')}\n\n"
        else:
            logger.info("No news available for podcast generation (normal on weekends)")

        # Sanity check - ensure we have actual content
        if not user_prompt.strip():
            raise ValueError("Generated empty prompt - no content to create podcast from")

        # Generate script
        system_prompt = PODCAST_NEWS_ANCHOR_PROMPT.format(
            podcast_name=self.podcast_name,
            duration=self.duration,
            word_count=word_count,
        )

        logger.info(f"Generating podcast script with {self.llm_model}...")

        response = self.client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        content = response.choices[0].message.content
        script = self._parse_json_response(content)

        logger.info(f"Generated {len(script.get('segments', []))} segments")

        # Translate to Chinese if requested (for TTS)
        if self.translate:
            logger.info("Translating script to Chinese...")
            script = self._translate_to_chinese(script)

        return script

    def _parse_json_response(self, content: str) -> dict:
        """Parse JSON response from OpenAI, handling edge cases."""
        content = content.strip()

        # Remove potential BOM characters
        if content.startswith("\ufeff"):
            content = content[1:]

        # Handle potential markdown code blocks (```json ... ```)
        if content.startswith("```"):
            lines = content.split("\n")
            lines = lines[1:]  # Remove first line (```json or ```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response content: {content[:500]}...")
            raise

    def _translate_to_chinese(self, script: dict) -> dict:
        """Translate podcast script segments to Chinese."""
        segments_text = json.dumps(script["segments"], ensure_ascii=False, indent=2)

        response = self.client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate the following podcast script segments to Chinese. "
                        "Maintain the same JSON structure with 'speaker' and 'text' fields. "
                        "Keep speaker names as 'host' and 'guest' (do not translate these). "
                        'Return valid JSON only with the structure: {"segments": [...]}'
                    ),
                },
                {"role": "user", "content": segments_text},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        content = response.choices[0].message.content
        translated = self._parse_json_response(content)

        # Handle both {"segments": [...]} and direct [...] formats
        if "segments" in translated:
            return translated
        return {"segments": translated}
