"""
블로그 글 → 네이버 블로그용 HTML 변환
"""
import re


def to_naver_html(text: str) -> str:
    """마크다운 스타일 블로그 글을 네이버 블로그 붙여넣기용 HTML로 변환"""
    lines = text.split("\n")
    html_lines = []
    in_table = False
    in_list = False
    table_rows = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # ── 마크다운 표 처리 ─────────────────────────────
        if stripped.startswith("|") and stripped.endswith("|"):
            if not in_table:
                in_table = True
                table_rows = []
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            table_rows.append(cells)
            # 구분선 행이면 건너뜀
            if all(re.match(r"^[-:]+$", c) for c in cells):
                table_rows.pop()
            continue
        else:
            if in_table:
                html_lines.append(_render_table(table_rows))
                table_rows = []
                in_table = False

        # ── 목록 처리 ────────────────────────────────────
        if stripped.startswith("- ") or stripped.startswith("✔") or stripped.startswith("✅") or stripped.startswith("⚠️"):
            if not in_list:
                html_lines.append('<ul style="margin:8px 0; padding-left:20px;">')
                in_list = True
            content = _inline(stripped.lstrip("-✔✅⚠️ ").strip())
            html_lines.append(f'  <li style="margin:4px 0;">{content}</li>')
            continue
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False

        # ── 제목 처리 ────────────────────────────────────
        if stripped.startswith("# "):
            html_lines.append(f'<h2 style="font-size:22px;font-weight:800;color:#1a1a1a;margin:24px 0 12px;">{_inline(stripped[2:])}</h2>')
            continue
        if stripped.startswith("## "):
            html_lines.append(f'<h3 style="font-size:18px;font-weight:700;color:#1a1a1a;margin:20px 0 10px;">{_inline(stripped[3:])}</h3>')
            continue
        if stripped.startswith("### "):
            html_lines.append(f'<h4 style="font-size:16px;font-weight:700;color:#333;margin:16px 0 8px;">{_inline(stripped[4:])}</h4>')
            continue

        # ── **굵은 줄** 단독 소제목 처리 ────────────────
        if re.match(r"^\*\*[^*]+\*\*$", stripped):
            title = stripped.strip("*")
            html_lines.append(f'<p style="font-size:16px;font-weight:700;color:#1a1a1a;margin:18px 0 6px;">{title}</p>')
            continue

        # ── 이미지 플레이스홀더 ──────────────────────────
        if re.match(r"^\[이미지\d+\]", stripped):
            n = re.search(r"\d+", stripped).group()
            html_lines.append(
                f'<div style="background:#f5f5f5;border:2px dashed #ccc;'
                f'height:220px;display:flex;align-items:center;justify-content:center;'
                f'border-radius:8px;margin:16px 0;color:#999;font-size:14px;">'
                f'📷 이미지 {n} 삽입 위치</div>'
            )
            continue

        # ── 구분선 ───────────────────────────────────────
        if stripped in ("---", "***", "___"):
            html_lines.append('<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">')
            continue

        # ── 해시태그 줄 ──────────────────────────────────
        if stripped.startswith("#") and " #" in stripped:
            tags = re.findall(r"#\S+", stripped)
            tag_html = " ".join(
                f'<span style="display:inline-block;background:#f0faf4;color:#03C75A;'
                f'padding:2px 8px;border-radius:12px;font-size:12px;margin:2px;">{t}</span>'
                for t in tags
            )
            html_lines.append(f'<div style="margin:16px 0 4px;">{tag_html}</div>')
            continue

        # ── 빈 줄 ────────────────────────────────────────
        if not stripped:
            html_lines.append('<div style="height:10px;"></div>')
            continue

        # ── 일반 문단 ────────────────────────────────────
        html_lines.append(
            f'<p style="font-size:15px;line-height:1.85;color:#1a1a1a;margin:0 0 10px;">'
            f'{_inline(stripped)}</p>'
        )

    # 닫힌 태그 마무리
    if in_list:
        html_lines.append("</ul>")
    if in_table:
        html_lines.append(_render_table(table_rows))

    wrapper = (
        '<div style="font-family:\'Noto Sans KR\',\'맑은 고딕\',sans-serif;'
        'max-width:720px;margin:0 auto;padding:8px;">\n'
        + "\n".join(html_lines)
        + "\n</div>"
    )
    return wrapper


def _inline(text: str) -> str:
    """인라인 마크다운 변환 (**bold**, `code`, [link](url))"""
    # 굵은 글씨
    text = re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', text)
    text = re.sub(r"__(.+?)__",     r'<strong>\1</strong>', text)
    # 기울임
    text = re.sub(r"\*(.+?)\*",     r'<em>\1</em>', text)
    # 링크
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" target="_blank" style="color:#03C75A;">\1</a>',
        text,
    )
    # 코드
    text = re.sub(r"`(.+?)`", r'<code style="background:#f5f5f5;padding:1px 4px;border-radius:3px;">\1</code>', text)
    return text


def _render_table(rows: list) -> str:
    if not rows:
        return ""
    html = (
        '<table style="width:100%;border-collapse:collapse;'
        'margin:16px 0;font-size:14px;">'
    )
    for r_idx, row in enumerate(rows):
        html += "<tr>"
        for cell in row:
            if r_idx == 0:
                html += (
                    f'<th style="background:#f5f5f5;border:1px solid #ddd;'
                    f'padding:8px 12px;text-align:left;font-weight:700;">{_inline(cell)}</th>'
                )
            else:
                html += (
                    f'<td style="border:1px solid #ddd;padding:8px 12px;">{_inline(cell)}</td>'
                )
        html += "</tr>"
    html += "</table>"
    return html
