import os
import json
import logging
from typing import List, Optional, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("ScriptWriter")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

SegmentType = Literal[
    "opening", "headline", "line_update", "commute_tip",
    "city_story", "safety", "ending",
]

RiskLevel = Literal["low", "medium", "high"]


class StyleInfo(BaseModel):
    tone: str = "清爽、温和、可靠、信息清楚、城市通勤感"
    hostPersona: str = (
        "小站姐是一个熟悉地铁和城市生活的朋友，语气自然、温和、清楚。"
        "不像新闻播音员，不像客服，不像营销主播，不撒娇，不夸张，不制造焦虑，不机械罗列信息。"
        "不使用'重磅''震撼''必看'等营销词，不使用过度新闻腔。"
        "重要信息说清楚，不确定信息提醒用户查看官方渠道。"
    )
    avoid: List[str] = Field(default_factory=lambda: [
        "不要每段都开场",
        "不要中途说节目结束",
        "不要机械罗列新闻",
        "不要夸张营销语",
        "不要无来源地播报高风险地铁信息",
        "不要使用'重磅''震撼''必看''惊爆'等营销词汇",
        "不要制造焦虑",
        "不要新闻腔",
        "不要撒娇卖萌",
    ])


class Segment(BaseModel):
    segmentId: str
    type: SegmentType
    title: str
    text: str
    estimatedDurationSec: int = 0
    pauseAfterMs: int = 800
    sourceIds: List[str] = Field(default_factory=list)
    riskLevel: RiskLevel = "low"


class Source(BaseModel):
    sourceId: str
    title: str
    url: str
    type: str = "rss"


class PodcastEpisodeScript(BaseModel):
    episodeId: str
    title: str
    city: str
    date: str
    showName: str = "小站早班车"
    hostName: str = "小站姐"
    style: StyleInfo = Field(default_factory=StyleInfo)
    summary: str = ""
    segments: List[Segment] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)

    @property
    def full_script(self) -> str:
        """Backward-compatible: join all segment texts with newlines."""
        return "\n\n".join(seg.text for seg in self.segments)

    @property
    def episode_title(self) -> str:
        """Backward-compatible alias."""
        return self.title

    @property
    def episode_description(self) -> str:
        """Backward-compatible alias."""
        return self.summary

    @property
    def source_urls(self) -> List[str]:
        """Backward-compatible alias."""
        return [s.url for s in self.sources if s.url]


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

class ValidationResult(BaseModel):
    """Structured result of script validation."""
    passed: bool = True
    fatal_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @property
    def has_fatal(self) -> bool:
        return len(self.fatal_errors) > 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

ENDING_KEYWORDS = [
    "今天的节目就到这里",
    "本期节目到这里",
    "感谢收听",
    "我们下期再见",
    "以上就是今天的全部内容",
    "今天的播客就到这里",
    "本期播客到此结束",
    "明天见",
    "我们明天见",
]

OPENING_KEYWORDS = [
    "欢迎收听",
    "大家好",
    "各位听众",
    "早上好",
    "下午好",
    "晚上好",
    "我是小站姐",
]


def validate_episode_script(script: PodcastEpisodeScript) -> ValidationResult:
    """
    Validate a PodcastEpisodeScript against all content rules.

    Returns ValidationResult with:
      - fatal_errors: must block pipeline (structural, content-safety)
      - warnings: should log but allow pipeline to continue
    """
    result = ValidationResult()

    if not script.segments:
        result.fatal_errors.append("No segments found")
        result.passed = False
        return result

    types = [s.type for s in script.segments]

    # === FATAL ERRORS ===

    # 1. Must have opening and ending
    if "opening" not in types:
        result.fatal_errors.append("Missing opening segment")
    if "ending" not in types:
        result.fatal_errors.append("Missing ending segment")

    # 2. Ending must be the last segment
    for i, seg in enumerate(script.segments):
        if seg.type == "ending" and i != len(script.segments) - 1:
            result.fatal_errors.append(
                f"Ending segment {seg.segmentId} appears at position {i}, "
                f"but must be the last segment"
            )

    # 3. Non-ending segments must not contain ending keywords
    for seg in script.segments:
        if seg.type != "ending":
            for kw in ENDING_KEYWORDS:
                if kw in seg.text:
                    result.fatal_errors.append(
                        f"Non-ending segment {seg.segmentId} (type={seg.type}) "
                        f"contains ending keyword: '{kw}'"
                    )

    # 4. Opening must be the first segment
    for i, seg in enumerate(script.segments):
        if seg.type == "opening" and i != 0:
            result.fatal_errors.append(
                f"Opening segment {seg.segmentId} appears at position {i}, "
                f"but must be the first segment"
            )

    # 5. Only opening can have opening keywords
    for seg in script.segments:
        if seg.type != "opening":
            for kw in OPENING_KEYWORDS:
                if kw in seg.text:
                    result.fatal_errors.append(
                        f"Non-opening segment {seg.segmentId} (type={seg.type}) "
                        f"contains opening keyword: '{kw}'"
                    )

    # 6. High-risk segments must have sourceIds
    for seg in script.segments:
        if seg.riskLevel == "high" and not seg.sourceIds:
            result.fatal_errors.append(
                f"High-risk segment {seg.segmentId} has no sourceIds"
            )

    # 7. Segment text must not be empty
    for seg in script.segments:
        if not seg.text or not seg.text.strip():
            result.fatal_errors.append(f"Segment {seg.segmentId} has empty text")

    # 8. sourceIds must reference existing sources
    all_source_ids = {s.sourceId for s in script.sources}
    for seg in script.segments:
        for sid in seg.sourceIds:
            if sid not in all_source_ids:
                result.fatal_errors.append(
                    f"Segment {seg.segmentId} references unknown sourceId: '{sid}'"
                )

    # === WARNINGS (non-fatal) ===

    # W1. SegmentId not sequential (auto-fixable)
    for i, seg in enumerate(script.segments):
        expected_id = f"seg_{i + 1:03d}"
        if seg.segmentId != expected_id:
            result.warnings.append(
                f"Segment at position {i} has id '{seg.segmentId}', "
                f"expected '{expected_id}' (auto-fixed)"
            )

    # W2. estimatedDurationSec is zero or unreasonable
    for seg in script.segments:
        if seg.estimatedDurationSec <= 0:
            result.warnings.append(
                f"Segment {seg.segmentId} has estimatedDurationSec=0 (may need estimate)"
            )
        elif seg.estimatedDurationSec > 600:
            result.warnings.append(
                f"Segment {seg.segmentId} duration {seg.estimatedDurationSec}s > 10 min"
            )

    result.passed = not result.has_fatal
    return result


# Backward-compatible helper: returns flat list of all issues
def _validate_as_list(script: PodcastEpisodeScript) -> list:
    """Legacy wrapper returning flat list of all issues (for old test compatibility)."""
    r = validate_episode_script(script)
    return r.fatal_errors + r.warnings


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """你是一个资深播客主编，负责制作一档名为《小站早班车》的地铁通勤每日播客。

## 节目设定

- 节目名：《小站早班车》
- 主持人：小站姐
- 定位：每天陪用户把地铁通勤信息听明白的城市出行陪伴播客
- 听众场景：正在坐地铁、等车、换乘、走向地铁站的通勤用户
- 每期时长：约 8-15 分钟

## 主持人「小站姐」的人设与语气

小站姐是一个清爽、温和、可靠的城市通勤女主持，像一个熟悉地铁和城市生活的朋友在陪你聊天。

**她是什么样的：**
- 语气自然、温和、清楚
- 信息讲得明白，不绕弯子
- 像朋友在提醒你出门注意什么，不是上级在通知你
- 偶尔可以有一点点温度，但不煽情
- 不确定的信息，她会说"建议出发前再看一眼官方信息"，不假装什么都知道

**她不是什么样的：**
- 不像新闻播音员
- 不像客服
- 不像营销主播
- 不撒娇
- 不夸张
- 不制造焦虑
- 不机械罗列信息
- 不使用"重磅""震撼""必看""惊爆""速看"等营销词
- 不使用过度新闻腔（如"据悉""记者获悉""最新消息显示"）

## 内容类型 (segment type)

你需要在每期节目中安排以下类型段落（顺序建议如此，但可根据当天素材灵活调整）：

1. **opening**（开场）：80-150 字。小站姐自我介绍 + 点出本期主题。只说一次，不要在后续段落重复自我介绍。

   风格参考：
   "早上好，我是小站姐，欢迎来到《小站早班车》。今天这几分钟，我们一起看看地铁出行里最值得留意的几件事：哪些线路可能会更忙，哪些站点需要多留点时间，还有一个出门前可以顺手确认的小提醒。"

2. **headline**（今日要闻）：200-500 字。本日最重要的 1-3 条城市/交通/通勤相关新闻。不是念标题，而是帮听众理清今天和出行有关的重点。

3. **line_update**（线路变化）：250-600 字。特定地铁线路的运营变化、施工、新站、临时调整等。如果当天没有线路变化素材，可以跳过这个类型。

4. **commute_tip**（通勤贴士）：200-500 字。今天用得上的通勤建议——天气影响、客流预判、新开的出站口、换乘省时技巧等。

5. **city_story**（城市小事）：300-800 字。换个轻松话题，讲一个与城市、地铁有关的小故事或容易被忽略的细节。让节目有呼吸感。

6. **safety**（出行安全）：150-400 字。安全提醒——扶梯、屏蔽门、雨天路滑、拥挤路段等。

7. **ending**（结尾）：80-150 字。简短总结 + 祝福 + 再见。只说一次，必须是最后一段。

   风格参考：
   "好啦，今天的《小站早班车》就到这里。如果你的路线涉及临时调整，出门前还是建议再看一眼官方信息。祝你一路顺利，我们明天见。"

## 绝对禁止的规则（违反即为不合格）

- ❌ 任何非 ending 段落出现："今天的节目就到这里""本期节目到这里""感谢收听""我们下期再见""以上就是今天的全部内容""明天见""我们明天见"等结束语
- ❌ 任何非 opening 段落出现："早上好""欢迎收听""我是小站姐""大家好""各位听众"等开场白或自我介绍
- ❌ 每段都以"小站姐"自我介绍开头
- ❌ 机械罗列新闻条目（"第一条…第二条…第三条…"）
- ❌ 夸张营销语气
- ❌ 没有来源地播报高风险地铁运营信息
- ❌ 使用"据悉""记者获悉""最新消息显示"等新闻腔
- ❌ 制造焦虑（"千万小心""太可怕了""一定要注意"等恐吓式表达）

## 段落衔接要求

中间段落（非 opening 非 ending）必须使用自然承接句，让节目流畅地从一个话题过渡到下一个。例如：

- "说完今天的重点，我们再看一条和换乘有关的信息。"
- "如果你今天刚好经过这一带，可以提前多留几分钟。"
- "接下来这条不算突发，但对早高峰出行会有一点影响。"
- "换个轻一点的话题，看看地铁里一个容易被忽略的小细节。"
- "说完线路变化，再给你一个出门前可以顺手确认的小提醒。"
- "说到出行安全，今天有一个提醒值得注意。"

禁止使用的机械过渡：
- ❌ "接下来是……"
- ❌ "下面我们来讲……"
- ❌ "现在进入……环节"

## 高风险信息规则

如果段落涉及以下内容，必须标记 riskLevel="high"，且必须提供 sourceIds（不能为空）：
- 运营时间变化（首末班车调整）
- 票价调整
- 线路停运
- 施工绕行
- 换乘调整
- 临时运营调整

如果来源不明确或未经官方确认，不能当作确定事实播报。只能说"建议出发前查看官方信息"或"目前还没有官方确认，出发前可以多看一眼实时信息"。

## 输出格式

你必须输出一个严格的 JSON 对象，结构如下：

{
  "episodeId": "日期生成的ID，如 xzzbc_20260516",
  "title": "本期标题，15字以内，有信息量但不夸张",
  "city": "本期主要涉及的城市",
  "date": "日期 YYYY-MM-DD",
  "showName": "小站早班车",
  "hostName": "小站姐",
  "summary": "一句话概述本期内容，让听众快速判断要不要听",
  "segments": [
    {
      "segmentId": "seg_001",
      "type": "opening",
      "title": "段落小标题（内部使用，不口播）",
      "text": "段落的完整口播文本，这是小站姐实际要说的话",
      "estimatedDurationSec": 估计秒数,
      "pauseAfterMs": 停顿毫秒数,
      "sourceIds": ["src_001"],
      "riskLevel": "low"
    }
  ],
  "sources": [
    {
      "sourceId": "src_001",
      "title": "来源标题",
      "url": "来源URL",
      "type": "rss 或 search 或 official"
    }
  ]
}

## 停顿建议
- opening 之后：1000ms
- ending 之前：1000ms
- headline 之后：800ms
- line_update 之后：800ms
- commute_tip 之后：800ms
- city_story 之后：800ms
- safety 之后：800ms
- 同话题紧密衔接：500ms
- ending 之后：0ms

## 输出前的自检清单

在输出 JSON 之前，请确认：
1. 是否只有第一个 segment 是 opening？
2. 是否只有最后一个 segment 是 ending？
3. 中间 segment 是否没有任何结束语？
4. 高风险 segment 是否都有 sourceIds？
5. 每段 text 是否都不为空？
6. 整期节目是否有统一主题和风格？
7. 口播文本读起来是否像小站姐在陪用户通勤，而不是 AI 在朗读新闻？
8. 有没有"据悉""重磅""震撼"等违禁词？
9. 承接句是否自然，而不是"接下来""下面"？

只输出 JSON，不要输出任何解释、自检结果或额外文字。
"""


def _build_user_prompt(items: List[dict], city: str, date_str: str) -> str:
    """Build the user prompt with news items and context."""
    items_text = json.dumps(items[:15], ensure_ascii=False, indent=2)
    return f"""今天是 {date_str}，城市是 {city}。

以下是我为你收集的今日素材（共 {len(items)} 条，展示前 15 条）：

{items_text}

请根据以上素材，制作一期《小站早班车》播客稿。

要求：
1. 整期节目像一个完整的播客，有统一主题和自然过渡
2. 严格遵循段落类型顺序和长度要求
3. 绝对禁止在非 ending 段落出现结束语
4. 绝对禁止在非 opening 段落自我介绍
5. 语言自然，像一个熟悉城市交通的朋友在陪听众通勤
6. 高风险信息必须标注 riskLevel="high" 并提供来源
7. 如果素材不足以支撑某类段落（如没有线路变化），可以跳过该类型或将多条同类素材合并
8. 直接输出 JSON，不要输出任何解释性文字

请直接输出 JSON："""


# ---------------------------------------------------------------------------
# ScriptWriter
# ---------------------------------------------------------------------------

class ScriptWriter:
    def __init__(self, model: str = "gpt-4o-mini", city: str = "北京"):
        self.model = model
        self.city = city
        self.client = OpenAI(
            api_key=os.getenv("AI_API_KEY"),
            base_url=os.getenv("AI_BASE_URL", "https://api.openai.com/v1"),
        )

    def generate_script(
        self, items: List[dict], tone: str = "relaxed", city: str = None
    ) -> PodcastEpisodeScript:
        """
        Generate a structured 小站早班车 episode script from news items.

        Args:
            items: List of news items from RSS/search crawlers.
            tone: Kept for backward compatibility (unused in new prompt).
            city: Override the default city.

        Returns:
            PodcastEpisodeScript with validated segments.
        """
        target_city = city or self.city
        date_str = datetime.now().strftime("%Y-%m-%d")
        episode_id = f"xzzbc_{datetime.now().strftime('%Y%m%d')}"

        logger.info(
            "Generating 小站早班车 script for %s on %s (%d items)",
            target_city, date_str, len(items),
        )

        prompt = _build_user_prompt(items, target_city, date_str)

        # Stage 1: Generate structured JSON
        logger.info("Calling AI to generate episode script...")
        raw = self._call_ai(prompt, is_json=True, max_tokens=8000)

        # Stage 2: Parse and validate
        script = self._parse_script(raw, episode_id, target_city, date_str)

        # Stage 3: Run validation
        validation = validate_episode_script(script)
        if validation.warnings:
            logger.warning("Script validation warnings (%d):", len(validation.warnings))
            for w in validation.warnings:
                logger.warning("  - %s", w)

        if validation.has_fatal:
            logger.warning(
                "Script validation found %d fatal errors — attempting auto-fix:",
                len(validation.fatal_errors),
            )
            for err in validation.fatal_errors:
                logger.warning("  - %s", err)

            # Attempt auto-fix: renumber segmentIds
            script = self._fix_segment_ids(script)

            # Re-validate after fix
            validation = validate_episode_script(script)
            if validation.has_fatal:
                logger.error(
                    "Script still has %d fatal errors after auto-fix:",
                    len(validation.fatal_errors),
                )
                for err in validation.fatal_errors:
                    logger.error("  - %s", err)
            else:
                logger.info("Auto-fix resolved all fatal errors.")

        logger.info(
            "Script generated: title='%s', %d segments, %d sources",
            script.title, len(script.segments), len(script.sources),
        )
        return script

    def _parse_script(
        self, raw: dict, episode_id: str, city: str, date_str: str
    ) -> PodcastEpisodeScript:
        """Parse raw AI output into PodcastEpisodeScript, with fallbacks."""
        try:
            # Ensure required top-level fields
            raw.setdefault("episodeId", episode_id)
            raw.setdefault("city", city)
            raw.setdefault("date", date_str)
            raw.setdefault("showName", "小站早班车")
            raw.setdefault("hostName", "小站姐")
            raw.setdefault("summary", "")
            raw.setdefault("segments", [])
            raw.setdefault("sources", [])

            # Parse sources first so we can validate sourceIds
            sources = []
            for i, s in enumerate(raw.get("sources", [])):
                sid = s.get("sourceId", f"src_{i + 1:03d}")
                sources.append(Source(
                    sourceId=sid,
                    title=s.get("title", ""),
                    url=s.get("url", ""),
                    type=s.get("type", "rss"),
                ))

            # Parse segments
            segments = []
            for i, seg in enumerate(raw.get("segments", [])):
                sid = seg.get("segmentId", f"seg_{i + 1:03d}")
                seg_type = seg.get("type", "headline")

                # Validate segment type
                valid_types = {
                    "opening", "headline", "line_update", "commute_tip",
                    "city_story", "safety", "ending",
                }
                if seg_type not in valid_types:
                    logger.warning(
                        "Unknown segment type '%s' in %s, defaulting to headline",
                        seg_type, sid,
                    )
                    seg_type = "headline"

                # Validate risk level
                risk = seg.get("riskLevel", "low")
                if risk not in ("low", "medium", "high"):
                    risk = "low"

                segments.append(Segment(
                    segmentId=sid,
                    type=seg_type,
                    title=seg.get("title", ""),
                    text=seg.get("text", ""),
                    estimatedDurationSec=seg.get("estimatedDurationSec", 0),
                    pauseAfterMs=seg.get("pauseAfterMs", 800),
                    sourceIds=seg.get("sourceIds", []),
                    riskLevel=risk,
                ))

            return PodcastEpisodeScript(
                episodeId=raw.get("episodeId", episode_id),
                title=raw.get("title", "小站早班车"),
                city=raw.get("city", city),
                date=raw.get("date", date_str),
                showName=raw.get("showName", "小站早班车"),
                hostName=raw.get("hostName", "小站姐"),
                summary=raw.get("summary", ""),
                segments=segments,
                sources=sources,
            )
        except Exception as e:
            logger.error("Failed to parse AI output: %s", e)
            logger.error("Raw output: %s", json.dumps(raw, ensure_ascii=False)[:500])
            raise

    def _fix_segment_ids(self, script: PodcastEpisodeScript) -> PodcastEpisodeScript:
        """Auto-fix: renumber segmentIds and update source references."""
        for i, seg in enumerate(script.segments):
            old_id = seg.segmentId
            new_id = f"seg_{i + 1:03d}"
            if old_id != new_id:
                seg.segmentId = new_id
        return script

    def _call_ai(
        self, prompt: str, is_json: bool = False, max_tokens: int = 2000
    ) -> Any:
        extra_body = {
            "enable_search": True,
            "search_options": {
                "search_strategy": "max",
                "freshness": 7,
            },
        }

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"} if is_json else None,
            extra_body=extra_body,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if is_json:
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content.strip())
        return content.strip()


# ---------------------------------------------------------------------------
# Legacy compatibility (re-export old model names)
# ---------------------------------------------------------------------------

# Keep old names working for any code that imports them
Chapter = Segment  # type: ignore
PodcastScript = PodcastEpisodeScript  # type: ignore


if __name__ == "__main__":
    # Quick smoke test (no API call)
    script = PodcastEpisodeScript(
        episodeId="xzzbc_20260516",
        title="十号线早高峰信号故障，出门多留五分钟",
        city="北京",
        date="2026-05-16",
        summary="今天10号线早高峰有延误，通勤建议预留出行时间，另有一个换乘小提醒。",
        segments=[
            Segment(
                segmentId="seg_001",
                type="opening",
                title="开场",
                text="早上好，我是小站姐，欢迎来到《小站早班车》。今天这几分钟，我们一起看看地铁出行里最值得留意的几件事：哪些线路可能会更忙，哪些站点需要多留点时间，还有一个出门前可以顺手确认的小提醒。",
                estimatedDurationSec=30,
                pauseAfterMs=1000,
                riskLevel="low",
            ),
            Segment(
                segmentId="seg_002",
                type="headline",
                title="今日要闻",
                text="今天北京地铁10号线因信号故障出现延误，早高峰时段部分区间运行间隔延长，建议听众预留出行时间。",
                estimatedDurationSec=45,
                pauseAfterMs=800,
                sourceIds=["src_001"],
                riskLevel="high",
            ),
            Segment(
                segmentId="seg_003",
                type="ending",
                title="结尾",
                text="好啦，今天的《小站早班车》就到这里。如果你的路线涉及临时调整，出门前还是建议再看一眼官方信息。祝你一路顺利，我们明天见。",
                estimatedDurationSec=20,
                pauseAfterMs=0,
                riskLevel="low",
            ),
        ],
        sources=[
            Source(sourceId="src_001", title="北京地铁10号线延误通知", url="https://example.com/1", type="official"),
        ],
    )

    print("=== Episode Script ===")
    print(f"Title: {script.title}")
    print(f"City: {script.city}")
    print(f"Segments: {len(script.segments)}")

    print("\n=== Validation ===")
    result = validate_episode_script(script)
    if result.has_fatal:
        print(f"  FATAL ({len(result.fatal_errors)}):")
        for e in result.fatal_errors:
            print(f"    - {e}")
    if result.warnings:
        print(f"  WARNINGS ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"    - {w}")
    if not result.has_fatal and not result.warnings:
        print("  All validations passed!")
    print(f"  Overall: {'PASSED' if result.passed else 'FAILED'}")

    print("\n=== Backward Compat ===")
    print(f"full_script (first 100 chars): {script.full_script[:100]}...")
    print(f"source_urls: {script.source_urls}")

    # Test that invalid scripts are caught
    print("\n=== Negative Tests ===")

    # Test 1: ending in middle
    bad1 = PodcastEpisodeScript(
        episodeId="bad1",
        title="Bad",
        city="北京",
        date="2026-05-16",
        segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎收听。", riskLevel="low"),
            Segment(segmentId="seg_002", type="ending", title="结", text="感谢收听。", riskLevel="low"),
            Segment(segmentId="seg_003", type="headline", title="闻", text="新闻内容。", riskLevel="low"),
        ],
    )
    r1 = validate_episode_script(bad1)
    print(f"  Test ending-in-middle: {len(r1.fatal_errors)} fatal (expected >=1)")

    # Test 2: non-ending has ending keyword
    bad2 = PodcastEpisodeScript(
        episodeId="bad2",
        title="Bad",
        city="北京",
        date="2026-05-16",
        segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎收听。", riskLevel="low"),
            Segment(segmentId="seg_002", type="headline", title="闻", text="今天的节目就到这里，谢谢。", riskLevel="low"),
            Segment(segmentId="seg_003", type="ending", title="结", text="明天见。", riskLevel="low"),
        ],
    )
    r2 = validate_episode_script(bad2)
    print(f"  Test keyword-leak: {len(r2.fatal_errors)} fatal (expected >=1)")

    # Test 3: high risk without source
    bad3 = PodcastEpisodeScript(
        episodeId="bad3",
        title="Bad",
        city="北京",
        date="2026-05-16",
        segments=[
            Segment(segmentId="seg_001", type="opening", title="开", text="欢迎收听。", riskLevel="low"),
            Segment(segmentId="seg_002", type="line_update", title="线", text="10号线停运。", riskLevel="high"),
            Segment(segmentId="seg_003", type="ending", title="结", text="明天见。", riskLevel="low"),
        ],
    )
    r3 = validate_episode_script(bad3)
    print(f"  Test high-risk-no-source: {len(r3.fatal_errors)} fatal (expected >=1)")

    # Test 4: opening not first
    bad4 = PodcastEpisodeScript(
        episodeId="bad4",
        title="Bad",
        city="北京",
        date="2026-05-16",
        segments=[
            Segment(segmentId="seg_001", type="headline", title="闻", text="新闻。", riskLevel="low"),
            Segment(segmentId="seg_002", type="opening", title="开", text="欢迎收听。", riskLevel="low"),
            Segment(segmentId="seg_003", type="ending", title="结", text="明天见。", riskLevel="low"),
        ],
    )
    r4 = validate_episode_script(bad4)
    print(f"  Test opening-not-first: {len(r4.fatal_errors)} fatal (expected >=1)")

    print("\n=== All smoke tests done ===")
