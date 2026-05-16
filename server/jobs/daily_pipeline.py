import json
import logging
import os
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

from crawlers.rss_crawler import RSSCrawler
from ai.script_writer import (
    ScriptWriter,
    PodcastEpisodeScript,
    Segment,
    validate_episode_script,
    ValidationResult,
)
from ai.script_reviewer import review_script, ReviewResult
from tts.openai_tts import TTSService as OpenAITTS
from tts.cosyvoice_tts import CosyVoiceTTS
from audio.assembler import (
    PodcastAudioSegment,
    PodcastEpisodeAudioJob,
    PodcastAudioAssembler,
)
from storage.registry import register_episode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("DailyPipeline")


# ---------------------------------------------------------------------------
# Segment-type → default pause (ms) – used as fallback when the AI doesn't set it
# ---------------------------------------------------------------------------
DEFAULT_PAUSE_MAP = {
    "opening": 1000,
    "headline": 800,
    "line_update": 800,
    "commute_tip": 800,
    "city_story": 800,
    "safety": 800,
    "ending": 0,
}


def _segment_pause(seg: Segment) -> int:
    """Return pauseAfterMs, falling back to per-type default if zero and not ending."""
    if seg.pauseAfterMs > 0:
        return seg.pauseAfterMs
    return DEFAULT_PAUSE_MAP.get(seg.type, 800)


# ---------------------------------------------------------------------------
# DailyPipeline
# ---------------------------------------------------------------------------

class DailyPipeline:
    def __init__(self, theme: str = "metro", city: str = None):
        # MetroCast 默认使用 metro 主题，通过搜索获取地铁出行信息
        # 保留 tech/finance/lifestyle 仅用于兼容旧调用
        THEMES = {
            "metro": [],  # 地铁主题使用 fetch_metro_items 搜索，不走 RSS
            "tech": [
                "https://news.ycombinator.com/rss",
                "https://www.theverge.com/rss/index.xml",
            ],
            "finance": [
                "https://rss.caixin.com/rss/all.xml",
                "https://wallstreetcn.com/rss/articles",
            ],
            "lifestyle": [
                "https://www.zhihu.com/rss",
            ],
        }

        feeds = THEMES.get(theme, THEMES["tech"])
        self.crawler = RSSCrawler(feeds=feeds)
        self.city = city or os.getenv("METROCAST_CITY", "北京")
        self.writer = ScriptWriter(
            model=os.getenv("AI_MODEL", "qwen-max"),
            city=self.city,
        )

        tts_engine = os.getenv("TTS_ENGINE", "openai").lower()
        if tts_engine == "cosyvoice":
            self.tts = CosyVoiceTTS(voice=os.getenv("COSYVOICE_VOICE", "longxiaochun"))
        else:
            self.tts = OpenAITTS(voice=os.getenv("OPENAI_VOICE", "alloy"))

    def run(self, mode: str = "news", topic: str = None) -> Optional[dict]:
        """
        Run the full pipeline.

        Args:
            mode: "news" (RSS), "trending" (search trending), or "deep_dive" (topic search).
            topic: Required for deep_dive mode.
        """
        logger.info("Starting pipeline in %s mode (city=%s)...", mode, self.city)

        # ── 1. Fetch items ──────────────────────────────────────────────
        if mode == "trending":
            logger.info("Discovering metro trending topics for %s...", self.city)
            items = self.crawler.discover_by_search(
                f"{self.city}地铁 今日 出行 通勤 热点 提醒"
            )
        elif mode == "deep_dive" and topic:
            logger.info("Deep Dive on metro topic: %s", topic)
            items = self.crawler.discover_by_search(
                f"{self.city} {topic} 地铁 轨道交通 出行"
            )
        elif self.crawler.feeds:
            # 有 RSS feeds 的主题（tech/finance/lifestyle）
            logger.info("Fetching items from RSS feeds...")
            items = self.crawler.fetch_items()
        else:
            # 默认 metro 主题：使用搜索获取地铁出行信息
            logger.info("Fetching metro transit items via search for %s...", self.city)
            items = self.crawler.fetch_metro_items(self.city)

        logger.info("Fetched %d raw items.", len(items))

        # ── 1b. Filter for transit relevance ───────────────────────────
        if items:
            items = RSSCrawler.filter_transit_relevant(items)
            logger.info("After transit filter: %d relevant items.", len(items))

        if not items:
            logger.warning(
                "No metro/transit-relevant items found for %s. "
                "Skipping episode generation — generating from unrelated "
                "material would produce unsafe metro content.", self.city
            )
            return None

        # ── 2. Generate structured script ───────────────────────────────
        logger.info("Generating structured 小站早班车 script via AI...")
        try:
            tone = "informative" if mode == "deep_dive" else "relaxed"
            script: PodcastEpisodeScript = self.writer.generate_script(
                items, tone=tone, city=self.city,
            )
            logger.info(
                "Script generated: title='%s', %d segments, %d sources",
                script.title, len(script.segments), len(script.sources),
            )
        except Exception as e:
            logger.error("Failed to generate script: %s", e)
            return None

        # ── 2b. Validate script ─────────────────────────────────────────
        validation = validate_episode_script(script)
        if validation.warnings:
            logger.warning("Script validation WARNINGS (%d):", len(validation.warnings))
            for w in validation.warnings:
                logger.warning("  - %s", w)

        if validation.has_fatal:
            logger.error(
                "Script validation FAILED with %d fatal errors — blocking pipeline:",
                len(validation.fatal_errors),
            )
            for err in validation.fatal_errors:
                logger.error("  - %s", err)
            logger.error(
                "Pipeline aborted: unsafe or malformed script. "
                "Regenerate with better material or fix ScriptWriter prompt."
            )
            return None

        logger.info("Script validation PASSED (0 fatal, %d warnings).", len(validation.warnings))

        # ── 2c. Content-safety review ──────────────────────────────────
        logger.info("Running content-safety review...")
        review = review_script(script)
        if review.warnings:
            logger.warning("Review WARNINGS (%d):", len(review.warnings))
            for w in review.warnings:
                logger.warning("  [%s] %s", w.code, w.message)
        if review.has_errors:
            logger.error(
                "Content review FAILED with %d errors — blocking pipeline:",
                len(review.errors),
            )
            for e in review.errors:
                logger.error("  [%s] %s", e.code, e.message)
            logger.error("Pipeline aborted: content-safety review failed.")
            return None
        logger.info("Content review PASSED (0 errors, %d warnings).", len(review.warnings))

        # ── 3. TTS per segment ──────────────────────────────────────────
        logger.info("Synthesizing per-segment audio via TTS...")
        prefix = "knowledge" if mode == "deep_dive" else "episode"
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        segments_dir = os.path.join("storage", f"segments_{prefix}_{date_str}")
        os.makedirs(segments_dir, exist_ok=True)

        all_audio_infos: List[dict] = []
        for seg in script.segments:
            # Collapse newlines so TTS produces ONE file per segment
            flat_text = seg.text.replace("\n", " ").strip()
            if not flat_text:
                logger.warning("Segment %s has empty text, skipping TTS.", seg.segmentId)
                continue

            try:
                seg_infos = self.tts.generate_audio(flat_text, segments_dir)
                if seg_infos:
                    # Tag each output with the segment metadata
                    for info in seg_infos:
                        info["_segmentId"] = seg.segmentId
                        info["_segmentType"] = seg.type
                        info["_segmentTitle"] = seg.title
                        info["_sourceIds"] = seg.sourceIds
                        info["_riskLevel"] = seg.riskLevel
                    all_audio_infos.extend(seg_infos)
                else:
                    logger.warning("TTS returned no audio for segment %s", seg.segmentId)
            except Exception as e:
                logger.error("TTS failed for segment %s: %s", seg.segmentId, e)

        logger.info("TTS generated %d audio files for %d segments.",
                     len(all_audio_infos), len(script.segments))

        if not all_audio_infos:
            logger.error("No TTS audio generated. Aborting.")
            return None

        # ── 4. Build PodcastAudioSegment list for assembler ─────────────
        segments: List[PodcastAudioSegment] = []

        # Map segmentId → Segment for pause lookup
        seg_map = {s.segmentId: s for s in script.segments}

        # Sort audio infos by their segment order (they should already be in order)
        for info in all_audio_infos:
            sid = info.get("_segmentId", f"seg_{info['index']:03d}")
            seg_data = seg_map.get(sid)
            pause_ms = _segment_pause(seg_data) if seg_data else 800

            segments.append(PodcastAudioSegment(
                segment_id=sid,
                audio_path=info["audio_path"],
                pause_after_ms=pause_ms,
            ))

        # ── 5. Assemble via PodcastAudioAssembler (unchanged) ────────────
        logger.info("Assembling audio segments via PodcastAudioAssembler...")

        output_dir = os.path.join("storage", f"assembled_{prefix}_{date_str}")
        job = PodcastEpisodeAudioJob(
            job_id=f"{prefix}_{date_str}",
            segments=segments,
            output_dir=output_dir,
        )

        assembler = PodcastAudioAssembler()
        try:
            result = assembler.assemble(job)
            audio_path = result["final_audio_path"]
            quality = result["quality"]
            logger.info("Assembly complete — status: %s", quality["status"])
            if quality.get("blocking_issues"):
                logger.error("Quality BLOCKING: %s", quality["blocking_issues"])
            if quality.get("warnings"):
                logger.warning("Quality warnings: %s", quality["warnings"])
        except Exception as e:
            logger.error("Failed to assemble audio: %s", e)
            return None

        # ── 6. Persist full episode metadata ─────────────────────────────
        createdAt = datetime.now().isoformat()
        episode_json_path = os.path.join(output_dir, "episode.json")
        episode_meta = {
            "episodeId": script.episodeId,
            "title": script.title,
            "city": script.city,
            "date": script.date,
            "showName": script.showName,
            "hostName": script.hostName,
            "summary": script.summary,
            "segments": [s.model_dump() for s in script.segments],
            "sources": [s.model_dump() for s in script.sources],
            "style": script.style.model_dump(),
            "audioPath": audio_path,
            "createdAt": createdAt,
            "segmentsCount": len(script.segments),
            "durationSec": quality.get("duration_sec", 0),
            "validationResult": {
                "passed": validation.passed,
                "fatalErrors": validation.fatal_errors,
                "warnings": validation.warnings,
            },
            "reviewResult": {
                "passed": review.passed,
                "errors": [e.model_dump() for e in review.errors],
                "warnings": [w.model_dump() for w in review.warnings],
            },
        }

        try:
            with open(episode_json_path, "w", encoding="utf-8") as f:
                json.dump(episode_meta, f, ensure_ascii=False, indent=2)
            logger.info("Episode JSON saved to %s", episode_json_path)
        except Exception as e:
            logger.warning("Failed to save episode JSON: %s", e)

        # ── 7. Register in episode index ──────────────────────────────────
        registry_entry = {
            "episodeId": script.episodeId,
            "title": script.title,
            "city": script.city,
            "date": script.date,
            "summary": script.summary,
            "audioPath": audio_path,
            "createdAt": createdAt,
            "segmentsCount": len(script.segments),
            "durationSec": quality.get("duration_sec", 0),
        }
        try:
            register_episode(registry_entry)
            logger.info("Episode registered in storage/episodes.json")
        except Exception as e:
            logger.warning("Failed to register episode: %s", e)

        logger.info("Pipeline completed successfully!")
        return {
            "title": script.title,
            "episodeId": script.episodeId,
            "audio_path": audio_path,
            "episode_json": episode_json_path,
            "segments_count": len(script.segments),
            "quality": quality,
        }


if __name__ == "__main__":
    pipeline = DailyPipeline()
    pipeline.run()
