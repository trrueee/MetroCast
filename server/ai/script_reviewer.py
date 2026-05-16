"""
Script quality reviewer for 小站早班车.

Audits a PodcastEpisodeScript for content safety, structural integrity,
and brand compliance. Returns ReviewResult with errors (block pipeline)
and warnings (log but continue).
"""
from typing import List, Optional
from pydantic import BaseModel, Field

from ai.script_writer import (
    PodcastEpisodeScript,
    Segment,
)


# ---------------------------------------------------------------------------
# Review data models
# ---------------------------------------------------------------------------

class ReviewIssue(BaseModel):
    code: str
    message: str
    segmentId: Optional[str] = None
    severity: str = "error"  # "error" or "warning"


class ReviewResult(BaseModel):
    errors: List[ReviewIssue] = Field(default_factory=list)
    warnings: List[ReviewIssue] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def passed(self) -> bool:
        return not self.has_errors


# ---------------------------------------------------------------------------
# Keyword lists
# ---------------------------------------------------------------------------

OPENING_KEYWORDS = [
    "早上好", "欢迎收听", "欢迎来到", "我是小站姐",
    "大家好", "各位听众", "下午好", "晚上好",
]

ENDING_KEYWORDS = [
    "今天的节目就到这里", "本期节目到这里", "感谢收听",
    "我们下期再见", "以上就是今天的全部内容", "明天的节目",
    "今天的播客就到这里", "本期播客到此结束",
    "明天见", "我们明天见",
]

MARKETING_KEYWORDS = [
    "重磅", "震撼", "必看", "惊爆", "速看", "爆炸",
    "疯狂", "限时", "抢购", "独家",
]

NEWS_JARGON_KEYWORDS = [
    "据悉", "记者获悉", "最新消息显示", "本报记者",
    "新华社", "央视报道",
]

HIGH_RISK_METRO_KEYWORDS = [
    "停运", "暂停运营", "首末班车", "票价", "施工",
    "绕行", "换乘调整", "限流", "封站", "甩站",
    "运营时间", "关闭出入口",
]

# Official source domains (configurable list)
OFFICIAL_DOMAINS = [
    "bjsubway.com", "北京地铁", "bjmtr.com",
    "gov.cn", "交通委", "轨道交通",
]


# ---------------------------------------------------------------------------
# Audit rules
# ---------------------------------------------------------------------------

def _is_official_source(source_type: str, source_title: str, source_url: str) -> bool:
    """Heuristic: check if a source looks like an official transit authority."""
    combined = f"{source_type} {source_title} {source_url}".lower()
    if source_type == "official":
        return True
    for domain in OFFICIAL_DOMAINS:
        if domain in combined:
            return True
    return False


def review_script(script: PodcastEpisodeScript) -> ReviewResult:
    """
    Audit a PodcastEpisodeScript against all content-safety and quality rules.

    Returns ReviewResult with:
      - errors: must block pipeline (fatal content issues)
      - warnings: should log but pipeline may continue
    """
    result = ReviewResult()

    # --- shortcuts ---
    segments = script.segments
    sources = script.sources
    if not segments:
        result.errors.append(ReviewIssue(
            code="NO_SEGMENTS",
            message="Episode has no segments",
            severity="error",
        ))
        return result

    n = len(segments)
    source_map = {s.sourceId: s for s in sources}

    # ── Structural checks ──────────────────────────────────────────────

    # Rule 1: opening is first
    if segments[0].type != "opening":
        result.errors.append(ReviewIssue(
            code="OPENING_NOT_FIRST",
            message=f"First segment is type='{segments[0].type}', must be 'opening'",
            segmentId=segments[0].segmentId,
            severity="error",
        ))

    # Rule 2: ending is last
    if segments[-1].type != "ending":
        result.errors.append(ReviewIssue(
            code="ENDING_NOT_LAST",
            message=f"Last segment is type='{segments[-1].type}', must be 'ending'",
            segmentId=segments[-1].segmentId,
            severity="error",
        ))

    # ── Per-segment checks ─────────────────────────────────────────────

    for i, seg in enumerate(segments):
        is_first = (i == 0)
        is_last = (i == n - 1)

        # Rule 3: Non-opening segments must not contain opening keywords
        if seg.type != "opening":
            for kw in OPENING_KEYWORDS:
                if kw in seg.text:
                    result.errors.append(ReviewIssue(
                        code="OPENING_KEYWORD_LEAK",
                        message=f"Segment type='{seg.type}' contains opening keyword: '{kw}'",
                        segmentId=seg.segmentId,
                        severity="error",
                    ))

        # Rule 4: Non-ending segments must not contain ending keywords
        if seg.type != "ending":
            for kw in ENDING_KEYWORDS:
                if kw in seg.text:
                    result.errors.append(ReviewIssue(
                        code="ENDING_KEYWORD_LEAK",
                        message=f"Segment type='{seg.type}' contains ending keyword: '{kw}'",
                        segmentId=seg.segmentId,
                        severity="error",
                    ))

        # Rule 7: High-risk metro keywords without riskLevel="high" → warning
        if seg.riskLevel != "high":
            for kw in HIGH_RISK_METRO_KEYWORDS:
                if kw in seg.text:
                    result.warnings.append(ReviewIssue(
                        code="HIGH_RISK_CONTENT_NO_FLAG",
                        message=(
                            f"Segment text contains metro risk keyword '{kw}' "
                            f"but riskLevel={seg.riskLevel}"
                        ),
                        segmentId=seg.segmentId,
                        severity="warning",
                    ))

        # Rule 8: riskLevel="high" must have sourceIds
        if seg.riskLevel == "high" and not seg.sourceIds:
            result.errors.append(ReviewIssue(
                code="HIGH_RISK_NO_SOURCE",
                message="Segment riskLevel='high' but has no sourceIds",
                segmentId=seg.segmentId,
                severity="error",
            ))

        # Rule 9: High-risk segment needs at least one official source
        if seg.riskLevel == "high" and seg.sourceIds:
            has_official = False
            for sid in seg.sourceIds:
                src = source_map.get(sid)
                if src and _is_official_source(src.type, src.title, src.url):
                    has_official = True
                    break
            if not has_official:
                result.warnings.append(ReviewIssue(
                    code="HIGH_RISK_NO_OFFICIAL_SOURCE",
                    message=(
                        "Segment riskLevel='high' has sources but none appear "
                        "to be official. Consider adding an official transit source."
                    ),
                    segmentId=seg.segmentId,
                    severity="warning",
                ))

        # Rule 10: sourceIds must reference existing sources
        for sid in seg.sourceIds:
            if sid not in source_map:
                result.errors.append(ReviewIssue(
                    code="UNKNOWN_SOURCE_ID",
                    message=f"sourceId '{sid}' not found in episode sources",
                    segmentId=seg.segmentId,
                    severity="error",
                ))

        # Rule 11: Segment text must not be empty
        if not seg.text or not seg.text.strip():
            result.errors.append(ReviewIssue(
                code="EMPTY_TEXT",
                message="Segment text is empty",
                segmentId=seg.segmentId,
                severity="error",
            ))

        # Rule 12: Duration sanity
        if seg.estimatedDurationSec <= 0:
            result.warnings.append(ReviewIssue(
                code="NO_DURATION_ESTIMATE",
                message="estimatedDurationSec is 0 (no estimate provided)",
                segmentId=seg.segmentId,
                severity="warning",
            ))
        elif seg.estimatedDurationSec > 600:
            result.warnings.append(ReviewIssue(
                code="LONG_DURATION",
                message=f"estimatedDurationSec={seg.estimatedDurationSec}s > 10 min",
                segmentId=seg.segmentId,
                severity="warning",
            ))

    # ── Full-script checks ─────────────────────────────────────────────

    full_text = " ".join(seg.text for seg in segments)

    # Rule 5: No marketing keywords anywhere
    for kw in MARKETING_KEYWORDS:
        if kw in full_text:
            result.errors.append(ReviewIssue(
                code="MARKETING_KEYWORD",
                message=f"Script contains marketing keyword: '{kw}'",
                severity="error",
            ))

    # Rule 6: No news jargon anywhere
    for kw in NEWS_JARGON_KEYWORDS:
        if kw in full_text:
            result.warnings.append(ReviewIssue(
                code="NEWS_JARGON",
                message=f"Script contains news jargon: '{kw}'",
                severity="warning",
            ))

    return result
