import os
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class TTSService:
    def __init__(self, voice: str = "alloy"):
        self.voice = voice
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_audio(self, text: str, output_dir: str) -> list:
        """
        Splits text by newlines, generates per-segment MP3 via OpenAI TTS.
        Returns a list of segment metadata dicts.
        """
        os.makedirs(output_dir, exist_ok=True)
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        segments = []

        for i, p in enumerate(paragraphs):
            seg_filename = f"segment_{i:03d}.mp3"
            seg_path = os.path.join(output_dir, seg_filename)

            response = self.client.audio.speech.create(
                model="tts-1",
                voice=self.voice,
                input=p
            )
            response.stream_to_file(seg_path)

            segments.append({
                "index": i,
                "text": p,
                "voice": self.voice,
                "audio_path": seg_path,
                "filename": seg_filename,
            })

        if not segments:
            raise Exception("OpenAI TTS generated no segments")
        return segments
