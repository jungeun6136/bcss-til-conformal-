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
from modules.blog_analyzer import BlogAnalyzer
from modules.blog_poster import NaverBlogPoster
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
/* ═══ 전역 배경 ═══════════════════════════════════════════ */
.stApp { background: #f0f4f8; }
.main .block-container { background: transparent; }

/* ═══ 다크 사이드바 ════════════════════════════════════════ */
section[data-testid="stSidebar"] > div:first-child { background: #0d1b2a !important; }
section[data-testid="stSidebar"] label { color: #8fafc8 !important; font-size: 0.75rem !important; font-weight: 600 !important; letter-spacing: 0.5px !important; }
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span { color: #c8dcea !important; }
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 { color: #e8f4fd !important; }
section[data-testid="stSidebar"] input { background: #152334 !important; color: #e8f4fd !important; border: 1px solid #1e3550 !important; border-radius: 8px !important; }
section[data-testid="stSidebar"] input:focus { border-color: #03C75A !important; box-shadow: 0 0 0 2px rgba(3,199,90,0.2) !important; }
section[data-testid="stSidebar"] .stSelectbox > div > div { background: #152334 !important; border: 1px solid #1e3550 !important; color: #e8f4fd !important; border-radius: 8px !important; }
section[data-testid="stSidebar"] hr { border-color: #1e3550 !important; }
section[data-testid="stSidebar"] .stButton > button { border-radius: 10px !important; }

/* ═══ 타이포 ═══════════════════════════════════════════════ */
.main-title { font-size:1.75rem; font-weight:900; background:linear-gradient(90deg,#03C75A,#00BCD4); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; margin:0 0 2px; letter-spacing:-0.5px; }
.sub-title  { font-size:0.85rem; color:#6b7c93; margin:0 0 8px; font-weight:500; }

/* ═══ 스텝바 ═══════════════════════════════════════════════ */
.step-bar { display:flex; align-items:center; gap:6px; margin:12px 0 4px; }
.step-wrap { display:flex; flex-direction:column; align-items:center; gap:5px; }
.step-dot { width:34px; height:34px; border-radius:50%; background:#e4eaf0; color:#a0adb8; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:0.78rem; flex-shrink:0; transition:all 0.35s cubic-bezier(0.34,1.56,0.64,1); box-shadow:0 2px 8px rgba(0,0,0,0.06); }
.step-dot.active { background:linear-gradient(135deg,#03C75A,#00BCD4); color:white; box-shadow:0 4px 18px rgba(3,199,90,0.4); animation:pulse-step 2.2s ease-in-out infinite; }
.step-dot.done { background:linear-gradient(135deg,#b2f0da,#80deea); color:#006644; }
.step-lbl { font-size:0.68rem; font-weight:600; white-space:nowrap; color:#a0adb8; transition:color 0.3s; }
.step-lbl.active { color:#03C75A; }
.step-lbl.done { color:#00a86b; }
.step-line { flex:1; height:3px; background:#e4eaf0; border-radius:3px; margin-bottom:22px; }
.step-line.done { background:linear-gradient(90deg,#03C75A,#00BCD4); }
@keyframes pulse-step { 0%,100%{box-shadow:0 4px 18px rgba(3,199,90,0.4);} 50%{box-shadow:0 4px 28px rgba(3,199,90,0.65),0 0 0 7px rgba(3,199,90,0.1);} }

/* ═══ 제품 카드 ════════════════════════════════════════════ */
.pcard { border-radius:18px; background:white; box-shadow:0 2px 14px rgba(0,0,0,0.07); overflow:hidden; transition:all 0.22s cubic-bezier(0.25,0.8,0.25,1); cursor:pointer; position:relative; border:2px solid transparent; margin-bottom:4px; }
.pcard:hover { transform:translateY(-5px); box-shadow:0 14px 36px rgba(0,0,0,0.13); }
.pcard.pcard-sel { border-color:#03C75A; box-shadow:0 0 0 4px rgba(3,199,90,0.12),0 10px 30px rgba(3,199,90,0.2); }
.pcard-img-wrap { position:relative; overflow:hidden; }
.pcard-img-wrap img { width:100%; height:130px; object-fit:cover; display:block; transition:transform 0.3s ease; }
.pcard:hover .pcard-img-wrap img { transform:scale(1.05); }
.pcard-img-placeholder { height:130px; background:linear-gradient(135deg,#f0f4f8,#e4eaf0); display:flex; align-items:center; justify-content:center; font-size:2rem; color:#c0ccd8; }
.pcard-price-overlay { position:absolute; bottom:0; left:0; right:0; background:linear-gradient(0deg,rgba(10,20,35,0.82) 0%,transparent 100%); padding:22px 10px 8px; }
.pcard-price-overlay span { color:white; font-size:1rem; font-weight:800; text-shadow:0 1px 4px rgba(0,0,0,0.4); }
.pcard-check { position:absolute; top:9px; right:9px; width:28px; height:28px; background:linear-gradient(135deg,#03C75A,#00BCD4); border-radius:50%; display:flex; align-items:center; justify-content:center; color:white; font-size:13px; font-weight:900; box-shadow:0 3px 10px rgba(3,199,90,0.5); animation:pop-in 0.25s cubic-bezier(0.34,1.56,0.64,1); }
@keyframes pop-in { from{transform:scale(0);opacity:0;} to{transform:scale(1);opacity:1;} }
.pcard-body { padding:10px 10px 8px; }
.pcard-name { font-size:0.77rem; font-weight:600; line-height:1.38; color:#1a2840; min-height:2.4em; }
.pcard-brand { font-size:0.68rem; color:#8fafc8; margin-top:3px; font-weight:500; }
.pcard-rating { font-size:0.69rem; color:#6b7c93; margin-top:5px; }

/* ═══ 키워드 칩 ════════════════════════════════════════════ */
.kw-chip { display:inline-block; background:linear-gradient(135deg,#edfaf3,#e4f7f5); border:1px solid rgba(3,199,90,0.4); color:#047a42; padding:5px 14px; border-radius:20px; margin:3px; font-size:0.81rem; font-weight:600; box-shadow:0 1px 4px rgba(3,199,90,0.12); }

/* ═══ 스코어바 ════════════════════════════════════════════ */
.sbar-wrap { background:#e8edf2; border-radius:6px; overflow:hidden; height:7px; margin-top:4px; }
.sbar-fill { height:7px; border-radius:6px; background:linear-gradient(90deg,#03C75A,#00BCD4); }
.comp-badge { display:inline-block; padding:2px 8px; border-radius:12px; font-size:0.68rem; font-weight:700; }
.comp-low  { background:#e8f8f0; color:#1b7a42; }
.comp-mid  { background:#fff3e0; color:#c05c00; }
.comp-high { background:#fdecea; color:#c12020; }
.blog-fire { color:#ff6b35; font-weight:700; font-size:0.78rem; }

/* ═══ 통계 카드 ════════════════════════════════════════════ */
.stat-card { background:white; border:none; border-radius:18px; padding:1rem; text-align:center; box-shadow:0 3px 16px rgba(0,0,0,0.08); }
.stat-num  { font-size:1.5rem; font-weight:900; background:linear-gradient(135deg,#03C75A,#00BCD4); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.stat-lbl  { font-size:0.72rem; color:#8fafc8; margin-top:2px; font-weight:600; }

/* ═══ 포스트 박스 ══════════════════════════════════════════ */
.post-box { background:white; border:1px solid #e4eaf0; border-radius:18px; padding:1.4rem 1.6rem; white-space:pre-wrap; font-size:0.92rem; line-height:1.9; max-height:580px; overflow-y:auto; box-shadow:0 3px 16px rgba(0,0,0,0.05); }

/* ═══ 메인 키워드 배지 ════════════════════════════════════ */
.kw-meta-card { background:linear-gradient(135deg,#f0fdf6,#e8f9f7); border:1px solid rgba(3,199,90,0.3); border-radius:14px; padding:12px 16px; margin-bottom:10px; box-shadow:0 2px 10px rgba(3,199,90,0.1); }

/* ═══ 기타 ════════════════════════════════════════════════ */
.info-block { background:#f0faf5; border-left:4px solid #03C75A; padding:0.6rem 0.9rem; border-radius:6px; margin:4px 0; }
.err-box { background:#fff3f3; border:1px solid #f5c6c6; border-radius:18px; padding:1.4rem; text-align:center; }
.block-container { padding-top:2rem !important; padding-bottom:1rem !important; }
section[data-testid="stSidebar"] .block-container { padding-top:0 !important; }
div[data-testid="stVerticalBlock"] > div { gap:0.28rem; }
hr { margin:0.6rem 0 !important; border-color:#e4eaf0 !important; }
.home-cta > div > button { font-size:1.05rem !important; height:3rem !important; }
.type-tile { border-radius:20px; padding:20px 8px; text-align:center; cursor:pointer; transition:all 0.2s cubic-bezier(0.25,0.8,0.25,1); background:white; box-shadow:0 3px 14px rgba(0,0,0,0.07); }
.type-tile:hover { transform:translateY(-4px); box-shadow:0 10px 30px rgba(0,0,0,0.12); }
</style>
""", unsafe_allow_html=True)


# ── 세션 상태 초기화 ─────────────────────────────────
DEFAULTS = {
    "page": "home",      # "home"=랜딩 "tool"=도구
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
    # 키워드 스코어 & 블로그 분석
    "kw_scored": [],       # [{keyword, total, competition, score, blog_count}, ...]
    "kw_main_meta": {},    # 메인 키워드 메타 (total, competition, score)
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
        dot_cls  = "done" if i < current else ("active" if i == current else "")
        lbl_cls  = "done" if i < current else ("active" if i == current else "")
        icon     = "✓" if i < current else str(i + 1)
        html += (
            f'<div class="step-wrap">'
            f'<div class="step-dot {dot_cls}">{icon}</div>'
            f'<span class="step-lbl {lbl_cls}">{label}</span>'
            f'</div>'
        )
        if i < len(labels) - 1:
            line_cls = "done" if i < current else ""
            html += f'<div class="step-line {line_cls}"></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def show_tool_header():
    st.markdown('<div class="main-title">✍️ 네이버 블로그 자동화</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Brand Connect URL + 키워드 → 완성된 블로그 글 + 이미지 자동 생성</div>',
        unsafe_allow_html=True,
    )
    step_bar(st.session_state.step if st.session_state.step >= 0 else 0)
    st.divider()


def render_kw_chips(kws):
    st.markdown("".join(f'<span class="kw-chip">#{k}</span>' for k in kws),
                unsafe_allow_html=True)


def suggest_competitor_queries(api_key: str, keyword: str, product_name: str) -> list:
    """Claude Haiku로 경쟁 제품 검색어 2개 자동 생성"""
    try:
        import anthropic, json, re
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{"role": "user", "content":
                f"제품명: {product_name}\n키워드: {keyword}\n\n"
                "이 제품과 경쟁하는 다른 브랜드의 유사 제품 네이버 검색어 2개를 "
                "JSON 배열로만 출력하세요. 예: [\"LG 인덕션 추천\", \"쿠쿠 인덕션\"]"}]
        )
        m = re.search(r'\[.*?\]', msg.content[0].text, re.DOTALL)
        return json.loads(m.group()) if m else []
    except Exception:
        return []


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
                name  = product.get("name", "")
                short = (name[:28] + "…") if len(name) > 28 else name
                price = product.get("price", "")
                rt    = product.get("rating", "")
                rc    = product.get("review_count", "")
                brand = product.get("brand", "") or product.get("mall_name", "")
                img   = product.get("image", "")

                card_cls = "pcard pcard-sel" if is_sel else "pcard"
                check_html = '<div class="pcard-check">✓</div>' if is_sel else ""

                if img:
                    img_html = (
                        f'<div class="pcard-img-wrap">'
                        f'<img src="{img}" onerror="this.parentNode.innerHTML=\'<div class=pcard-img-placeholder>🛍️</div>\'">'
                        + (f'<div class="pcard-price-overlay"><span>{price}원</span></div>' if price else "")
                        + f'</div>'
                    )
                else:
                    img_html = (
                        f'<div class="pcard-img-placeholder">🛍️</div>'
                        + (f'<div style="padding:4px 10px 0;color:#e53935;font-size:0.95rem;font-weight:800;">{price}원</div>' if price else "")
                    )

                st.markdown(
                    f'<div class="{card_cls}">'
                    + check_html
                    + img_html
                    + f'<div class="pcard-body">'
                    + f'<div class="pcard-name">{short}</div>'
                    + (f'<div class="pcard-brand">{brand}</div>' if brand else "")
                    + (f'<div class="pcard-rating">⭐ {rt}' + (f' <span style="color:#c0ccd8;">· {rc}개</span>' if rc else "") + "</div>" if rt or rc else "")
                    + "</div></div>",
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
    if st.session_state.page == "home":
        # ── 랜딩 페이지 사이드바 (최소화) ──────────────
        st.markdown(
            '<div style="text-align:center;padding:24px 8px 16px;">'
            '<div style="font-size:2.4rem;">✍️</div>'
            '<div style="font-size:1.05rem;font-weight:800;color:#03C75A;margin:10px 0 6px;">'
            '네이버 블로그 자동화</div>'
            '<div style="font-size:.74rem;color:#aaa;line-height:1.6;">'
            'AI가 만드는 SEO 최적화<br>블로그 글 자동 생성</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.divider()
        if st.button("✍️ 글 작성 시작하기", type="primary", use_container_width=True):
            st.session_state.page = "tool"
            st.rerun()
        st.caption("글 유형을 먼저 선택한 후 시작하세요.")

    else:
        # ── 도구 페이지 사이드바 ─────────────────────
        st.markdown("### ✍️ 네이버 블로그 자동화")
        st.markdown("---")

        if st.button("🏠 홈으로 돌아가기", use_container_width=True):
            reset()
            st.rerun()

        st.markdown("---")

        disabled = st.session_state.step > 0

        brand_url = st.text_input(
            "🔗 Brand Connect URL",
            value=st.session_state.brand_url,
            placeholder="https://brand.naver.com/...",
            disabled=disabled,
        )

        # 메인 키워드는 URL에서 자동 추출 후 표시 (읽기 전용)
        if st.session_state.keyword and disabled:
            _m = st.session_state.get("kw_main_meta", {})
            _tot = _m.get("total", 0)
            _sc  = _m.get("score", 0)
            st.markdown(
                f'<div style="background:linear-gradient(135deg,rgba(3,199,90,0.12),rgba(0,188,212,0.08));'
                f'border:1px solid rgba(3,199,90,0.35);border-radius:10px;'
                f'padding:10px 12px;margin-bottom:8px;">'
                f'<div style="font-size:0.66rem;color:#5aaa7a;font-weight:700;letter-spacing:0.4px;margin-bottom:3px;">🎯 메인 키워드</div>'
                f'<div style="font-size:0.9rem;font-weight:800;color:#e8f8f0;">{st.session_state.keyword}</div>'
                + (f'<div style="font-size:0.68rem;color:#7abf9a;margin-top:3px;">📊 {_tot:,}회/월'
                   + (f' · 점수 {_sc:.1f}' if _sc else '') + '</div>' if _tot else '')
                + '</div>',
                unsafe_allow_html=True,
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
            can_go = bool(brand_url)
            if st.button("➡️ 분석 시작", type="primary",
                         use_container_width=True, disabled=not can_go):
                st.session_state.keyword   = ""   # URL에서 자동 추출
                st.session_state.brand_url = brand_url
                st.session_state.category  = category
                st.session_state.post_type = post_type
                st.session_state.search_query = ""
                st.session_state.comp_sq_0 = ""
                st.session_state.comp_sq_1 = ""
                st.session_state.kw_researched = False
                st.session_state.step = 1
                st.rerun()
            if not can_go:
                st.caption("Brand Connect URL을 입력하면 활성화됩니다.")


# ── 공통: API 키 확인 ────────────────────────────────
naver_key, naver_secret, naver_customer, anthropic_key, missing = check_env()
if missing:
    st.error(f"⚠️ .env 파일에 다음 키가 없습니다: {', '.join(missing)}")
    st.stop()


# ════════════════════════════════════════════════
# PAGE: HOME — 랜딩 페이지
# ════════════════════════════════════════════════
if st.session_state.page == "home":


    # ── 히어로 배너 ─────────────────────────────────────────
    components.html("""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:-apple-system,'Noto Sans KR',sans-serif;
  background:linear-gradient(135deg,#060d1a 0%,#0c1a35 50%,#081426 100%);
  height:360px;overflow:hidden;position:relative;}
canvas{position:absolute;top:0;left:0;width:100%;height:100%;}
.hero{position:relative;z-index:10;display:flex;flex-direction:column;
  align-items:center;justify-content:center;height:100%;padding:20px;text-align:center;}
.badge{background:rgba(3,199,90,.11);border:1px solid rgba(3,199,90,.3);color:#03C75A;
  padding:6px 20px;border-radius:20px;font-size:10.5px;font-weight:700;letter-spacing:3px;
  margin-bottom:20px;animation:fadeUp .6s ease forwards;}
.title{font-size:2.6rem;font-weight:900;line-height:1.2;margin-bottom:14px;
  animation:fadeUp .6s .12s ease both;}
.gr{background:linear-gradient(90deg,#03C75A,#00e676,#69ff6e);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.wh{color:#fff;font-size:1.5rem;font-weight:700;}
.sub{color:rgba(255,255,255,.5);font-size:.86rem;animation:fadeUp .6s .25s ease both;}
.stats{display:flex;gap:44px;margin-top:26px;animation:fadeUp .6s .4s ease both;}
.stat{text-align:center;}
.snum{font-size:1.55rem;font-weight:800;color:#03C75A;}
.slbl{font-size:.64rem;color:rgba(255,255,255,.38);margin-top:3px;letter-spacing:.8px;}
@keyframes fadeUp{from{opacity:0;transform:translateY(18px);}to{opacity:1;transform:translateY(0);}}
</style></head><body>
<canvas id="c"></canvas>
<div class="hero">
  <div class="badge">✨ AI-POWERED NAVER BLOG AUTOMATION</div>
  <div class="title">
    <span class="gr">네이버 블로그 자동화</span><br>
    <span class="wh">키워드 하나로 완성</span>
  </div>
  <div class="sub">경쟁사 분석 · SEO 키워드 · AI 작성 · 이미지 수집 — 전부 자동</div>
  <div class="stats">
    <div class="stat"><div class="snum" id="n1">0</div><div class="slbl">서브키워드 분석</div></div>
    <div class="stat"><div class="snum">4가지</div><div class="slbl">글 유형 지원</div></div>
    <div class="stat"><div class="snum">~30초</div><div class="slbl">완성 소요 시간</div></div>
    <div class="stat"><div class="snum">100%</div><div class="slbl">블로거 스타일</div></div>
  </div>
</div>
<script>
const canvas=document.getElementById('c'),ctx=canvas.getContext('2d');
function rs(){canvas.width=window.innerWidth;canvas.height=360;}rs();
const pts=Array.from({length:60},()=>({
  x:Math.random()*canvas.width,y:Math.random()*canvas.height,
  vx:(Math.random()-.5)*.5,vy:(Math.random()-.5)*.5,
  r:Math.random()*1.8+.3,o:Math.random()*.4+.1
}));
function draw(){
  ctx.clearRect(0,0,canvas.width,canvas.height);
  pts.forEach(p=>{
    p.x+=p.vx;p.y+=p.vy;
    if(p.x<0||p.x>canvas.width)p.vx*=-1;
    if(p.y<0||p.y>canvas.height)p.vy*=-1;
    ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
    ctx.fillStyle=`rgba(3,199,90,${p.o})`;ctx.fill();
  });
  for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++){
    const dx=pts[j].x-pts[i].x,dy=pts[j].y-pts[i].y,d=Math.sqrt(dx*dx+dy*dy);
    if(d<115){ctx.beginPath();ctx.moveTo(pts[i].x,pts[i].y);ctx.lineTo(pts[j].x,pts[j].y);
      ctx.strokeStyle=`rgba(3,199,90,${.13*(1-d/115)})`;ctx.lineWidth=.5;ctx.stroke();}
  }
  requestAnimationFrame(draw);
}
draw();
let n=0;const el=document.getElementById('n1');
const t=setInterval(()=>{n+=2;if(n>=30){n=30;clearInterval(t);}el.textContent=n+'+';},38);
</script></body></html>""", height=360)

    # ── 프로세스 플로우 인포그래픽 ───────────────────────────
    components.html("""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:-apple-system,'Noto Sans KR',sans-serif;background:#fff;
  padding:20px 12px 12px;}
.label{text-align:center;font-size:.68rem;font-weight:700;color:#03C75A;
  letter-spacing:2.5px;margin-bottom:16px;}
.flow{display:flex;align-items:center;justify-content:center;}
.step{display:flex;flex-direction:column;align-items:center;gap:8px;
  flex:0 0 auto;width:110px;animation:popIn .45s ease both;}
.step:nth-child(1){animation-delay:.05s;}.step:nth-child(3){animation-delay:.22s;}
.step:nth-child(5){animation-delay:.4s;}.step:nth-child(7){animation-delay:.58s;}
.step:nth-child(9){animation-delay:.76s;}
.iw{width:58px;height:58px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:1.4rem;position:relative;
  box-shadow:0 3px 14px rgba(0,0,0,.09);}
.ring{position:absolute;inset:-5px;border-radius:50%;
  border:2px dashed rgba(3,199,90,.25);animation:spin 9s linear infinite;}
.num{position:absolute;top:-2px;right:-2px;width:18px;height:18px;
  background:#03C75A;color:#fff;border-radius:50%;font-size:.58rem;font-weight:800;
  display:flex;align-items:center;justify-content:center;}
.st{font-size:.76rem;font-weight:800;color:#1a1a1a;text-align:center;}
.sd{font-size:.64rem;color:#999;text-align:center;line-height:1.35;}
.arr{flex:1;display:flex;align-items:center;padding:0 2px;margin-bottom:30px;}
.arr svg{width:100%;height:20px;overflow:visible;}
@keyframes popIn{from{opacity:0;transform:scale(.6);}to{opacity:1;transform:scale(1);}}
@keyframes spin{to{transform:rotate(360deg);}}
@keyframes dash{to{stroke-dashoffset:0;}}
</style></head><body>
<div class="label">▶ 자동화 프로세스</div>
<div class="flow">
  <div class="step">
    <div class="iw" style="background:linear-gradient(135deg,#e8f5e9,#c8e6c9);">
      <span>🎯</span><div class="ring"></div><div class="num">1</div></div>
    <div class="st">URL 입력</div><div class="sd">Brand Connect</div>
  </div>
  <div class="arr"><svg viewBox="0 0 52 20"><path d="M2 10H42" stroke="#03C75A" stroke-width="1.8"
    stroke-dasharray="5 3" stroke-dashoffset="55" style="animation:dash .9s .15s linear forwards;"/>
    <path d="M38 5L48 10L38 15" stroke="#03C75A" stroke-width="1.8" fill="none"/></svg></div>
  <div class="step">
    <div class="iw" style="background:linear-gradient(135deg,#e3f2fd,#bbdefb);">
      <span>🔑</span><div class="ring"></div><div class="num">2</div></div>
    <div class="st">키워드 자동 확정</div><div class="sd">검색량 1위 선택</div>
  </div>
  <div class="arr"><svg viewBox="0 0 52 20"><path d="M2 10H42" stroke="#03C75A" stroke-width="1.8"
    stroke-dasharray="5 3" stroke-dashoffset="55" style="animation:dash .9s .4s linear forwards;"/>
    <path d="M38 5L48 10L38 15" stroke="#03C75A" stroke-width="1.8" fill="none"/></svg></div>
  <div class="step">
    <div class="iw" style="background:linear-gradient(135deg,#fff3e0,#ffe0b2);">
      <span>🛍️</span><div class="ring"></div><div class="num">3</div></div>
    <div class="st">제품 선택</div><div class="sd">최저가 확정</div>
  </div>
  <div class="arr"><svg viewBox="0 0 52 20"><path d="M2 10H42" stroke="#03C75A" stroke-width="1.8"
    stroke-dasharray="5 3" stroke-dashoffset="55" style="animation:dash .9s .65s linear forwards;"/>
    <path d="M38 5L48 10L38 15" stroke="#03C75A" stroke-width="1.8" fill="none"/></svg></div>
  <div class="step">
    <div class="iw" style="background:linear-gradient(135deg,#fce4ec,#f8bbd0);">
      <span>🤖</span><div class="ring"></div><div class="num">4</div></div>
    <div class="st">AI 글 작성</div><div class="sd">SEO 최적화</div>
  </div>
  <div class="arr"><svg viewBox="0 0 52 20"><path d="M2 10H42" stroke="#03C75A" stroke-width="1.8"
    stroke-dasharray="5 3" stroke-dashoffset="55" style="animation:dash .9s .9s linear forwards;"/>
    <path d="M38 5L48 10L38 15" stroke="#03C75A" stroke-width="1.8" fill="none"/></svg></div>
  <div class="step">
    <div class="iw" style="background:linear-gradient(135deg,#e8eaf6,#c5cae9);">
      <span>✅</span><div class="ring"></div><div class="num">5</div></div>
    <div class="st">완성 & 저장</div><div class="sd">HTML + 이미지</div>
  </div>
</div>
</body></html>""", height=198)

    # ── 글 유형 선택 타일 ────────────────────────────────────
    st.markdown(
        '<div style="margin:12px 0 10px;text-align:center;">'
        '<span style="font-size:.68rem;font-weight:700;color:#03C75A;letter-spacing:2.5px;">'
        '▶ 글 유형을 선택하세요</span></div>',
        unsafe_allow_html=True,
    )
    tc1, tc2, tc3, tc4 = st.columns(4)
    TYPES = [
        ("review",  "📝", "리뷰형",      "#e8f5e9", "#2e7d32"),
        ("compare", "⚖️", "비교형",      "#e3f2fd", "#1565c0"),
        ("info",    "💡", "정보전달형",  "#fff8e1", "#e65100"),
        ("howto",   "🛠️", "활용법형",    "#f3e5f5", "#6a1b9a"),
    ]
    for col, (ptype, icon, name, bg, accent) in zip([tc1, tc2, tc3, tc4], TYPES):
        with col:
            is_sel = st.session_state.post_type == ptype
            bdr = f"2.5px solid {accent}" if is_sel else "2px solid #e8e8e8"
            st.markdown(
                f'<div class="type-tile" style="background:{"" + bg if is_sel else "#fafafa"};'
                f'border:{bdr};">'
                f'<div style="font-size:2rem;margin-bottom:6px;">{icon}</div>'
                f'<div style="font-size:.84rem;font-weight:800;'
                f'color:{accent if is_sel else "#1a1a1a"};">{name}</div>'
                + (f'<div style="font-size:.65rem;color:{accent};font-weight:700;margin-top:5px;">✓ 선택</div>' if is_sel else '')
                + '</div>',
                unsafe_allow_html=True,
            )
            if st.button("선택됨" if is_sel else "선택", key=f"ht_{ptype}",
                         use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                st.session_state.post_type = ptype
                st.rerun()

    # ── CTA ─────────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown('<div class="home-cta">', unsafe_allow_html=True)
        if st.button("✍️ 글 작성 시작하기 →", type="primary", use_container_width=True):
            st.session_state.page = "tool"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.caption("키워드와 URL은 다음 화면에서 입력합니다.")



# ════════════════════════════════════════════════
# STEP 0: 입력 안내 (도구 페이지)
# ════════════════════════════════════════════════
elif st.session_state.step == 0:
    show_tool_header()
    st.markdown(
        '<div style="display:flex;align-items:center;justify-content:center;min-height:340px;">'
        '<div style="max-width:500px;text-align:center;padding:36px 24px;">'
        '<div style="width:80px;height:80px;background:linear-gradient(135deg,#03C75A,#00BCD4);'
        'border-radius:50%;display:flex;align-items:center;justify-content:center;'
        'font-size:2.2rem;margin:0 auto 20px;box-shadow:0 8px 28px rgba(3,199,90,0.3);">✍️</div>'
        '<div style="font-size:1.35rem;font-weight:900;color:#1a2840;margin-bottom:10px;letter-spacing:-0.3px;">'
        '사이드바에서 URL을 입력하세요</div>'
        '<div style="font-size:0.86rem;color:#6b7c93;line-height:1.85;margin-bottom:28px;">'
        '← 왼쪽 사이드바에 Brand Connect URL을 입력한 후<br>'
        '<strong style="color:#03C75A;">➡️ 분석 시작</strong>을 누르면 모든 것이 자동으로 진행됩니다.</div>'
        '<div style="display:flex;flex-direction:column;gap:10px;text-align:left;'
        'background:white;border-radius:16px;padding:18px 20px;'
        'box-shadow:0 3px 16px rgba(0,0,0,0.07);">'
        '<div style="display:flex;align-items:center;gap:10px;">'
        '<span style="font-size:1.1rem;">🔗</span>'
        '<div><div style="font-size:0.8rem;font-weight:700;color:#1a2840;">Brand Connect URL</div>'
        '<div style="font-size:0.73rem;color:#8fafc8;">제품 링크만 입력하면 끝!</div></div></div>'
        '<div style="display:flex;align-items:center;gap:10px;">'
        '<span style="font-size:1.1rem;">🎯</span>'
        '<div><div style="font-size:0.8rem;font-weight:700;color:#1a2840;">메인 키워드 자동 추출</div>'
        '<div style="font-size:0.73rem;color:#8fafc8;">검색량 × 경쟁도 × 관련성 스코어링</div></div></div>'
        '<div style="display:flex;align-items:center;gap:10px;">'
        '<span style="font-size:1.1rem;">🔥</span>'
        '<div><div style="font-size:0.8rem;font-weight:700;color:#1a2840;">경쟁 블로그 분석</div>'
        '<div style="font-size:0.73rem;color:#8fafc8;">상위 블로그 출현 키워드 부스팅</div></div></div>'
        '</div></div></div>',
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════
# STEP 1: 제품 검색 & 선택
# ════════════════════════════════════════════════
elif st.session_state.step == 1:
    show_tool_header()
    st.markdown("### 🛍️ 제품 검색 & 선택")

    naver_cid = os.getenv("NAVER_CLIENT_ID", "")
    naver_csec = os.getenv("NAVER_CLIENT_SECRET", "")
    scraper = ProductScraper(naver_cid, naver_csec)

    def _is_valid_product_name(s: str) -> bool:
        """실제 제품명인지 판단: 한글 포함 + 5자 이상 + 기본값 아님"""
        return (
            bool(s)
            and len(s) >= 5
            and any('가' <= c <= '힣' for c in s)
            and s not in ("제품", "상품", "이미지", "products")
        )

    # ── 전체 자동화 초기화 (최초 1회) ─────────────────────────
    if not st.session_state.kw_researched:
        with st.spinner("🤖 URL 분석 중..."):

            # 1. Brand URL → 제품명 추출
            product_name_from_url = ""
            if st.session_state.brand_url:
                try:
                    url_data = scraper._scrape_from_url(st.session_state.brand_url)
                    extracted = url_data.get("name", "").strip()
                    if _is_valid_product_name(extracted):
                        product_name_from_url = extracted
                except Exception:
                    pass

        # 제품명 추출 성공 → 자동 분석 진행
        if product_name_from_url:
            with st.spinner("🤖 키워드 리서치 · 블로그 분석 · 제품 검색 · 경쟁사 탐색 중..."):
                naver_cid = os.getenv("NAVER_CLIENT_ID", "")
                naver_csec = os.getenv("NAVER_CLIENT_SECRET", "")
                researcher = NaverKeywordResearch(naver_key, naver_secret, naver_customer)

                # 2. 키워드 API + 스코어링
                try:
                    raw_kws = researcher.get_related_keywords(product_name_from_url, top_n=30)
                    if raw_kws:
                        scored_kws = researcher.score_keywords(raw_kws, product_name_from_url)
                        best_meta = researcher.select_main_keyword(raw_kws, product_name_from_url)
                        st.session_state.keyword = best_meta.get("keyword", product_name_from_url)
                        st.session_state.kw_main_meta = best_meta

                        rest = [k for k in scored_kws if k["keyword"] != st.session_state.keyword]

                        # 3. 경쟁 블로그 분석 — 서브키워드 순위 보정
                        sub_kw_texts = [k["keyword"] for k in rest[:15]]
                        if naver_cid and sub_kw_texts:
                            try:
                                analyzer = BlogAnalyzer(naver_cid, naver_csec)
                                freq = analyzer.analyze_keyword_frequency(
                                    st.session_state.keyword, sub_kw_texts, top_n=10
                                )
                                boosted = analyzer.boost_scores(rest, freq)
                                st.session_state.kw_scored = boosted
                                final_sub = [k for k in boosted if k.get("total", 0) > 100]
                                st.session_state.sub_keywords = [k["keyword"] for k in final_sub[:8]]
                            except Exception:
                                st.session_state.kw_scored = rest
                                st.session_state.sub_keywords = researcher.select_sub_keywords(rest, count=8)
                        else:
                            st.session_state.kw_scored = rest
                            st.session_state.sub_keywords = researcher.select_sub_keywords(rest, count=8)
                    else:
                        st.session_state.keyword = product_name_from_url
                        st.session_state.sub_keywords = []
                        st.session_state.kw_scored = []
                        st.session_state.kw_main_meta = {}
                except Exception:
                    st.session_state.keyword = product_name_from_url
                    st.session_state.sub_keywords = []
                    st.session_state.kw_scored = []
                    st.session_state.kw_main_meta = {}

                # 4. 메인 제품 검색
                try:
                    st.session_state.search_results = scraper.search_products(product_name_from_url, top_n=8)
                    st.session_state.search_query = product_name_from_url
                except Exception:
                    st.session_state.search_results = []
                    st.session_state.search_query = product_name_from_url

                # 5. 경쟁사 자동 탐색 (비교형)
                if st.session_state.post_type == "compare":
                    comp_queries = suggest_competitor_queries(
                        anthropic_key, st.session_state.keyword, product_name_from_url
                    )
                    for ci, cq in enumerate(comp_queries[:2]):
                        try:
                            results = scraper.search_products(cq, top_n=8)
                            st.session_state[f"comp_sr_{ci}"] = results
                            st.session_state[f"comp_sq_{ci}"] = cq
                            if results:
                                st.session_state[f"comp_sel_{ci}"] = dict(results[0])
                        except Exception:
                            st.session_state[f"comp_sr_{ci}"] = []
                            st.session_state[f"comp_sq_{ci}"] = cq

        else:
            # 제품명 추출 실패 → 키워드/검색 없이 대기, 사용자 직접 입력 유도
            st.session_state.keyword = ""
            st.session_state.search_results = []
            st.session_state.search_query = ""

        st.session_state.kw_researched = True
        st.rerun()

    # ── Naver Client 키 누락 경고 ────────────────────────────
    if not naver_cid:
        st.info(
            "💡 **네이버 쇼핑 제품 검색**을 사용하려면 `.env`에 `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET`을 추가하세요. "
            "([developers.naver.com](https://developers.naver.com) → 앱 등록 → Shopping 검색 권한)  "
            "현재는 **직접 입력 폼**으로 제품 정보를 입력할 수 있습니다.",
            icon="ℹ️",
        )

    # ── 메인 키워드 입력 / 교차검증 ─────────────────────────
    _kw_ok = _is_valid_product_name(st.session_state.keyword)
    if not _kw_ok:
        st.error(
            "⚠️ URL에서 제품명을 자동으로 가져오지 못했습니다.  \n"
            "**아래에 제품명을 직접 입력하고 Enter를 누르면 자동으로 검색됩니다.**",
            icon="✏️",
        )
    kw_col, _ = st.columns([3, 1])
    with kw_col:
        new_kw = st.text_input(
            "🎯 제품명 / 메인 키워드" + (" (자동 추출 — 수정 가능)" if _kw_ok else " ← 직접 입력"),
            value=st.session_state.keyword if _kw_ok else "",
            key="kw_override",
            placeholder="" if _kw_ok else "예) 로보락 S8 Pro 로봇청소기",
        )
    # 입력값이 유효한 제품명이면 키워드 + 검색 업데이트
    if _is_valid_product_name(new_kw) and new_kw != st.session_state.keyword:
        naver_cid_manual = os.getenv("NAVER_CLIENT_ID", "")
        naver_csec_manual = os.getenv("NAVER_CLIENT_SECRET", "")
        with st.spinner("🔍 키워드 분석 · 블로그 분석 · 제품 검색 중..."):
            st.session_state.keyword = new_kw
            st.session_state.search_query = new_kw
            try:
                researcher = NaverKeywordResearch(naver_key, naver_secret, naver_customer)
                raw_kws = researcher.get_related_keywords(new_kw, top_n=30)
                if raw_kws:
                    scored_kws = researcher.score_keywords(raw_kws, new_kw)
                    best_meta = researcher.select_main_keyword(raw_kws, new_kw)
                    st.session_state.keyword = best_meta.get("keyword", new_kw)
                    st.session_state.kw_main_meta = best_meta
                    rest = [k for k in scored_kws if k["keyword"] != st.session_state.keyword]
                    if naver_cid_manual and rest:
                        try:
                            analyzer = BlogAnalyzer(naver_cid_manual, naver_csec_manual)
                            freq = analyzer.analyze_keyword_frequency(
                                st.session_state.keyword, [k["keyword"] for k in rest[:15]], top_n=10
                            )
                            boosted = analyzer.boost_scores(rest, freq)
                            st.session_state.kw_scored = boosted
                            st.session_state.sub_keywords = [
                                k["keyword"] for k in boosted if k.get("total", 0) > 100
                            ][:8]
                        except Exception:
                            st.session_state.kw_scored = rest
                            st.session_state.sub_keywords = researcher.select_sub_keywords(rest, count=8)
                    else:
                        st.session_state.kw_scored = rest
                        st.session_state.sub_keywords = researcher.select_sub_keywords(rest, count=8)
            except Exception:
                pass
            try:
                st.session_state.search_results = scraper.search_products(new_kw, top_n=8)
            except Exception:
                st.session_state.search_results = []
        st.rerun()

    # ── 메인 제품 검색 ────────────────────────────────────
    st.markdown("#### 1. 메인 제품 선택")
    st.caption("제품명을 검색해서 카드를 클릭하거나, 아래 직접 입력 폼을 사용하세요.")

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
                results = scraper.search_products(mq, top_n=8)
                st.session_state.search_results = results
                st.session_state.search_query = mq
                st.session_state.product_info = None
            st.rerun()

    if st.session_state.search_results:
        cnt = len(st.session_state.search_results)
        st.markdown(f"**검색 결과 {cnt}개** (가격 낮은 순 · 클릭해서 선택)")
        render_product_cards(st.session_state.search_results, "main", "product_info")
    elif st.session_state.search_query:
        st.warning("검색 결과가 없습니다. 다른 검색어를 시도하거나 아래 직접 입력 폼을 사용하세요.", icon="⚠️")

    # ── 직접 입력 폼 (항상 접근 가능) ────────────────────────
    if not st.session_state.product_info:
        with st.expander(
            "✍️ 제품 정보 직접 입력" + (" ← 검색 결과 없음 시 여기서 입력" if st.session_state.search_query and not st.session_state.search_results else ""),
            expanded=bool(not st.session_state.search_results),
        ):
            mi1, mi2 = st.columns(2)
            with mi1:
                mn  = st.text_input("제품명 *", placeholder="예) 삼성 갤럭시 S25 256GB", key="mi_name")
                mp  = st.text_input("최저가 (원) *", placeholder="예) 1,100,000", key="mi_price")
                mb  = st.text_input("브랜드", placeholder="예) Samsung", key="mi_brand")
            with mi2:
                mr   = st.text_input("평점", placeholder="예) 4.7", key="mi_rating")
                mc   = st.text_input("리뷰 수", placeholder="예) 2,345", key="mi_review")
                mimg = st.text_input("이미지 URL (선택)", placeholder="https://...", key="mi_img")
            md = st.text_area("제품 설명 / 스펙", placeholder="주요 특징, 스펙 등을 자유롭게 입력하세요", height=80, key="mi_desc")
            if st.button("✅ 이 정보로 적용", type="primary", key="mi_apply"):
                if mn and mp:
                    price_raw = mp.replace(",", "").replace(" ", "")
                    price_int = int(price_raw) if price_raw.isdigit() else 0
                    st.session_state.product_info = {
                        "name": mn, "price": mp, "price_int": price_int,
                        "brand": mb, "rating": mr, "review_count": mc,
                        "image": mimg, "images": [mimg] if mimg else [],
                        "description": md, "specs": {}, "promotions": {},
                        "pros": [], "cons": [], "key_features": [],
                    }
                    st.rerun()
                else:
                    st.error("제품명과 최저가는 필수 입력값입니다.")

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

    # ── 경쟁 제품 교차검증 (비교형만) ──────────────────────
    if st.session_state.post_type == "compare":
        st.divider()
        st.markdown("#### 2. 경쟁 제품 교차검증")
        st.caption("AI가 자동으로 찾아 선택했습니다. 다른 제품으로 교체하려면 카드를 클릭하세요.")

        for ci in range(2):
            sr_key  = f"comp_sr_{ci}"
            sq_key  = f"comp_sq_{ci}"
            sel_key = f"comp_sel_{ci}"
            label   = f"경쟁 제품 {ci + 1}"

            sel = st.session_state.get(sel_key)
            comp_results = st.session_state.get(sr_key, [])

            # 자동 선택된 제품 표시
            if sel:
                st.success(
                    f"🤖 **{label} 자동 선택**: {sel.get('name', '')}  |  "
                    f"최저가: **{sel.get('price', '')}원**"
                    + (f"  |  ⭐{sel.get('rating', '')} ({sel.get('review_count', '')}개)" if sel.get("rating") else "")
                )
            else:
                st.warning(f"⚠️ {label} — 자동 검색 결과 없음. 직접 검색해주세요.")

            # 교체 expander (필요할 때만 열기)
            with st.expander(f"🔄 {label} 교체하기", expanded=not bool(sel)):
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
                if comp_results:
                    render_product_cards(comp_results, f"c{ci}", sel_key)

    # ── 키워드 스코어 대시보드 ───────────────────────────
    _kw_meta   = st.session_state.get("kw_main_meta", {})
    _kw_scored = st.session_state.get("kw_scored", [])
    if _kw_meta or st.session_state.sub_keywords:
        st.divider()
        st.markdown("#### 🔑 키워드 분석 결과")

        # ── 메인 키워드 배지 카드 ──────────────────────
        if _kw_meta:
            _comp  = _kw_meta.get("competition", "")
            _total = _kw_meta.get("total", 0)
            _score = _kw_meta.get("score", 0)
            _comp_badge_cls = {"낮음": "comp-badge comp-low", "중간": "comp-badge comp-mid", "높음": "comp-badge comp-high"}.get(_comp, "comp-badge")
            st.markdown(
                f'<div class="kw-meta-card">'
                f'<div style="font-size:0.72rem;color:#6b9c7a;font-weight:700;letter-spacing:0.5px;margin-bottom:4px;">🎯 메인 키워드</div>'
                f'<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">'
                f'<span style="font-size:1.15rem;font-weight:900;background:linear-gradient(90deg,#03C75A,#00BCD4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">{st.session_state.keyword}</span>'
                + (f'<span style="font-size:0.78rem;color:#2d6a4f;font-weight:600;">📊 {_total:,}회/월</span>' if _total else '')
                + (f'<span class="{_comp_badge_cls}">경쟁도 {_comp}</span>' if _comp else '')
                + (f'<span style="font-size:0.75rem;color:#8fafc8;">점수 {_score:.1f}</span>' if _score else '')
                + '</div></div>',
                unsafe_allow_html=True,
            )

        # ── 서브키워드 스코어 카드 리스트 ──────────────
        if _kw_scored:
            top_sub = [k for k in _kw_scored if k.get("total", 0) > 100][:12]
            if top_sub:
                max_score = max((k.get("score", 0) for k in top_sub), default=1) or 1
                rows_html = ""
                for k in top_sub:
                    kw_text = k.get("keyword", "")
                    total   = k.get("total", 0)
                    comp    = k.get("competition", "")
                    sc      = k.get("score", 0)
                    bc      = k.get("blog_count", 0)
                    is_sel  = kw_text in st.session_state.sub_keywords
                    bar_pct = int(sc / max_score * 100)
                    badge_cls = {"낮음": "comp-badge comp-low", "중간": "comp-badge comp-mid", "높음": "comp-badge comp-high"}.get(comp, "comp-badge")
                    fire_html = f'<span class="blog-fire">{"🔥" * min(bc, 5)}&nbsp;{bc}</span>' if bc else '<span style="color:#c0ccd8;font-size:0.72rem;">—</span>'
                    row_bg = "linear-gradient(90deg,rgba(3,199,90,0.06),rgba(0,188,212,0.04))" if is_sel else "white"

                    rows_html += (
                        f'<div style="display:grid;grid-template-columns:1fr 90px 64px 60px 56px;'
                        f'align-items:center;gap:10px;padding:9px 14px;background:{row_bg};'
                        f'border-bottom:1px solid #f0f4f8;">'
                        # 키워드 + 바
                        f'<div>'
                        f'<div style="font-size:0.8rem;font-weight:{"700" if is_sel else "500"};color:#1a2840;">'
                        f'{"<span style=\'color:#03C75A;\'>✓ </span>" if is_sel else ""}{kw_text}</div>'
                        f'<div class="sbar-wrap"><div class="sbar-fill" style="width:{bar_pct}%;"></div></div>'
                        f'</div>'
                        # 검색량
                        f'<div style="font-size:0.76rem;color:#6b7c93;text-align:right;font-weight:500;">{total:,}</div>'
                        # 경쟁도
                        f'<div style="text-align:center;"><span class="{badge_cls}">{comp or "—"}</span></div>'
                        # 블로그
                        f'<div style="text-align:center;">{fire_html}</div>'
                        # 점수
                        f'<div style="text-align:right;font-size:0.82rem;font-weight:800;background:linear-gradient(135deg,#03C75A,#00BCD4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">{sc:.1f}</div>'
                        f'</div>'
                    )

                st.markdown(
                    f'<div style="background:white;border-radius:16px;overflow:hidden;'
                    f'box-shadow:0 3px 16px rgba(0,0,0,0.07);margin-bottom:6px;">'
                    f'<div style="display:grid;grid-template-columns:1fr 90px 64px 60px 56px;'
                    f'gap:10px;padding:8px 14px;background:#f8fafc;border-bottom:2px solid #f0f4f8;">'
                    f'<div style="font-size:0.69rem;font-weight:700;color:#8fafc8;letter-spacing:0.5px;">키워드</div>'
                    f'<div style="font-size:0.69rem;font-weight:700;color:#8fafc8;text-align:right;">검색량/월</div>'
                    f'<div style="font-size:0.69rem;font-weight:700;color:#8fafc8;text-align:center;">경쟁도</div>'
                    f'<div style="font-size:0.69rem;font-weight:700;color:#8fafc8;text-align:center;">블로그</div>'
                    f'<div style="font-size:0.69rem;font-weight:700;color:#8fafc8;text-align:right;">점수</div>'
                    f'</div>'
                    f'{rows_html}</div>',
                    unsafe_allow_html=True,
                )
                st.caption("✓ 체크 = 글에 포함될 서브키워드 | 🔥 = 상위 블로그 출현 횟수")
        elif st.session_state.sub_keywords:
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
    show_tool_header()
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
        images_dir.mkdir(parents=True, exist_ok=True)
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
    show_tool_header()
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

    # ════════════════════════════════════════════════
    # 자동 발행 섹션
    # ════════════════════════════════════════════════
    st.divider()
    st.markdown("### 🚀 네이버 블로그 자동 발행")

    _naver_id = os.getenv("NAVER_ID", "")
    _naver_pw = os.getenv("NAVER_PW", "")
    _poster   = NaverBlogPoster(str(Path(__file__).parent / "poster_data"))

    # 상태 카드 3개
    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        _login_status = "✅ 로그인됨" if _poster.is_logged_in() else "❌ 미로그인"
        st.markdown(
            f'<div class="stat-card"><div class="stat-num" style="font-size:1.1rem;">{_login_status}</div>'
            f'<div class="stat-lbl">로그인 상태</div></div>',
            unsafe_allow_html=True,
        )
    with pc2:
        _today = _poster.today_count()
        st.markdown(
            f'<div class="stat-card"><div class="stat-num">{_today}/{_poster.MAX_DAILY}</div>'
            f'<div class="stat-lbl">오늘 발행</div></div>',
            unsafe_allow_html=True,
        )
    with pc3:
        _rem = _poster.remaining()
        _rem_color = "#03C75A" if _rem > 0 else "#e53935"
        st.markdown(
            f'<div class="stat-card"><div class="stat-num" style="color:{_rem_color};">{_rem}개</div>'
            f'<div class="stat-lbl">남은 발행 횟수</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    if not _naver_id or not _naver_pw:
        st.warning(
            "📋 `.env` 파일에 `NAVER_ID`와 `NAVER_PW`를 추가하면 자동 발행이 활성화됩니다.",
            icon="ℹ️",
        )
    elif not _poster.is_logged_in():
        st.info("네이버에 로그인하면 자동 발행 버튼이 활성화됩니다.", icon="🔑")
        if st.button("🔑 네이버 로그인하기", use_container_width=True):
            with st.spinner("브라우저를 열어 로그인 중... (캡챠/2FA 발생 시 직접 처리하세요)"):
                _ok, _msg = _poster.login(_naver_id, _naver_pw)
            if _ok:
                st.success(_msg)
                st.rerun()
            else:
                st.error(_msg)
    else:
        _col_post, _col_logout = st.columns([3, 1])
        with _col_post:
            _can = _poster.can_post()
            if st.button(
                "🚀 네이버 블로그에 자동 발행",
                type="primary",
                use_container_width=True,
                disabled=not _can,
            ):
                _title = post.split("\n")[0].strip().lstrip("#").strip() or st.session_state.keyword
                with st.spinner("블로그에 발행 중... 브라우저가 잠시 열립니다."):
                    _ok, _msg = _poster.post(
                        title=_title,
                        content=post,
                        images=st.session_state.saved_images,
                        naver_id=_naver_id,
                    )
                if _ok:
                    st.success(f"✅ {_msg}")
                else:
                    st.error(f"발행 실패: {_msg}")
                st.rerun()
            if not _can:
                st.caption(f"오늘 발행 한도({_poster.MAX_DAILY}개) 도달 — 내일 다시 가능합니다.")
        with _col_logout:
            if st.button("로그아웃", use_container_width=True):
                _poster.clear_login()
                st.rerun()

    st.divider()
    if st.button("🏠 새 글 작성하기 (처음으로)", type="primary"):
        reset()
        st.rerun()


# ════════════════════════════════════════════════
# STEP -1: 오류 화면
# ════════════════════════════════════════════════
elif st.session_state.step == -1:
    show_tool_header()
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
