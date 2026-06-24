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

    def select_sub_keywords(self, keywords: List[Dict], count: int = 8) -> List[str]:
        """검색량 상위 키워드 중 글에 섞기 적합한 것들만 선택"""
        selected = []
        for k in keywords[:count]:
            if k["total"] > 100:  # 월 100회 이상 검색되는 키워드만
                selected.append(k["keyword"])
        return selected
