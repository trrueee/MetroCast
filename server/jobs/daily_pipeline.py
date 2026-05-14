import logging
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

from crawlers.rss_crawler import RSSCrawler
from ai.script_writer import ScriptWriter
from tts.openai_tts import TTSService as OpenAITTS
from tts.cosyvoice_tts import CosyVoiceTTS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DailyPipeline")

class DailyPipeline:
    def __init__(self, theme: str = "tech"):
        # 预设不同领域的频道池
        THEMES = {
            "tech": [
                "https://news.ycombinator.com/rss",
                "https://www.theverge.com/rss/index.xml"
            ],
            "finance": [
                "https://rss.caixin.com/rss/all.xml",
                "https://wallstreetcn.com/rss/articles"
            ],
            "lifestyle": [
                "https://www.zhihu.com/rss"
            ]
        }
        
        feeds = THEMES.get(theme, THEMES["tech"])
        self.crawler = RSSCrawler(feeds=feeds)
        self.writer = ScriptWriter(model=os.getenv("AI_MODEL", "qwen-max"))
        
        # Select TTS Engine
        tts_engine = os.getenv("TTS_ENGINE", "openai").lower()
        if tts_engine == "cosyvoice":
            self.tts = CosyVoiceTTS(voice=os.getenv("COSYVOICE_VOICE", "longxiaochun"))
        else:
            self.tts = OpenAITTS(voice=os.getenv("OPENAI_VOICE", "alloy"))

    def run(self, mode: str = "news", topic: str = None):
        """
        运行流水线。
        mode: "news" (从 RSS 抓取) 或 "deep_dive" (针对特定主题全网深挖)
        """
        logger.info(f"Starting pipeline in {mode} mode...")
        
        # 1. Fetch items
        if mode == "trending":
            logger.info("Discovering trending topics from across the web...")
            items = self.crawler.discover_by_search("今天全网最火、最有意思的科技与社会热点新闻")
        elif mode == "deep_dive" and topic:
            logger.info(f"Starting Deep Dive on topic: {topic}")
            items = self.crawler.discover_by_search(f"{topic} 深度解析与知识点科普整理")
        else:
            logger.info("Fetching items from RSS feeds...")
            items = self.crawler.fetch_items()
            
        logger.info(f"Fetched {len(items)} items.")
        
        if not items:
            logger.warning("No items fetched. Skipping script generation.")
            return

        # 2. Generate script
        logger.info("Generating script via AI...")
        try:
            # 知识模式下使用更正式的语气
            script = self.writer.generate_script(items, tone="informative" if mode == "deep_dive" else "relaxed")
            logger.info(f"Script generated: {script.episode_title}")
        except Exception as e:
            logger.error(f"Failed to generate script: {e}")
            return

        # 3. Generate Audio
        logger.info("Synthesizing audio via TTS...")
        prefix = "knowledge" if mode == "deep_dive" else "episode"
        audio_filename = f"{prefix}_{datetime.now().strftime('%Y%m%d')}.mp3"
        audio_path = os.path.join("storage", audio_filename)
        
        os.makedirs("storage", exist_ok=True)
        
        try:
            self.tts.generate_audio(script.full_script, audio_path)
            logger.info(f"Audio generated successfully: {audio_path}")
        except Exception as e:
            logger.error(f"Failed to generate audio: {e}")
            return

        logger.info("Pipeline completed successfully!")
        return {
            "title": script.episode_title,
            "audio_path": audio_path,
            "script": script.full_script
        }

if __name__ == "__main__":
    pipeline = DailyPipeline()
    pipeline.run() 
