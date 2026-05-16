import feedparser
import hashlib
from datetime import datetime
from typing import List, Dict
import os
from openai import OpenAI
import json

class RSSCrawler:
    def __init__(self, feeds: List[str]):
        self.feeds = feeds

    def fetch_items(self) -> List[Dict]:
        all_items = []
        for feed_url in self.feeds:
            try:
                feed = feedparser.parse(feed_url)
                source_name = feed.feed.get('title', feed_url)
                
                for entry in feed.entries:
                    content = entry.get('summary', entry.get('description', ''))
                    # Create a hash for deduplication
                    content_hash = hashlib.md5((entry.title + content).encode()).hexdigest()
                    
                    item = {
                        "source": source_name,
                        "title": entry.title,
                        "url": entry.link,
                        "content": content,
                        "published_at": entry.get('published', datetime.now().isoformat()),
                        "id": content_hash # 使用 id 作为统一标识
                    }
                    all_items.append(item)
            except Exception as e:
                print(f"Error fetching {feed_url}: {e}")
        return all_items

    def discover_by_search(self, query: str, city: str = None) -> List[dict]:
        """
        纯搜索驱动：根据关键词发现热点并返回标准格式。
        city: 可选的城市名，用于限定搜索范围。
        """
        client = OpenAI(
            api_key=os.getenv("AI_API_KEY") or os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("AI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        )

        response = client.chat.completions.create(
            model=os.getenv("AI_MODEL", "qwen-max"),
            messages=[{
                "role": "user",
                "content": (
                    f"请搜索关键词 '{query}'，总结出 3-5 条最相关、最新的信息。"
                    "以 JSON 格式输出，包含一个 'news' 列表，每一项有 title, content 两个字段。"
                    "只保留与地铁、轨道交通、城市通勤、出行直接相关的信息。"
                    "如果没有直接相关的信息，news 列表可以为空。"
                    "不要编造信息。"
                )
            }],
            extra_body={
                "enable_search": True,
                "search_options": {
                    "search_strategy": "max",
                    "freshness": 7
                }
            },
            response_format={"type": "json_object"}
        )

        try:
            data = json.loads(response.choices[0].message.content)
            news_list = data.get("news", [])

            items = []
            for news in news_list:
                items.append({
                    "source": "Web Search (Metro)",
                    "title": news.get("title", ""),
                    "content": news.get("content", ""),
                    "url": "https://www.google.com/search?q=" + news.get("title", ""),
                    "id": hashlib.md5(news.get("title", "").encode()).hexdigest()
                })
            return items
        except Exception as e:
            print(f"Search Discovery Error: {e}")
            return []

    def fetch_metro_items(self, city: str = "北京") -> List[dict]:
        """
        地铁播客专用：从多个搜索查询聚合城市轨道交通出行信息。
        每个查询独立搜索，结果合并去重。
        """
        queries = [
            f"{city}地铁 今日运营 调整 出行提示",
            f"{city}地铁 首末班车 施工 换乘 调整",
            f"{city} 轨道交通 通勤 早高峰 提醒",
            f"{city}地铁 新站 开通 线路 变化",
            f"{city} 城市交通 出行安全 地铁",
        ]

        all_items = []
        seen_ids = set()

        for query in queries:
            items = self.discover_by_search(query, city=city)
            for item in items:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    all_items.append(item)

        return all_items

    @staticmethod
    def filter_transit_relevant(items: List[dict]) -> List[dict]:
        """
        过滤出与地铁/通勤/城市出行相关的条目。
        不相关的素材不进入脚本生成。
        """
        TRANSIT_KEYWORDS = [
            "地铁", "轨道交通", "轻轨", "通勤", "出行",
            "公交", "换乘", "线路", "站点", "车站",
            "首末班车", "票价", "运营", "施工", "绕行",
            "限流", "封站", "站台", "屏蔽门", "扶梯",
            "早高峰", "晚高峰", "客流", "区间",
        ]

        relevant = []
        for item in items:
            text = (item.get("title", "") + " " + item.get("content", "")).lower()
            if any(kw in text for kw in TRANSIT_KEYWORDS):
                relevant.append(item)

        return relevant


if __name__ == "__main__":
    crawler = RSSCrawler(feeds=[])
    # 测试地铁搜索模式
    items = crawler.fetch_metro_items("北京")
    print(f"Found {len(items)} metro items via search.")
    for t in items[:10]:
        print(f"- {t['title']}")
    # 测试过滤
    filtered = RSSCrawler.filter_transit_relevant(items)
    print(f"\nAfter transit filter: {len(filtered)} items (from {len(items)})")
