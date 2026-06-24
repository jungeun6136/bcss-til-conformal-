import requests
import re
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from urllib.parse import urlparse, quote


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class ProductScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def research_product(self, url: str, keyword: str) -> Dict:
        """
        Brand Connect URL + 키워드로 제품 정보를 최대한 수집.
        URL 스크래핑 → 네이버쇼핑 검색 → 두 결과 병합.
        """
        result = self._empty_product(keyword)

        # 1차: URL에서 직접 수집
        url_info = self._scrape_from_url(url)
        self._merge(result, url_info)

        # 2차: 네이버쇼핑에서 추가 수집
        search_term = result.get("name") or keyword
        naver_info = self._search_naver_shopping(search_term)
        self._merge(result, naver_info)

        # 3차: 스펙이 부족하면 키워드 + "스펙" 으로 추가 검색
        if not result.get("specs"):
            spec_info = self._search_naver_shopping(f"{search_term} 스펙")
            self._merge(result, spec_info)

        return result

    # ── URL 스크래핑 ─────────────────────────────
    def _scrape_from_url(self, url: str) -> Dict:
        try:
            final_url = self._follow_redirects(url)
            domain = urlparse(final_url).netloc
            if "smartstore.naver.com" in domain or "brand.naver.com" in domain:
                return self._scrape_naver_smartstore(final_url)
            elif "coupang.com" in domain:
                return self._scrape_coupang(final_url)
            else:
                return self._scrape_generic(final_url)
        except Exception:
            return self._empty_product("")

    def _follow_redirects(self, url: str) -> str:
        try:
            resp = self.session.head(url, allow_redirects=True, timeout=10)
            return resp.url
        except Exception:
            return url

    def _scrape_naver_smartstore(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            name = self._text(soup.select_one(
                "h3.se_textarea, ._1eddO7u4UC, [class*='productTitle'], h1"
            ))
            price = re.sub(r"[^\d,]", "", self._text(
                soup.select_one("[class*='price'], strong.price")
            ))
            desc_tags = soup.select("[class*='description'], [class*='detail'], p")
            description = " ".join(
                t.get_text(strip=True) for t in desc_tags[:5]
                if len(t.get_text(strip=True)) > 20
            )
            images = [
                img.get("src") or img.get("data-src", "")
                for img in soup.select("img")
                if (img.get("src") or img.get("data-src", "")).startswith("http")
            ]
            specs = self._extract_spec_table(soup)
            return {"name": name, "price": price, "description": description[:600],
                    "specs": specs, "images": images[:8], "rating": "", "review_count": "", "source_url": url}
        except Exception:
            return self._empty_product("")

    def _scrape_coupang(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            name = self._text(soup.select_one(
                "h2.prod-buy-header__title, [class*='product-title']"
            ))
            price = re.sub(r"[^\d,]", "", self._text(
                soup.select_one("[class*='total-price'], strong.final-price")
            ))
            specs = self._extract_spec_table(soup)
            images = [
                img.get("src", "")
                for img in soup.select("[class*='prod-image'] img, #productImage img")
                if img.get("src", "").startswith("http")
            ]
            return {"name": name, "price": price, "description": "", "specs": specs,
                    "images": images[:8],
                    "rating": self._text(soup.select_one("[class*='rating-star']")),
                    "review_count": self._text(soup.select_one("[class*='count-rvw']")),
                    "source_url": url}
        except Exception:
            return self._empty_product("")

    def _scrape_generic(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            og_title = soup.find("meta", property="og:title")
            og_desc = soup.find("meta", property="og:description")
            og_image = soup.find("meta", property="og:image")
            name = og_title["content"] if og_title else self._text(soup.select_one("h1"))
            description = og_desc["content"] if og_desc else ""
            images = [og_image["content"]] if og_image and og_image.get("content") else []
            for img in soup.select("img"):
                src = img.get("src", "")
                if src.startswith("http"):
                    images.append(src)
            specs = self._extract_spec_table(soup)
            return {"name": name, "price": "", "description": description[:600],
                    "specs": specs, "images": images[:8], "rating": "", "review_count": "", "source_url": url}
        except Exception:
            return self._empty_product("")

    # ── 네이버쇼핑 검색 ──────────────────────────
    def _search_naver_shopping(self, query: str) -> Dict:
        try:
            url = f"https://search.naver.com/search.naver?where=nexearch&query={quote(query)}"
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")

            # 상품 이름
            name_el = soup.select_one(
                "[class*='product_name'], [class*='item_title'], h3.name"
            )
            name = self._text(name_el)

            # 가격
            price_el = soup.select_one("[class*='price_num'], [class*='price']")
            price = re.sub(r"[^\d,]", "", self._text(price_el)) if price_el else ""

            # 설명
            desc_el = soup.select_one("[class*='desc'], [class*='detail_desc']")
            description = self._text(desc_el)

            # 스펙 테이블
            specs = self._extract_spec_table(soup)

            # 이미지
            images = []
            for img in soup.select("img"):
                src = img.get("src") or img.get("data-src") or ""
                if src.startswith("http") and any(
                    x in src for x in ["pstatic", "shopping", "image"]
                ):
                    images.append(src)

            # 평점/리뷰
            rating = self._text(soup.select_one("[class*='star_score'], [class*='rating']"))
            review = self._text(soup.select_one("[class*='review_count'], [class*='count']"))

            return {"name": name, "price": price, "description": description[:600],
                    "specs": specs, "images": images[:8],
                    "rating": rating, "review_count": review, "source_url": url}
        except Exception:
            return self._empty_product("")

    # ── 헬퍼 ────────────────────────────────────
    def _extract_spec_table(self, soup) -> Dict:
        specs = {}
        for row in soup.select("table tr")[:15]:
            cells = row.select("th, td")
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                if key and val and len(key) < 30:
                    specs[key] = val
        # dl/dt/dd 형태도 처리
        for dt, dd in zip(soup.select("dt")[:10], soup.select("dd")[:10]):
            key = dt.get_text(strip=True)
            val = dd.get_text(strip=True)
            if key and val and len(key) < 30:
                specs[key] = val
        return specs

    def _merge(self, base: Dict, new: Dict):
        """base에 없는 필드만 new에서 채워 넣기"""
        for field in ["name", "price", "description", "rating", "review_count", "source_url"]:
            if not base.get(field) and new.get(field):
                base[field] = new[field]
        if not base.get("specs") and new.get("specs"):
            base["specs"] = new["specs"]
        elif new.get("specs"):
            base["specs"].update({k: v for k, v in new["specs"].items() if k not in base["specs"]})
        if not base.get("images"):
            base["images"] = new.get("images", [])
        else:
            existing = set(base["images"])
            for img in new.get("images", []):
                if img not in existing:
                    base["images"].append(img)
                    existing.add(img)
        base["images"] = base["images"][:10]

    def _text(self, el) -> str:
        return el.get_text(strip=True) if el else ""

    def _empty_product(self, name: str) -> Dict:
        return {
            "name": name,
            "price": "",
            "specs": {},
            "description": "",
            "images": [],
            "rating": "",
            "review_count": "",
            "source_url": "",
        }
