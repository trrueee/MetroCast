from duckduckgo_search import DDGS
import logging

logger = logging.getLogger("SearchTool")

class SearchTool:
    def __init__(self, max_results: int = 5):
        self.max_results = max_results

    def search(self, query: str) -> str:
        """
        执行 Web 搜索并返回聚合后的背景文本
        """
        logger.info(f"正在搜索背景信息: {query}")
        results_text = []
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=self.max_results)
                for r in results:
                    results_text.append(f"Title: {r['title']}\nSnippet: {r['body']}\nSource: {r['href']}\n")
            
            return "\n".join(results_text)
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return ""

if __name__ == "__main__":
    tool = SearchTool()
    print(tool.search("OpenAI GPT-5 latest news"))
