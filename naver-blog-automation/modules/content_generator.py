import anthropic
from typing import Dict, List
from .templates import get_system_prompt, get_user_prompt


class ContentGenerator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-opus-4-8"  # 최고 품질 모델 사용

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
