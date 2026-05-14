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

    def discover_by_search(self, query: str) -> List[dict]:
        """
        纯搜索驱动：根据关键词发现热点并返回标准格式
        """
        client = OpenAI(
            api_key=os.getenv("AI_API_KEY") or os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("AI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        )
        
        # 利用 Qwen-Max 的 search_strategy: max 发现最火热的话题
        response = client.chat.completions.create(
            model=os.getenv("AI_MODEL", "qwen-max"),
            messages=[{
                "role": "user", 
                "content": f"请针对关键词 '{query}' 搜索并总结出 3-5 个最重要的时事。以 JSON 格式输出，包含一个 'news' 列表，每一项有 title, content 两个字段。"
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
                    "source": "Web Search (Trending)",
                    "title": news.get("title", ""),
                    "content": news.get("content", ""),
                    "url": "https://www.google.com/search?q=" + news.get("title", ""),
                    "id": hashlib.md5(news.get("title", "").encode()).hexdigest()
                })
            return items
        except Exception as e:
            print(f"Search Discovery Error: {e}")
            return []

if __name__ == "__main__":
    test_feeds = [
        "https://news.ycombinator.com/rss"
    ]
    crawler = RSSCrawler(test_feeds)
    # 测试搜索模式
    trending = crawler.discover_by_search("今日全球科技热点")
    print(f"Found {len(trending)} trending topics via search.")
    for t in trending:
        print(f"- {t['title']}")
