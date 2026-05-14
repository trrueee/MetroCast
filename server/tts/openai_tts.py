import os
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class TTSService:
    def __init__(self, voice: str = "alloy"):
        self.voice = voice
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_audio(self, text: str, output_path: str) -> str:
        """
        Generates audio from text using OpenAI TTS.
        """
        response = self.client.audio.speech.create(
            model="tts-1",
            voice=self.voice,
            input=text
        )
        
        response.stream_to_file(output_path)
        return output_path

if __name__ == "__main__":
    pass
    # Test
    # tts = TTSService()
    # tts.generate_audio("你好，欢迎收听地铁播客。", "test.mp3")
