import requests
import re
from bs4 import BeautifulSoup
from typing import Dict, Optional
from urllib.parse import urlparse, urljoin


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class ProductScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def scrape_product_from_url(self, url: str) -> Dict:
        """Brand Connect URL이나 제품 URL에서 정보 추출"""
        print(f"  [스크래핑] URL 분석 중: {url[:60]}...")

        # URL 추적 (리다이렉트 따라가기)
        final_url = self._follow_redirects(url)
        domain = urlparse(final_url).netloc

        if "smartstore.naver.com" in domain or "brand.naver.com" in domain:
            return self._scrape_naver_smartstore(final_url)
        elif "coupang.com" in domain:
            return self._scrape_coupang(final_url)
        elif "auction.co.kr" in domain or "gmarket.co.kr" in domain:
            return self._scrape_gmarket_auction(final_url)
        else:
            return self._scrape_generic(final_url)

    def search_product_on_naver(self, product_name: str) -> Dict:
        """네이버쇼핑에서 제품 검색하여 정보 수집"""
        print(f"  [검색] 네이버쇼핑에서 '{product_name}' 검색 중...")
        search_url = f"https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={requests.utils.quote(product_name)}"

        try:
            resp = self.session.get(search_url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")

            product_info = {
                "name": product_name,
                "price": self._extract_price_from_search(soup),
                "specs": self._extract_specs_from_search(soup),
                "description": self._extract_description_from_search(soup),
                "images": self._extract_images_from_search(soup),
                "rating": "",
                "review_count": "",
                "source_url": search_url,
            }
            return product_info
        except Exception as e:
            print(f"  [경고] 네이버 검색 실패: {e}")
            return self._empty_product(product_name)

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

            name = self._text(soup.select_one("h3.se_textarea, ._1eddO7u4UC, [class*='productTitle']"))
            price = self._text(soup.select_one("[class*='price'], [class*='Price'], strong.price"))
            price = re.sub(r"[^\d,]", "", price) if price else ""

            description_tags = soup.select("[class*='description'], [class*='detail'], p")
            description = " ".join(
                t.get_text(strip=True) for t in description_tags[:5] if len(t.get_text(strip=True)) > 20
            )

            images = [
                img.get("src", img.get("data-src", ""))
                for img in soup.select("img[src*='pstatic'], img[src*='naver']")
                if img.get("src") or img.get("data-src")
            ]

            return {
                "name": name or url.split("/")[-1],
                "price": price,
                "specs": {},
                "description": description[:500],
                "images": images[:5],
                "rating": "",
                "review_count": "",
                "source_url": url,
            }
        except Exception as e:
            print(f"  [경고] 스마트스토어 스크래핑 실패: {e}")
            return self._empty_product(url)

    def _scrape_coupang(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")

            name = self._text(soup.select_one("h2.prod-buy-header__title, [class*='product-title']"))
            price = self._text(soup.select_one("[class*='total-price'], strong.final-price"))
            price = re.sub(r"[^\d,]", "", price) if price else ""

            specs = {}
            spec_table = soup.select("table.prod-attr-table tr, [class*='spec'] tr")
            for row in spec_table[:10]:
                cells = row.select("th, td")
                if len(cells) >= 2:
                    specs[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)

            images = [
                img.get("src", "")
                for img in soup.select("[class*='prod-image'] img, #productImage img")
                if img.get("src", "").startswith("http")
            ]

            return {
                "name": name or "",
                "price": price,
                "specs": specs,
                "description": "",
                "images": images[:5],
                "rating": self._text(soup.select_one("[class*='rating-star']")),
                "review_count": self._text(soup.select_one("[class*='count-rvw']")),
                "source_url": url,
            }
        except Exception as e:
            print(f"  [경고] 쿠팡 스크래핑 실패: {e}")
            return self._empty_product(url)

    def _scrape_gmarket_auction(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            name = self._text(soup.select_one("h1, [class*='itemtit'], [class*='item-title']"))
            price = self._text(soup.select_one("[class*='price'], [id*='price']"))
            price = re.sub(r"[^\d,]", "", price) if price else ""
            images = [
                img.get("src", "")
                for img in soup.select("[class*='image'] img")
                if img.get("src", "").startswith("http")
            ]
            return {
                "name": name or "",
                "price": price,
                "specs": {},
                "description": "",
                "images": images[:5],
                "rating": "",
                "review_count": "",
                "source_url": url,
            }
        except Exception as e:
            print(f"  [경고] G마켓/옥션 스크래핑 실패: {e}")
            return self._empty_product(url)

    def _scrape_generic(self, url: str) -> Dict:
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")

            # OG 태그에서 정보 추출 (대부분의 쇼핑몰이 지원)
            og_title = soup.find("meta", property="og:title")
            og_desc = soup.find("meta", property="og:description")
            og_image = soup.find("meta", property="og:image")

            name = og_title["content"] if og_title else self._text(soup.select_one("h1"))
            description = og_desc["content"] if og_desc else ""
            images = [og_image["content"]] if og_image and og_image.get("content") else []

            # 추가 이미지
            for img in soup.select("img"):
                src = img.get("src", "")
                if src.startswith("http") and len(src) > 10:
                    images.append(src)

            return {
                "name": name or url,
                "price": "",
                "specs": {},
                "description": description[:500],
                "images": images[:5],
                "rating": "",
                "review_count": "",
                "source_url": url,
            }
        except Exception as e:
            print(f"  [경고] 일반 스크래핑 실패: {e}")
            return self._empty_product(url)

    def _extract_price_from_search(self, soup) -> str:
        el = soup.select_one("[class*='price']")
        if el:
            return re.sub(r"[^\d,]", "", el.get_text(strip=True))
        return ""

    def _extract_specs_from_search(self, soup) -> Dict:
        specs = {}
        for row in soup.select("table tr")[:8]:
            cells = row.select("th, td")
            if len(cells) >= 2:
                specs[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)
        return specs

    def _extract_description_from_search(self, soup) -> str:
        desc_el = soup.select_one("[class*='description'], [class*='summary']")
        return desc_el.get_text(strip=True)[:500] if desc_el else ""

    def _extract_images_from_search(self, soup) -> list:
        imgs = []
        for img in soup.select("img"):
            src = img.get("src", img.get("data-src", ""))
            if src and src.startswith("http"):
                imgs.append(src)
        return imgs[:5]

    def _text(self, el) -> str:
        return el.get_text(strip=True) if el else ""

    def _empty_product(self, name: str) -> Dict:
        return {
            "name": name,
            "price": "",
            "specs": {},
            "description": "",
            "images": [],
            "rating": "",
            "review_count": "",
            "source_url": "",
        }
