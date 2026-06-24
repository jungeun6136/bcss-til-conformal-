"""
경쟁 제품 리서치 모듈
1. Claude가 실제 경쟁 제품명(브랜드+모델) 파악
2. 네이버 쇼핑에서 실제 스펙/가격 수집
3. 비교 데이터 구조로 반환
"""

import json
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from urllib.parse import quote

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


class CompetitorResearcher:
    def __init__(self, anthropic_key: str, naver_client_id: str = "", naver_client_secret: str = ""):
        import anthropic
        self.client = anthropic.Anthropic(api_key=anthropic_key)
        self.model = "claude-opus-4-8"
        self.naver_client_id = naver_client_id
        self.naver_client_secret = naver_client_secret
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def research(self, product_name: str, category: str, price: str, keyword: str) -> List[Dict]:
        """
        메인 제품 정보를 받아 실제 경쟁 제품 2~3개의 스펙/가격을 반환.
        """
        # STEP 1: Claude가 실제 경쟁 제품명 파악
        competitor_names = self._get_competitor_names(product_name, category, price, keyword)
        if not competitor_names:
            return []

        # STEP 2: 각 경쟁 제품 실데이터 수집
        competitors = []
        for name in competitor_names[:3]:
            data = self._scrape_competitor(name)
            if data.get("name"):
                competitors.append(data)

        return competitors

    # ── STEP 1: Claude로 경쟁 제품명 파악 ───────────────
    def _get_competitor_names(self, product_name: str, category: str, price: str, keyword: str) -> List[str]:
        prompt = f"""
다음 제품과 직접 경쟁하는 실제 제품 2~3개를 알려주세요.

메인 제품: {product_name}
카테고리: {category}
가격대: {price if price else "미확인"}
관련 키워드: {keyword}

조건:
- 실제로 시중에 판매 중인 제품이어야 합니다 (브랜드명 + 모델명 포함)
- 비슷한 가격대의 경쟁 제품으로 선정
- 소비자가 구매 시 실제로 고민하는 제품들

아래 JSON 형식으로만 답변 (다른 텍스트 없이):
{{
  "competitors": [
    "브랜드명 모델명 (예: 삼성 비스포크 무풍에어컨 AR09)",
    "브랜드명 모델명 2",
    "브랜드명 모델명 3"
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

    # ── STEP 2: 경쟁 제품 실데이터 수집 ─────────────────
    def _scrape_competitor(self, product_name: str) -> Dict:
        """네이버 쇼핑 공식 API → 스크래핑 순서로 경쟁 제품 정보 수집"""

        # 2-1. 네이버 쇼핑 공식 API 시도
        if self.naver_client_id and self.naver_client_secret:
            result = self._naver_api(product_name)
            if result.get("price") or result.get("specs"):
                return result

        # 2-2. 네이버 쇼핑 스크래핑 폴백
        result = self._scrape_naver_shopping(product_name)
        if result.get("price"):
            return result

        # 2-3. Claude 지식 기반 폴백
        return self._claude_product_info(product_name)

    def _naver_api(self, query: str) -> Dict:
        try:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/shop.json",
                headers={
                    "X-Naver-Client-Id": self.naver_client_id,
                    "X-Naver-Client-Secret": self.naver_client_secret,
                },
                params={"query": query, "display": 1, "sort": "sim"},
                timeout=8,
            )
            items = resp.json().get("items", [])
            if not items:
                return {"name": query}
            item = items[0]
            name = re.sub(r"<[^>]+>", "", item.get("title", query))
            price = re.sub(r"[^\d]", "", item.get("lprice", ""))
            price_fmt = f"{int(price):,}" if price else ""
            return {
                "name": name,
                "price": price_fmt,
                "brand": item.get("brand", ""),
                "maker": item.get("maker", ""),
                "category": item.get("category3", ""),
                "image": item.get("image", ""),
                "link": item.get("link", ""),
                "specs": {
                    "브랜드": item.get("brand", ""),
                    "제조사": item.get("maker", ""),
                    "카테고리": item.get("category3", ""),
                },
            }
        except Exception:
            return {"name": query}

    def _scrape_naver_shopping(self, query: str) -> Dict:
        try:
            url = f"https://search.shopping.naver.com/search/all?query={quote(query)}"
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")

            name_el = soup.select_one(
                "div.basicList_title__xCSyB, strong.basicList_name__WqGRC"
            )
            name = name_el.get_text(strip=True) if name_el else query

            price_els = soup.select("span.basicList_price_sell__UuHRB strong")[:3]
            prices = []
            for pe in price_els:
                p = re.sub(r"[^\d]", "", pe.get_text())
                if p and int(p) > 1000:
                    prices.append(int(p))
            avg_price = f"{sum(prices)//len(prices):,}" if prices else ""

            # 스펙 추출
            specs = {}
            for row in soup.select("table tr")[:8]:
                cells = row.select("th, td")
                if len(cells) >= 2:
                    k, v = cells[0].get_text(strip=True), cells[1].get_text(strip=True)
                    if k and v and len(k) < 20:
                        specs[k] = v

            image_el = soup.select_one("img[class*='basicList_thumb']")
            image = image_el.get("src", "") if image_el else ""

            return {
                "name": name,
                "price": avg_price,
                "specs": specs,
                "image": image,
                "link": url,
                "brand": "",
            }
        except Exception:
            return {"name": query}

    def _claude_product_info(self, product_name: str) -> Dict:
        """스크래핑 모두 실패 시 Claude 지식으로 보완"""
        try:
            prompt = f"""
"{product_name}" 제품의 정보를 아래 JSON 형식으로만 답변하세요:
{{
  "name": "정확한 제품명",
  "price": "시중 가격 (예: 250,000)",
  "specs": {{
    "스펙항목1": "값",
    "스펙항목2": "값",
    "스펙항목3": "값"
  }},
  "key_features": ["특징1", "특징2", "특징3"],
  "pros": ["장점1", "장점2"],
  "cons": ["단점1"]
}}
"""
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            start, end = raw.find("{"), raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            data.setdefault("name", product_name)
            data.setdefault("image", "")
            data.setdefault("link", "")
            return data
        except Exception:
            return {"name": product_name, "price": "", "specs": {}, "image": "", "link": ""}

    # ── 비교 요약 생성 ────────────────────────────────────
    def build_comparison_summary(
        self, main_product: Dict, competitors: List[Dict]
    ) -> str:
        """메인 제품 vs 경쟁 제품들의 비교 요약 텍스트 생성 (프롬프트 주입용)"""
        if not competitors:
            return ""

        lines = ["[실제 경쟁 제품 비교 데이터]"]
        lines.append(f"■ 메인 제품: {main_product.get('name', '')} / 가격: {main_product.get('price', '미확인')}원")
        lines.append("")

        all_spec_keys = set()
        for comp in competitors:
            all_spec_keys.update(comp.get("specs", {}).keys())
        all_spec_keys.update(main_product.get("specs", {}).keys())

        for i, comp in enumerate(competitors, 1):
            lines.append(f"■ 경쟁 제품 {i}: {comp.get('name', '')} / 가격: {comp.get('price', '미확인')}원")
            for k in list(all_spec_keys)[:6]:
                main_val = main_product.get("specs", {}).get(k, "-")
                comp_val  = comp.get("specs", {}).get(k, "-")
                if main_val != "-" or comp_val != "-":
                    lines.append(f"  {k}: 메인={main_val} / 경쟁={comp_val}")
            if comp.get("pros"):
                lines.append(f"  경쟁제품 장점: {', '.join(comp['pros'])}")
            if comp.get("cons"):
                lines.append(f"  경쟁제품 약점: {', '.join(comp['cons'])}")
            lines.append("")

        lines.append("→ 위 실제 데이터를 바탕으로 메인 제품이 경쟁 제품 대비 우위인 항목을 명확하게 부각하세요.")
        lines.append("→ 비교표(마크다운 표)를 반드시 포함하세요.")
        return "\n".join(lines)
