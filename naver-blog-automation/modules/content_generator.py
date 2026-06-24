import anthropic
import json
from typing import Dict, List
from .templates import get_system_prompt, get_user_prompt


class ContentGenerator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-opus-4-8"

    def research_product(self, keyword: str, brand_url: str, category: str) -> Dict:
        """
        스크래핑이 막혔을 때 Claude가 직접 제품 정보를 리서치해서 반환.
        학습 데이터 기반으로 실제 제품 스펙·가격·특징을 JSON으로 생성.
        """
        prompt = f"""
다음 제품에 대한 정보를 JSON 형식으로 알려주세요.

제품 키워드: {keyword}
카테고리: {category}
참고 URL: {brand_url}

아래 JSON 형식으로만 답변하세요 (다른 텍스트 없이):
{{
  "name": "정확한 제품명 또는 대표 제품명",
  "price": "일반적인 시중 가격 (예: 150,000~300,000)",
  "description": "제품의 주요 특징과 용도를 2-3문장으로 설명",
  "specs": {{
    "스펙항목1": "값1",
    "스펙항목2": "값2",
    "스펙항목3": "값3",
    "스펙항목4": "값4",
    "스펙항목5": "값5"
  }},
  "rating": "일반적인 소비자 평점 (예: 4.3)",
  "review_count": "대략적인 리뷰 수 (예: 2,400여 개)",
  "key_features": ["주요 특징1", "주요 특징2", "주요 특징3"],
  "pros": ["장점1", "장점2", "장점3"],
  "cons": ["단점 또는 주의사항1", "단점 또는 주의사항2"]
}}

실제로 존재하는 제품 정보를 기반으로 작성하고, 모르는 정보는 "확인 필요"로 표시하세요.
"""
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # JSON 파싱
        try:
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            data  = json.loads(raw[start:end])
            # key_features → description 보완
            if data.get("key_features") and not data.get("description"):
                data["description"] = " / ".join(data["key_features"])
            return data
        except Exception:
            return {"name": keyword, "price": "", "specs": {}, "description": raw[:300],
                    "images": [], "rating": "", "review_count": ""}

    def generate_blog_post(
        self,
        category: str,
        post_type: str,
        keyword: str,
        sub_keywords: List[str],
        product_info: Dict,
        brand_connect_url: str,
    ) -> str:
        print(f"  [글 생성] Claude가 '{keyword}' 관련 블로그 글 작성 중...")

        system_prompt = get_system_prompt(category, post_type)
        user_prompt = get_user_prompt(
            category, post_type, keyword, sub_keywords, product_info, brand_connect_url
        )

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = message.content[0].text
        print(f"  [글 생성] 완료 ({len(content)}자)")
        return content

    def refine_post(self, original_post: str, feedback: str) -> str:
        """사용자 피드백을 반영해서 글 수정"""
        print("  [글 수정] 피드백 반영 중...")

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system="당신은 네이버 블로그 글을 수정하는 전문 에디터입니다. 기존 글의 톤과 스타일을 유지하면서 피드백을 반영합니다.",
            messages=[
                {
                    "role": "user",
                    "content": f"다음 블로그 글을 아래 피드백을 반영해서 수정해주세요.\n\n[원본 글]\n{original_post}\n\n[수정 요청]\n{feedback}",
                }
            ],
        )

        return message.content[0].text
