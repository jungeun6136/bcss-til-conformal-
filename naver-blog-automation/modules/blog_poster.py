import json
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Tuple, List


class NaverBlogPoster:
    MAX_DAILY = 3
    LOGIN_URL  = "https://nid.naver.com/nidlogin.login"
    WRITE_PATH = "https://blog.naver.com/PostWrite.naver"

    def __init__(self, data_dir: str = "poster_data"):
        self.data_dir    = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_file = self.data_dir / "cookies.json"
        self.log_file    = self.data_dir / "post_log.json"

    # ── 일일 한도 ─────────────────────────────────────
    def today_count(self) -> int:
        return self._load_log().get(datetime.now().strftime("%Y-%m-%d"), 0)

    def can_post(self) -> bool:
        return self.today_count() < self.MAX_DAILY

    def remaining(self) -> int:
        return self.MAX_DAILY - self.today_count()

    def _load_log(self) -> dict:
        try:
            return json.loads(self.log_file.read_text(encoding="utf-8")) if self.log_file.exists() else {}
        except Exception:
            return {}

    def _record_post(self):
        today = datetime.now().strftime("%Y-%m-%d")
        log = self._load_log()
        log[today] = log.get(today, 0) + 1
        self.log_file.write_text(json.dumps(log, ensure_ascii=False), encoding="utf-8")

    # ── 쿠키 ─────────────────────────────────────────
    def is_logged_in(self) -> bool:
        return self.cookie_file.exists()

    def clear_login(self):
        self.cookie_file.unlink(missing_ok=True)

    def _save_cookies(self, context):
        cookies = context.cookies()
        self.cookie_file.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")

    def _load_cookies(self, context):
        if self.cookie_file.exists():
            cookies = json.loads(self.cookie_file.read_text(encoding="utf-8"))
            context.add_cookies(cookies)

    # ── 스텔스 유틸 ──────────────────────────────────
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
    _BROWSER_ARGS = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-web-security",
    ]
    _STEALTH_JS = """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US'] });
        window.chrome = { runtime: {} };
    """

    def _ctx_opts(self):
        return dict(
            user_agent=self._UA,
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            permissions=["clipboard-read", "clipboard-write"],
        )

    def _patch(self, page):
        page.add_init_script(self._STEALTH_JS)

    def _jitter(self, lo=700, hi=2000):
        time.sleep(random.uniform(lo, hi) / 1000)

    def _type_human(self, page, selector: str, text: str):
        el = page.locator(selector).first
        el.click()
        self._jitter(200, 500)
        for ch in text:
            page.keyboard.type(ch, delay=random.randint(30, 80))

    def _paste_content(self, page, selector: str, text: str) -> bool:
        """클립보드로 긴 텍스트 붙여넣기"""
        try:
            el = page.locator(selector).first
            el.wait_for(state="visible", timeout=4000)
            el.click()
            self._jitter(400, 800)
            page.evaluate(f"navigator.clipboard.writeText({json.dumps(text)})")
            self._jitter(200, 400)
            page.keyboard.press("Control+a")
            self._jitter(100, 200)
            page.keyboard.press("Control+v")
            return True
        except Exception:
            return False

    # ── 로그인 ────────────────────────────────────────
    def login(self, naver_id: str, naver_pw: str) -> Tuple[bool, str]:
        """
        헤드리스=False 브라우저를 열어 로그인.
        캡챠/2FA 발생 시 사용자가 직접 처리하고 완료 버튼을 누름.
        """
        if not naver_id or not naver_pw:
            return False, ".env 파일에 NAVER_ID 와 NAVER_PW 를 추가하세요."
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return False, "pip install playwright 후 playwright install chromium 을 실행하세요."

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=self._BROWSER_ARGS,
                    slow_mo=60,
                )
                context = browser.new_context(**self._ctx_opts())
                page = context.new_page()
                self._patch(page)

                page.goto(self.LOGIN_URL, wait_until="networkidle", timeout=20000)
                self._jitter(600, 1200)

                # ID / PW 입력
                self._type_human(page, "#id", naver_id)
                self._jitter(500, 900)
                self._type_human(page, "#pw", naver_pw)
                self._jitter(700, 1400)

                page.locator("#log\\.login").click()
                self._jitter(2500, 4500)

                # 최대 20초 대기 (캡챠/2FA 처리 시간)
                for _ in range(20):
                    if "nid.naver.com" not in page.url:
                        break
                    time.sleep(1)
                else:
                    browser.close()
                    return False, "로그인 시간 초과 — 캡챠나 2FA가 발생했을 수 있습니다."

                self._save_cookies(context)
                browser.close()
                return True, "로그인 완료. 쿠키를 저장했습니다."
        except Exception as e:
            return False, f"로그인 오류: {e}"

    # ── 포스팅 ────────────────────────────────────────
    def post(
        self,
        title: str,
        content: str,
        images: List[str] = [],
        naver_id: str = "",
    ) -> Tuple[bool, str]:
        if not self.can_post():
            return False, f"오늘 발행 한도({self.MAX_DAILY}개) 도달. 내일 다시 시도하세요."
        if not self.is_logged_in():
            return False, "먼저 로그인이 필요합니다."

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return False, "pip install playwright 후 playwright install chromium 을 실행하세요."

        write_url = (
            f"https://blog.naver.com/{naver_id}/postwrite"
            if naver_id else self.WRITE_PATH
        )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,   # 일부 환경에서 headless=True 시 클립보드 차단
                    args=self._BROWSER_ARGS,
                    slow_mo=40,
                )
                context = browser.new_context(**self._ctx_opts())
                self._load_cookies(context)
                page = context.new_page()
                self._patch(page)

                page.goto(write_url, wait_until="networkidle", timeout=30000)
                self._jitter(2500, 4000)

                # 세션 만료 체크
                if "nid.naver.com" in page.url:
                    browser.close()
                    self.clear_login()
                    return False, "로그인 세션 만료 — 다시 로그인하세요."

                page.wait_for_load_state("networkidle")
                self._jitter(2000, 3000)

                # ── 제목 입력 ────────────────────────
                TITLE_SELECTORS = [
                    ".se-title-input",
                    "[placeholder='제목을 입력하세요.']",
                    "[placeholder='제목']",
                    "input[class*='title']",
                    ".blog_title input",
                ]
                for sel in TITLE_SELECTORS:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=2000):
                            el.click()
                            self._jitter(300, 600)
                            page.keyboard.type(title, delay=45)
                            break
                    except Exception:
                        continue

                self._jitter(800, 1500)

                # ── 본문 붙여넣기 ────────────────────
                CONTENT_SELECTORS = [
                    ".se-content .se-component-content",
                    ".se-content",
                    ".se-placeholder",
                    "[contenteditable='true']",
                    ".se-text-paragraph",
                ]
                filled = False
                for sel in CONTENT_SELECTORS:
                    if self._paste_content(page, sel, content):
                        filled = True
                        break

                if not filled:
                    browser.close()
                    return False, "본문 에디터를 찾을 수 없습니다. 셀렉터 업데이트 필요."

                self._jitter(1500, 2500)

                # ── 이미지 업로드 ────────────────────
                IMAGE_BTN_SELECTORS = [
                    "button[data-name='image']",
                    ".se-toolbar-item-image button",
                    "button[title*='이미지']",
                    "button[aria-label*='이미지']",
                ]
                for img_path in images[:5]:
                    try:
                        img_p = Path(img_path)
                        if not img_p.exists():
                            continue
                        for ibtn in IMAGE_BTN_SELECTORS:
                            try:
                                btn = page.locator(ibtn).first
                                if btn.is_visible(timeout=1500):
                                    btn.click()
                                    self._jitter(800, 1500)
                                    break
                            except Exception:
                                continue
                        # 파일 선택
                        fi = page.locator("input[type='file']").last
                        fi.set_input_files(str(img_p))
                        self._jitter(2500, 4000)
                    except Exception:
                        continue

                self._jitter(1000, 2000)

                # ── 발행 ─────────────────────────────
                PUBLISH_SELECTORS = [
                    "button.publish_btn__Y--Ws",
                    "button[class*='publish']",
                    "button:has-text('발행')",
                    ".btn_publish",
                    "#publish-btn",
                ]
                published = False
                for sel in PUBLISH_SELECTORS:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            self._jitter(1500, 2500)
                            # 발행 확인 팝업
                            for csel in ["button:has-text('확인')", "button.confirm", ".btn_confirm"]:
                                try:
                                    cbtn = page.locator(csel).first
                                    if cbtn.is_visible(timeout=1500):
                                        cbtn.click()
                                        self._jitter(500, 1000)
                                        break
                                except Exception:
                                    continue
                            published = True
                            break
                    except Exception:
                        continue

                self._jitter(2000, 3500)
                browser.close()

                if published:
                    self._record_post()
                    cnt = self.today_count()
                    return True, f"발행 완료 · 오늘 {cnt}/{self.MAX_DAILY}개 발행됨"
                else:
                    return False, "발행 버튼을 찾지 못했습니다. 네이버 에디터 버전이 바뀌었을 수 있습니다."

        except Exception as e:
            return False, f"포스팅 중 오류: {e}"
