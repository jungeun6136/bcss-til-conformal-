import streamlit as st
import streamlit.components.v1 as components
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
from modules.html_formatter import to_naver_html
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
    .main-title { font-size:1.7rem; font-weight:800; color:#03C75A; margin:0 0 2px; }
    .sub-title  { font-size:0.88rem; color:#888; margin:0 0 8px; }
    .step-bar   { display:flex; align-items:center; gap:8px; margin:8px 0; }
    .step-dot   { width:26px; height:26px; border-radius:50%; background:#e0e0e0;
                  color:#999; display:flex; align-items:center; justify-content:center;
                  font-weight:700; font-size:0.78rem; flex-shrink:0; }
    .step-dot.active  { background:#03C75A; color:white; }
    .step-dot.done    { background:#b2dfdb; color:#00796b; }
    .step-line  { flex:1; height:2px; background:#e0e0e0; }
    .step-line.done { background:#b2dfdb; }
    .kw-chip    { display:inline-block; background:#f0faf4; border:1px solid #03C75A;
                  color:#03C75A; padding:3px 12px; border-radius:20px;
                  margin:3px; font-size:0.82rem; }
    .post-box   { background:#fafafa; border:1px solid #e0e0e0; border-radius:10px;
                  padding:1.2rem; white-space:pre-wrap; font-size:0.92rem;
                  line-height:1.8; max-height:580px; overflow-y:auto; }
    .stat-card  { background:white; border:1px solid #eee; border-radius:10px;
                  padding:0.75rem; text-align:center; }
    .stat-num   { font-size:1.5rem; font-weight:800; color:#03C75A; }
    .stat-lbl   { font-size:0.75rem; color:#888; }
    .info-block { background:#f8f8f8; border-left:4px solid #03C75A;
                  padding:0.6rem 0.8rem; border-radius:4px; margin:4px 0; }
    .err-box    { background:#fff3f3; border:1px solid #ffcdd2; border-radius:10px;
                  padding:1.2rem; text-align:center; }
    /* 전역 여백 축소 */
    .block-container { padding-top:1rem !important; padding-bottom:1rem !important; }
    section[data-testid="stSidebar"] .block-container { padding-top:0.5rem !important; }
    div[data-testid="stVerticalBlock"] > div { gap:0.3rem; }
    hr { margin:0.5rem 0 !important; }
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
    "post_html": None,
    "saved_images": [],
    "output_dir": None,
    "error_msg": "",
    # 검색 UI 상태
    "search_results": [],
    "search_query": "",
    "comp_sr_0": [],   # 경쟁제품1 검색결과
    "comp_sr_1": [],   # 경쟁제품2 검색결과
    "comp_sq_0": "",   # 경쟁제품1 검색어
    "comp_sq_1": "",   # 경쟁제품2 검색어
    "comp_sel_0": None,  # 경쟁제품1 선택값
    "comp_sel_1": None,  # 경쟁제품2 선택값
    "kw_researched": False,
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


def render_product_cards(results: list, key_prefix: str, sel_key: str):
    """상품 목록을 카드 그리드로 표시. 선택 시 session_state[sel_key]에 저장."""
    COLS = 4
    sel = st.session_state.get(sel_key)

    for row_start in range(0, len(results), COLS):
        chunk = results[row_start: row_start + COLS]
        cols = st.columns(len(chunk))
        for col, product in zip(cols, chunk):
            idx = results.index(product)
            with col:
                is_sel = bool(
                    sel
                    and sel.get("price") == product.get("price")
                    and sel.get("name") == product.get("name")
                )
                border = "#03C75A" if is_sel else "#e0e0e0"
                bg = "#f0faf4" if is_sel else "#ffffff"

                # 이미지
                image = product.get("image", "")
                if image:
                    try:
                        st.image(image, use_container_width=True)
                    except Exception:
                        st.markdown('<div style="height:80px;background:#f5f5f5;border-radius:6px;"></div>',
                                    unsafe_allow_html=True)
                else:
                    st.markdown('<div style="height:80px;background:#f5f5f5;border-radius:6px;"></div>',
                                unsafe_allow_html=True)

                name = product.get("name", "")
                short = (name[:26] + "…") if len(name) > 26 else name
                price = product.get("price", "")
                rt = product.get("rating", "")
                rc = product.get("review_count", "")
                brand = product.get("brand", "") or product.get("mall_name", "")

                st.markdown(
                    f'<div style="border:2px solid {border};background:{bg};border-radius:8px;'
                    f'padding:8px;margin:2px 0;">'
                    f'<div style="font-size:0.78rem;font-weight:600;min-height:2.2em;line-height:1.3;color:#1a1a1a;">{short}</div>'
                    + (f'<div style="font-size:0.7rem;color:#888;margin-top:2px;">{brand}</div>' if brand else '')
                    + (f'<div style="color:#e53935;font-size:1rem;font-weight:800;margin:4px 0;">{price}원</div>' if price else '')
                    + (f'<div style="font-size:0.7rem;color:#666;">⭐{rt}' + (f' · {rc}개' if rc else '') + '</div>' if rt or rc else '')
                    + '</div>',
                    unsafe_allow_html=True,
                )

                btn_label = "✅ 선택됨" if is_sel else "선택"
                if st.button(btn_label, key=f"{key_prefix}_{idx}",
                             use_container_width=True,
                             type="primary" if is_sel else "secondary"):
                    st.session_state[sel_key] = dict(product)
                    st.rerun()


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
        if st.button("➡️ 제품 검색 시작", type="primary",
                     use_container_width=True, disabled=not can_go):
            st.session_state.keyword   = keyword
            st.session_state.brand_url = brand_url
            st.session_state.category  = category
            st.session_state.post_type = post_type
            st.session_state.search_query = keyword
            st.session_state.comp_sq_0 = ""
            st.session_state.comp_sq_1 = ""
            st.session_state.kw_researched = False
            st.session_state.step = 1
            st.rerun()
        if not can_go:
            st.caption("키워드와 URL을 입력하면 활성화됩니다.")


# ── 메인 영역 ─────────────────────────────────────────
st.markdown('<div class="main-title">✍️ 네이버 블로그 자동화</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Brand Connect URL + 키워드 → 완성된 블로그 글 + 이미지 자동 생성</div>', unsafe_allow_html=True)

naver_key, naver_secret, naver_customer, anthropic_key, missing = check_env()
if missing:
    st.error(f"⚠️ .env 파일에 다음 키가 없습니다: {', '.join(missing)}")
    st.stop()

step_bar(st.session_state.step if st.session_state.step >= 0 else 0)
st.divider()


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

    st.divider()
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
# STEP 1: 제품 검색 & 선택
# ════════════════════════════════════════════════
elif st.session_state.step == 1:
    st.markdown("### 🛍️ 제품 검색 & 선택")

    naver_cid = os.getenv("NAVER_CLIENT_ID", "")
    naver_csec = os.getenv("NAVER_CLIENT_SECRET", "")
    scraper = ProductScraper(naver_cid, naver_csec)

    # ── 키워드 리서치 (최초 1회) ──────────────────────────
    if not st.session_state.kw_researched:
        with st.spinner("🔑 연관 키워드 수집 중..."):
            try:
                researcher = NaverKeywordResearch(naver_key, naver_secret, naver_customer)
                raw_kws = researcher.get_related_keywords(st.session_state.keyword, top_n=30)
                st.session_state.sub_keywords = researcher.select_sub_keywords(raw_kws, count=8)
            except Exception:
                st.session_state.sub_keywords = []
        st.session_state.kw_researched = True
        st.rerun()

    # ── 메인 제품 검색 ────────────────────────────────────
    st.markdown("#### 1. 메인 제품 선택")
    st.caption("제품명을 검색해서 카드를 클릭하면 정확한 최저가가 바로 적용됩니다.")

    cq, cb = st.columns([5, 1])
    with cq:
        mq = st.text_input(
            "검색어", label_visibility="collapsed",
            value=st.session_state.search_query or st.session_state.keyword,
            placeholder="예) 삼성 에어프라이어 5.5L",
            key="main_q",
        )
    with cb:
        if st.button("🔍 검색", key="main_search", use_container_width=True):
            with st.spinner("검색 중..."):
                st.session_state.search_results = scraper.search_products(mq, top_n=8)
                st.session_state.search_query = mq
                st.session_state.product_info = None  # 검색어 바뀌면 선택 초기화
            st.rerun()

    if st.session_state.search_results:
        cnt = len(st.session_state.search_results)
        st.markdown(f"**검색 결과 {cnt}개** (가격 낮은 순 · 클릭해서 선택)")
        render_product_cards(st.session_state.search_results, "main", "product_info")

    info = st.session_state.product_info
    if info:
        st.success(
            f"✅ 선택됨: **{info.get('name', '')}**  |  "
            f"최저가: **{info.get('price', '')}원**"
            + (f"  |  ⭐{info.get('rating', '')} ({info.get('review_count', '')}개)" if info.get("rating") else "")
        )

        with st.expander("✏️ 제품 정보 수정 (필요 시)", expanded=False):
            ec1, ec2 = st.columns(2)
            with ec1:
                info["name"]         = st.text_input("제품명", value=info.get("name", ""), key="edit_name")
                info["price"]        = st.text_input("최저가 (원)", value=info.get("price", ""), key="edit_price")
                info["rating"]       = st.text_input("평점", value=info.get("rating", ""), key="edit_rt", placeholder="예) 4.7")
                info["review_count"] = st.text_input("리뷰 수", value=info.get("review_count", ""), key="edit_rc", placeholder="예) 1,234")
            with ec2:
                info["description"] = st.text_area("제품 설명", value=info.get("description", ""), height=150, key="edit_desc")
            st.markdown("**스펙 정보** (항목명: 값 형식으로 한 줄씩)")
            spec_str = "\n".join(f"{k}: {v}" for k, v in info.get("specs", {}).items())
            new_spec_str = st.text_area("스펙", value=spec_str, height=120, key="edit_specs", label_visibility="collapsed")
            new_specs = {}
            for ln in new_spec_str.strip().splitlines():
                if ":" in ln:
                    k, _, v = ln.partition(":")
                    if k.strip() and v.strip():
                        new_specs[k.strip()] = v.strip()
            info["specs"] = new_specs

    # ── 경쟁 제품 검색 (비교형만) ─────────────────────────
    if st.session_state.post_type == "compare":
        st.divider()
        st.markdown("#### 2. 경쟁 제품 선택 (비교형)")
        st.caption("비교할 경쟁 제품을 검색해서 선택하세요. 최대 2개까지 선택 가능합니다.")

        for ci in range(2):
            sr_key  = f"comp_sr_{ci}"
            sq_key  = f"comp_sq_{ci}"
            sel_key = f"comp_sel_{ci}"
            label   = f"경쟁 제품 {ci + 1}"

            st.markdown(f"**{label}**")
            cq2, cb2 = st.columns([5, 1])
            with cq2:
                cq_val = st.text_input(
                    label, label_visibility="collapsed",
                    value=st.session_state.get(sq_key, ""),
                    placeholder="예) LG 에어프라이어 6L",
                    key=f"comp_q_{ci}",
                )
            with cb2:
                if st.button("🔍 검색", key=f"comp_btn_{ci}", use_container_width=True):
                    with st.spinner(f"{label} 검색 중..."):
                        st.session_state[sr_key]  = scraper.search_products(cq_val, top_n=8)
                        st.session_state[sq_key]  = cq_val
                        st.session_state[sel_key] = None
                    st.rerun()

            comp_results = st.session_state.get(sr_key, [])
            if comp_results:
                render_product_cards(comp_results, f"c{ci}", sel_key)

            sel = st.session_state.get(sel_key)
            if sel:
                st.success(
                    f"✅ {label} 선택됨: **{sel.get('name', '')}**  |  "
                    f"최저가: **{sel.get('price', '')}원**"
                    + (f"  |  ⭐{sel.get('rating', '')} ({sel.get('review_count', '')}개)" if sel.get("rating") else "")
                )

    # ── 서브키워드 ────────────────────────────────────────
    if st.session_state.sub_keywords:
        st.divider()
        st.markdown("**🔑 글에 포함될 서브키워드**")
        render_kw_chips(st.session_state.sub_keywords)

    # ── 하단 버튼 ─────────────────────────────────────────
    st.divider()
    col_back, col_next = st.columns([1, 2])
    with col_back:
        if st.button("← 처음으로", use_container_width=True):
            reset()
            st.rerun()
    with col_next:
        can_proceed = st.session_state.product_info is not None
        if st.button(
            "✅ 이 정보로 블로그 글 작성하기",
            type="primary",
            use_container_width=True,
            disabled=not can_proceed,
        ):
            # 경쟁제품 조합
            if st.session_state.post_type == "compare":
                comps = []
                for ci in range(2):
                    sel = st.session_state.get(f"comp_sel_{ci}")
                    if sel:
                        comps.append(dict(sel))
                st.session_state.competitors = comps
            st.session_state.step = 2
            st.rerun()
        if not can_proceed:
            st.caption("위에서 메인 제품을 먼저 선택해주세요.")


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

        # HTML 변환
        html_code = to_naver_html(post)
        st.session_state.post_html = html_code
        progress.progress(90)

        # 파일 저장
        output_dir.mkdir(parents=True, exist_ok=True)
        image_guide = downloader.generate_image_guide(saved_images)
        with open(output_dir / "blog_post.txt", "w", encoding="utf-8") as f:
            f.write(post)
            if image_guide:
                f.write("\n\n" + image_guide)
        with open(output_dir / "blog_post.html", "w", encoding="utf-8") as f:
            f.write(html_code)

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
    post      = st.session_state.post_content
    html_code = st.session_state.post_html or to_naver_html(post)
    images    = st.session_state.saved_images
    info      = st.session_state.product_info or {}

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

    tab1, tab2, tab3, tab4 = st.tabs(["📄 완성된 글", "🌐 HTML 코드", "🔑 서브키워드", "🖼️ 이미지"])

    # ── 탭1: 완성 글 ──────────────────────────
    with tab1:
        st.markdown(
            f'<div class="post-box">{post}</div>',
            unsafe_allow_html=True,
        )
        st.caption("아래 텍스트 박스의 오른쪽 상단 복사 아이콘을 클릭하면 전체 복사됩니다.")
        st.code(post, language="")

        col_dl, col_regen = st.columns(2)
        with col_dl:
            st.download_button(
                "💾 .txt 파일로 저장",
                data=post.encode("utf-8"),
                file_name=f"blog_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col_regen:
            if st.button("🔄 글 다시 생성하기", use_container_width=True):
                st.session_state.post_content = None
                st.session_state.post_html = None
                st.session_state.step = 2
                st.rerun()

        st.divider()
        st.markdown("#### ✏️ 수정 요청")
        feedback = st.text_area(
            "수정하고 싶은 내용을 구체적으로 입력하세요",
            placeholder="예) 말투를 더 친근하게 바꿔줘 / 가격 정보를 더 강조해줘 / 마지막 단락을 더 자연스럽게",
        )
        if st.button("🔄 수정 반영하기", type="secondary") and feedback:
            with st.spinner("수정 중..."):
                try:
                    gen = ContentGenerator(anthropic_key)
                    new_post = gen.refine_post(post, feedback)
                    st.session_state.post_content = new_post
                    st.session_state.post_html = to_naver_html(new_post)
                    out = Path(st.session_state.output_dir) / "blog_post.txt"
                    with open(out, "w", encoding="utf-8") as f:
                        f.write(new_post)
                    with open(Path(st.session_state.output_dir) / "blog_post.html", "w", encoding="utf-8") as f:
                        f.write(st.session_state.post_html)
                    st.success("수정 완료!")
                    st.rerun()
                except Exception as e:
                    st.error(f"수정 실패: {e}")

    # ── 탭2: HTML 코드 ─────────────────────────
    with tab2:
        st.caption("아래 HTML을 복사해서 네이버 블로그 에디터의 'HTML 편집' 모드에 붙여넣으세요.")
        st.info("코드 박스 오른쪽 상단의 복사 아이콘을 클릭하면 전체 복사됩니다.", icon="💡")
        st.code(html_code, language="html")
        st.download_button(
            "💾 .html 파일로 저장",
            data=html_code.encode("utf-8"),
            file_name=f"blog_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
            mime="text/html",
            use_container_width=True,
        )
        with st.expander("🔍 HTML 미리보기"):
            components.html(html_code, height=600, scrolling=True)

    # ── 탭3: 키워드 ────────────────────────────
    with tab3:
        if st.session_state.sub_keywords:
            st.markdown("#### 글에 포함된 서브키워드")
            render_kw_chips(st.session_state.sub_keywords)
        else:
            st.info("수집된 서브키워드가 없습니다.")

    # ── 탭4: 이미지 ────────────────────────────
    with tab4:
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

    st.divider()
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
