import json
import requests
import re
from bs4 import BeautifulSoup
from typing import Dict, List
from urllib.parse import urlparse, quote

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

NOISE_PATTERNS = [
    "로그인", "회원가입", "장바구니", "비정상적인 접근", "접속을 일시적",
    "KT인터넷", "당일개통", "shop.kt", "copyright", "고객센터",
    "서비스 이용약관", "개인정보처리방침", "이벤트 혜택",
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

        # 1순위: 네이버 공식 쇼핑 검색 API (키 있을 때)
        if self.naver_client_id and self.naver_client_secret:
            api_info = self._naver_official_api(keyword)
            self._merge(result, api_info)

        # 2순위: 네이버 쇼핑 내부 JSON API
        if not result.get("price"):
            json_info = self._naver_shopping_json_api(keyword)
            self._merge(result, json_info)

        # 3순위: 네이버 쇼핑 HTML 파싱
        if not result.get("price"):
            html_info = self._naver_shopping_html(keyword)
            self._merge(result, html_info)

        # 4순위: URL 직접 스크래핑 (스펙/이미지 보완)
        url_info = self._scrape_from_url(url)
        self._merge(result, url_info)

        result["description"] = self._clean_description(result.get("description", ""))
        return result

    # ── 1. 네이버 공식 쇼핑 API ─────────────────────────
    def _naver_official_api(self, query: str) -> Dict:
        try:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/shop.json",
                headers={
                    "X-Naver-Client-Id": self.naver_client_id,
                    "X-Naver-Client-Secret": self.naver_client_secret,
                },
                params={"query": query, "display": 5, "sort": "sim"},
                timeout=8,
            )
            items = resp.json().get("items", [])
            if not items:
                return self._empty_product(query)
            prices = [int(it["lprice"]) for it in items if it.get("lprice") and it["lprice"].isdigit()]
            min_price = f"{min(prices):,}" if prices else ""
            item = items[0]
            name = re.sub(r"<[^>]+>", "", item.get("title", ""))
            return {
                "name": name, "price": min_price,
                "brand": item.get("brand", ""), "maker": item.get("maker", ""),
                "images": [item.get("image", "")],
                "specs": {"브랜드": item.get("brand",""), "카테고리": item.get("category3","")},
                "description": "", "rating": "", "review_count": "",
                "source_url": item.get("link",""),
            }
        except Exception:
            return self._empty_product(query)

    # ── 2. 네이버 쇼핑 내부 JSON API ────────────────────
    def _naver_shopping_json_api(self, query: str) -> Dict:
        """Naver Shopping의 내부 검색 API 직접 호출"""
        try:
            headers = {
                **HEADERS,
                "Referer": f"https://search.shopping.naver.com/search/all?query={quote(query)}",
                "Accept": "application/json, text/plain, */*",
                "Sec-Fetch-Site": "same-origin",
            }
            url = "https://search.shopping.naver.com/api/search"
            params = {
                "query": query,
                "sort": "price_asc",
                "productSet": "total",
                "viewType": "list",
                "pagingIndex": 1,
                "pagingSize": 5,
            }
            resp = self.session.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200:
                return self._empty_product(query)
            data = resp.json()
            products = (
                data.get("shoppingResult", {}).get("products", [])
                or data.get("products", [])
            )
            if not products:
                return self._empty_product(query)

            prices = []
            images = []
            specs = {}
            name = ""
            for p in products[:5]:
                lp = p.get("lowPrice") or p.get("price", "")
                if str(lp).replace(",", "").isdigit() and int(str(lp).replace(",", "")) > 1000:
                    prices.append(int(str(lp).replace(",", "")))
                if p.get("imageUrl"):
                    images.append(p["imageUrl"])
                if not name and p.get("productName"):
                    name = p["productName"]

            # 스펙 추출
            first = products[0]
            for attr_key in ["attributes", "attribute", "spec"]:
                attrs = first.get(attr_key, {})
                if isinstance(attrs, dict):
                    for k, v in list(attrs.items())[:8]:
                        if k and v:
                            specs[k] = v

            min_price = f"{min(prices):,}" if prices else ""
            return {
                "name": name, "price": min_price,
                "images": images[:6], "specs": specs,
                "description": "", "rating": first.get("reviewScore",""),
                "review_count": str(first.get("reviewCount","")),
                "brand": first.get("brand",""), "source_url": "",
            }
        except Exception:
            return self._empty_product(query)

    # ── 3. 네이버 쇼핑 HTML 파싱 ────────────────────────
    def _naver_shopping_html(self, query: str) -> Dict:
        """HTML 파싱 + __NEXT_DATA__ 시도"""
        try:
            url = f"https://search.shopping.naver.com/search/all?query={quote(query)}&sort=price_asc"
            resp = self.session.get(url, timeout=12)
            soup = BeautifulSoup(resp.text, "lxml")

            # __NEXT_DATA__ JSON 추출 시도
            next_data_tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if next_data_tag:
                try:
                    nd = json.loads(next_data_tag.string)
                    products = (
                        nd.get("props", {}).get("pageProps", {})
                        .get("initialState", {}).get("products", {})
                        .get("list", [])
                    )
                    if products:
                        prices = []
                        images = []
                        for p in products[:5]:
                            item = p.get("item", p)
                            lp = item.get("lowPrice") or item.get("price","")
                            lp_str = str(lp).replace(",","")
                            if lp_str.isdigit() and int(lp_str) > 1000:
                                prices.append(int(lp_str))
                            for img_key in ["imageUrl","thumbnail","img"]:
                                if item.get(img_key):
                                    images.append(item[img_key])
                                    break
                        if prices:
                            return {
                                "name": products[0].get("item",{}).get("productName",""),
                                "price": f"{min(prices):,}",
                                "images": images[:6], "specs": {},
                                "description": "", "rating": "", "review_count": "",
                                "source_url": url,
                            }
                except Exception:
                    pass

            # CSS 셀렉터 파싱 (다양한 클래스명 시도)
            price_selectors = [
                "span.price_num__em strong",
                "strong[class*='price_num']",
                "em[class*='price']",
                "[class*='price_sell'] strong",
                "[class*='priceValue']",
                "[class*='lowestPrice']",
            ]
            price = ""
            for sel in price_selectors:
                els = soup.select(sel)
                if els:
                    candidates = []
                    for el in els[:5]:
                        p = re.sub(r"[^\d]", "", el.get_text())
                        if p and int(p) > 1000:
                            candidates.append(int(p))
                    if candidates:
                        price = f"{min(candidates):,}"
                        break

            # 이미지 수집
            images = []
            for img in soup.select("img"):
                src = img.get("src") or img.get("data-src") or ""
                if src.startswith("http") and any(x in src for x in ["pstatic", "shopping", "product"]):
                    if len(src) > 20:
                        images.append(src)

            name_el = soup.select_one("[class*='product_name'], [class*='basicList_name'], [class*='item_title']")
            name = name_el.get_text(strip=True) if name_el else ""

            return {
                "name": name, "price": price, "images": images[:6],
                "specs": {}, "description": "",
                "rating": "", "review_count": "", "source_url": url,
            }
        except Exception:
            return self._empty_product(query)

    # ── 4. URL 직접 스크래핑 ────────────────────────────
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
            images = [
                img.get("src","") for img in soup.select("img")
                if "pstatic" in img.get("src","") and len(img.get("src","")) > 30
            ]
            desc_tags = [
                t.get_text(strip=True) for t in soup.select("[class*='description'] p")
                if not _is_noise(t.get_text(strip=True))
            ]
            return {"name": name, "price": price, "description": " ".join(desc_tags[:3]),
                    "specs": specs, "images": images[:8], "rating": "", "review_count": "", "source_url": url}
        except Exception:
            return self._empty_product("")

    def _scrape_coupang(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            name  = self._text(soup.select_one("h2.prod-buy-header__title, [class*='product-title']"))
            price = re.sub(r"[^\d,]", "", self._text(soup.select_one("[class*='total-price']")))
            specs = self._extract_spec_table(soup)
            images = [
                img.get("src","") for img in soup.select("[class*='prod-image'] img")
                if img.get("src","").startswith("http")
            ]
            return {"name": name, "price": price, "description": "", "specs": specs,
                    "images": images[:8],
                    "rating": self._text(soup.select_one("[class*='rating-star']")),
                    "review_count": self._text(soup.select_one("[class*='count-rvw']")),
                    "source_url": url}
        except Exception:
            return self._empty_product("")

    def _scrape_og(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            name = (soup.find("meta", property="og:title") or {}).get("content","")
            desc = (soup.find("meta", property="og:description") or {}).get("content","")
            img  = (soup.find("meta", property="og:image") or {}).get("content","")
            if _is_noise(desc):
                desc = ""
            return {"name": name, "price": "", "description": desc[:400],
                    "specs": self._extract_spec_table(soup),
                    "images": [img] if img else [], "rating": "", "review_count": "", "source_url": url}
        except Exception:
            return self._empty_product("")

    # ── 헬퍼 ────────────────────────────────────────────
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
        for f in ["name", "price", "description", "rating", "review_count", "source_url", "brand"]:
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
