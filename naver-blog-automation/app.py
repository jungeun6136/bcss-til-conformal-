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
from modules.competitor_researcher import CompetitorResearcher
from modules.templates import CATEGORIES, POST_TYPES

# ── 페이지 설정 ─────────────────────────────────────
st.set_page_config(
    page_title="네이버 블로그 자동화",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-title { font-size:1.9rem; font-weight:800; color:#03C75A; }
    .sub-title  { font-size:0.95rem; color:#888; margin-bottom:1.5rem; }
    .step-bar   { display:flex; align-items:center; gap:8px; margin-bottom:1.5rem; }
    .step-dot   { width:28px; height:28px; border-radius:50%; background:#e0e0e0;
                  color:#999; display:flex; align-items:center; justify-content:center;
                  font-weight:700; font-size:0.8rem; }
    .step-dot.active  { background:#03C75A; color:white; }
    .step-dot.done    { background:#b2dfdb; color:#00796b; }
    .step-line  { flex:1; height:2px; background:#e0e0e0; }
    .step-line.done { background:#b2dfdb; }
    .kw-chip    { display:inline-block; background:#f0faf4; border:1px solid #03C75A;
                  color:#03C75A; padding:3px 12px; border-radius:20px;
                  margin:3px; font-size:0.82rem; }
    .post-box   { background:#fafafa; border:1px solid #e0e0e0; border-radius:10px;
                  padding:1.5rem; white-space:pre-wrap; font-size:0.93rem;
                  line-height:1.85; max-height:620px; overflow-y:auto; }
    .stat-card  { background:white; border:1px solid #eee; border-radius:10px;
                  padding:1rem; text-align:center; }
    .stat-num   { font-size:1.7rem; font-weight:800; color:#03C75A; }
    .stat-lbl   { font-size:0.78rem; color:#888; }
    .info-block { background:#f8f8f8; border-left:4px solid #03C75A;
                  padding:0.8rem 1rem; border-radius:4px; margin:0.5rem 0; }
    .err-box    { background:#fff3f3; border:1px solid #ffcdd2; border-radius:10px;
                  padding:1.5rem; text-align:center; }
</style>
""", unsafe_allow_html=True)


# ── 세션 상태 초기화 ─────────────────────────────────
DEFAULTS = {
    "step": 0,           # 0=입력 1=제품확인 2=글생성중 3=완료 -1=오류
    "keyword": "",
    "brand_url": "",
    "category": "electronics",
    "post_type": "review",
    "product_info": None,
    "sub_keywords": [],
    "competitors": [],
    "post_content": None,
    "saved_images": [],
    "output_dir": None,
    "error_msg": "",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def reset():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


def check_env():
    k = os.getenv("NAVER_API_KEY", "")
    s = os.getenv("NAVER_SECRET_KEY", "")
    c = os.getenv("NAVER_CUSTOMER_ID", "")
    a = os.getenv("ANTHROPIC_API_KEY", "")
    missing = [n for n, v in [("NAVER_API_KEY",k),("NAVER_SECRET_KEY",s),
                                ("NAVER_CUSTOMER_ID",c),("ANTHROPIC_API_KEY",a)]
               if not v or "your-" in v]
    return k, s, c, a, missing


def step_bar(current: int):
    labels = ["입력", "제품 확인", "글 작성", "완료"]
    html = '<div class="step-bar">'
    for i, label in enumerate(labels):
        cls = "done" if i < current else ("active" if i == current else "")
        icon = "✓" if i < current else str(i + 1)
        html += f'<div class="step-dot {cls}">{icon}</div>'
        html += f'<span style="font-size:0.8rem;color:{"#03C75A" if i<=current else "#aaa"}">{label}</span>'
        if i < len(labels) - 1:
            line_cls = "done" if i < current else ""
            html += f'<div class="step-line {line_cls}"></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_kw_chips(kws):
    st.markdown("".join(f'<span class="kw-chip">#{k}</span>' for k in kws),
                unsafe_allow_html=True)


# ── 사이드바 ─────────────────────────────────────────
with st.sidebar:
    st.markdown("### ✍️ 네이버 블로그 자동화")
    st.markdown("---")

    # 항상 보이는 홈 버튼
    if st.button("🏠 처음으로 (초기화)", use_container_width=True):
        reset()
        st.rerun()

    st.markdown("---")

    # 입력 폼 (step 0일 때만 활성화)
    disabled = st.session_state.step > 0

    keyword = st.text_input(
        "🎯 메인 키워드",
        value=st.session_state.keyword,
        placeholder="예) 에어프라이어 추천",
        disabled=disabled,
    )
    brand_url = st.text_input(
        "🔗 Brand Connect URL",
        value=st.session_state.brand_url,
        placeholder="https://brandc.naver.com/...",
        disabled=disabled,
    )
    category = st.selectbox(
        "📂 카테고리",
        options=list(CATEGORIES.keys()),
        format_func=lambda x: CATEGORIES[x],
        index=list(CATEGORIES.keys()).index(st.session_state.category),
        disabled=disabled,
    )
    post_type = st.selectbox(
        "✍️ 글 유형",
        options=list(POST_TYPES.keys()),
        format_func=lambda x: {
            "review":  "📝 리뷰형 — 솔직 사용 후기",
            "compare": "⚖️ 비교형 — 제품 비교 분석",
            "info":    "💡 정보전달형 — 구매 전 핵심 정보",
            "howto":   "🛠️ 활용법형 — 사용 팁 & 노하우",
        }[x],
        index=list(POST_TYPES.keys()).index(st.session_state.post_type),
        disabled=disabled,
    )

    st.markdown("---")

    if st.session_state.step == 0:
        can_go = bool(keyword and brand_url)
        if st.button("🔍 제품 정보 수집하기", type="primary",
                     use_container_width=True, disabled=not can_go):
            st.session_state.keyword  = keyword
            st.session_state.brand_url = brand_url
            st.session_state.category  = category
            st.session_state.post_type = post_type
            st.session_state.step = 1
            st.rerun()
        if not can_go:
            st.caption("키워드와 URL을 입력하면 활성화됩니다.")


# ── 메인 영역 ─────────────────────────────────────────
st.markdown('<div class="main-title">✍️ 네이버 블로그 자동화</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Brand Connect URL + 키워드 → 완성된 블로그 글 + 이미지 자동 생성</div>',
            unsafe_allow_html=True)

naver_key, naver_secret, naver_customer, anthropic_key, missing = check_env()
if missing:
    st.error(f"⚠️ .env 파일에 다음 키가 없습니다: {', '.join(missing)}")
    st.stop()

step_bar(st.session_state.step if st.session_state.step >= 0 else 0)
st.markdown("---")


# ════════════════════════════════════════════════
# STEP 0: 초기 안내 화면
# ════════════════════════════════════════════════
if st.session_state.step == 0:
    st.markdown("### 사용 방법")
    c1, c2, c3, c4 = st.columns(4)
    for col, icon, title, desc in [
        (c1, "1️⃣", "키워드 입력",       "블로그 주제 키워드를 왼쪽에 입력"),
        (c2, "2️⃣", "URL 입력",          "브랜드커넥트 제품 링크 붙여넣기"),
        (c3, "3️⃣", "제품 정보 확인",    "수집된 정보를 검토 후 수정 가능"),
        (c4, "4️⃣", "글 생성",           "버튼 하나로 완성 글 + 이미지 출력"),
    ]:
        with col:
            st.markdown(f"**{icon} {title}**")
            st.caption(desc)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📂 지원 카테고리**")
        for v in CATEGORIES.values():
            st.markdown(f"- {v}")
    with col2:
        st.markdown("**✍️ 글 유형**")
        for v in POST_TYPES.values():
            st.markdown(f"- {v}")


# ════════════════════════════════════════════════
# STEP 1: 제품 정보 수집 & 확인
# ════════════════════════════════════════════════
elif st.session_state.step == 1:
    st.markdown("### 🔍 제품 정보 수집 중...")

    if st.session_state.product_info is None:
        progress = st.progress(0)
        status   = st.empty()

        try:
            # ① 키워드 수집
            status.markdown("**1/3  🔍 연관 키워드 수집 중...**")
            progress.progress(10)
            researcher = NaverKeywordResearch(naver_key, naver_secret, naver_customer)
            raw_kws = researcher.get_related_keywords(st.session_state.keyword, top_n=30)
            st.session_state.sub_keywords = researcher.select_sub_keywords(raw_kws, count=8)

            # ② URL + 네이버 쇼핑 API 스크래핑
            status.markdown("**2/3  🛍️ 제품 정보 수집 중...**")
            progress.progress(35)
            naver_client_id     = os.getenv("NAVER_CLIENT_ID", "")
            naver_client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
            scraper = ProductScraper(naver_client_id, naver_client_secret)
            info = scraper.research_product(
                st.session_state.brand_url, st.session_state.keyword
            )

            # ③ 핵심 필드가 비어있으면 Claude가 직접 리서치
            missing_fields = not info.get("price") or not info.get("description") or not info.get("specs")
            if missing_fields:
                status.markdown("**3/4  🤖 Claude가 제품 정보 보완 중...**")
                progress.progress(55)
                generator = ContentGenerator(anthropic_key)
                claude_info = generator.research_product(
                    st.session_state.keyword,
                    st.session_state.brand_url,
                    CATEGORIES.get(st.session_state.category, st.session_state.category),
                )
                for field in ["price", "description", "rating", "review_count"]:
                    if not info.get(field) and claude_info.get(field):
                        info[field] = claude_info[field]
                if not info.get("specs") and claude_info.get("specs"):
                    info["specs"] = claude_info["specs"]
                if claude_info.get("pros"):
                    info["pros"] = claude_info["pros"]
                if claude_info.get("cons"):
                    info["cons"] = claude_info["cons"]
                if claude_info.get("key_features"):
                    info["key_features"] = claude_info["key_features"]

            st.session_state.product_info = info

            # ④ 비교형 글일 때: 실제 경쟁 제품 자동 수집
            if st.session_state.post_type == "compare":
                status.markdown("**4/4  ⚔️ 실제 경쟁 제품 조사 중...**")
                progress.progress(75)
                naver_client_id     = os.getenv("NAVER_CLIENT_ID", "")
                naver_client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
                comp_researcher = CompetitorResearcher(anthropic_key, naver_client_id, naver_client_secret)
                competitors = comp_researcher.research(
                    product_name=info.get("name", st.session_state.keyword),
                    category=CATEGORIES.get(st.session_state.category, st.session_state.category),
                    price=info.get("price", ""),
                    keyword=st.session_state.keyword,
                )
                st.session_state.competitors = competitors

            progress.progress(100)
            status.markdown("✅ **수집 완료! 아래 내용을 확인하고 수정하세요.**")

        except Exception as e:
            st.session_state.step = -1
            st.session_state.error_msg = str(e)
            st.rerun()

    info = st.session_state.product_info
    if info:
        st.success("제품 정보 수집 완료! 내용을 확인하고 수정한 뒤 글 작성을 진행하세요.")
        st.markdown("#### 📋 수집된 제품 정보")
        st.caption("잘못된 정보는 직접 수정하세요. 수정한 내용이 그대로 블로그 글에 반영됩니다.")

        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("제품명", value=info.get("name", ""))
            new_price = st.text_input("가격 (숫자만)", value=info.get("price", ""),
                                      placeholder="예) 89,000")
            new_rating = st.text_input("평점", value=info.get("rating", ""),
                                       placeholder="예) 4.7")
            new_review = st.text_input("리뷰 수", value=info.get("review_count", ""),
                                       placeholder="예) 1,234")
        with col2:
            new_desc = st.text_area("제품 설명",
                                    value=info.get("description", ""),
                                    height=160,
                                    placeholder="제품의 주요 특징, 용도, 장점 등을 입력하세요.")

        st.markdown("**스펙 정보**")
        specs = info.get("specs", {})
        if specs:
            spec_text = "\n".join(f"{k}: {v}" for k, v in specs.items())
        else:
            spec_text = ""
        new_specs_text = st.text_area(
            "스펙 (한 줄에 하나씩, 항목명: 값 형식)",
            value=spec_text,
            height=140,
            placeholder="무게: 1.2kg\n색상: 블랙\n용량: 5.5L",
        )

        # Claude 리서치 결과 (장단점/특징)
        pros = info.get("pros", [])
        cons = info.get("cons", [])
        features = info.get("key_features", [])
        if pros or cons or features:
            st.markdown("**🤖 Claude 리서치 결과**")
            c_a, c_b = st.columns(2)
            with c_a:
                if features:
                    st.markdown("**주요 특징**")
                    for f in features:
                        st.markdown(f"- {f}")
                if pros:
                    st.markdown("**장점**")
                    for p in pros:
                        st.markdown(f"- ✅ {p}")
            with c_b:
                if cons:
                    st.markdown("**주의사항 / 단점**")
                    for c in cons:
                        st.markdown(f"- ⚠️ {c}")
            st.caption("위 내용은 Claude의 지식 기반 리서치 결과입니다. 실제와 다를 수 있으니 확인 후 사용하세요.")

        # 비교형 글일 때: 경쟁 제품 표시
        if st.session_state.post_type == "compare" and st.session_state.competitors:
            st.markdown("---")
            st.markdown("#### ⚔️ 수집된 경쟁 제품")
            st.caption("아래 경쟁 제품들과의 실제 스펙 비교를 바탕으로 글이 작성됩니다.")
            for i, comp in enumerate(st.session_state.competitors, 1):
                with st.expander(f"경쟁 제품 {i}: {comp.get('name', '미확인')}  |  가격: {comp.get('price', '미확인')}원"):
                    c1, c2 = st.columns(2)
                    with c1:
                        if comp.get("image"):
                            try:
                                st.image(comp["image"], width=160)
                            except Exception:
                                pass
                        if comp.get("pros"):
                            st.markdown("**장점**")
                            for p in comp["pros"]:
                                st.markdown(f"- {p}")
                    with c2:
                        if comp.get("specs"):
                            st.markdown("**스펙**")
                            for k, v in list(comp["specs"].items())[:6]:
                                st.markdown(f"- {k}: {v}")
                        if comp.get("cons"):
                            st.markdown("**약점**")
                            for c in comp["cons"]:
                                st.markdown(f"- {c}")
        elif st.session_state.post_type == "compare" and not st.session_state.competitors:
            st.info("경쟁 제품 수집 결과가 없습니다. 글 작성은 계속 진행할 수 있습니다.")

        # 연관 키워드 미리보기
        if st.session_state.sub_keywords:
            st.markdown("**🔑 글에 포함될 서브키워드**")
            render_kw_chips(st.session_state.sub_keywords)

        st.markdown("---")
        col_a, col_b = st.columns([1, 1])
        with col_a:
            if st.button("← 다시 입력하기", use_container_width=True):
                reset()
                st.rerun()
        with col_b:
            if st.button("✅ 이 정보로 블로그 글 작성하기", type="primary",
                         use_container_width=True):
                # 수정된 내용 반영
                new_specs = {}
                for line in new_specs_text.strip().splitlines():
                    if ":" in line:
                        k, _, v = line.partition(":")
                        new_specs[k.strip()] = v.strip()

                st.session_state.product_info.update({
                    "name": new_name,
                    "price": new_price,
                    "rating": new_rating,
                    "review_count": new_review,
                    "description": new_desc,
                    "specs": new_specs,
                })
                st.session_state.step = 2
                st.rerun()


# ════════════════════════════════════════════════
# STEP 2: 글 생성 중
# ════════════════════════════════════════════════
elif st.session_state.step == 2:
    st.markdown("### ✍️ 블로그 글 생성 중...")
    progress = st.progress(0)
    status   = st.empty()

    try:
        # 이미지 다운로드
        status.markdown("**📸 제품 이미지 다운로드 중...**")
        progress.progress(20)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        safe_kw = "".join(c for c in st.session_state.keyword
                          if c.isalnum() or c in (' ', '-', '_')).strip()[:20]
        output_dir = Path(__file__).parent / "output" / f"{timestamp}_{safe_kw}"
        images_dir = output_dir / "images"
        downloader = ImageDownloader(str(images_dir))
        saved_images = downloader.download_images(
            st.session_state.product_info.get("images", []), prefix="product"
        )
        st.session_state.saved_images = saved_images
        st.session_state.output_dir   = str(output_dir)
        progress.progress(45)

        # 글 생성 (비교형이면 경쟁 제품 데이터 주입)
        status.markdown("**✍️ Claude가 블로그 글을 작성 중입니다... (30초~1분 소요)**")
        progress.progress(50)
        generator = ContentGenerator(anthropic_key)

        # 비교형: 경쟁 제품 비교 요약 텍스트 생성 후 product_info에 주입
        product_info_for_gen = dict(st.session_state.product_info)
        if st.session_state.post_type == "compare" and st.session_state.competitors:
            from modules.competitor_researcher import CompetitorResearcher
            comp_researcher = CompetitorResearcher(anthropic_key)
            comparison_summary = comp_researcher.build_comparison_summary(
                product_info_for_gen,
                st.session_state.competitors,
            )
            product_info_for_gen["comparison_data"] = comparison_summary

        post = generator.generate_blog_post(
            category=st.session_state.category,
            post_type=st.session_state.post_type,
            keyword=st.session_state.keyword,
            sub_keywords=st.session_state.sub_keywords,
            product_info=product_info_for_gen,
            brand_connect_url=st.session_state.brand_url,
        )
        st.session_state.post_content = post
        progress.progress(90)

        # 파일 저장
        output_dir.mkdir(parents=True, exist_ok=True)
        image_guide = downloader.generate_image_guide(saved_images)
        with open(output_dir / "blog_post.txt", "w", encoding="utf-8") as f:
            f.write(post)
            if image_guide:
                f.write("\n\n" + image_guide)

        progress.progress(100)
        st.session_state.step = 3
        st.rerun()

    except Exception as e:
        st.session_state.step = -1
        st.session_state.error_msg = str(e)
        st.rerun()


# ════════════════════════════════════════════════
# STEP 3: 결과 화면
# ════════════════════════════════════════════════
elif st.session_state.step == 3:
    post    = st.session_state.post_content
    images  = st.session_state.saved_images
    info    = st.session_state.product_info or {}

    # 통계 카드
    c1, c2, c3, c4 = st.columns(4)
    for col, num, lbl in [
        (c1, len(st.session_state.sub_keywords), "서브키워드"),
        (c2, info.get("name", "-")[:6] + "…" if len(info.get("name",""))>6 else info.get("name","-"), "제품"),
        (c3, len(images), "저장된 이미지"),
        (c4, f"{len(post):,}", "글자수"),
    ]:
        with col:
            st.markdown(
                f'<div class="stat-card"><div class="stat-num">{num}</div>'
                f'<div class="stat-lbl">{lbl}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📄 완성된 글", "🔑 수집된 키워드", "🖼️ 이미지"])

    # ── 탭1: 완성 글 ──────────────────────────
    with tab1:
        st.markdown(
            f'<div class="post-box">{post}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        dl_col, _, re_col = st.columns([1, 0.2, 1])
        with dl_col:
            st.download_button(
                "💾 파일로 저장 (.txt)",
                data=post.encode("utf-8"),
                file_name=f"blog_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with re_col:
            if st.button("🔄 글 다시 생성하기", use_container_width=True):
                st.session_state.post_content = None
                st.session_state.step = 2
                st.rerun()

        st.markdown("---")
        st.markdown("#### ✏️ 수정 요청")
        feedback = st.text_area(
            "수정하고 싶은 내용을 구체적으로 입력하세요",
            placeholder="예) 말투를 더 친근하게 바꿔줘 / 가격 정보를 더 강조해줘 / 마지막 단락을 더 자연스럽게",
        )
        if st.button("🔄 수정 반영하기", type="secondary") and feedback:
            with st.spinner("수정 중..."):
                try:
                    gen = ContentGenerator(anthropic_key)
                    st.session_state.post_content = gen.refine_post(post, feedback)
                    out = Path(st.session_state.output_dir) / "blog_post.txt"
                    with open(out, "w", encoding="utf-8") as f:
                        f.write(st.session_state.post_content)
                    st.success("수정 완료!")
                    st.rerun()
                except Exception as e:
                    st.error(f"수정 실패: {e}")

    # ── 탭2: 키워드 ────────────────────────────
    with tab2:
        if st.session_state.sub_keywords:
            st.markdown("#### 글에 포함된 서브키워드")
            render_kw_chips(st.session_state.sub_keywords)
        else:
            st.info("수집된 서브키워드가 없습니다.")

    # ── 탭3: 이미지 ────────────────────────────
    with tab3:
        if images:
            st.caption(f"저장 위치: `{st.session_state.output_dir}/images/`")
            cols = st.columns(min(len(images), 3))
            for i, img_path in enumerate(images):
                with cols[i % 3]:
                    try:
                        st.image(img_path, caption=f"이미지 {i+1}", use_container_width=True)
                    except Exception:
                        st.warning(f"이미지 {i+1} 미리보기 불가")
        else:
            st.info("다운로드된 이미지가 없습니다. 직접 제품 이미지를 추가해주세요.")

    st.markdown("---")
    if st.button("🏠 새 글 작성하기 (처음으로)", type="primary"):
        reset()
        st.rerun()


# ════════════════════════════════════════════════
# STEP -1: 오류 화면
# ════════════════════════════════════════════════
elif st.session_state.step == -1:
    st.markdown(
        f"""
        <div class="err-box">
            <h2>⚠️ 오류가 발생했습니다</h2>
            <p style="color:#888; font-size:0.9rem">{st.session_state.error_msg}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏠 처음으로 돌아가기", type="primary", use_container_width=True):
            reset()
            st.rerun()
    with col2:
        if st.button("↩️ 제품 정보 단계로", use_container_width=True):
            st.session_state.step = 1
            st.session_state.error_msg = ""
            st.rerun()
