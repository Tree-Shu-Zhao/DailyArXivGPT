"""Generate voice audio from podcast script using volcengine TTS API."""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

from loguru import logger

try:
    import websockets
except ImportError:
    websockets = None

from .volcengine_protocols import (
    EventType,
    MsgType,
    finish_connection,
    finish_session,
    receive_message,
    start_connection,
    start_session,
    wait_for_event,
)

ENDPOINT = "wss://openspeech.bytedance.com/api/v3/sami/podcasttts"


class VoiceGenerator:
    """Generates voice audio from podcast scripts using Volcengine TTS API."""

    def __init__(
        self,
        app_id: str,
        access_key: str,
        resource_id: str = "volc.service_type.10050",
        host_voice: str = "zh_male_dayixiansheng_v2_saturn_bigtts",
        guest_voice: str = "zh_female_mizaitongxue_v2_saturn_bigtts",
        audio_format: str = "mp3",
        sample_rate: int = 24000,
        speech_rate: int = 0,
        use_head_music: bool = False,
        use_tail_music: bool = False,
    ):
        """Initialize the voice generator.

        Args:
            app_id: Volcengine application ID
            access_key: Volcengine access key
            resource_id: Volcengine resource ID
            host_voice: Voice name for the host speaker
            guest_voice: Voice name for the guest speaker
            audio_format: Output audio format (mp3, wav)
            sample_rate: Audio sample rate
            speech_rate: Speech rate (-100 to 100)
            use_head_music: Whether to add intro music
            use_tail_music: Whether to add outro music

        Raises:
            ImportError: If websockets package is not installed
            ValueError: If app_id or access_key is not provided
        """
        if websockets is None:
            raise ImportError(
                "websockets package is required. Install with: pip install websockets"
            )

        if not app_id or not access_key:
            raise ValueError("Volcengine app_id and access_key are required")

        self.app_id = app_id
        self.access_key = access_key
        self.resource_id = resource_id
        self.speaker_mapping = {"host": host_voice, "guest": guest_voice}
        self.audio_format = audio_format
        self.sample_rate = sample_rate
        self.speech_rate = speech_rate
        self.use_head_music = use_head_music
        self.use_tail_music = use_tail_music

    def generate(self, script: dict, output_path: Path) -> Path:
        """Generate audio from podcast script.

        Args:
            script: Dict with 'segments' list containing speaker/text pairs
            output_path: Path to save the audio file

        Returns:
            Path to the generated audio file

        Raises:
            ValueError: If no segments found in script
            RuntimeError: If audio generation fails
        """
        nlp_texts = self._convert_script(script)
        if not nlp_texts:
            raise ValueError("No segments found in podcast script")

        logger.info(f"Generating audio for {len(nlp_texts)} segments...")

        # Run async audio generation
        return asyncio.run(self._generate_audio(nlp_texts, output_path))

    def _convert_script(self, script: dict) -> list[dict]:
        """Convert podcast script segments to volcengine nlp_texts format."""
        nlp_texts = []
        for segment in script.get("segments", []):
            speaker_key = segment.get("speaker", "host")
            speaker_name = self.speaker_mapping.get(speaker_key, speaker_key)
            nlp_texts.append(
                {
                    "text": segment.get("text", ""),
                    "speaker": speaker_name,
                }
            )
        return nlp_texts

    async def _generate_audio(self, nlp_texts: list[dict], output_path: Path) -> Path:
        """Generate audio using volcengine podcast TTS API."""
        # Build headers
        headers = {
            "X-Api-App-Id": self.app_id,
            "X-Api-App-Key": "aGjiRDfUWi",
            "X-Api-Access-Key": self.access_key,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Connect-Id": str(uuid.uuid4()),
        }

        # Build request parameters
        req_params = {
            "input_id": f"podcast_{int(time.time())}",
            "nlp_texts": nlp_texts,
            "action": 3,  # Multi-speaker mode with nlp_texts
            "use_head_music": self.use_head_music,
            "use_tail_music": self.use_tail_music,
            "input_info": {
                "input_url": "",
                "return_audio_url": False,
                "only_nlp_text": False,
            },
            "speaker_info": {
                "random_order": False,
            },
            "audio_config": {
                "format": self.audio_format,
                "sample_rate": self.sample_rate,
                "speech_rate": self.speech_rate,
            },
        }

        podcast_audio = bytearray()
        is_podcast_round_end = True
        last_round_id = -1
        task_id = ""
        retry_num = 5
        current_round = 0

        # Suppress websockets logging noise
        logging.getLogger("websockets").setLevel(logging.WARNING)

        while retry_num > 0:
            websocket = await websockets.connect(
                ENDPOINT,
                additional_headers=headers,
            )

            try:
                # Add retry info if resuming from previous failure
                if not is_podcast_round_end and task_id:
                    req_params["retry_info"] = {
                        "retry_task_id": task_id,
                        "last_finished_round_id": last_round_id,
                    }

                # Start connection
                await start_connection(websocket)
                await wait_for_event(
                    websocket, MsgType.FullServerResponse, EventType.ConnectionStarted
                )

                # Start session
                session_id = str(uuid.uuid4())
                if not task_id:
                    task_id = session_id

                await start_session(
                    websocket, json.dumps(req_params).encode(), session_id
                )
                await wait_for_event(
                    websocket, MsgType.FullServerResponse, EventType.SessionStarted
                )

                # Finish session to start processing
                await finish_session(websocket, session_id)

                # Receive audio chunks
                audio = bytearray()

                while True:
                    msg = await receive_message(websocket)

                    # Audio data chunk
                    if (
                        msg.type == MsgType.AudioOnlyServer
                        and msg.event == EventType.PodcastRoundResponse
                    ):
                        audio.extend(msg.payload)
                        logger.debug(f"Audio received: {len(msg.payload)} bytes")

                    # Error message
                    elif msg.type == MsgType.Error:
                        raise RuntimeError(f"Server error: {msg.payload.decode()}")

                    elif msg.type == MsgType.FullServerResponse:
                        # Round start
                        if msg.event == EventType.PodcastRoundStart:
                            data = json.loads(msg.payload.decode())
                            voice = data.get("speaker", "unknown")
                            current_round = data.get("round_id", 0)
                            if current_round == -1:
                                voice = "head_music"
                            elif current_round == 9999:
                                voice = "tail_music"
                            is_podcast_round_end = False
                            logger.info(f"Round {current_round} started: {voice}")

                        # Round end
                        elif msg.event == EventType.PodcastRoundEnd:
                            data = json.loads(msg.payload.decode())
                            if data.get("is_error"):
                                logger.error(f"Round error: {data}")
                                break
                            is_podcast_round_end = True
                            last_round_id = current_round
                            if audio:
                                podcast_audio.extend(audio)
                                logger.info(
                                    f"Round {current_round} completed: {len(audio)} bytes"
                                )
                                audio.clear()

                        # Podcast end
                        elif msg.event == EventType.PodcastEnd:
                            data = json.loads(msg.payload.decode())
                            logger.info(f"Podcast generation completed: {data}")

                    # Session finished
                    if msg.event == EventType.SessionFinished:
                        break

                # Finish connection
                await finish_connection(websocket)
                await wait_for_event(
                    websocket, MsgType.FullServerResponse, EventType.ConnectionFinished
                )

                # Check if podcast completed successfully
                if is_podcast_round_end:
                    break
                else:
                    logger.warning(
                        f"Podcast not finished, resuming from round {last_round_id}"
                    )
                    retry_num -= 1
                    await asyncio.sleep(1)

            finally:
                await websocket.close()

        if not podcast_audio:
            raise RuntimeError("No audio data received from TTS API")

        # Save audio file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(podcast_audio)

        logger.info(f"Audio saved: {output_path} ({len(podcast_audio)} bytes)")
        return output_path
