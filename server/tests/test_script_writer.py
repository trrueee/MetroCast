"""
Tests for script_writer.py — models, validation, and backward compatibility.

Usage:
    cd server
    python -m pytest tests/test_script_writer.py -v
    # or
    python tests/test_script_writer.py
"""
import json
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.script_writer import (
    PodcastEpisodeScript,
    Segment,
    Source,
    StyleInfo,
    validate_episode_script,
    ValidationResult,
    ScriptWriter,
    PodcastScript,   # backward-compat alias
    Chapter,         # backward-compat alias
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_valid_script(**overrides) -> PodcastEpisodeScript:
    """Build a minimal valid episode script."""
    defaults = {
        "episodeId": "xzzbc_20260516",
        "title": "测试播客",
        "city": "北京",
        "date": "2026-05-16",
        "summary": "测试摘要",
        "segments": [
            Segment(
                segmentId="seg_001", type="opening", title="开场",
                text="早上好，我是小站姐，欢迎来到《小站早班车》。",
                pauseAfterMs=1000, estimatedDurationSec=30,
            ),
            Segment(
                segmentId="seg_002", type="headline", title="要闻",
                text="今天北京地铁运行正常。",
                pauseAfterMs=800, estimatedDurationSec=45,
                sourceIds=["src_001"], riskLevel="low",
            ),
            Segment(
                segmentId="seg_003", type="ending", title="结尾",
                text="今天的《小站早班车》就到这里，祝你一路顺利，我们明天见。",
                pauseAfterMs=0, estimatedDurationSec=20,
            ),
        ],
        "sources": [
            Source(sourceId="src_001", title="地铁日报", url="https://example.com", type="official"),
        ],
    }
    defaults.update(overrides)
    return PodcastEpisodeScript(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPodcastEpisodeScript(unittest.TestCase):
    """Model creation and serialization."""

    def test_valid_script_creation(self):
        script = make_valid_script()
        self.assertEqual(script.title, "测试播客")
        self.assertEqual(script.showName, "小站早班车")
        self.assertEqual(script.hostName, "小站姐")
        self.assertEqual(len(script.segments), 3)

    def test_segment_types(self):
        script = make_valid_script()
        types = [s.type for s in script.segments]
        self.assertEqual(types, ["opening", "headline", "ending"])

    def test_style_defaults(self):
        script = make_valid_script()
        self.assertIn("城市通勤感", script.style.tone)
        self.assertIn("不要每段都开场", script.style.avoid)

    def test_json_round_trip(self):
        script = make_valid_script()
        data = script.model_dump()
        restored = PodcastEpisodeScript(**data)
        self.assertEqual(restored.title, script.title)
        self.assertEqual(len(restored.segments), len(script.segments))
        self.assertEqual(restored.segments[0].text, script.segments[0].text)

    def test_json_serialization(self):
        script = make_valid_script()
        json_str = script.model_dump_json(indent=2, ensure_ascii=False)
        data = json.loads(json_str)
        self.assertEqual(data["showName"], "小站早班车")
        self.assertEqual(data["hostName"], "小站姐")
        self.assertEqual(len(data["segments"]), 3)
        self.assertIn("style", data)
        self.assertIn("avoid", data["style"])


class TestValidateEpisodeScript(unittest.TestCase):
    """Validation rule checks — uses ValidationResult with fatal_errors / warnings."""

    def test_valid_script_passes(self):
        result = validate_episode_script(make_valid_script())
        self.assertTrue(result.passed, f"Unexpected fatal: {result.fatal_errors}")
        self.assertFalse(result.has_fatal)
        self.assertEqual(len(result.fatal_errors), 0,
                         f"Unexpected fatal: {result.fatal_errors}")

    def test_missing_opening(self):
        script = make_valid_script(segments=[
            Segment(segmentId="seg_001", type="headline", title="闻", text="新闻。"),
            Segment(segmentId="seg_002", type="ending", title="结", text="再见。"),
        ])
        result = validate_episode_script(script)
        self.assertTrue(result.has_fatal)
        self.assertTrue(any("opening" in e.lower() for e in result.fatal_errors))

    def test_missing_ending(self):
        script = make_valid_script(segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎。"),
            Segment(segmentId="seg_002", type="headline", title="闻", text="新闻。"),
        ])
        result = validate_episode_script(script)
        self.assertTrue(result.has_fatal)
        self.assertTrue(any("ending" in e.lower() for e in result.fatal_errors))

    def test_ending_not_last(self):
        script = make_valid_script(segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎。"),
            Segment(segmentId="seg_002", type="ending", title="结", text="再见。"),
            Segment(segmentId="seg_003", type="headline", title="闻", text="新闻。"),
        ])
        result = validate_episode_script(script)
        self.assertTrue(result.has_fatal)
        self.assertTrue(any("last segment" in e for e in result.fatal_errors))

    def test_ending_keyword_in_headline(self):
        script = make_valid_script(segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎。"),
            Segment(segmentId="seg_002", type="headline", title="闻",
                    text="这条新闻很重要。今天的节目就到这里，感谢收听。"),
            Segment(segmentId="seg_003", type="ending", title="结", text="明天见。"),
        ])
        result = validate_episode_script(script)
        self.assertTrue(result.has_fatal)
        self.assertTrue(any("ending keyword" in e for e in result.fatal_errors))

    def test_opening_not_first(self):
        script = make_valid_script(segments=[
            Segment(segmentId="seg_001", type="headline", title="闻", text="先播新闻。"),
            Segment(segmentId="seg_002", type="opening", title="开", text="欢迎收听。"),
            Segment(segmentId="seg_003", type="ending", title="结", text="再见。"),
        ])
        result = validate_episode_script(script)
        self.assertTrue(result.has_fatal)
        self.assertTrue(any("first segment" in e for e in result.fatal_errors))

    def test_high_risk_without_source(self):
        script = make_valid_script(segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎。"),
            Segment(segmentId="seg_002", type="line_update", title="线",
                    text="10号线今日全线停运。", riskLevel="high", sourceIds=[]),
            Segment(segmentId="seg_003", type="ending", title="结", text="再见。"),
        ])
        result = validate_episode_script(script)
        self.assertTrue(result.has_fatal)
        self.assertTrue(any("no sourceIds" in e for e in result.fatal_errors))

    def test_empty_segment_text(self):
        script = make_valid_script(segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎。"),
            Segment(segmentId="seg_002", type="headline", title="闻", text=""),
            Segment(segmentId="seg_003", type="ending", title="结", text="再见。"),
        ])
        result = validate_episode_script(script)
        self.assertTrue(result.has_fatal)
        self.assertTrue(any("empty text" in e for e in result.fatal_errors))

    def test_non_sequential_ids(self):
        """Non-sequential segmentIds are a warning, not fatal."""
        script = make_valid_script(segments=[
            Segment(segmentId="seg_005", type="opening", title="开", text="欢迎。"),
            Segment(segmentId="seg_001", type="headline", title="闻", text="新闻。"),
            Segment(segmentId="seg_003", type="ending", title="结", text="再见。"),
        ])
        result = validate_episode_script(script)
        self.assertFalse(result.has_fatal,
                         f"Non-sequential IDs should be warning, not fatal: {result.fatal_errors}")
        self.assertTrue(any("expected" in e for e in result.warnings))

    def test_opening_keyword_in_headline(self):
        script = make_valid_script(segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎收听。"),
            Segment(segmentId="seg_002", type="headline", title="闻",
                    text="大家好，今天我们先看一条重要新闻。"),
            Segment(segmentId="seg_003", type="ending", title="结", text="再见。"),
        ])
        result = validate_episode_script(script)
        self.assertTrue(result.has_fatal)
        self.assertTrue(any("opening keyword" in e for e in result.fatal_errors))

    def test_unknown_source_id(self):
        script = make_valid_script(segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎。"),
            Segment(segmentId="seg_002", type="headline", title="闻", text="新闻。",
                    sourceIds=["src_999"]),
            Segment(segmentId="seg_003", type="ending", title="结", text="再见。"),
        ])
        result = validate_episode_script(script)
        self.assertTrue(result.has_fatal)
        self.assertTrue(any("unknown sourceId" in e for e in result.fatal_errors))

    def test_no_segments(self):
        script = PodcastEpisodeScript(
            episodeId="empty", title="Empty", city="北京", date="2026-05-16",
        )
        result = validate_episode_script(script)
        self.assertTrue(result.has_fatal)
        self.assertTrue(any("No segments" in e for e in result.fatal_errors))

    def test_all_ending_keywords_blocked(self):
        """Every ending keyword should trigger a fatal error if found in a non-ending segment."""
        from ai.script_writer import ENDING_KEYWORDS
        for kw in ENDING_KEYWORDS:
            script = make_valid_script(segments=[
                Segment(segmentId="seg_001", type="opening", title="开", text="欢迎。"),
                Segment(segmentId="seg_002", type="headline", title="闻",
                        text=f"这是一条新闻。{kw}"),
                Segment(segmentId="seg_003", type="ending", title="结", text="再见。"),
            ])
            result = validate_episode_script(script)
            self.assertTrue(
                any(kw in e for e in result.fatal_errors),
                f"Keyword '{kw}' should have been caught as fatal but wasn't",
            )

    def test_warnings_on_missing_duration(self):
        """Segments without estimatedDurationSec should produce warnings."""
        script = make_valid_script(segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎。",
                    estimatedDurationSec=0),
            Segment(segmentId="seg_002", type="ending", title="结", text="再见。",
                    estimatedDurationSec=0),
        ])
        result = validate_episode_script(script)
        self.assertFalse(result.has_fatal)
        self.assertTrue(any("duration" in w.lower() for w in result.warnings))

    def test_fatal_blocks_pipeline_scenario(self):
        """Simulate a real pipeline-blocking scenario: ending keyword in headline."""
        script = make_valid_script(segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎。",
                    estimatedDurationSec=30),
            Segment(segmentId="seg_002", type="headline", title="闻",
                    text="今天的地铁运行平稳。我们明天见！", estimatedDurationSec=40),
            Segment(segmentId="seg_003", type="ending", title="结", text="再见。",
                    estimatedDurationSec=20),
        ])
        result = validate_episode_script(script)
        self.assertTrue(result.has_fatal, "Ending keyword leak must be fatal")
        self.assertFalse(result.passed)
        # The pipeline should check has_fatal and return None


class TestBackwardCompatibility(unittest.TestCase):
    """Old PodcastScript / Chapter names must still work."""

    def test_chapter_alias(self):
        """Chapter should be the same class as Segment."""
        ch = Chapter(
            segmentId="seg_001", type="opening", title="开",
            text="欢迎。", key_points=["a", "b"],
        )
        self.assertEqual(ch.segmentId, "seg_001")
        self.assertEqual(ch.type, "opening")

    def test_podcast_script_alias(self):
        """PodcastScript should be the same class as PodcastEpisodeScript."""
        ps = PodcastScript(
            episodeId="test", title="Test", city="北京", date="2026-05-16",
            segments=[
                Segment(segmentId="seg_001", type="opening", title="开", text="欢迎。"),
                Segment(segmentId="seg_002", type="ending", title="结", text="再见。"),
            ],
        )
        self.assertEqual(ps.episode_title, "Test")
        self.assertIn("欢迎", ps.full_script)

    def test_full_script_property(self):
        script = make_valid_script()
        full = script.full_script
        self.assertIn("小站姐", full)
        self.assertIn("小站早班车", full)

    def test_episode_title_property(self):
        script = make_valid_script()
        self.assertEqual(script.episode_title, script.title)

    def test_source_urls_property(self):
        script = make_valid_script()
        self.assertEqual(script.source_urls, ["https://example.com"])


class TestScriptWriterInit(unittest.TestCase):
    """ScriptWriter class instantiation (no API calls)."""

    def test_default_city(self):
        writer = ScriptWriter(city="上海")
        self.assertEqual(writer.city, "上海")

    def test_default_model(self):
        writer = ScriptWriter()
        self.assertEqual(writer.model, "gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
