import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict


class BlogAnalyzer:
    BLOG_SEARCH_URL = "https://openapi.naver.com/v1/search/blog.json"

    def __init__(self, client_id: str, client_secret: str):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        })

    def fetch_top_posts(self, keyword: str, top_n: int = 10) -> List[Dict]:
        try:
            resp = self.session.get(
                self.BLOG_SEARCH_URL,
                params={"query": keyword, "display": top_n, "sort": "sim"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception as e:
            print(f"  [경고] 블로그 검색 실패: {e}")
            return []

    def _scrape_content(self, url: str) -> str:
        # mobile URL scrapes cleaner
        mobile = re.sub(r"https?://blog\.naver\.com", "https://m.blog.naver.com", url)
        for target in [mobile, url]:
            try:
                resp = self.session.get(target, timeout=8, allow_redirects=True)
                soup = BeautifulSoup(resp.content, "lxml")
                for tag in soup(["script", "style", "nav", "header", "footer"]):
                    tag.decompose()
                area = (
                    soup.find("div", class_="se-main-container")
                    or soup.find("div", class_="post_ct")
                    or soup.find("div", id="postViewArea")
                    or soup.find("div", class_="se_doc_viewer")
                    or soup.body
                )
                text = area.get_text(" ", strip=True) if area else ""
                if len(text) > 100:
                    return text
            except Exception:
                continue
        return ""

    def analyze_keyword_frequency(
        self,
        main_keyword: str,
        sub_keywords: List[str],
        top_n: int = 10,
    ) -> Dict[str, int]:
        """상위 블로그 글에서 각 키워드 출현 포스트 수 반환"""
        posts = self.fetch_top_posts(main_keyword, top_n)
        freq: Dict[str, int] = {kw: 0 for kw in sub_keywords}

        for post in posts:
            # description만으로도 어느 정도 파악 가능 (scraping 실패 대비)
            snippet = re.sub(r"<[^>]+>", "", post.get("description", ""))
            content = self._scrape_content(post.get("link", "")) or snippet
            for kw in sub_keywords:
                if kw in content:
                    freq[kw] += 1

        return freq

    def boost_scores(
        self,
        scored_keywords: List[Dict],
        freq: Dict[str, int],
        boost_per_post: float = 0.3,
    ) -> List[Dict]:
        """블로그 출현 빈도에 따라 score를 부스팅한 복사본 반환"""
        result = []
        for k in scored_keywords:
            kw = k.get("keyword", "")
            boosted = dict(k)
            blog_count = freq.get(kw, 0)
            boosted["score"] = round(k.get("score", 0) + blog_count * boost_per_post, 2)
            boosted["blog_count"] = blog_count
            result.append(boosted)
        return sorted(result, key=lambda x: x["score"], reverse=True)
