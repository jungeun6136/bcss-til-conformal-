import streamlit as st
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from modules.keyword_research import NaverKeywordResearch
from modules.product_scraper import ProductScraper
from modules.image_downloader import ImageDownloader
from modules.content_generator import ContentGenerator
from modules.templates import CATEGORIES, POST_TYPES

# ── 페이지 설정 ──────────────────────────────
st.set_page_config(
    page_title="네이버 블로그 자동화",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS 스타일 ────────────────────────────────
st.markdown("""
<style>
    .main-title {
        font-size: 2rem;
        font-weight: 800;
        color: #03C75A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1rem;
        color: #888;
        margin-bottom: 2rem;
    }
    .step-badge {
        background: #03C75A;
        color: white;
        border-radius: 50%;
        width: 28px;
        height: 28px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 0.85rem;
        margin-right: 8px;
    }
    .keyword-chip {
        display: inline-block;
        background: #f0faf4;
        border: 1px solid #03C75A;
        color: #03C75A;
        padding: 3px 12px;
        border-radius: 20px;
        margin: 3px;
        font-size: 0.85rem;
    }
    .post-box {
        background: #f9f9f9;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1.5rem;
        white-space: pre-wrap;
        font-size: 0.95rem;
        line-height: 1.8;
        max-height: 600px;
        overflow-y: auto;
    }
    .stat-card {
        background: white;
        border: 1px solid #eee;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .stat-number {
        font-size: 1.8rem;
        font-weight: 800;
        color: #03C75A;
    }
    .stat-label {
        font-size: 0.8rem;
        color: #888;
    }
    div[data-testid="stButton"] button {
        border-radius: 8px;
    }
    .stProgress > div > div {
        background-color: #03C75A;
    }
</style>
""", unsafe_allow_html=True)


def check_env():
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
    if not anthropic_key or "your-" in anthropic_key:
        missing.append("ANTHROPIC_API_KEY")
    return naver_key, naver_secret, naver_customer, anthropic_key, missing


def render_keyword_chips(keywords):
    chips_html = ""
    for kw in keywords:
        chips_html += f'<span class="keyword-chip">#{kw}</span>'
    st.markdown(chips_html, unsafe_allow_html=True)


# ── 사이드바 ──────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 설정")
    st.markdown("---")

    keyword = st.text_input(
        "🎯 메인 키워드",
        placeholder="예) 에어프라이어 추천",
        help="블로그 글의 핵심 키워드를 입력하세요"
    )

    brand_url = st.text_input(
        "🔗 Brand Connect URL",
        placeholder="https://brandc.naver.com/...",
        help="브랜드커넥트에서 발급받은 제품 링크"
    )

    category = st.selectbox(
        "📂 카테고리",
        options=list(CATEGORIES.keys()),
        format_func=lambda x: CATEGORIES[x],
        index=0,
    )

    post_type = st.selectbox(
        "✍️ 글 유형",
        options=list(POST_TYPES.keys()),
        format_func=lambda x: {
            "review": "📝 리뷰형 — 직접 써본 솔직 후기",
            "compare": "⚖️ 비교형 — 제품 비교 분석",
            "info": "💡 정보전달형 — 구매 전 필수 정보",
            "howto": "🛠️ 활용법형 — 사용 팁 & 노하우",
        }[x],
        index=0,
    )

    st.markdown("---")
    generate_btn = st.button(
        "🚀 블로그 글 생성하기",
        type="primary",
        use_container_width=True,
        disabled=not (keyword and brand_url),
    )

    if not keyword or not brand_url:
        st.caption("키워드와 URL을 입력하면 버튼이 활성화됩니다.")


# ── 메인 영역 ─────────────────────────────────
st.markdown('<div class="main-title">✍️ 네이버 블로그 자동화</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Brand Connect URL + 키워드 → 완성된 블로그 글 + 이미지 자동 생성</div>', unsafe_allow_html=True)

naver_key, naver_secret, naver_customer, anthropic_key, missing = check_env()

if missing:
    st.error(f"⚠️ .env 파일에 다음 키가 없습니다: {', '.join(missing)}")
    st.info("naver-blog-automation 폴더 안의 .env 파일을 확인하세요.")
    st.stop()

# ── 세션 상태 초기화 ─────────────────────────
if "post_content" not in st.session_state:
    st.session_state.post_content = None
if "sub_keywords" not in st.session_state:
    st.session_state.sub_keywords = []
if "product_info" not in st.session_state:
    st.session_state.product_info = None
if "saved_images" not in st.session_state:
    st.session_state.saved_images = []
if "output_dir" not in st.session_state:
    st.session_state.output_dir = None


# ── 생성 실행 ─────────────────────────────────
if generate_btn:
    st.session_state.post_content = None
    st.session_state.sub_keywords = []
    st.session_state.product_info = None
    st.session_state.saved_images = []

    progress = st.progress(0)
    status = st.empty()

    # STEP 1: 키워드 수집
    status.markdown("**1/4** 🔍 연관 키워드 수집 중...")
    progress.progress(10)
    try:
        researcher = NaverKeywordResearch(naver_key, naver_secret, naver_customer)
        raw_keywords = researcher.get_related_keywords(keyword, top_n=30)
        st.session_state.sub_keywords = researcher.select_sub_keywords(raw_keywords, count=8)
        progress.progress(25)
    except Exception as e:
        st.warning(f"키워드 수집 실패 (계속 진행): {e}")
        raw_keywords = []
        st.session_state.sub_keywords = []

    # STEP 2: 제품 정보 스크래핑
    status.markdown("**2/4** 🛍️ 제품 정보 수집 중...")
    progress.progress(30)
    try:
        scraper = ProductScraper()
        product_info = scraper.scrape_product_from_url(brand_url)
        if not product_info.get("name") or len(product_info.get("description", "")) < 30:
            extra = scraper.search_product_on_naver(keyword)
            for field in ["name", "price", "specs", "description", "images"]:
                if not product_info.get(field) and extra.get(field):
                    product_info[field] = extra[field]
        st.session_state.product_info = product_info
        progress.progress(50)
    except Exception as e:
        st.warning(f"제품 정보 수집 실패 (계속 진행): {e}")
        st.session_state.product_info = {"name": keyword, "price": "", "specs": {}, "description": "", "images": []}

    # STEP 3: 이미지 다운로드
    status.markdown("**3/4** 📸 이미지 다운로드 중...")
    progress.progress(55)
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        safe_kw = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).strip()[:20]
        output_dir = Path(__file__).parent / "output" / f"{timestamp}_{safe_kw}"
        images_dir = output_dir / "images"
        downloader = ImageDownloader(str(images_dir))
        saved_images = downloader.download_images(
            st.session_state.product_info.get("images", []),
            prefix="product"
        )
        st.session_state.saved_images = saved_images
        st.session_state.output_dir = str(output_dir)
        progress.progress(70)
    except Exception as e:
        st.warning(f"이미지 다운로드 실패 (계속 진행): {e}")
        st.session_state.saved_images = []
        output_dir = Path(__file__).parent / "output" / f"{timestamp}_{safe_kw}"
        st.session_state.output_dir = str(output_dir)

    # STEP 4: 글 생성
    status.markdown("**4/4** ✍️ 블로그 글 작성 중... (30초~1분 소요)")
    progress.progress(75)
    try:
        generator = ContentGenerator(anthropic_key)
        post_content = generator.generate_blog_post(
            category=category,
            post_type=post_type,
            keyword=keyword,
            sub_keywords=st.session_state.sub_keywords,
            product_info=st.session_state.product_info,
            brand_connect_url=brand_url,
        )
        st.session_state.post_content = post_content

        # 파일 저장
        output_dir = Path(st.session_state.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        post_file = output_dir / "blog_post.txt"
        image_guide = downloader.generate_image_guide(st.session_state.saved_images) if st.session_state.saved_images else ""
        with open(post_file, "w", encoding="utf-8") as f:
            f.write(post_content)
            if image_guide:
                f.write("\n\n" + image_guide)

        progress.progress(100)
        status.markdown("✅ **완료!**")
    except Exception as e:
        progress.progress(0)
        status.error(f"글 생성 실패: {e}")


# ── 결과 표시 ─────────────────────────────────
if st.session_state.post_content:
    st.markdown("---")

    # 통계 카드
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{len(st.session_state.sub_keywords)}</div>
            <div class="stat-label">수집된 서브키워드</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        product_name = st.session_state.product_info.get("name", "")
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">✅</div>
            <div class="stat-label">제품 정보 수집</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{len(st.session_state.saved_images)}</div>
            <div class="stat-label">다운로드된 이미지</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        char_count = len(st.session_state.post_content)
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{char_count:,}</div>
            <div class="stat-label">생성된 글자수</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["📄 완성된 글", "🔑 수집된 키워드", "🖼️ 다운로드 이미지"])

    with tab1:
        st.markdown("#### 완성된 블로그 글")
        st.markdown(
            f'<div class="post-box">{st.session_state.post_content}</div>',
            unsafe_allow_html=True
        )
        st.markdown("<br>", unsafe_allow_html=True)

        col_a, col_b, col_c = st.columns([1, 1, 2])
        with col_a:
            st.download_button(
                label="💾 파일로 저장",
                data=st.session_state.post_content.encode("utf-8"),
                file_name=f"blog_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col_b:
            st.button("📋 클립보드 복사", use_container_width=True,
                      help="아래 텍스트를 Ctrl+A, Ctrl+C로 복사하세요")

        st.markdown("---")
        st.markdown("#### ✏️ 수정 요청")
        feedback = st.text_area("수정하고 싶은 내용을 입력하세요", placeholder="예) 좀 더 친근한 말투로 바꿔줘 / 가격 정보를 더 강조해줘")
        if st.button("🔄 수정 반영하기", type="secondary") and feedback:
            with st.spinner("수정 중..."):
                try:
                    generator = ContentGenerator(anthropic_key)
                    refined = generator.refine_post(st.session_state.post_content, feedback)
                    st.session_state.post_content = refined
                    st.rerun()
                except Exception as e:
                    st.error(f"수정 실패: {e}")

    with tab2:
        if st.session_state.sub_keywords:
            st.markdown("#### 글에 포함된 서브키워드")
            render_keyword_chips(st.session_state.sub_keywords)
        else:
            st.info("서브키워드 수집 결과가 없습니다.")

    with tab3:
        if st.session_state.saved_images:
            st.markdown(f"#### 다운로드된 제품 이미지 ({len(st.session_state.saved_images)}개)")
            st.caption(f"저장 위치: `{st.session_state.output_dir}/images/`")
            cols = st.columns(min(len(st.session_state.saved_images), 3))
            for i, img_path in enumerate(st.session_state.saved_images):
                with cols[i % 3]:
                    try:
                        st.image(img_path, caption=f"이미지 {i+1}", use_container_width=True)
                    except Exception:
                        st.warning(f"이미지 {i+1} 미리보기 불가")
        else:
            st.info("다운로드된 이미지가 없습니다. 직접 제품 이미지를 추가해주세요.")

elif not generate_btn:
    # 초기 화면
    st.markdown("---")
    st.markdown("### 사용 방법")
    cols = st.columns(4)
    steps = [
        ("1️⃣", "키워드 입력", "블로그에 쓸 메인 키워드를 입력하세요"),
        ("2️⃣", "URL 입력", "브랜드커넥트에서 발급받은 제품 링크를 붙여넣으세요"),
        ("3️⃣", "카테고리/유형 선택", "제품 카테고리와 글 유형을 선택하세요"),
        ("4️⃣", "생성 버튼 클릭", "버튼 하나로 완성된 블로그 글이 자동 생성됩니다"),
    ]
    for col, (icon, title, desc) in zip(cols, steps):
        with col:
            st.markdown(f"**{icon} {title}**")
            st.caption(desc)

    st.markdown("---")
    st.markdown("### 지원 카테고리 및 글 유형")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📂 카테고리 (8종)**")
        for k, v in CATEGORIES.items():
            st.markdown(f"- {v}")
    with col2:
        st.markdown("**✍️ 글 유형 (4종)**")
        for k, v in POST_TYPES.items():
            st.markdown(f"- {v}")
