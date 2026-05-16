"""
Tests for script_reviewer.py — the dedicated script quality auditor.

Usage:
    cd server
    python -m pytest tests/test_script_reviewer.py -v
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.script_reviewer import (
    review_script,
    ReviewResult,
    ReviewIssue,
)
from ai.script_writer import (
    PodcastEpisodeScript,
    Segment,
    Source,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seg(tag: str, stype: str, text: str, **kwargs) -> Segment:
    """Shorthand for creating a test Segment."""
    defaults = {
        "segmentId": tag,
        "type": stype,
        "title": stype,
        "text": text,
        "estimatedDurationSec": 30,
        "riskLevel": "low",
    }
    defaults.update(kwargs)
    return Segment(**defaults)


def _script(*segs: Segment, sources: list = None) -> PodcastEpisodeScript:
    """Shorthand for creating a test PodcastEpisodeScript."""
    if sources is None:
        sources = [Source(sourceId="src_001", title="地铁官方", url="https://bjsubway.com", type="official")]
    return PodcastEpisodeScript(
        episodeId="test",
        title="测试",
        city="北京",
        date="2026-05-16",
        segments=list(segs),
        sources=sources,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReviewResult(unittest.TestCase):
    """ReviewResult data model."""

    def test_empty_passes(self):
        r = ReviewResult()
        self.assertTrue(r.passed)
        self.assertFalse(r.has_errors)

    def test_error_fails(self):
        r = ReviewResult(
            errors=[ReviewIssue(code="E1", message="bad", severity="error")],
        )
        self.assertFalse(r.passed)
        self.assertTrue(r.has_errors)

    def test_warning_still_passes(self):
        r = ReviewResult(
            warnings=[ReviewIssue(code="W1", message="note", severity="warning")],
        )
        self.assertTrue(r.passed)
        self.assertFalse(r.has_errors)


class TestStructuralRules(unittest.TestCase):
    """Opening/ending position rules."""

    def test_valid_structure_passes(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "早上好，我是小站姐，欢迎来到《小站早班车》。"),
            _seg("seg_002", "headline", "今天地铁运行正常。"),
            _seg("seg_003", "ending", "今天的节目就到这里，我们明天见。"),
        ))
        self.assertTrue(result.passed)
        self.assertEqual(len(result.errors), 0)

    def test_opening_not_first(self):
        result = review_script(_script(
            _seg("seg_001", "headline", "先看新闻。"),
            _seg("seg_002", "opening", "早上好，我是小站姐。"),
            _seg("seg_003", "ending", "明天见。"),
        ))
        self.assertTrue(result.has_errors)
        self.assertTrue(any("OPENING_NOT_FIRST" == e.code for e in result.errors))

    def test_ending_not_last(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。"),
            _seg("seg_002", "ending", "再见。"),
            _seg("seg_003", "headline", "还有一条新闻。"),
        ))
        self.assertTrue(result.has_errors)
        self.assertTrue(any("ENDING_NOT_LAST" == e.code for e in result.errors))

    def test_no_segments(self):
        script = PodcastEpisodeScript(
            episodeId="empty", title="E", city="北京", date="2026-05-16",
        )
        result = review_script(script)
        self.assertTrue(result.has_errors)
        self.assertTrue(any("NO_SEGMENTS" == e.code for e in result.errors))


class TestKeywordLeakRules(unittest.TestCase):
    """Opening/ending keyword leak detection."""

    def test_ending_keyword_in_headline(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎收听。"),
            _seg("seg_002", "headline", "这条新闻之后，我们明天见。"),
            _seg("seg_003", "ending", "再见。"),
        ))
        self.assertTrue(result.has_errors)
        self.assertTrue(any("ENDING_KEYWORD_LEAK" == e.code for e in result.errors))

    def test_opening_keyword_in_body(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。"),
            _seg("seg_002", "headline", "大家好，今天来看一条重要新闻。"),
            _seg("seg_003", "ending", "再见。"),
        ))
        self.assertTrue(result.has_errors)
        self.assertTrue(any("OPENING_KEYWORD_LEAK" == e.code for e in result.errors))

    def test_ending_keyword_in_ending_is_ok(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。"),
            _seg("seg_002", "headline", "新闻内容。"),
            _seg("seg_003", "ending", "今天的节目就到这里，感谢收听，我们明天见。"),
        ))
        self.assertTrue(result.passed)
        self.assertFalse(any(
            "ENDING_KEYWORD_LEAK" == e.code for e in result.errors
        ))


class TestMarketingAndJargonRules(unittest.TestCase):
    """Marketing words and news jargon."""

    def test_marketing_keyword_blocked(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。"),
            _seg("seg_002", "headline", "重磅消息！今天地铁有重大变化！"),
            _seg("seg_003", "ending", "再见。"),
        ))
        self.assertTrue(result.has_errors)
        self.assertTrue(any("MARKETING_KEYWORD" == e.code for e in result.errors))

    def test_news_jargon_warning(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。"),
            _seg("seg_002", "headline", "据悉，今天地铁10号线将临时调整。"),
            _seg("seg_003", "ending", "再见。"),
        ))
        self.assertFalse(result.has_errors)
        self.assertTrue(any("NEWS_JARGON" == w.code for w in result.warnings))


class TestHighRiskRules(unittest.TestCase):
    """Metro high-risk content rules."""

    def test_high_risk_without_source(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。"),
            _seg("seg_002", "line_update", "10号线今日全线停运。",
                 riskLevel="high", sourceIds=[]),
            _seg("seg_003", "ending", "再见。"),
        ))
        self.assertTrue(result.has_errors)
        self.assertTrue(any("HIGH_RISK_NO_SOURCE" == e.code for e in result.errors))

    def test_high_risk_with_source_passes(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。"),
            _seg("seg_002", "line_update", "10号线停运。",
                 riskLevel="high", sourceIds=["src_001"]),
            _seg("seg_003", "ending", "再见。"),
            sources=[
                Source(sourceId="src_001", title="北京地铁官方通知",
                       url="https://bjsubway.com/notice", type="official"),
            ],
        ))
        self.assertTrue(result.passed)

    def test_metro_keyword_no_high_flag_warns(self):
        """Text mentions 停运 but riskLevel is low → warning."""
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。"),
            _seg("seg_002", "headline", "今天上午10号线有短暂停运。",
                 riskLevel="low"),
            _seg("seg_003", "ending", "再见。"),
        ))
        self.assertFalse(result.has_errors)
        self.assertTrue(any("HIGH_RISK_CONTENT_NO_FLAG" == w.code
                          for w in result.warnings))

    def test_high_risk_rss_source_warns(self):
        """High risk with only RSS source (not official) → warning."""
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。"),
            _seg("seg_002", "line_update", "10号线停运。",
                 riskLevel="high", sourceIds=["src_001"]),
            _seg("seg_003", "ending", "再见。"),
            sources=[
                Source(sourceId="src_001", title="社交媒体爆料",
                       url="https://weibo.com/post", type="rss"),
            ],
        ))
        self.assertFalse(result.has_errors, f"Should pass: {result.errors}")
        self.assertTrue(any("HIGH_RISK_NO_OFFICIAL_SOURCE" == w.code
                          for w in result.warnings))


class TestSourceIdValidation(unittest.TestCase):
    """Source reference checks."""

    def test_unknown_source_id(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。"),
            _seg("seg_002", "headline", "新闻。", sourceIds=["src_999"]),
            _seg("seg_003", "ending", "再见。"),
        ))
        self.assertTrue(result.has_errors)
        self.assertTrue(any("UNKNOWN_SOURCE_ID" == e.code for e in result.errors))


class TestEmptyTextAndDuration(unittest.TestCase):
    """Empty text and duration sanity."""

    def test_empty_text(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。"),
            _seg("seg_002", "headline", ""),
            _seg("seg_003", "ending", "再见。"),
        ))
        self.assertTrue(result.has_errors)
        self.assertTrue(any("EMPTY_TEXT" == e.code for e in result.errors))

    def test_zero_duration_warns(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。", estimatedDurationSec=0),
            _seg("seg_002", "ending", "再见。", estimatedDurationSec=0),
        ))
        self.assertTrue(result.passed)
        self.assertTrue(any("NO_DURATION_ESTIMATE" == w.code
                          for w in result.warnings))

    def test_long_duration_warns(self):
        result = review_script(_script(
            _seg("seg_001", "opening", "欢迎。", estimatedDurationSec=700),
            _seg("seg_002", "ending", "再见。", estimatedDurationSec=30),
        ))
        self.assertTrue(result.passed)
        self.assertTrue(any("LONG_DURATION" == w.code for w in result.warnings))


class TestFullEpisodeIntegration(unittest.TestCase):
    """End-to-end: a realistic episode should pass all checks."""

    def test_realistic_episode_passes(self):
        script = _script(
            _seg("seg_001", "opening", "早上好，我是小站姐，欢迎来到《小站早班车》。"
                 "今天来看看北京地铁出行最值得留意的几件事。",
                 estimatedDurationSec=30, pauseAfterMs=1000),
            _seg("seg_002", "headline", "今天早高峰北京地铁整体运行平稳，"
                 "但10号线北段因信号调试，部分区间运行间隔略有延长，"
                 "建议走这条线的朋友多留两三分钟。",
                 estimatedDurationSec=45, pauseAfterMs=800,
                 sourceIds=["src_001"], riskLevel="medium"),
            _seg("seg_003", "commute_tip", "说到早高峰，如果你在国贸站换乘，"
                 "最近东南口新开了一条通道，从站台走到地面比原来少了差不多一分半钟，"
                 "知道的人还不多，今天可以试试。",
                 estimatedDurationSec=40, pauseAfterMs=800),
            _seg("seg_004", "ending", "好啦，今天的《小站早班车》就到这里。"
                 "如果你的路线涉及临时调整，出门前还是建议再看一眼官方信息。"
                 "祝你一路顺利，我们明天见。",
                 estimatedDurationSec=20, pauseAfterMs=0),
        )
        result = review_script(script)
        self.assertTrue(result.passed, f"Episode should pass: {result.errors}")
        # May have warnings (e.g., "延长" is not a high-risk keyword so should be clean)
        if result.warnings:
            print(f"  (info) {len(result.warnings)} warnings: {[w.code for w in result.warnings]}")


if __name__ == "__main__":
    unittest.main()
