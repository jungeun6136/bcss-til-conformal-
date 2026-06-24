import requests
import re
from bs4 import BeautifulSoup
from typing import Dict, List
from urllib.parse import urlparse, quote


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 설명에서 걸러낼 광고/네비게이션 키워드
NOISE_PATTERNS = [
    "로그인", "회원가입", "장바구니", "배송비", "적립금", "쿠폰",
    "KT", "SKT", "LG유플러스", "인터넷", "TV 결합", "당일개통",
    "이벤트", "혜택", "shop.kt", "naver.com", "copyright",
    "고객센터", "서비스 이용약관", "개인정보",
]


def _is_noise(text: str) -> bool:
    if len(text) < 15 or len(text) > 400:
        return True
    return any(kw in text for kw in NOISE_PATTERNS)


class ProductScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def research_product(self, url: str, keyword: str) -> Dict:
        """
        Brand Connect URL + 키워드로 제품 정보 수집.
        네이버 쇼핑 검색을 메인으로, URL 스크래핑을 보조로 사용.
        """
        result = self._empty_product(keyword)

        # 1차: 네이버 쇼핑에서 검색 (가장 신뢰도 높음)
        naver_info = self._search_naver_shopping(keyword)
        self._merge(result, naver_info)

        # 2차: URL에서 추가 정보 수집
        url_info = self._scrape_from_url(url)
        self._merge(result, url_info)

        # 3차: 스펙 정보가 부족하면 "{키워드} 스펙" 추가 검색
        if len(result.get("specs", {})) < 3:
            spec_info = self._search_naver_shopping(f"{keyword} 스펙 성능")
            if spec_info.get("specs"):
                result["specs"].update(spec_info["specs"])

        # 설명 정제
        result["description"] = self._clean_description(result.get("description", ""))

        return result

    # ── 네이버 쇼핑 검색 (핵심) ────────────────────────
    def _search_naver_shopping(self, query: str) -> Dict:
        """search.shopping.naver.com 에서 제품 정보 수집"""
        try:
            url = f"https://search.shopping.naver.com/search/all?query={quote(query)}"
            resp = self.session.get(url, timeout=12)
            soup = BeautifulSoup(resp.text, "lxml")

            # ── 제품명 ──
            name_el = soup.select_one(
                "div.basicList_title__xCSyB, "
                "strong.basicList_name__WqGRC, "
                "a[class*='basicList_link']"
            )
            name = name_el.get_text(strip=True) if name_el else ""

            # ── 가격 (최저가) ──
            price_el = soup.select_one(
                "span.basicList_price_sell__UuHRB strong, "
                "strong[class*='price_num'], "
                "em[class*='price']"
            )
            price = re.sub(r"[^\d,]", "", price_el.get_text()) if price_el else ""

            # 가격 범위 여러 개 수집해서 평균 계산
            price_els = soup.select("span.basicList_price_sell__UuHRB strong")[:5]
            if price_els:
                prices = []
                for pe in price_els:
                    p = re.sub(r"[^\d]", "", pe.get_text())
                    if p.isdigit() and int(p) > 1000:
                        prices.append(int(p))
                if prices:
                    avg_price = sum(prices) // len(prices)
                    price = f"{avg_price:,}"

            # ── 평점 ──
            rating_el = soup.select_one(
                "span[class*='starScore'], "
                "em[class*='rating'], "
                "span[class*='grade_num']"
            )
            rating = rating_el.get_text(strip=True) if rating_el else ""
            rating = re.sub(r"[^\d.]", "", rating)

            # ── 리뷰 수 ──
            review_el = soup.select_one(
                "span[class*='reviewCount'], "
                "em[class*='review'], "
                "a[class*='review']"
            )
            review_count = ""
            if review_el:
                review_count = re.sub(r"[^\d,]", "", review_el.get_text())

            # ── 제품 설명 ──
            desc_candidates = []
            for el in soup.select(
                "div.basicList_detail_box__OoXKt p, "
                "div[class*='desc'], "
                "p[class*='detail']"
            )[:8]:
                t = el.get_text(strip=True)
                if not _is_noise(t):
                    desc_candidates.append(t)
            description = " ".join(desc_candidates[:3])

            # ── 스펙 ──
            specs = {}
            for row in soup.select("dl[class*='spec'] dt, table tr")[:12]:
                cells = row.select("th, td, dt, dd")
                if len(cells) >= 2:
                    k = cells[0].get_text(strip=True)
                    v = cells[1].get_text(strip=True)
                    if k and v and len(k) < 25 and not _is_noise(k):
                        specs[k] = v

            # ── 이미지 ──
            images = []
            for img in soup.select("img[class*='basicList_thumb'], img[class*='product']"):
                src = img.get("src") or img.get("data-src") or ""
                if src.startswith("http") and "pstatic" in src:
                    images.append(src)

            return {
                "name": name,
                "price": price,
                "description": description,
                "specs": specs,
                "images": images[:8],
                "rating": rating,
                "review_count": review_count,
                "source_url": url,
            }
        except Exception as e:
            print(f"[쇼핑 검색 실패] {e}")
            return self._empty_product("")

    # ── URL 스크래핑 (보조) ─────────────────────────
    def _scrape_from_url(self, url: str) -> Dict:
        try:
            final_url = self._follow_redirects(url)
            domain = urlparse(final_url).netloc
            if "smartstore.naver.com" in domain or "brand.naver.com" in domain:
                return self._scrape_naver_smartstore(final_url)
            elif "coupang.com" in domain:
                return self._scrape_coupang(final_url)
            else:
                return self._scrape_og_tags(final_url)
        except Exception:
            return self._empty_product("")

    def _follow_redirects(self, url: str) -> str:
        try:
            resp = self.session.head(url, allow_redirects=True, timeout=10)
            return resp.url
        except Exception:
            return url

    def _scrape_naver_smartstore(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            name = self._text(soup.select_one(
                "h3.se_textarea, ._1eddO7u4UC, [class*='productTitle'], h1"
            ))
            price = re.sub(r"[^\d,]", "", self._text(
                soup.select_one("[class*='price'], strong.price")
            ))
            specs = self._extract_spec_table(soup)
            images = [
                img.get("src") or img.get("data-src", "")
                for img in soup.select("img")
                if (img.get("src") or img.get("data-src", "")).startswith("http")
                and "pstatic" in (img.get("src") or img.get("data-src", ""))
            ]
            desc_tags = soup.select("[class*='description'], [class*='detail']")
            desc = " ".join(
                t.get_text(strip=True) for t in desc_tags[:4]
                if not _is_noise(t.get_text(strip=True))
            )
            return {
                "name": name, "price": price, "description": desc,
                "specs": specs, "images": images[:8],
                "rating": "", "review_count": "", "source_url": url,
            }
        except Exception:
            return self._empty_product("")

    def _scrape_coupang(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            name = self._text(soup.select_one(
                "h2.prod-buy-header__title, [class*='product-title']"
            ))
            price = re.sub(r"[^\d,]", "", self._text(
                soup.select_one("[class*='total-price'], strong.final-price")
            ))
            specs = self._extract_spec_table(soup)
            images = [
                img.get("src", "")
                for img in soup.select("[class*='prod-image'] img")
                if img.get("src", "").startswith("http")
            ]
            return {
                "name": name, "price": price, "description": "",
                "specs": specs, "images": images[:8],
                "rating": self._text(soup.select_one("[class*='rating-star']")),
                "review_count": self._text(soup.select_one("[class*='count-rvw']")),
                "source_url": url,
            }
        except Exception:
            return self._empty_product("")

    def _scrape_og_tags(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            og_title = soup.find("meta", property="og:title")
            og_desc  = soup.find("meta", property="og:description")
            og_image = soup.find("meta", property="og:image")
            name  = og_title["content"] if og_title else ""
            desc  = og_desc["content"]  if og_desc  else ""
            imgs  = [og_image["content"]] if og_image and og_image.get("content") else []
            specs = self._extract_spec_table(soup)
            if _is_noise(desc):
                desc = ""
            return {
                "name": name, "price": "", "description": desc[:400],
                "specs": specs, "images": imgs,
                "rating": "", "review_count": "", "source_url": url,
            }
        except Exception:
            return self._empty_product("")

    # ── 헬퍼 ────────────────────────────────────────
    def _extract_spec_table(self, soup) -> Dict:
        specs = {}
        for row in soup.select("table tr")[:15]:
            cells = row.select("th, td")
            if len(cells) >= 2:
                k = cells[0].get_text(strip=True)
                v = cells[1].get_text(strip=True)
                if k and v and len(k) < 25 and not _is_noise(k):
                    specs[k] = v
        for dt, dd in zip(soup.select("dt")[:10], soup.select("dd")[:10]):
            k = dt.get_text(strip=True)
            v = dd.get_text(strip=True)
            if k and v and len(k) < 25 and not _is_noise(k):
                specs[k] = v
        return specs

    def _clean_description(self, text: str) -> str:
        """광고/네비게이션 노이즈 제거 후 깨끗한 설명 반환"""
        if not text:
            return ""
        sentences = re.split(r"[.!?]\s*", text)
        clean = [s.strip() for s in sentences if s.strip() and not _is_noise(s.strip())]
        return ". ".join(clean[:5])

    def _merge(self, base: Dict, new: Dict):
        for field in ["name", "price", "description", "rating", "review_count", "source_url"]:
            if not base.get(field) and new.get(field):
                base[field] = new[field]
        if not base.get("specs"):
            base["specs"] = new.get("specs", {})
        elif new.get("specs"):
            for k, v in new["specs"].items():
                if k not in base["specs"]:
                    base["specs"][k] = v
        existing = set(base.get("images", []))
        for img in new.get("images", []):
            if img not in existing:
                base.setdefault("images", []).append(img)
                existing.add(img)
        base["images"] = base.get("images", [])[:10]

    def _text(self, el) -> str:
        return el.get_text(strip=True) if el else ""

    def _empty_product(self, name: str) -> Dict:
        return {
            "name": name, "price": "", "specs": {},
            "description": "", "images": [],
            "rating": "", "review_count": "", "source_url": "",
        }
