import requests
import re
from bs4 import BeautifulSoup
from typing import Dict, Optional
from urllib.parse import urlparse, quote

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

NOISE_PATTERNS = [
    "로그인", "회원가입", "장바구니", "비정상적인 접근", "접속을 일시적",
    "KT", "SKT", "LG유플러스", "인터넷TV", "당일개통", "shop.kt",
    "copyright", "고객센터", "서비스 이용약관", "개인정보처리방침",
]


def _is_noise(text: str) -> bool:
    if not text or len(text) < 10 or len(text) > 500:
        return True
    return any(kw in text for kw in NOISE_PATTERNS)


class ProductScraper:
    def __init__(self, naver_client_id: str = "", naver_client_secret: str = ""):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.naver_client_id = naver_client_id
        self.naver_client_secret = naver_client_secret

    def research_product(self, url: str, keyword: str) -> Dict:
        result = self._empty_product(keyword)

        # 1순위: 네이버 공식 쇼핑 검색 API
        if self.naver_client_id and self.naver_client_secret:
            api_info = self._naver_shopping_api(keyword)
            if api_info.get("name") or api_info.get("price"):
                self._merge(result, api_info)

        # 2순위: URL 스크래핑 (가격/스펙 보완)
        url_info = self._scrape_from_url(url)
        self._merge(result, url_info)

        # 설명 정제
        result["description"] = self._clean_description(result.get("description", ""))
        return result

    # ── 네이버 공식 쇼핑 API ─────────────────────────
    def _naver_shopping_api(self, query: str) -> Dict:
        try:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/shop.json",
                headers={
                    "X-Naver-Client-Id": self.naver_client_id,
                    "X-Naver-Client-Secret": self.naver_client_secret,
                },
                params={"query": query, "display": 5, "sort": "sim"},
                timeout=10,
            )
            items = resp.json().get("items", [])
            if not items:
                return self._empty_product(query)

            item = items[0]
            # 상위 5개 최저가 평균 계산
            prices = []
            for it in items:
                p = re.sub(r"[^\d]", "", it.get("lprice", ""))
                if p and int(p) > 1000:
                    prices.append(int(p))
            avg_price = f"{sum(prices) // len(prices):,}" if prices else re.sub(r"[^\d,]", "", item.get("lprice", ""))

            name = re.sub(r"<[^>]+>", "", item.get("title", ""))  # HTML 태그 제거

            return {
                "name": name,
                "price": avg_price,
                "description": item.get("category3", "") + " " + item.get("category4", ""),
                "specs": {
                    "브랜드": item.get("brand", ""),
                    "제조사": item.get("maker", ""),
                    "카테고리": item.get("category1", ""),
                },
                "images": [item.get("image", "")],
                "rating": "",
                "review_count": "",
                "source_url": item.get("link", ""),
            }
        except Exception as e:
            print(f"[네이버 쇼핑 API 실패] {e}")
            return self._empty_product(query)

    # ── URL 스크래핑 ─────────────────────────────────
    def _scrape_from_url(self, url: str) -> Dict:
        try:
            final_url = self._follow_redirects(url)
            domain = urlparse(final_url).netloc
            if "smartstore.naver.com" in domain or "brand.naver.com" in domain:
                return self._scrape_smartstore(final_url)
            elif "coupang.com" in domain:
                return self._scrape_coupang(final_url)
            else:
                return self._scrape_og(final_url)
        except Exception:
            return self._empty_product("")

    def _follow_redirects(self, url: str) -> str:
        try:
            resp = self.session.head(url, allow_redirects=True, timeout=8)
            return resp.url
        except Exception:
            return url

    def _scrape_smartstore(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            name  = self._text(soup.select_one("h3.se_textarea, [class*='productTitle'], h1"))
            price = re.sub(r"[^\d,]", "", self._text(soup.select_one("[class*='price'], strong.price")))
            specs = self._extract_spec_table(soup)
            images = [img.get("src","") for img in soup.select("img")
                      if "pstatic" in img.get("src","")]
            desc_tags = [t.get_text(strip=True) for t in soup.select("[class*='description'] p")
                         if not _is_noise(t.get_text(strip=True))]
            return {"name": name, "price": price, "description": " ".join(desc_tags[:3]),
                    "specs": specs, "images": images[:6], "rating": "", "review_count": "", "source_url": url}
        except Exception:
            return self._empty_product("")

    def _scrape_coupang(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            name  = self._text(soup.select_one("h2.prod-buy-header__title, [class*='product-title']"))
            price = re.sub(r"[^\d,]", "", self._text(soup.select_one("[class*='total-price']")))
            specs = self._extract_spec_table(soup)
            images = [img.get("src","") for img in soup.select("[class*='prod-image'] img")
                      if img.get("src","").startswith("http")]
            return {"name": name, "price": price, "description": "",
                    "specs": specs, "images": images[:6],
                    "rating": self._text(soup.select_one("[class*='rating-star']")),
                    "review_count": self._text(soup.select_one("[class*='count-rvw']")),
                    "source_url": url}
        except Exception:
            return self._empty_product("")

    def _scrape_og(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            name = (soup.find("meta", property="og:title") or {}).get("content", "")
            desc = (soup.find("meta", property="og:description") or {}).get("content", "")
            img  = (soup.find("meta", property="og:image") or {}).get("content", "")
            if _is_noise(desc):
                desc = ""
            return {"name": name, "price": "", "description": desc[:400],
                    "specs": self._extract_spec_table(soup),
                    "images": [img] if img else [], "rating": "", "review_count": "", "source_url": url}
        except Exception:
            return self._empty_product("")

    # ── 헬퍼 ────────────────────────────────────────
    def _extract_spec_table(self, soup) -> Dict:
        specs = {}
        for row in soup.select("table tr")[:15]:
            cells = row.select("th, td")
            if len(cells) >= 2:
                k, v = cells[0].get_text(strip=True), cells[1].get_text(strip=True)
                if k and v and len(k) < 25 and not _is_noise(k):
                    specs[k] = v
        return specs

    def _clean_description(self, text: str) -> str:
        if not text:
            return ""
        sentences = re.split(r"[.!?]\s+", text)
        clean = [s.strip() for s in sentences if s.strip() and not _is_noise(s.strip())]
        return ". ".join(clean[:5])

    def _merge(self, base: Dict, new: Dict):
        for f in ["name", "price", "description", "rating", "review_count", "source_url"]:
            if not base.get(f) and new.get(f):
                base[f] = new[f]
        if not base.get("specs"):
            base["specs"] = new.get("specs", {})
        else:
            for k, v in new.get("specs", {}).items():
                if k not in base["specs"] and v:
                    base["specs"][k] = v
        existing = set(base.get("images", []))
        for img in new.get("images", []):
            if img and img not in existing:
                base.setdefault("images", []).append(img)
                existing.add(img)
        base["images"] = [i for i in base.get("images", []) if i][:10]

    def _text(self, el) -> str:
        return el.get_text(strip=True) if el else ""

    def _empty_product(self, name: str) -> Dict:
        return {"name": name, "price": "", "specs": {}, "description": "",
                "images": [], "rating": "", "review_count": "", "source_url": ""}
