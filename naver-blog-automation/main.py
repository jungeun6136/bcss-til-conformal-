#!/usr/bin/env python3
"""
네이버 블로그 자동화 시스템
Brand Connect URL + 키워드 입력 → 완성된 블로그 글 + 이미지 세트 출력
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# 필수 패키지 임포트
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from modules.keyword_research import NaverKeywordResearch
from modules.product_scraper import ProductScraper
from modules.image_downloader import ImageDownloader
from modules.content_generator import ContentGenerator
from modules.templates import CATEGORIES, POST_TYPES

console = Console() if HAS_RICH else None


def print_header():
    if HAS_RICH:
        console.print(Panel.fit(
            "[bold cyan]네이버 블로그 자동화 시스템[/bold cyan]\n"
            "[dim]Brand Connect URL → 완성 블로그 글 + 이미지[/dim]",
            border_style="cyan"
        ))
    else:
        print("\n" + "=" * 50)
        print("  네이버 블로그 자동화 시스템")
        print("  Brand Connect URL → 완성 블로그 글 + 이미지")
        print("=" * 50 + "\n")


def choose_category() -> str:
    print("\n📂 카테고리를 선택하세요:")
    items = list(CATEGORIES.items())
    for i, (key, name) in enumerate(items, 1):
        print(f"  {i}. {name}")

    while True:
        choice = input("\n번호 입력 (1-8): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            selected = items[int(choice) - 1]
            print(f"  ✓ 선택: {selected[1]}")
            return selected[0]
        print("  올바른 번호를 입력하세요.")


def choose_post_type() -> str:
    print("\n✍️  글 유형을 선택하세요:")
    items = list(POST_TYPES.items())
    for i, (key, name) in enumerate(items, 1):
        descriptions = {
            "review": "직접 써본 솔직한 후기 형태",
            "compare": "2-3개 제품 비교 분석",
            "info": "구매 전 알아야 할 정보 전달",
            "howto": "활용법·사용 팁 중심",
        }
        print(f"  {i}. {name}  ─  {descriptions.get(key, '')}")

    while True:
        choice = input("\n번호 입력 (1-4): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            selected = items[int(choice) - 1]
            print(f"  ✓ 선택: {selected[1]}")
            return selected[0]
        print("  올바른 번호를 입력하세요.")


def get_keywords(researcher: NaverKeywordResearch, keyword: str) -> list:
    print(f"\n🔍 '{keyword}' 관련 서브키워드 검색 중...")
    keywords = researcher.get_related_keywords(keyword, top_n=30)

    if not keywords:
        print("  키워드 API 응답 없음 - 서브키워드 없이 진행합니다.")
        return []

    # 상위 키워드 표시
    print(f"\n  📊 연관 키워드 상위 10개 (월 검색량 기준):")
    for i, kw in enumerate(keywords[:10], 1):
        total = kw['total']
        bar = "█" * min(20, total // 500) if total > 0 else ""
        print(f"  {i:2}. {kw['keyword']:<20} {total:>6,}회  {bar}")

    selected = researcher.select_sub_keywords(keywords, count=8)
    print(f"\n  ✓ 글에 포함할 서브키워드: {', '.join(selected)}")
    return selected


def save_output(keyword: str, post_content: str, image_guide: str, output_base: Path) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).strip()
    folder_name = f"{timestamp}_{safe_keyword[:20]}"
    output_dir = output_base / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)

    post_file = output_dir / "blog_post.txt"
    with open(post_file, "w", encoding="utf-8") as f:
        f.write(post_content)
        f.write("\n\n")
        f.write(image_guide)

    return str(output_dir)


def check_env() -> tuple:
    """환경변수 유효성 검사"""
    naver_key = os.getenv("NAVER_API_KEY")
    naver_secret = os.getenv("NAVER_SECRET_KEY")
    naver_customer = os.getenv("NAVER_CUSTOMER_ID")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    missing = []
    if not naver_key:
        missing.append("NAVER_API_KEY")
    if not naver_secret:
        missing.append("NAVER_SECRET_KEY")
    if not naver_customer:
        missing.append("NAVER_CUSTOMER_ID")
    if not anthropic_key or anthropic_key == "your-anthropic-api-key-here":
        missing.append("ANTHROPIC_API_KEY")

    if missing:
        print(f"\n❌ .env 파일에 다음 키가 없거나 설정되지 않았습니다:")
        for m in missing:
            print(f"   - {m}")
        if "ANTHROPIC_API_KEY" in missing:
            print("\n   → Anthropic API 키 발급: https://console.anthropic.com")
        return None, None, None, None

    return naver_key, naver_secret, naver_customer, anthropic_key


def main():
    print_header()

    # 환경변수 확인
    naver_key, naver_secret, naver_customer, anthropic_key = check_env()
    if not all([naver_key, naver_secret, naver_customer, anthropic_key]):
        sys.exit(1)

    # 모듈 초기화
    researcher = NaverKeywordResearch(naver_key, naver_secret, naver_customer)
    scraper = ProductScraper()
    generator = ContentGenerator(anthropic_key)

    print("\n" + "─" * 50)

    # ① 메인 키워드 입력
    keyword = input("\n🎯 메인 키워드를 입력하세요\n   예) 에어프라이어 추천, 선크림 비교, 유산균 효능\n   → ").strip()
    if not keyword:
        print("키워드를 입력해주세요.")
        sys.exit(1)

    # ② Brand Connect URL 입력
    print("\n🔗 Brand Connect 제품 링크를 붙여넣으세요")
    print("   (브랜드커넥트에서 발급받은 바이럴 URL)")
    brand_url = input("   → ").strip()
    if not brand_url:
        print("URL을 입력해주세요.")
        sys.exit(1)

    # ③ 카테고리 선택
    category = choose_category()

    # ④ 글 유형 선택
    post_type = choose_post_type()

    print("\n" + "─" * 50)
    print("\n🚀 자동화 시작!\n")

    # ⑤ 서브키워드 수집
    sub_keywords = get_keywords(researcher, keyword)

    # ⑥ 제품 정보 스크래핑
    print(f"\n🛍️  제품 정보 수집 중...")
    product_info = scraper.scrape_product_from_url(brand_url)

    # 스크래핑 결과가 빈약하면 네이버쇼핑 추가 검색
    if not product_info.get("name") or len(product_info.get("description", "")) < 50:
        print("  URL에서 정보가 부족해서 네이버쇼핑 추가 검색 중...")
        naver_info = scraper.search_product_on_naver(keyword)
        # 없는 정보만 보완
        for field in ["name", "price", "specs", "description", "images"]:
            if not product_info.get(field) and naver_info.get(field):
                product_info[field] = naver_info[field]

    print(f"  ✓ 제품명: {product_info.get('name', '미확인')}")
    print(f"  ✓ 가격: {product_info.get('price', '미확인')}원")
    print(f"  ✓ 이미지: {len(product_info.get('images', []))}개 발견")

    # ⑦ 이미지 다운로드
    output_base = Path(__file__).parent / "output"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).strip()
    folder_name = f"{timestamp}_{safe_keyword[:20]}"
    output_dir = output_base / folder_name
    images_dir = output_dir / "images"

    print(f"\n📸 이미지 다운로드 중...")
    downloader = ImageDownloader(str(images_dir))
    saved_images = downloader.download_images(
        product_info.get("images", []),
        prefix="product"
    )
    image_guide = downloader.generate_image_guide(saved_images)

    # ⑧ 블로그 글 생성
    print(f"\n✍️  블로그 글 생성 중...")
    post_content = generator.generate_blog_post(
        category=category,
        post_type=post_type,
        keyword=keyword,
        sub_keywords=sub_keywords,
        product_info=product_info,
        brand_connect_url=brand_url,
    )

    # ⑨ 결과 저장
    output_dir.mkdir(parents=True, exist_ok=True)
    post_file = output_dir / "blog_post.txt"
    with open(post_file, "w", encoding="utf-8") as f:
        f.write(post_content)
        f.write("\n\n")
        f.write(image_guide)

    # ⑩ 완료 안내
    print("\n" + "=" * 50)
    print("✅ 완료!")
    print(f"\n📁 결과물 저장 위치:")
    print(f"   {output_dir}/")
    print(f"   ├── blog_post.txt  ← 블로그 글 (이미지 삽입 위치 표시됨)")
    print(f"   └── images/        ← 제품 이미지 {len(saved_images)}개")
    print("\n📋 업로드 방법:")
    print("   1. blog_post.txt 열기")
    print("   2. 내용 복사해서 네이버 블로그 에디터에 붙여넣기")
    print("   3. [이미지1], [이미지2] 표시된 자리에 images/ 폴더의 이미지 순서대로 삽입")
    print("=" * 50)

    # 글 미리보기 (첫 300자)
    print(f"\n📄 글 미리보기 (첫 300자):")
    print("─" * 50)
    print(post_content[:300] + "...")
    print("─" * 50)

    # 수정 요청 옵션
    while True:
        print("\n수정이 필요하신가요?")
        print("  1. 네, 수정 요청 있어요")
        print("  2. 아니요, 완료합니다")
        choice = input("  선택 (1/2): ").strip()

        if choice == "1":
            feedback = input("\n수정 내용을 입력하세요: ").strip()
            if feedback:
                post_content = generator.refine_post(post_content, feedback)
                with open(post_file, "w", encoding="utf-8") as f:
                    f.write(post_content)
                    f.write("\n\n")
                    f.write(image_guide)
                print("  ✓ 수정 완료! blog_post.txt 업데이트됨")
        else:
            break

    print("\n블로그 업로드 화이팅! 🎉\n")


if __name__ == "__main__":
    main()
