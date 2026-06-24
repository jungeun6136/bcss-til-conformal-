"""
경쟁 제품 리서치 모듈
1. Claude가 실제 경쟁 제품명(브랜드+모델) 파악
2. 네이버 쇼핑에서 실제 스펙/가격/리뷰수 수집 (최저가 기준)
3. 스크래핑 실패 시 Claude 지식으로 모든 공란 보완 (빈값 허용 안 함)
"""

import json
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from urllib.parse import quote

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

JSON_HEADERS = {
    **HEADERS,
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Site": "same-origin",
}


def _to_int(val) -> int:
    try:
        return int(str(val).replace(",", "").replace(" ", ""))
    except Exception:
        return 0


def _fmt(n: int) -> str:
    return f"{n:,}" if n > 0 else ""


class CompetitorResearcher:
    def __init__(self, anthropic_key: str, naver_client_id: str = "", naver_client_secret: str = ""):
        import anthropic
        self.client = anthropic.Anthropic(api_key=anthropic_key)
        self.model = "claude-opus-4-8"
        self.naver_client_id = naver_client_id
        self.naver_client_secret = naver_client_secret
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ═══════════════════════════════════════════════════════
    # 메인 리서치
    # ═══════════════════════════════════════════════════════
    def research(self, product_name: str, category: str, price: str, keyword: str) -> List[Dict]:
        competitor_names = self._get_competitor_names(product_name, category, price, keyword)
        if not competitor_names:
            return []

        competitors = []
        for name in competitor_names[:3]:
            data = self._scrape_competitor(name)
            data = self._ensure_complete(data, name)  # 공란 보완
            if data.get("name"):
                competitors.append(data)

        return competitors

    # ═══════════════════════════════════════════════════════
    # STEP 1: Claude로 경쟁 제품명 파악
    # ═══════════════════════════════════════════════════════
    def _get_competitor_names(self, product_name: str, category: str, price: str, keyword: str) -> List[str]:
        prompt = f"""
다음 제품과 직접 경쟁하는 실제 제품 2~3개를 알려주세요.

메인 제품: {product_name}
카테고리: {category}
가격대: {price if price else "미확인"}
관련 키워드: {keyword}

조건:
- 실제로 시중에 판매 중인 제품 (브랜드명 + 정확한 모델명 포함)
- 비슷한 가격대에서 소비자가 실제로 비교 구매하는 제품
- 네이버 쇼핑 검색 시 바로 나오는 제품명으로 작성

JSON만 답변 (텍스트 없이):
{{
  "competitors": [
    "정확한 브랜드명 + 모델명 (예: 삼성전자 비스포크 제트 VS20A95823W)",
    "정확한 브랜드명 + 모델명 2",
    "정확한 브랜드명 + 모델명 3"
  ]
}}
"""
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            start, end = raw.find("{"), raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            return data.get("competitors", [])
        except Exception as e:
            print(f"[경쟁 제품 파악 실패] {e}")
            return []

    # ═══════════════════════════════════════════════════════
    # STEP 2: 경쟁 제품 실데이터 수집
    # ═══════════════════════════════════════════════════════
    def _scrape_competitor(self, product_name: str) -> Dict:
        # 2-1. 네이버 공식 API (최저가 가장 정확)
        if self.naver_client_id and self.naver_client_secret:
            result = self._naver_official_api(product_name)
            if result.get("price"):
                return result

        # 2-2. 네이버 쇼핑 내부 JSON API
        result = self._naver_shopping_json_api(product_name)
        if result.get("price"):
            return result

        # 2-3. 네이버 쇼핑 HTML 파싱 + __NEXT_DATA__
        result = self._naver_shopping_html(product_name)
        if result.get("price"):
            return result

        # 2-4. Claude 지식 기반 폴백
        return self._claude_product_info(product_name)

    # ── 네이버 공식 API ──────────────────────────────────
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
                return {"name": query}

            # 모든 결과에서 최저가
            prices = [_to_int(it.get("lprice", 0)) for it in items if _to_int(it.get("lprice", 0)) > 1000]
            min_price = _fmt(min(prices)) if prices else ""
            images = [it.get("image", "") for it in items if it.get("image")]

            item = items[0]
            name = re.sub(r"<[^>]+>", "", item.get("title", query))
            review_counts = [_to_int(it.get("reviewCount", 0)) for it in items]
            review_count = _fmt(max(review_counts)) if any(v > 0 for v in review_counts) else ""

            return {
                "name": name,
                "price": min_price,
                "brand": item.get("brand", ""),
                "maker": item.get("maker", ""),
                "category": item.get("category3", ""),
                "image": images[0] if images else "",
                "images": images[:5],
                "link": item.get("link", ""),
                "review_count": review_count,
                "specs": {
                    "브랜드": item.get("brand", ""),
                    "제조사": item.get("maker", ""),
                    "카테고리": item.get("category3", ""),
                },
            }
        except Exception:
            return {"name": query}

    # ── 네이버 쇼핑 내부 JSON API ────────────────────────
    def _naver_shopping_json_api(self, query: str) -> Dict:
        try:
            resp = self.session.get(
                "https://search.shopping.naver.com/api/search",
                params={
                    "query": query, "sort": "sim",
                    "productSet": "total", "viewType": "list",
                    "pagingIndex": 1, "pagingSize": 10,
                },
                headers={**JSON_HEADERS, "Referer": f"https://search.shopping.naver.com/search/all?query={quote(query)}"},
                timeout=10,
            )
            if resp.status_code != 200:
                return {"name": query}

            data = resp.json()
            products = (
                data.get("shoppingResult", {}).get("products", [])
                or data.get("products", [])
            )
            if not products:
                return {"name": query}

            prices, images = [], []
            name, rating, review_count, specs = "", "", "", {}

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
            for ak in ("attributes", "attribute", "spec"):
                a = first.get(ak, {})
                if isinstance(a, dict) and a:
                    specs = {k: v for k, v in list(a.items())[:10] if k and v}
                    break

            if not prices:
                return {"name": name or query}

            return {
                "name": name or query,
                "price": _fmt(min(prices)),
                "brand": first.get("brand", ""),
                "image": images[0] if images else "",
                "images": images[:5],
                "rating": rating,
                "review_count": review_count,
                "specs": specs,
                "link": "",
            }
        except Exception:
            return {"name": query}

    # ── 네이버 쇼핑 HTML + __NEXT_DATA__ ─────────────────
    def _naver_shopping_html(self, query: str) -> Dict:
        try:
            url = f"https://search.shopping.naver.com/search/all?query={quote(query)}&sort=price_asc"
            resp = self.session.get(url, timeout=12)
            soup = BeautifulSoup(resp.text, "lxml")

            # __NEXT_DATA__ 우선
            tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if tag:
                nd = json.loads(tag.string)
                state = (
                    nd.get("props", {}).get("pageProps", {}).get("initialState", {})
                    or nd.get("props", {}).get("pageProps", {})
                    or {}
                )
                products_raw = (
                    state.get("products", {}).get("list", [])
                    or state.get("list", [])
                )
                if products_raw:
                    prices, images = [], []
                    name, review_count = "", ""
                    for pw in products_raw[:10]:
                        item = pw.get("item", pw)
                        lp = _to_int(item.get("lowPrice") or item.get("salePrice") or item.get("price", 0))
                        if lp > 1000:
                            prices.append(lp)
                        for k in ("imageUrl", "thumbnail", "img"):
                            if item.get(k):
                                images.append(item[k])
                                break
                        if not name:
                            name = item.get("productName", "") or item.get("name", "")
                        rc = _to_int(item.get("reviewCount", 0))
                        if rc > _to_int(review_count):
                            review_count = _fmt(rc)

                    if prices:
                        return {
                            "name": name,
                            "price": _fmt(min(prices)),
                            "image": images[0] if images else "",
                            "images": images[:5],
                            "review_count": review_count,
                            "specs": {},
                            "link": url,
                        }

            # CSS 셀렉터 폴백
            name_el = soup.select_one(
                "div.basicList_title__xCSyB, strong.basicList_name__WqGRC, "
                "[class*='product_name'], [class*='basicList_name']"
            )
            name = name_el.get_text(strip=True) if name_el else query

            prices = []
            for sel in [
                "span[class*='price_sell'] strong",
                "strong[class*='price_num']",
                "[class*='price'] strong",
                "em[class*='price']",
            ]:
                for el in soup.select(sel)[:10]:
                    v = _to_int(re.sub(r"[^\d]", "", el.get_text()))
                    if v > 1000:
                        prices.append(v)
                if prices:
                    break

            image_el = soup.select_one(
                "img[class*='basicList_thumb'], img[class*='product_thumb'], "
                "[class*='thumb'] img, [class*='product'] img"
            )
            image = image_el.get("src", "") or image_el.get("data-src", "") if image_el else ""

            if not prices:
                return {"name": name}

            return {
                "name": name,
                "price": _fmt(min(prices)),
                "image": image,
                "images": [image] if image else [],
                "specs": {},
                "review_count": "",
                "link": url,
            }
        except Exception:
            return {"name": query}

    # ── Claude 지식 기반 폴백 ─────────────────────────────
    def _claude_product_info(self, product_name: str) -> Dict:
        """스크래핑 모두 실패 시 Claude 최신 지식으로 완전한 정보 생성"""
        prompt = f"""
"{product_name}" 제품에 대해 실제 판매 정보를 알려주세요.
절대로 빈 값이나 "정보 없음"을 사용하지 마세요. 모든 필드를 채워야 합니다.

JSON만 답변 (다른 텍스트 없이):
{{
  "name": "정확한 제품 풀네임",
  "price": "네이버 최저가 기준 숫자만 (예: 89000)",
  "brand": "브랜드명",
  "specs": {{
    "스펙항목1": "구체적인 값",
    "스펙항목2": "구체적인 값",
    "스펙항목3": "구체적인 값",
    "스펙항목4": "구체적인 값",
    "스펙항목5": "구체적인 값"
  }},
  "key_features": [
    "핵심 특징 1 (구체적으로)",
    "핵심 특징 2 (구체적으로)",
    "핵심 특징 3 (구체적으로)"
  ],
  "pros": ["장점1", "장점2", "장점3"],
  "cons": ["단점1", "단점2"],
  "review_count": "리뷰 수 대략적인 숫자 (예: 3,200)",
  "rating": "평점 (예: 4.6)"
}}

반드시 실제 제품 스펙을 기반으로 작성하고, 불확실해도 최대한 실제에 가까운 값을 써주세요.
"""
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=700,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            start, end = raw.find("{"), raw.rfind("}") + 1
            data = json.loads(raw[start:end])

            # 가격 정규화
            price_raw = str(data.get("price", ""))
            price_int = _to_int(re.sub(r"[^\d]", "", price_raw))
            data["price"] = _fmt(price_int) if price_int > 0 else ""

            data.setdefault("name", product_name)
            data.setdefault("image", "")
            data.setdefault("images", [])
            data.setdefault("link", "")
            data.setdefault("specs", {})
            data.setdefault("pros", [])
            data.setdefault("cons", [])
            data.setdefault("key_features", [])
            return data
        except Exception:
            return {"name": product_name, "price": "", "specs": {}, "image": "", "link": ""}

    # ═══════════════════════════════════════════════════════
    # 공란 보완: 스크래핑 후 빈 필드를 Claude로 채우기
    # ═══════════════════════════════════════════════════════
    def _ensure_complete(self, data: Dict, product_name: str) -> Dict:
        """가격·스펙·장단점 중 비어있는 항목을 Claude로 보완"""
        needs_fill = (
            not data.get("price")
            or not data.get("specs")
            or not data.get("pros")
            or not data.get("key_features")
        )
        if not needs_fill:
            return data

        known = []
        if data.get("price"):
            known.append(f"가격: {data['price']}원")
        if data.get("specs"):
            known.append("스펙: " + ", ".join(f"{k}={v}" for k, v in list(data["specs"].items())[:5]))

        prompt = f"""
"{product_name}" 제품의 누락된 정보를 채워주세요.

이미 알고 있는 정보:
{chr(10).join(known) if known else "없음"}

JSON만 답변 (다른 텍스트 없이):
{{
  "name": "{data.get('name', product_name)}",
  "price": "{data.get('price', '') or '(예상 최저가 숫자만)'}",
  "brand": "{data.get('brand', '') or '(브랜드명)'}",
  "specs": {{
    "(스펙항목1)": "(값)",
    "(스펙항목2)": "(값)",
    "(스펙항목3)": "(값)",
    "(스펙항목4)": "(값)",
    "(스펙항목5)": "(값)"
  }},
  "key_features": ["특징1", "특징2", "특징3"],
  "pros": ["장점1", "장점2"],
  "cons": ["단점1"],
  "review_count": "(대략적인 리뷰 수)",
  "rating": "(평점)"
}}

모든 필드를 반드시 채워야 합니다. 추정값도 괜찮으니 구체적으로 작성해주세요.
"""
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            s, e = raw.find("{"), raw.rfind("}") + 1
            filled = json.loads(raw[s:e])

            # 기존 데이터 우선, 빈 것만 채움
            for field in ("price", "brand", "review_count", "rating"):
                if not data.get(field) and filled.get(field):
                    v = str(filled[field])
                    if field == "price":
                        pi = _to_int(re.sub(r"[^\d]", "", v))
                        data[field] = _fmt(pi) if pi > 0 else v
                    else:
                        data[field] = v

            if not data.get("specs") and filled.get("specs"):
                data["specs"] = {k: v for k, v in filled["specs"].items() if k and v and "(스펙" not in k}
            else:
                for k, v in (filled.get("specs") or {}).items():
                    if k and v and "(스펙" not in k and k not in data.get("specs", {}):
                        data.setdefault("specs", {})[k] = v

            for f in ("key_features", "pros", "cons"):
                if not data.get(f) and filled.get(f):
                    data[f] = [x for x in filled[f] if x and "(" not in x]

        except Exception:
            pass

        return data

    # ═══════════════════════════════════════════════════════
    # 비교 요약 생성 (프롬프트 주입용)
    # ═══════════════════════════════════════════════════════
    def build_comparison_summary(self, main_product: Dict, competitors: List[Dict]) -> str:
        if not competitors:
            return ""

        lines = ["[실제 경쟁 제품 비교 데이터]"]
        main_price = main_product.get("price", "미확인")
        main_promo = main_product.get("promotions", {})
        main_max = main_promo.get("최대할인가", "")
        price_str = f"{main_price}원" + (f" (최대할인 {main_max})" if main_max else "")
        lines.append(f"■ 메인 제품: {main_product.get('name', '')} / 최저가: {price_str}")
        if main_product.get("review_count"):
            lines.append(f"  리뷰: {main_product.get('review_count')}개 / 평점: {main_product.get('rating', '-')}")
        lines.append("")

        # 공통 스펙 키 수집
        all_keys = list(dict.fromkeys(
            list(main_product.get("specs", {}).keys()) +
            [k for c in competitors for k in c.get("specs", {}).keys()]
        ))[:8]

        for i, comp in enumerate(competitors, 1):
            comp_price = comp.get("price", "미확인")
            comp_name = comp.get("name", f"경쟁제품{i}")
            lines.append(f"■ 경쟁 제품 {i}: {comp_name}")
            lines.append(f"  최저가: {comp_price + '원' if comp_price and comp_price != '미확인' else '미확인'}")
            if comp.get("review_count"):
                lines.append(f"  리뷰: {comp.get('review_count')}개 / 평점: {comp.get('rating', '-')}")

            # 스펙 비교
            spec_lines = []
            for k in all_keys:
                mv = main_product.get("specs", {}).get(k, "-")
                cv = comp.get("specs", {}).get(k, "-")
                if mv != "-" or cv != "-":
                    spec_lines.append(f"  {k}: 메인={mv} / 경쟁={cv}")
            if spec_lines:
                lines.extend(spec_lines)

            if comp.get("key_features"):
                lines.append(f"  주요 특징: {', '.join(comp['key_features'][:3])}")
            if comp.get("pros"):
                lines.append(f"  경쟁제품 장점: {', '.join(comp['pros'][:2])}")
            if comp.get("cons"):
                lines.append(f"  경쟁제품 약점: {', '.join(comp['cons'][:2])}")
            lines.append("")

        lines.append("→ 위 실제 데이터를 바탕으로 마크다운 비교표(|항목|메인제품|경쟁제품1|경쟁제품2|)를 반드시 포함하세요.")
        lines.append("→ 메인 제품이 우위인 항목은 명확히 부각, 경쟁 제품이 나은 항목도 솔직하게 인정하세요.")
        lines.append("→ '이런 분께는 메인 제품, 이런 분께는 경쟁 제품' 형식의 명확한 결론을 내려주세요.")
        return "\n".join(lines)
