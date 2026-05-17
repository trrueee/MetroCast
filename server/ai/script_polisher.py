"""
Script polisher — second-pass refinement for 小站早班车.

After the main AI generates a structured script, this module runs each
segment through a cheaper model (temperature=0.3) to improve conversational
naturalness without changing the structure or factual content.

Inspired by Voicebox's ``rewrite_as_profile`` pattern.
"""
import logging
import os
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv

from ai.script_writer import PodcastEpisodeScript

load_dotenv()
logger = logging.getLogger("ScriptPolisher")

POLISH_SYSTEM_PROMPT = """你是一个播客口播文本润色器。你的任务是把播客稿的每一段文本改得更自然、更像朋友在聊天，同时严格遵守以下规则：

## 你必须做的
- 让句子更口语化、更流畅，像朋友在说话而不是在朗读
- 保持原意、所有事实信息、所有来源引用不变
- 保持段落长度大致不变（±20%）
- 保持原有的称呼、地名、线路名、数字精确不变

## 你绝对不能做的
- 不要改变段落的主题或信息
- 不要添加"重磅""震撼""必看"等营销词汇
- 不要添加结束语（如"感谢收听""明天见"）
- 不要添加开场白（如"大家好""我是小站姐"）
- 不要添加新闻腔（"据悉""记者获悉"）
- 不要添加新的信息或编造细节
- 不要让语气变得夸张或焦虑

如果原文已经很好、很自然，直接返回原文即可。
只输出润色后的文本，不要加任何解释、引号或标记。"""


def _build_polish_prompt(original_text: str, segment_type: str) -> str:
    """Build a per-segment polish prompt."""
    type_hints = {
        "opening": "这是开场白，保持问候和主题引入的语气。",
        "ending": "这是结尾，保持总结和再见的语气。可以保留结束语（如\"明天见\"）。",
        "headline": "这是今日要闻，保持信息清晰，但不要念得像新闻联播。",
        "line_update": "这是线路变化信息，保持实用、清楚的提醒语气。",
        "commute_tip": "这是通勤贴士，保持贴心、实用的建议语气。",
        "city_story": "这是城市小事，保持轻松、有温度的讲述语气。",
        "safety": "这是安全提醒，保持温和但认真的提醒语气，不要制造恐慌。",
    }
    hint = type_hints.get(segment_type, "保持自然流畅的口语语气。")
    return f"{hint}\n\n原文：\n{original_text}\n\n润色后："


class ScriptPolisher:
    """Lightweight second-pass script refinement."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or "qwen-turbo"  # cheaper model for polish
        self.client = OpenAI(
            api_key=os.getenv("AI_API_KEY"),
            base_url=os.getenv("AI_BASE_URL", "https://api.openai.com/v1"),
        )
        self.enabled = os.getenv("SCRIPT_POLISH_ENABLED", "true").lower() == "true"

    def polish_segment_text(self, text: str, segment_type: str) -> str:
        """Polish a single segment's spoken text."""
        if not text.strip():
            return text

        prompt = _build_polish_prompt(text, segment_type)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": POLISH_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=min(len(text) * 3, 2048),
            )
            polished = response.choices[0].message.content.strip()

            # Sanity: if the model returned something drastically different,
            # keep the original
            if len(polished) < len(text) * 0.3 or len(polished) > len(text) * 2.5:
                logger.warning(
                    "Polish output length anomaly (%d -> %d chars), keeping original",
                    len(text), len(polished),
                )
                return text

            return polished
        except Exception as e:
            logger.warning("Polish failed for segment type=%s: %s", segment_type, e)
            return text

    def polish_script(self, script: PodcastEpisodeScript) -> PodcastEpisodeScript:
        """
        Polish all segments in a script.

        Returns the same script object with polished texts (mutates in place).
        """
        if not self.enabled:
            logger.info("Script polish disabled (SCRIPT_POLISH_ENABLED=false)")
            return script

        logger.info("Polishing %d segments via %s...", len(script.segments), self.model)
        changed = 0
        for seg in script.segments:
            original = seg.text
            seg.text = self.polish_segment_text(original, seg.type)
            if seg.text != original:
                changed += 1
                logger.debug("  %s (%s): %d -> %d chars",
                            seg.segmentId, seg.type, len(original), len(seg.text))

        logger.info("Polish complete: %d/%d segments refined", changed, len(script.segments))
        return script
