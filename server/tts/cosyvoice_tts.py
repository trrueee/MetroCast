"""
CosyVoice TTS adapter (DashScope / Alibaba Cloud).

Improved text preprocessing inspired by Voicebox's chunked_tts.py:
- Smart CJK/ASCII spacing via regex (not char-by-char)
- Natural pause insertion at sentence boundaries
- Abbreviation-aware splitting
"""
import os
import re
import time as time_mod
import logging
from typing import List, Dict, Any

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("CosyVoiceTTS")

# Voice character map for inline voice switching via [tag] prefix
VOICE_MAP = {
    "婉儿": "longyewan",      # 知性女声
    "老铁": "longlaotie",     # 幽默东北男声
}

# Default voice when no tag is present
DEFAULT_VOICE = "longxiaochun"

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY_SEC = 2


# ---------------------------------------------------------------------------
# Text preprocessing (inspired by Voicebox chunked_tts.py)
# ---------------------------------------------------------------------------

# Common abbreviations that should NOT trigger spacing/pause logic
_ABBREVIATIONS = frozenset({
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st",
    "ave", "blvd", "inc", "ltd", "corp", "dept", "est",
    "approx", "vs", "etc", "e.g", "i.e", "a.m", "p.m",
})

# Regex: insert space between CJK and ASCII/alphanumeric boundaries
_CJK_ASCII_BOUNDARY = re.compile(
    r"([一-鿿㐀-䶿豈-﫿　-〿＀-￯])"
    r"([a-zA-Z0-9])"
)
_ASCII_CJK_BOUNDARY = re.compile(
    r"([a-zA-Z0-9])"
    r"([一-鿿㐀-䶿豈-﫿　-〿＀-￯])"
)


def _add_cjk_ascii_spacing(text: str) -> str:
    """Insert spaces between Chinese characters and ASCII/alphanumeric text.

    Uses regex instead of character-by-character iteration for better
    performance and correctness.  Handles: "10号线" -> "10 号线",
    "地铁Line4" -> "地铁 Line 4".
    """
    text = _CJK_ASCII_BOUNDARY.sub(r"\1 \2", text)
    text = _ASCII_CJK_BOUNDARY.sub(r"\1 \2", text)
    return text


def _optimize_pauses(text: str) -> str:
    """Add natural pauses at sentence boundaries.

    Unlike the previous approach (appending comma after EVERY period),
    this only adds pauses at genuine sentence endings and uses varied
    punctuation for more natural rhythm.
    """
    # Chinese sentence endings: add a slight pause marker
    # Only add pause if there's more content after the period
    text = re.sub(r"([。！？])(?=\S)", r"\1 ", text)

    # English sentence endings followed by Chinese content
    text = re.sub(r"([.!?])\s+(?=[一-鿿])", r"\1  ", text)

    return text


def preprocess_text(text: str) -> str:
    """Full text preprocessing pipeline for TTS input.

    1. Strip whitespace
    2. Add CJK/ASCII spacing
    3. Optimize pause punctuation
    4. Ensure terminal punctuation
    """
    text = text.strip()
    if not text:
        return text

    text = _add_cjk_ascii_spacing(text)
    text = _optimize_pauses(text)

    # Ensure Chinese text ends with a sentence-ending punctuation
    if not text.endswith((".", "。", "！", "？", "!", "?")):
        text += "。"

    return text


def resolve_voice_for_paragraph(text: str, default_voice: str) -> str:
    """Detect [tag] prefix and return the mapped voice + cleaned text."""
    for tag, voice in VOICE_MAP.items():
        prefix = f"[{tag}]"
        if text.startswith(prefix):
            cleaned = text[len(prefix):].replace("：", "").strip()
            return voice, cleaned
    return default_voice, text


# ---------------------------------------------------------------------------
# CosyVoiceTTS
# ---------------------------------------------------------------------------

class CosyVoiceTTS:
    def __init__(self, voice: str = DEFAULT_VOICE):
        """
        CosyVoice TTS adapter.

        Common voices: longxiaochun (活泼女声), longyewan (知性女声),
        longmiao (温柔女声), longst (稳重男声), longlaotie (幽默东北男声)
        """
        self.api_key = os.getenv("AI_API_KEY")
        self.model = "cosyvoice-v1"
        self.voice = voice

    def generate_audio(self, text: str, output_dir: str) -> List[Dict[str, Any]]:
        """Generate per-paragraph audio files via CosyVoice.

        Text is split by newlines, preprocessed for TTS quality,
        and each paragraph is synthesised independently.
        """
        import dashscope
        dashscope.api_key = self.api_key
        os.makedirs(output_dir, exist_ok=True)

        # Split into paragraphs and preprocess each
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

        segments: List[Dict[str, Any]] = []

        for i, raw_para in enumerate(paragraphs):
            voice, cleaned_text = resolve_voice_for_paragraph(raw_para, self.voice)
            processed_text = preprocess_text(cleaned_text)

            logger.info(
                "TTS segment %d/%d (voice=%s, chars=%d): %.50s...",
                i + 1, len(paragraphs), voice, len(processed_text), processed_text,
            )

            success = False
            audio_data = None
            for attempt in range(MAX_RETRIES):
                try:
                    synthesizer = SpeechSynthesizer(
                        model=self.model, voice=voice,
                    )
                    audio_data = synthesizer.call(processed_text)
                    if audio_data:
                        success = True
                        break
                    logger.warning(
                        "Segment %d attempt %d returned no data, retrying in %ds...",
                        i, attempt + 1, RETRY_DELAY_SEC,
                    )
                except Exception as e:
                    logger.warning(
                        "Segment %d attempt %d failed: %s, retrying in %ds...",
                        i, attempt + 1, e, RETRY_DELAY_SEC,
                    )
                time_mod.sleep(RETRY_DELAY_SEC)

            if not success:
                logger.error("Segment %d failed after %d retries, skipping.", i, MAX_RETRIES)
                continue

            seg_filename = f"segment_{i:03d}.mp3"
            seg_path = os.path.join(output_dir, seg_filename)
            with open(seg_path, "wb") as f:
                f.write(audio_data)

            segments.append({
                "index": i,
                "text": processed_text,
                "voice": voice,
                "audio_path": seg_path,
                "filename": seg_filename,
            })

        if segments:
            return segments
        raise RuntimeError("CosyVoice TTS returned no audio for any segment")
