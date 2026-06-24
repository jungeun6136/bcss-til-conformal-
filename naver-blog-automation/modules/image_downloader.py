import os
import requests
import re
from pathlib import Path
from typing import List
from urllib.parse import urlparse


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.naver.com/",
}


class ImageDownloader:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_images(self, image_urls: List[str], prefix: str = "product") -> List[str]:
        """이미지 URL 목록을 다운로드하고 저장된 경로 반환"""
        saved_paths = []
        valid_urls = [url for url in image_urls if url and url.startswith("http")]

        for i, url in enumerate(valid_urls[:8], 1):
            ext = self._get_extension(url)
            filename = f"{prefix}_{i:02d}{ext}"
            save_path = self.output_dir / filename

            if self._download_single(url, save_path):
                saved_paths.append(str(save_path))
                print(f"  [이미지] 저장 완료: {filename}")
            else:
                print(f"  [이미지] 다운로드 실패: {url[:50]}...")

        return saved_paths

    def _download_single(self, url: str, save_path: Path) -> bool:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15, stream=True)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type and "octet-stream" not in content_type:
                return False

            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            # 최소 크기 체크 (너무 작으면 아이콘이나 오류 이미지)
            if save_path.stat().st_size < 5000:
                save_path.unlink(missing_ok=True)
                return False

            return True
        except Exception:
            return False

    def _get_extension(self, url: str) -> str:
        path = urlparse(url).path.lower()
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
            if path.endswith(ext):
                return ext if ext != ".jpeg" else ".jpg"
        return ".jpg"

    def generate_image_guide(self, saved_paths: List[str]) -> str:
        """글 작성 시 이미지 삽입 가이드 생성"""
        if not saved_paths:
            return "\n[이미지 없음 - 직접 제품 이미지를 추가해주세요]\n"

        lines = ["\n" + "=" * 50]
        lines.append("📸 이미지 삽입 가이드")
        lines.append("=" * 50)
        lines.append(f"총 {len(saved_paths)}개 이미지가 images/ 폴더에 저장되었습니다.")
        lines.append("")
        for i, path in enumerate(saved_paths, 1):
            filename = Path(path).name
            lines.append(f"  [{i}번 이미지] → {filename}")
        lines.append("")
        lines.append("글에서 [이미지1], [이미지2] 표시된 자리에 순서대로 삽입하세요.")
        lines.append("=" * 50 + "\n")
        return "\n".join(lines)
