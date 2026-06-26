import hmac
import hashlib
import base64
import time
import requests
from typing import List, Dict


class NaverKeywordResearch:
    BASE_URL = "https://api.naver.com"

    def __init__(self, api_key: str, secret_key: str, customer_id: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.customer_id = str(customer_id)

    def _generate_signature(self, timestamp: str, method: str, uri: str) -> str:
        message = f"{timestamp}.{method}.{uri}"
        signing_key = self.secret_key.encode("utf-8")
        msg = message.encode("utf-8")
        signature = hmac.new(signing_key, msg, digestmod=hashlib.sha256).digest()
        return base64.b64encode(signature).decode("utf-8")

    def _get_headers(self, method: str, uri: str) -> Dict:
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(timestamp, method, uri)
        return {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Timestamp": timestamp,
            "X-API-KEY": self.api_key,
            "X-Customer": self.customer_id,
            "X-Signature": signature,
        }

    def get_related_keywords(self, keyword: str, top_n: int = 20) -> List[Dict]:
        uri = "/keywordstool"
        headers = self._get_headers("GET", uri)
        params = {"hintKeywords": keyword, "showDetail": "1"}

        try:
            response = requests.get(
                self.BASE_URL + uri, headers=headers, params=params, timeout=10
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"  [경고] 키워드 API 호출 실패: {e}")
            return []

        keywords = []
        for item in data.get("keywordList", []):
            pc = item.get("monthlyPcQcCnt", 0)
            mobile = item.get("monthlyMobileQcCnt", 0)
            pc = int(pc) if isinstance(pc, (int, float)) else 0
            mobile = int(mobile) if isinstance(mobile, (int, float)) else 0
            keywords.append(
                {
                    "keyword": item.get("relKeyword", ""),
                    "monthly_pc": pc,
                    "monthly_mobile": mobile,
                    "total": pc + mobile,
                    "competition": item.get("compIdx", ""),
                }
            )

        keywords.sort(key=lambda x: x["total"], reverse=True)
        # 메인 키워드 자신 제외하고 반환
        return [k for k in keywords if k["keyword"] != keyword][:top_n]

    def select_main_keyword(self, keywords: List[Dict], product_name: str = "") -> Dict:
        """검색량 × 경쟁도 × 관련성 스코어로 최적 메인 키워드 선택"""
        if not keywords:
            return {}

        prod_words = [w for w in product_name.split() if len(w) >= 2] if product_name else []
        COMP_WEIGHT = {"낮음": 3.0, "중간": 2.0, "높음": 1.0}

        def _score(k: Dict) -> float:
            total = k.get("total", 0)
            if 500 <= total <= 5000:
                vol = 1.0
            elif 5000 < total <= 30000:
                vol = 0.7
            else:
                vol = 0.3
            comp = COMP_WEIGHT.get(k.get("competition", ""), 1.5)
            kw_text = k.get("keyword", "")
            relevance = 1.5 if prod_words and any(w in kw_text for w in prod_words) else 1.0
            return vol * comp * relevance

        scored = sorted(keywords, key=_score, reverse=True)
        # 스코어 값도 첨부
        best = dict(scored[0])
        best["score"] = _score(scored[0])
        return best

    def score_keywords(self, keywords: List[Dict], product_name: str = "") -> List[Dict]:
        """각 키워드에 score 필드를 추가해 반환"""
        prod_words = [w for w in product_name.split() if len(w) >= 2] if product_name else []
        COMP_WEIGHT = {"낮음": 3.0, "중간": 2.0, "높음": 1.0}

        result = []
        for k in keywords:
            total = k.get("total", 0)
            if 500 <= total <= 5000:
                vol = 1.0
            elif 5000 < total <= 30000:
                vol = 0.7
            else:
                vol = 0.3
            comp = COMP_WEIGHT.get(k.get("competition", ""), 1.5)
            kw_text = k.get("keyword", "")
            relevance = 1.5 if prod_words and any(w in kw_text for w in prod_words) else 1.0
            scored = dict(k)
            scored["score"] = round(vol * comp * relevance, 2)
            result.append(scored)
        return sorted(result, key=lambda x: x["score"], reverse=True)

    def select_sub_keywords(self, keywords: List[Dict], count: int = 8) -> List[str]:
        """검색량 상위 키워드 중 글에 섞기 적합한 것들만 선택"""
        selected = []
        for k in keywords[:count]:
            if k["total"] > 100:  # 월 100회 이상 검색되는 키워드만
                selected.append(k["keyword"])
        return selected
