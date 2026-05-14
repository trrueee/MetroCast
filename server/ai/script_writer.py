import os
from typing import List, Optional, Any
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import logging
import json

load_dotenv()
logger = logging.getLogger("ScriptWriter")

from pydantic import BaseModel, Field, AliasChoices, field_validator

class Chapter(BaseModel):
    title: str = Field(..., validation_alias=AliasChoices('title', 'name'))
    script: str = Field(..., validation_alias=AliasChoices('script', 'text', 'content'))
    duration_estimate: int = Field(180, description="Estimated duration in seconds")
    key_points: List[str] = Field(default_factory=list)

    @field_validator('key_points', mode='before')
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, list):
            return [str(item) for item in v]
        if v is None:
            return []
        # 如果是数字或字符串，强制包装成列表
        return [str(v)]

class PodcastScript(BaseModel):
    episode_title: str
    episode_description: str
    full_script: str
    chapters: List[Chapter]
    source_urls: List[str]

class ScriptWriter:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.client = OpenAI(
            api_key=os.getenv("AI_API_KEY"),
            base_url=os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
        )

    def generate_script(self, items: List[dict], tone: str = "relaxed") -> PodcastScript:
        """
        多阶段生成流程：大纲规划 -> 分章扩写 -> 全文润色
        """
        # Step 1: Generate Outline
        logger.info("Stage 1: Generating Outline...")
        outline_prompt = f"""
        你是一个播客总编。请根据以下素材，规划一期 15 分钟播客的大纲。
        输出格式为 JSON: {{"title": "总标题", "description": "简介", "chapters": [{{"title": "章节标题", "key_points": ["要点1", "要点2"]}}]}}
        素材：\n{str(items[:10])}
        """
        outline_res = self._call_ai(outline_prompt, is_json=True)
        
        # Step 2: Expand Chapters
        logger.info("Stage 2: Expanding Chapters...")
        chapters_raw = outline_res.get('chapters', [])
        if isinstance(chapters_raw, dict):
            chapters_raw = [chapters_raw]
            
        chapters_final = []
        full_text_list = []
        last_sentences = "播客开始。"
        
        for i, ch in enumerate(chapters_raw):
            logger.info(f"Expanding chapter {i+1}: {ch['title']}")
            
            is_dialogue = (tone == "dialogue")
            role_prompt = """
            **模式：双人对话**
            请以两个主播的身份对话：
            - [婉儿]：女性，资深科技编辑，专业、知性。
            - [老铁]：男性，科技爱好者，幽默、喜欢提问。
            每一段对话必须以 [婉儿] 或 [老铁] 开头。
            """ if is_dialogue else ""

            expand_prompt = f"""
            你是一个资深的电台节目主持人。现在正在录制一档深度的科技闲谈播客。
            
            当前章节主题：{ch['title']}
            本章核心要点：{ch['key_points']}
            
            上一个环节的结尾是这样说的："{last_sentences}"
            
            {role_prompt}
            
            要求：
            1. 请写一段 800-1000 字的口播稿。
            2. **输出约束**：仅输出角色的对话内容。严禁输出任何类似“好的，这是为您生成的稿子”、“以上是全部内容”等评价性或说明性文字。
            3. **衔接要求**：禁止使用“接下来”等词汇。请自然转场。
            4. **全语种发音优化**：英文音节间插入连字符（如：Git-Hub, O-pen-AI）。
            5. 语气{tone}，字里行间要有呼吸感。
            """
            chapter_script = self._call_ai(expand_prompt, is_json=False)
            
            # --- AI 废话与“为什么”拦截器 ---
            lines = chapter_script.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                # 如果是双人模式，只保留角色标签开头的行，过滤掉 AI 的自我评价
                if is_dialogue:
                    if line.startswith(("[婉儿]", "[老铁]")):
                        cleaned_lines.append(line)
                else:
                    # 单人模式，过滤掉明显的 AI 寒暄词
                    if not any(stop_word in line for stop_word in ["这是为您", "为您生成", "希望满意", "以上内容"]):
                        cleaned_lines.append(line)
            
            chapter_script = "\n".join(cleaned_lines)

            replacements = {
                "为什么呢": "其实原因很简单",
                "这是为什么": "这背后的逻辑是",
                "为什么要": "核心目的其实是",
                "为什么": "原因在于",
                "why": "原因",
                "Why": "原因"
            }
            # ... (保持原有的替换逻辑)
            for old, new in replacements.items():
                if chapter_script.count(old) > 2: # 允许少量出现，超过 2 次开始暴力替换
                    chapter_script = chapter_script.replace(old, new, 2) # 只留两个，剩下的全换掉
            # ---------------------------

            # 提取最后两句话作为下一章的上下文
            sentences = [s for s in chapter_script.replace('。', '。\n').split('\n') if s.strip()]
            last_sentences = " ".join(sentences[-2:]) if len(sentences) >= 2 else chapter_script
            
            chapters_final.append(Chapter(
                title=ch['title'],
                script=chapter_script,
                key_points=ch['key_points']
            ))
            full_text_list.append(chapter_script)
        
        # Step 3: Combine
        return PodcastScript(
            episode_title=outline_res['title'],
            episode_description=outline_res['description'],
            full_script="\n\n".join(full_text_list),
            chapters=chapters_final,
            source_urls=[item.get('url', '') for item in items[:10]]
        )

    def _call_ai(self, prompt: str, is_json: bool = False) -> Any:
        # 根据文档，配置更高级的搜索参数
        extra_body = {
            "enable_search": True,
            "search_options": {
                "search_strategy": "max",  # 高性能搜索模式
                "freshness": 7             # 只看最近 7 天，确保时效性
            }
        }
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} if is_json else None,
            extra_body=extra_body,
            max_tokens=2000
        )
        content = response.choices[0].message.content
        if is_json:
            # Handle potential markdown
            if content.startswith("```"):
                content = content.split("```")[1].replace("json", "")
            return json.loads(content.strip())
        return content.strip()

if __name__ == "__main__":
    pass
    # Mock items for testing
    mock_items = [
        {"source": "HN", "title": "AI is fast", "content": "AI is evolving very quickly in 2024.", "url": "https://example.com/1"},
        {"source": "Verge", "title": "New Gadget", "content": "A new smartphone was released today.", "url": "https://example.com/2"}
    ]
    writer = ScriptWriter()
    # script = writer.generate_script(mock_items) # Requires API key
    # print(script.episode_title)
