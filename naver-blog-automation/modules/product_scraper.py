import json
import requests
import re
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
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
    "네이버 브랜드 커넥트", "브랜드 커넥트", "Naver Brand Connect",
    "스마트스토어", "네이버쇼핑", "네이버 쇼핑",
]


def _find_product_name(obj, depth: int = 0) -> str:
    """JSON 트리를 재귀적으로 탐색해 productName / name 필드 추출"""
    if depth > 8:
        return ""
    if isinstance(obj, dict):
        for key in ("productName", "name", "goodsName", "itemName"):
            val = obj.get(key, "")
            if isinstance(val, str) and len(val) > 3 and not any(n in val for n in NOISE_PATTERNS):
                return val.strip()
        for v in obj.values():
            found = _find_product_name(v, depth + 1)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj[:5]:
            found = _find_product_name(item, depth + 1)
            if found:
                return found
    return ""


def _is_noise(text: str) -> bool:
    if not text or len(text) < 10 or len(text) > 500:
        return True
    return any(kw in text for kw in NOISE_PATTERNS)


def _to_int(val) -> int:
    """문자열/숫자 → 정수, 실패 시 0"""
    try:
        return int(str(val).replace(",", "").replace(" ", ""))
    except Exception:
        return 0


def _fmt(price_int: int) -> str:
    return f"{price_int:,}" if price_int > 0 else ""


class ProductScraper:
    def __init__(self, naver_client_id: str = "", naver_client_secret: str = ""):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.naver_client_id = naver_client_id
        self.naver_client_secret = naver_client_secret

    # ═══════════════════════════════════════════════════════
    # 쇼핑 검색 (카드 선택 UI용)
    # ═══════════════════════════════════════════════════════
    def search_products(self, query: str, top_n: int = 8) -> List[Dict]:
        """키워드 → 네이버 쇼핑 상품 목록 반환 (최저가순 정렬)"""
        results = []

        # 1순위: 공식 API → lprice가 확정 최저가
        if self.naver_client_id and self.naver_client_secret:
            results = self._search_official_api(query, min(top_n, 10))
            print(f"[search] official API: {len(results)} results")

        # 2순위: 내부 JSON API
        if not results:
            results = self._search_json_api(query, top_n)
            print(f"[search] json API: {len(results)} results")

        # 3순위: HTML 파싱
        if not results:
            results = self._search_html(query, top_n)
            print(f"[search] html scrape: {len(results)} results")

        results.sort(key=lambda x: x.get("price_int", 0))
        return results[:top_n]

    def _search_official_api(self, query: str, n: int) -> List[Dict]:
        try:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/shop.json",
                headers={
                    "X-Naver-Client-Id": self.naver_client_id,
                    "X-Naver-Client-Secret": self.naver_client_secret,
                },
                params={"query": query, "display": n, "sort": "sim"},
                timeout=8,
            )
            items = resp.json().get("items", [])
            results = []
            for it in items:
                price_int = _to_int(it.get("lprice", 0))
                if price_int <= 100:
                    continue
                name = re.sub(r"<[^>]+>", "", it.get("title", "")).strip()
                results.append({
                    "name": name,
                    "price": _fmt(price_int),
                    "price_int": price_int,
                    "image": it.get("image", ""),
                    "brand": it.get("brand", "") or it.get("maker", ""),
                    "mall_name": it.get("mallName", ""),
                    "rating": "",
                    "review_count": _fmt(_to_int(it.get("reviewCount", 0))),
                    "source_url": it.get("link", ""),
                    "category": it.get("category3", "") or it.get("category2", ""),
                    "specs": {
                        "브랜드": it.get("brand", ""),
                        "제조사": it.get("maker", ""),
                        "카테고리": it.get("category3", ""),
                    },
                    "description": "",
                    "images": [it.get("image", "")],
                    "promotions": {},
                    "pros": [], "cons": [], "key_features": [],
                })
            return results
        except Exception as e:
            print(f"[search] error: {e}")
            return []

    def _search_json_api(self, query: str, n: int) -> List[Dict]:
        try:
            resp = self.session.get(
                "https://search.shopping.naver.com/api/search",
                params={
                    "query": query, "sort": "sim",
                    "productSet": "total", "viewType": "list",
                    "pagingIndex": 1, "pagingSize": n,
                },
                headers={
                    **HEADERS,
                    "Referer": f"https://search.shopping.naver.com/search/all?query={quote(query)}",
                    "Accept": "application/json, text/plain, */*",
                    "Sec-Fetch-Site": "same-origin",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            products = (
                data.get("shoppingResult", {}).get("products", [])
                or data.get("products", [])
            )
            results = []
            for p in products:
                price_int = _to_int(p.get("lowPrice") or p.get("price", 0))
                if price_int <= 100:
                    continue
                specs = {}
                for ak in ("attributes", "attribute", "spec"):
                    a = p.get(ak, {})
                    if isinstance(a, dict) and a:
                        specs = {k: v for k, v in list(a.items())[:8] if k and v}
                        break
                results.append({
                    "name": p.get("productName", "").strip(),
                    "price": _fmt(price_int),
                    "price_int": price_int,
                    "image": p.get("imageUrl", ""),
                    "brand": p.get("brand", ""),
                    "mall_name": p.get("mallName", ""),
                    "rating": str(p.get("reviewScore", "") or ""),
                    "review_count": _fmt(_to_int(p.get("reviewCount", 0))),
                    "source_url": "",
                    "category": p.get("category3Name", ""),
                    "specs": specs,
                    "description": "",
                    "images": [p.get("imageUrl", "")],
                    "promotions": {},
                    "pros": [], "cons": [], "key_features": [],
                })
            return results
        except Exception as e:
            print(f"[search] error: {e}")
            return []

    def _search_html(self, query: str, n: int) -> List[Dict]:
        try:
            url = f"https://search.shopping.naver.com/search/all?query={quote(query)}&sort=price_asc"
            resp = self.session.get(url, timeout=12)
            soup = BeautifulSoup(resp.content, "lxml")
            tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if not tag:
                return []
            nd = json.loads(tag.string)
            state = (
                nd.get("props", {}).get("pageProps", {}).get("initialState", {})
                or {}
            )
            products_raw = (
                state.get("products", {}).get("list", [])
                or state.get("list", [])
            )
            results = []
            for pw in products_raw[:n]:
                item = pw.get("item", pw)
                price_int = _to_int(item.get("lowPrice") or item.get("salePrice") or item.get("price", 0))
                if price_int <= 100:
                    continue
                image = ""
                for k in ("imageUrl", "thumbnail", "img"):
                    if item.get(k):
                        image = item[k]
                        break
                results.append({
                    "name": (item.get("productName") or item.get("name") or "").strip(),
                    "price": _fmt(price_int),
                    "price_int": price_int,
                    "image": image,
                    "brand": item.get("brand", ""),
                    "mall_name": item.get("mallName", ""),
                    "rating": str(item.get("reviewScore", "") or ""),
                    "review_count": _fmt(_to_int(item.get("reviewCount", 0))),
                    "source_url": url,
                    "category": "",
                    "specs": {},
                    "description": "",
                    "images": [image] if image else [],
                    "promotions": {},
                    "pros": [], "cons": [], "key_features": [],
                })
            return results
        except Exception as e:
            print(f"[search] error: {e}")
            return []

    # ═══════════════════════════════════════════════════════
    # 메인 리서치
    # ═══════════════════════════════════════════════════════
    def research_product(self, url: str, keyword: str) -> Dict:
        result = self._empty_product(keyword)

        # 1. 네이버 공식 쇼핑 API
        if self.naver_client_id and self.naver_client_secret:
            self._merge(result, self._naver_official_api(keyword))

        # 2. 네이버 쇼핑 내부 JSON API
        if not result.get("price"):
            self._merge(result, self._naver_shopping_json_api(keyword))

        # 3. 네이버 쇼핑 HTML + __NEXT_DATA__
        if not result.get("price"):
            self._merge(result, self._naver_shopping_html(keyword))

        # 4. URL 직접 스크래핑 (스펙·이미지·할인정보 보완)
        url_data = self._scrape_from_url(url)
        self._merge(result, url_data)
        # 프로모션 정보는 URL 스크래핑 결과를 우선
        if url_data.get("promotions"):
            result["promotions"] = url_data["promotions"]

        result["description"] = self._clean_description(result.get("description", ""))
        if not result.get("promotions"):
            result["promotions"] = {}
        return result

    # ═══════════════════════════════════════════════════════
    # 1. 네이버 공식 쇼핑 API
    # ═══════════════════════════════════════════════════════
    def _naver_official_api(self, query: str) -> Dict:
        try:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/shop.json",
                headers={
                    "X-Naver-Client-Id": self.naver_client_id,
                    "X-Naver-Client-Secret": self.naver_client_secret,
                },
                params={"query": query, "display": 10, "sort": "sim"},
                timeout=8,
            )
            items = resp.json().get("items", [])
            if not items:
                return self._empty_product(query)

            # 모든 결과에서 최저가 추출
            prices = [_to_int(it.get("lprice", 0)) for it in items if _to_int(it.get("lprice", 0)) > 1000]
            min_price = _fmt(min(prices)) if prices else ""
            review_counts = [_to_int(it.get("reviewCount", 0)) for it in items]
            max_review = max(review_counts) if review_counts else 0

            item = items[0]
            name = re.sub(r"<[^>]+>", "", item.get("title", ""))
            images = [it.get("image", "") for it in items if it.get("image")]
            return {
                "name": name,
                "price": min_price,
                "brand": item.get("brand", ""),
                "maker": item.get("maker", ""),
                "images": images[:8],
                "specs": {
                    "브랜드": item.get("brand", ""),
                    "카테고리": item.get("category3", ""),
                    "제조사": item.get("maker", ""),
                },
                "description": "",
                "rating": "",
                "review_count": _fmt(max_review) if max_review else "",
                "source_url": item.get("link", ""),
            }
        except Exception:
            return self._empty_product(query)

    # ═══════════════════════════════════════════════════════
    # 2. 네이버 쇼핑 내부 JSON API
    # ═══════════════════════════════════════════════════════
    def _naver_shopping_json_api(self, query: str) -> Dict:
        try:
            headers = {
                **HEADERS,
                "Referer": f"https://search.shopping.naver.com/search/all?query={quote(query)}",
                "Accept": "application/json, text/plain, */*",
                "Sec-Fetch-Site": "same-origin",
            }
            for sort in ("sim", "price_asc"):
                resp = self.session.get(
                    "https://search.shopping.naver.com/api/search",
                    params={
                        "query": query, "sort": sort,
                        "productSet": "total", "viewType": "list",
                        "pagingIndex": 1, "pagingSize": 10,
                    },
                    headers=headers, timeout=10,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                products = (
                    data.get("shoppingResult", {}).get("products", [])
                    or data.get("products", [])
                )
                if products:
                    break
            else:
                return self._empty_product(query)

            prices, images, specs = [], [], {}
            name, rating, review_count = "", "", ""
            for p in products[:10]:
                lp = _to_int(p.get("lowPrice") or p.get("price", 0))
                if lp > 1000:
                    prices.append(lp)
                if p.get("imageUrl"):
                    images.append(p["imageUrl"])
                if not name and p.get("productName"):
                    name = p["productName"]
                if not rating and p.get("reviewScore"):
                    rating = str(p["reviewScore"])
                rc = _to_int(p.get("reviewCount", 0))
                if rc > _to_int(review_count):
                    review_count = _fmt(rc)

            first = products[0]
            for attr_key in ("attributes", "attribute", "spec", "specs"):
                attrs = first.get(attr_key, {})
                if isinstance(attrs, dict):
                    for k, v in list(attrs.items())[:10]:
                        if k and v:
                            specs[k] = v
                    break

            return {
                "name": name,
                "price": _fmt(min(prices)) if prices else "",
                "images": images[:8],
                "specs": specs,
                "description": "",
                "rating": rating,
                "review_count": review_count,
                "brand": first.get("brand", ""),
                "source_url": "",
            }
        except Exception:
            return self._empty_product(query)

    # ═══════════════════════════════════════════════════════
    # 3. 네이버 쇼핑 HTML + __NEXT_DATA__ 파싱
    # ═══════════════════════════════════════════════════════
    def _naver_shopping_html(self, query: str) -> Dict:
        try:
            url = f"https://search.shopping.naver.com/search/all?query={quote(query)}&sort=price_asc"
            resp = self.session.get(url, timeout=14)
            soup = BeautifulSoup(resp.content, "lxml")

            # __NEXT_DATA__ 우선 시도
            nd_result = self._parse_next_data_search(soup, url)
            if nd_result.get("price"):
                return nd_result

            # CSS 셀렉터 폴백
            price_selectors = [
                "[class*='price_num__em'] strong",
                "strong[class*='price_num']",
                "em[class*='price']",
                "[class*='price_sell'] strong",
                "[class*='priceValue']",
                "[class*='lowestPrice']",
                "[class*='price_area'] strong",
                "span[class*='price'] strong",
            ]
            prices = []
            for sel in price_selectors:
                for el in soup.select(sel)[:10]:
                    v = _to_int(re.sub(r"[^\d]", "", el.get_text()))
                    if v > 1000:
                        prices.append(v)
                if prices:
                    break

            # 리뷰 수
            review_count = ""
            for sel in ["[class*='reviewCount']", "[class*='review_count']", "em[class*='count']"]:
                el = soup.select_one(sel)
                if el:
                    v = _to_int(re.sub(r"[^\d]", "", el.get_text()))
                    if v > 0:
                        review_count = _fmt(v)
                        break

            images = []
            for img in soup.select("img"):
                src = img.get("src") or img.get("data-src") or ""
                if src.startswith("http") and any(x in src for x in ["pstatic", "shopping", "product"]) and len(src) > 20:
                    images.append(src)

            name_el = soup.select_one(
                "[class*='product_name'], [class*='basicList_name'], [class*='item_title'], [class*='product_title']"
            )
            name = name_el.get_text(strip=True) if name_el else ""

            return {
                "name": name,
                "price": _fmt(min(prices)) if prices else "",
                "images": images[:8],
                "specs": {},
                "description": "",
                "rating": "",
                "review_count": review_count,
                "source_url": url,
            }
        except Exception:
            return self._empty_product(query)

    def _parse_next_data_search(self, soup: BeautifulSoup, source_url: str) -> Dict:
        """__NEXT_DATA__ JSON에서 상품 목록 파싱"""
        try:
            tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if not tag:
                return {}
            nd = json.loads(tag.string)

            # 다양한 경로 시도
            state = (
                nd.get("props", {}).get("pageProps", {}).get("initialState", {})
                or nd.get("props", {}).get("initialState", {})
                or nd.get("initialState", {})
            )

            # 제품 목록 찾기
            products_raw = (
                state.get("products", {}).get("list", [])
                or state.get("searchResult", {}).get("products", {}).get("list", [])
                or state.get("list", [])
            )

            if not products_raw:
                return {}

            prices, images, specs = [], [], {}
            name, rating, review_count = "", "", ""

            for p_wrap in products_raw[:10]:
                item = p_wrap.get("item", p_wrap)
                lp = _to_int(item.get("lowPrice") or item.get("salePrice") or item.get("price", 0))
                if lp > 1000:
                    prices.append(lp)
                for k in ("imageUrl", "thumbnail", "img", "imageLink"):
                    if item.get(k):
                        images.append(item[k])
                        break
                if not name:
                    name = item.get("productName", "") or item.get("name", "")
                if not rating:
                    rating = str(item.get("reviewScore", "") or item.get("scoreInfo", "") or "")
                rc = _to_int(item.get("reviewCount", 0) or item.get("purchaseCount", 0))
                if rc > _to_int(review_count):
                    review_count = _fmt(rc)
                if not specs:
                    for ak in ("attributes", "attribute", "spec"):
                        a = item.get(ak, {})
                        if isinstance(a, dict) and a:
                            specs = {k: v for k, v in list(a.items())[:10] if k and v}
                            break

            if not prices:
                return {}

            return {
                "name": name,
                "price": _fmt(min(prices)),
                "images": images[:8],
                "specs": specs,
                "description": "",
                "rating": rating,
                "review_count": review_count,
                "source_url": source_url,
            }
        except Exception:
            return {}

    # ═══════════════════════════════════════════════════════
    # 4. URL 직접 스크래핑
    # ═══════════════════════════════════════════════════════
    def _scrape_from_url(self, url: str) -> Dict:
        try:
            final_url = self._follow_redirects(url)
            domain = urlparse(final_url).netloc
            if "smartstore.naver.com" in domain or "brand.naver.com" in domain:
                result = self._scrape_smartstore(final_url)
            elif "coupang.com" in domain:
                result = self._scrape_coupang(final_url)
            else:
                result = self._scrape_og(final_url)
            # 제품명이 비어있으면 OG title / <title> 태그로 보완
            if not result.get("name"):
                try:
                    resp = self.session.get(final_url, timeout=10)
                    soup = BeautifulSoup(resp.content, "lxml")
                    og_title = (soup.find("meta", property="og:title") or {}).get("content", "")
                    page_title = soup.title.string.strip() if soup.title else ""
                    # 네이버 브랜드스토어 title 형식: "제품명 : 브랜드 스토어" → 앞부분 추출
                    for raw in [og_title, page_title]:
                        if raw:
                            name = re.split(r"[:\|｜–—]", raw)[0].strip()
                            if (name and len(name) > 3
                                    and not any(n in name for n in NOISE_PATTERNS)):
                                result["name"] = name
                                break
                except Exception:
                    pass
            return result
        except Exception:
            return self._empty_product("")

    def _follow_redirects(self, url: str) -> str:
        try:
            # HEAD를 막는 서버가 많아 GET으로 리다이렉트 추적
            resp = self.session.get(url, allow_redirects=True, timeout=10)
            return resp.url
        except Exception:
            return url

    # ── 스마트스토어 / 브랜드스토어 ──────────────────────────
    def _scrape_smartstore(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=12)
            soup = BeautifulSoup(resp.content, "lxml")

            # __NEXT_DATA__ 에서 상품 상세 정보 파싱
            nd_data = self._parse_smartstore_next_data(soup)
            if nd_data.get("price"):
                return nd_data

            # CSS 폴백
            name = self._text(soup.select_one(
                "[class*='productTitle'], [class*='product_title'], h1[class*='title'], h3[class*='title']"
            ))
            price = ""
            for sel in [
                "[class*='_1LY7DqCnwR']", "[class*='price_num']",
                "[class*='salePrice']", "[class*='sellingPrice']",
                "strong[class*='price']", "[class*='price'] strong",
                "span[class*='price_area']",
            ]:
                el = soup.select_one(sel)
                if el:
                    v = _to_int(re.sub(r"[^\d]", "", el.get_text()))
                    if v > 1000:
                        price = _fmt(v)
                        break

            promotions = self._extract_promotions_html(soup, _to_int(price))
            specs = self._extract_spec_table(soup)
            images = [
                img.get("src", "") for img in soup.select("img")
                if "pstatic" in img.get("src", "") and len(img.get("src", "")) > 30
            ]
            rating_el = soup.select_one("[class*='reviewSummary'], [class*='review_score'], [class*='rating']")
            rating = re.sub(r"[^\d.]", "", self._text(rating_el))[:4] if rating_el else ""

            review_count = ""
            for sel in ["[class*='reviewCount']", "[class*='review_count']", "[class*='totalReviewCount']"]:
                el = soup.select_one(sel)
                if el:
                    v = _to_int(re.sub(r"[^\d]", "", el.get_text()))
                    if v > 0:
                        review_count = _fmt(v)
                        break

            desc_tags = [
                t.get_text(strip=True) for t in soup.select("[class*='description'] p, [class*='info'] p")
                if not _is_noise(t.get_text(strip=True))
            ]

            return {
                "name": name, "price": price,
                "description": " ".join(desc_tags[:3]),
                "specs": specs, "images": images[:8],
                "rating": rating, "review_count": review_count,
                "promotions": promotions, "source_url": url,
            }
        except Exception:
            return self._empty_product("")

    def _parse_smartstore_next_data(self, soup: BeautifulSoup) -> Dict:
        """스마트스토어 __NEXT_DATA__ 파싱 - 가격·할인·리뷰 모두 추출"""
        try:
            tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if not tag:
                return {}
            nd = json.loads(tag.string)

            # state 경로 탐색
            state = (
                nd.get("props", {}).get("pageProps", {}).get("initialState", {})
                or nd.get("props", {}).get("pageProps", {})
                or {}
            )

            # product 객체 찾기 (다양한 경로)
            product = (
                state.get("product", {})
                or state.get("productDetail", {})
                or {}
            )
            # 스마트스토어는 product 아래 채널ID 키로 감싸는 경우 있음
            if product and not any(k in product for k in ("productName", "salePrice", "name")):
                for v in product.values():
                    if isinstance(v, dict) and (v.get("productName") or v.get("salePrice")):
                        product = v
                        break

            # 일반 경로 실패 시 전체 JSON 재귀 탐색
            name = product.get("productName", "") or product.get("name", "")
            if not name:
                name = _find_product_name(nd)
            sale_price = _to_int(product.get("salePrice", 0) or product.get("price", 0))
            discounted = _to_int(product.get("discountedSalePrice", 0) or product.get("discountPrice", 0))
            display_price = discounted if discounted and discounted < sale_price else sale_price

            # 할인 정보 수집
            benefit = (
                product.get("benefitSection", {})
                or product.get("benefit", {})
                or {}
            )
            imm_disc = _to_int(benefit.get("immediateDiscountAmount", 0) or benefit.get("immediateDiscount", 0))
            coupon_disc = _to_int(benefit.get("couponDiscountAmount", 0) or benefit.get("maxCouponDiscountAmount", 0))
            card_desc = ""
            for card in (benefit.get("cardPromotions") or benefit.get("cardBenefits") or [])[:1]:
                if isinstance(card, dict):
                    card_desc = card.get("description", "") or card.get("cardName", "")

            max_disc_total = imm_disc + coupon_disc
            max_disc_price = display_price - max_disc_total if max_disc_total > 0 else 0

            promotions = {}
            if imm_disc > 0:
                promotions["즉시할인"] = _fmt(imm_disc) + "원"
            if coupon_disc > 0:
                promotions["쿠폰할인"] = "최대 " + _fmt(coupon_disc) + "원"
            if card_desc:
                promotions["카드혜택"] = card_desc
            if max_disc_price > 0:
                promotions["최대할인가"] = _fmt(max_disc_price) + "원"

            # 리뷰
            review_summary = product.get("reviewSummary", {}) or product.get("review", {}) or {}
            rating = str(review_summary.get("averageRating", "") or review_summary.get("score", ""))[:4]
            review_count = _fmt(_to_int(review_summary.get("totalReviewCount", 0) or review_summary.get("count", 0)))

            # 스펙
            specs = {}
            for ak in ("attributes", "attribute", "spec", "productAttributes"):
                a = product.get(ak, {})
                if isinstance(a, dict) and a:
                    specs = {k: v for k, v in list(a.items())[:12] if k and v}
                    break
                elif isinstance(a, list):
                    for item in a[:12]:
                        if isinstance(item, dict):
                            k = item.get("name", "") or item.get("key", "")
                            v = item.get("value", "") or item.get("val", "")
                            if k and v:
                                specs[k] = v
                    break

            # 이미지
            images = []
            for ik in ("representativeImageUrl", "mainImage", "imageUrl"):
                img = product.get(ik)
                if img and isinstance(img, str):
                    images.append(img)
            for img_obj in (product.get("images") or product.get("imageList") or [])[:8]:
                if isinstance(img_obj, str):
                    images.append(img_obj)
                elif isinstance(img_obj, dict):
                    images.append(img_obj.get("url", "") or img_obj.get("imageUrl", ""))

            return {
                "name": name,
                "price": _fmt(display_price) if display_price else "",
                "specs": specs,
                "images": [i for i in images if i][:8],
                "rating": rating,
                "review_count": review_count,
                "promotions": promotions,
                "description": "",
                "source_url": "",
            }
        except Exception:
            return {}

    def _extract_promotions_html(self, soup: BeautifulSoup, base_price: int) -> Dict:
        """HTML에서 할인/쿠폰/카드혜택 정보 추출"""
        promotions = {}
        try:
            # 즉시할인
            for sel in [
                "[class*='immediateDiscount']", "[class*='immediate_discount']",
                "[class*='discountRate']", "[class*='discount_rate']",
            ]:
                el = soup.select_one(sel)
                if el:
                    v = re.sub(r"[^\d%원]", "", el.get_text())
                    if v:
                        promotions["즉시할인"] = v
                    break

            # 쿠폰
            for sel in [
                "[class*='coupon']", "[class*='Coupon']",
                "button[class*='benefit']", "[class*='benefit_coupon']",
            ]:
                el = soup.select_one(sel)
                if el:
                    txt = el.get_text(strip=True)
                    m = re.search(r"(\d[\d,]+)\s*원", txt)
                    if m:
                        promotions["쿠폰할인"] = "최대 " + _fmt(_to_int(m.group(1))) + "원"
                    break

            # 카드혜택
            for sel in ["[class*='cardBenefit']", "[class*='card_benefit']", "[class*='cardDiscount']"]:
                el = soup.select_one(sel)
                if el:
                    txt = el.get_text(strip=True)[:60]
                    if txt:
                        promotions["카드혜택"] = txt
                    break

            # 최대할인가 계산
            disc_sum = 0
            for v in promotions.values():
                m = re.search(r"(\d[\d,]+)", v)
                if m:
                    disc_sum += _to_int(m.group(1))
            if disc_sum > 0 and base_price > 0:
                promotions["최대할인가"] = _fmt(base_price - disc_sum) + "원"

        except Exception:
            pass
        return promotions

    # ── 쿠팡 ────────────────────────────────────────────
    def _scrape_coupang(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.content, "lxml")
            name = self._text(soup.select_one("h2.prod-buy-header__title, [class*='product-title']"))

            prices = []
            for sel in ["[class*='total-price']", "[class*='prod-price']", "[class*='price-value']"]:
                el = soup.select_one(sel)
                if el:
                    v = _to_int(re.sub(r"[^\d]", "", el.get_text()))
                    if v > 1000:
                        prices.append(v)
            price = _fmt(min(prices)) if prices else ""

            # 쿠팡 즉시할인/쿠폰
            promotions = {}
            coupon_el = soup.select_one("[class*='coupon-price'], [class*='discount']")
            if coupon_el:
                v = _to_int(re.sub(r"[^\d]", "", coupon_el.get_text()))
                if v > 0:
                    promotions["쿠폰할인"] = _fmt(v) + "원"
                    if _to_int(price) > 0:
                        promotions["최대할인가"] = _fmt(_to_int(price) - v) + "원"

            specs = self._extract_spec_table(soup)
            images = [
                img.get("src", "") for img in soup.select("[class*='prod-image'] img")
                if img.get("src", "").startswith("http")
            ]
            return {
                "name": name, "price": price, "description": "",
                "specs": specs, "images": images[:8],
                "rating": self._text(soup.select_one("[class*='rating-star']")),
                "review_count": self._text(soup.select_one("[class*='count-rvw']")),
                "promotions": promotions, "source_url": url,
            }
        except Exception:
            return self._empty_product("")

    # ── OG 태그 폴백 ─────────────────────────────────────
    def _scrape_og(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.content, "lxml")
            name = (soup.find("meta", property="og:title") or {}).get("content", "")
            desc = (soup.find("meta", property="og:description") or {}).get("content", "")
            img = (soup.find("meta", property="og:image") or {}).get("content", "")
            if _is_noise(desc):
                desc = ""
            return {
                "name": name, "price": "", "description": desc[:400],
                "specs": self._extract_spec_table(soup),
                "images": [img] if img else [],
                "rating": "", "review_count": "",
                "promotions": {}, "source_url": url,
            }
        except Exception:
            return self._empty_product("")

    # ═══════════════════════════════════════════════════════
    # 헬퍼
    # ═══════════════════════════════════════════════════════
    def _extract_spec_table(self, soup: BeautifulSoup) -> Dict:
        specs = {}
        for row in soup.select("table tr, dl, [class*='spec_table'] tr")[:20]:
            cells = row.select("th, td, dt, dd")
            if len(cells) >= 2:
                k = cells[0].get_text(strip=True)
                v = cells[1].get_text(strip=True)
                if k and v and len(k) < 25 and not _is_noise(k) and not _is_noise(v):
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
        # 프로모션 병합
        if not base.get("promotions"):
            base["promotions"] = new.get("promotions", {})

    def _text(self, el) -> str:
        return el.get_text(strip=True) if el else ""

    def _empty_product(self, name: str) -> Dict:
        return {
            "name": name, "price": "", "specs": {}, "description": "",
            "images": [], "rating": "", "review_count": "",
            "promotions": {}, "source_url": "",
        }
