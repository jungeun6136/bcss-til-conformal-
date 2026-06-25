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
    /* 전역 여백 */
    .block-container { padding-top:2.5rem !important; padding-bottom:1rem !important; }
    section[data-testid="stSidebar"] .block-container { padding-top:0.5rem !important; }
    div[data-testid="stVerticalBlock"] > div { gap:0.3rem; }
    hr { margin:0.5rem 0 !important; }
    /* 랜딩 페이지 전용 */
    .home-cta > div > button { font-size:1.1rem !important; height:3rem !important; }
    .type-tile { border-radius:16px; padding:18px 8px; text-align:center;
                 cursor:pointer; transition:all .15s; }
    .type-tile:hover { transform:translateY(-2px); box-shadow:0 6px 20px rgba(0,0,0,.1); }
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
            st.markdown(
                f'<div style="background:#f0faf4;border:1px solid #03C75A;border-radius:6px;'
                f'padding:6px 10px;font-size:0.82rem;color:#03C75A;margin-bottom:6px;">'
                f'🎯 메인 키워드: <b>{st.session_state.keyword}</b></div>',
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
        '<div style="display:flex;align-items:center;justify-content:center;'
        'min-height:300px;">'
        '<div style="max-width:480px;text-align:center;padding:32px;">'
        '<div style="font-size:3.5rem;margin-bottom:16px;">✍️</div>'
        '<div style="font-size:1.3rem;font-weight:800;color:#1a1a1a;margin-bottom:10px;">'
        '사이드바에서 정보를 입력하세요</div>'
        '<div style="font-size:.88rem;color:#666;line-height:1.8;margin-bottom:24px;">'
        '← 왼쪽 사이드바에 Brand Connect URL을 입력한 후<br>'
        '<strong style="color:#03C75A;">➡️ 분석 시작</strong> 버튼을 클릭하면 키워드부터 제품 검색까지 자동으로 진행됩니다.</div>'
        '<div style="display:flex;flex-direction:column;gap:8px;text-align:left;'
        'background:#f8f8f8;border-radius:12px;padding:16px;">'
        '<div style="font-size:.8rem;color:#555;">🔗 <b>Brand Connect URL</b> — 제품 링크만 입력하면 끝!</div>'
        '<div style="font-size:.8rem;color:#555;">🎯 <b>메인 키워드</b> — URL에서 자동 추출 + 검색량 분석</div>'
        '<div style="font-size:.8rem;color:#555;">📂 <b>카테고리 / 글 유형</b> — 이미 선택됨</div>'
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

    # ── 전체 자동화 초기화 (최초 1회) ─────────────────────────
    if not st.session_state.kw_researched:
        with st.spinner("🤖 URL 분석 · 키워드 리서치 · 제품 검색 · 경쟁사 탐색 중..."):

            # 1. Brand URL → 제품명 추출
            product_name_from_url = ""
            if st.session_state.brand_url:
                try:
                    url_data = scraper._scrape_from_url(st.session_state.brand_url)
                    extracted = url_data.get("name", "").strip()
                    if extracted and len(extracted) > 3:
                        product_name_from_url = extracted
                except Exception:
                    pass

            # URL에서 제품명 추출 실패 시 URL 경로에서 힌트 파싱
            if not product_name_from_url and st.session_state.brand_url:
                import re as _re
                slug = st.session_state.brand_url.rstrip("/").split("/")[-1]
                product_name_from_url = _re.sub(r"[_\-]", " ", slug).strip() or "제품"

            # 2. 키워드 API → 제품과 관련 있는 키워드 중 검색량 최고 = 메인키워드
            researcher = NaverKeywordResearch(naver_key, naver_secret, naver_customer)
            try:
                raw_kws = researcher.get_related_keywords(product_name_from_url, top_n=30)
                if raw_kws:
                    # 제품명 구성 단어 추출 (2자 이상)
                    prod_words = [w for w in product_name_from_url.split() if len(w) >= 2]
                    # 제품명 단어 중 하나라도 포함 + 4자 이상인 키워드 우선 선택
                    relevant = [
                        k for k in raw_kws
                        if len(k["keyword"]) >= 4
                        and any(w in k["keyword"] for w in prod_words)
                    ]
                    best = relevant[0] if relevant else raw_kws[0]
                    st.session_state.keyword = best["keyword"]
                    # 서브키워드: 메인 제외한 관련 키워드 상위 8개
                    rest = [k for k in raw_kws if k["keyword"] != best["keyword"]]
                    st.session_state.sub_keywords = researcher.select_sub_keywords(rest, count=8)
                else:
                    st.session_state.keyword = product_name_from_url
                    st.session_state.sub_keywords = []
            except Exception:
                st.session_state.keyword = product_name_from_url
                st.session_state.sub_keywords = []

            # 3. 메인 제품 자동 검색 (제품명으로)
            search_q = product_name_from_url
            try:
                st.session_state.search_results = scraper.search_products(search_q, top_n=8)
                st.session_state.search_query = search_q
            except Exception:
                st.session_state.search_results = []
                st.session_state.search_query = search_q

            # 4. 경쟁사 자동 탐색 + 1위 자동 선택 (비교형일 때만)
            if st.session_state.post_type == "compare":
                comp_queries = suggest_competitor_queries(
                    anthropic_key, st.session_state.keyword, search_q
                )
                for ci, cq in enumerate(comp_queries[:2]):
                    try:
                        results = scraper.search_products(cq, top_n=8)
                        st.session_state[f"comp_sr_{ci}"] = results
                        st.session_state[f"comp_sq_{ci}"] = cq
                        # 검색 결과 1위 자동 선택
                        if results:
                            st.session_state[f"comp_sel_{ci}"] = dict(results[0])
                    except Exception:
                        st.session_state[f"comp_sr_{ci}"] = []
                        st.session_state[f"comp_sq_{ci}"] = cq

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

    # ── 메인 키워드 교차검증 ─────────────────────────────
    kw_col, _ = st.columns([3, 1])
    with kw_col:
        new_kw = st.text_input(
            "🎯 메인 키워드 (자동 추출 — 수정 가능)",
            value=st.session_state.keyword,
            key="kw_override",
        )
        if new_kw != st.session_state.keyword:
            st.session_state.keyword = new_kw

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
