"""
TTS backend protocol and factory.

All TTS adapters implement the ``TTSBackend`` protocol so the pipeline
can swap engines via the ``TTS_ENGINE`` environment variable without
touching any orchestration code.

Inspired by Voicebox's ``backend/backends/__init__.py`` Protocol pattern.
"""
from __future__ import annotations

import os
import logging
from typing import Protocol, List, Dict, Any, Optional

logger = logging.getLogger("TTS")


class TTSBackend(Protocol):
    """Contract that every TTS adapter must satisfy."""

    def generate_audio(self, text: str, output_dir: str) -> List[Dict[str, Any]]:
        """
        Generate per-paragraph audio files from *text*.

        Returns a list of segment metadata dicts, each containing at minimum:
          - index: int
          - text: str
          - audio_path: str
          - filename: str
          - voice: str
        """
        ...


def get_tts_backend(
    engine: Optional[str] = None,
    voice: Optional[str] = None,
) -> TTSBackend:
    """
    Factory: return the configured TTS backend instance.

    Reads ``TTS_ENGINE`` from env (default ``cosyvoice``).
    Caches instances per engine name so repeated calls share the same object.
    """
    engine = (engine or os.getenv("TTS_ENGINE", "cosyvoice")).lower()

    if engine == "openai":
        from tts.openai_tts import TTSService
        voice = voice or os.getenv("OPENAI_VOICE", "alloy")
        logger.info("TTS backend: OpenAI (voice=%s)", voice)
        return TTSService(voice=voice)

    # Default: CosyVoice (DashScope)
    from tts.cosyvoice_tts import CosyVoiceTTS
    voice = voice or os.getenv("COSYVOICE_VOICE", "longxiaochun")
    logger.info("TTS backend: CosyVoice (voice=%s)", voice)
    return CosyVoiceTTS(voice=voice)
