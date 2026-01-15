"""Podcast generation workflow orchestrating news, script, and voice generation."""

import json
import os
from datetime import datetime
from pathlib import Path

from loguru import logger

from .workflow import Workflow
from .news_fetcher import NewsFetcher
from .podcast_generator import PodcastGenerator
from .voice_generator import VoiceGenerator


class PodcastWorkflow:
    """Orchestrates the complete podcast generation workflow."""

    def __init__(self, cfg: dict):
        """Initialize the podcast workflow.

        Args:
            cfg: Configuration dict from config.yaml
        """
        self.cfg = cfg
        self.output_dir = Path(cfg.get("podcast", {}).get("output_dir", "/app/podcasts"))

        # Initialize paper workflow
        self.paper_workflow = Workflow(cfg)

        # Initialize news fetcher
        news_cfg = cfg.get("news", {})
        self.news_fetcher = NewsFetcher(
            url_template=news_cfg.get("url_template", "https://tldr.tech/ai/{date}")
        )

        # Initialize podcast generator
        podcast_cfg = cfg.get("podcast", {})
        openai_cfg = cfg.get("openai", cfg.get("reader", {}))
        self.podcast_generator = PodcastGenerator(
            podcast_name=podcast_cfg.get("name", "AI Daily Digest"),
            target_duration_minutes=podcast_cfg.get("target_duration_minutes", 10),
            llm_model=openai_cfg.get("llm_model", openai_cfg.get("model", "gpt-5.2")),
            max_tokens=openai_cfg.get("max_tokens", 8000),
            temperature=openai_cfg.get("temperature", 0.7),
            translate_to_chinese=podcast_cfg.get("translate_to_chinese", True),
        )

        # Initialize voice generator (optional - may not have credentials)
        self.voice_generator = None
        volc_cfg = cfg.get("volcengine", {})
        app_id = volc_cfg.get("app_id") or os.environ.get("VOLCENGINE_APP_ID", "")
        access_key = volc_cfg.get("access_key") or os.environ.get("VOLCENGINE_ACCESS_KEY", "")

        if app_id and access_key:
            try:
                speakers = volc_cfg.get("speakers", {})
                self.voice_generator = VoiceGenerator(
                    app_id=app_id,
                    access_key=access_key,
                    resource_id=volc_cfg.get("resource_id", "volc.service_type.10050"),
                    host_voice=speakers.get("host", "zh_male_dayixiansheng_v2_saturn_bigtts"),
                    guest_voice=speakers.get("guest", "zh_female_mizaitongxue_v2_saturn_bigtts"),
                    audio_format=volc_cfg.get("audio_format", "mp3"),
                    sample_rate=volc_cfg.get("sample_rate", 24000),
                    speech_rate=volc_cfg.get("speech_rate", 0),
                    use_head_music=volc_cfg.get("use_head_music", False),
                    use_tail_music=volc_cfg.get("use_tail_music", False),
                )
                logger.info("Voice generator initialized with Volcengine TTS")
            except ImportError as e:
                logger.warning(f"Voice generator not available: {e}")
        else:
            logger.info("TTS credentials not configured - script-only mode")

    def run(self, date_str: str = None) -> dict:
        """Run the podcast generation workflow.

        Args:
            date_str: Target date (YYYY-MM-DD), defaults to today

        Returns:
            Dict with:
                - 'date': Target date string
                - 'script': Podcast script dict with segments
                - 'audio_path': Path to audio file (if TTS enabled), else None
                - 'cached': Whether result was loaded from cache
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Use date as filename: YYYY-MM-DD.mp3
        audio_filename = date_str + ".mp3"

        # Check cache
        audio_path = self.output_dir / audio_filename

        if audio_path.exists():
            logger.info(f"Found cached podcast: {audio_path}")
            return {
                "date": date_str,
                "script": None,
                "audio_path": str(audio_path),
                "cached": True,
            }

        # Fetch papers
        logger.info("Fetching relevant papers...")
        papers = self.paper_workflow.run()
        if not papers:
            logger.warning("No papers found - continuing with news only")

        # Fetch news
        logger.info("Fetching AI news...")
        try:
            news = self.news_fetcher.fetch(date_str)
            if not news:
                logger.info(
                    "No news items available - this is normal for weekends/holidays. "
                    "Podcast will be generated from papers only."
                )
        except Exception as e:
            logger.warning(f"Failed to fetch news: {e}")
            news = []

        if not papers and not news:
            raise ValueError(
                "No papers or news available to generate podcast. "
                "Papers may not be published yet, and news is not available (possibly weekend)."
            )

        # Format papers for podcast
        formatted_papers = []
        for paper in papers:
            formatted_papers.append(
                {
                    "title": paper.get("title", ""),
                    "summary": paper.get("key_contributions") or paper.get("abstract", ""),
                }
            )

        # Generate script
        logger.info("Generating podcast script...")
        script = self.podcast_generator.generate(formatted_papers, news)

        result = {
            "date": date_str,
            "script": script,
            "audio_path": None,
            "cached": False,
        }

        # Generate voice if TTS configured
        if self.voice_generator:
            logger.info("Generating podcast audio...")
            try:
                self.voice_generator.generate(script, audio_path)
                result["audio_path"] = str(audio_path)
            except Exception as e:
                logger.error(f"Audio generation failed: {e}")
        else:
            logger.info("TTS not configured - returning script only")

        return result
