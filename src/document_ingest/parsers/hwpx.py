# src/document_ingest/parsers/hwpx.py
"""HWPX 파서 — zipfile + xml.etree.ElementTree (M_06 스펙 §5.4).

네임스페이스 2종 모두 시도:
  hp  = http://www.hancom.co.kr/hwpml/2011/paragraph
  hp10 = http://www.hancom.co.kr/hwpml/2016/paragraph
"""

from __future__ import annotations

import logging
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from document_ingest.errors import IngestIOError, ParseError
from document_ingest.segments import _Segment

logger = logging.getLogger(__name__)

# 실제 한글과컴퓨터가 생성하는 파일의 네임스페이스 (스펙 §5.4, §15.4)
HWPX_NS: dict[str, str] = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
}

# ZIP 해제 후 최대 허용 크기 (1 GB) — A-2 ZIP 폭탄 방어 (스펙 §11.4 A-2)
_MAX_DECOMPRESSED_BYTES: int = 1024 * 1024 * 1024  # 1 GB


def _parse_hwpx(path: str) -> list[_Segment]:
    """HWPX 파일에서 섹션 단위 텍스트 세그먼트를 추출한다.

    - 2011 네임스페이스 시도 → 0건이면 2016 fallback.
    - section: 섹션 XML 파일명 (Contents/section0.xml 등).
    - page: None (렌더러가 계산, 스펙 §5.4).
    - 2종 모두 match 0건 → ParseError.

    Args:
        path: 절대 또는 상대 경로 문자열.

    Returns:
        list[_Segment]

    Raises:
        ParseError: 네임스페이스 match 0건, ZIP 손상, XML 파싱 실패.
        IngestIOError: ZIP 해제 크기가 1GB 초과.
    """
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ParseError(f"HWPX ZIP 열기 실패: {Path(path).name}: {exc}") from exc
    except Exception as exc:
        raise ParseError(f"HWPX 파일 오류: {Path(path).name}: {exc}") from exc

    segments: list[_Segment] = []

    with zf:
        section_names = sorted(
            n for n in zf.namelist() if n.startswith("Contents/section") and n.endswith(".xml")
        )

        if not section_names:
            raise ParseError(
                f"HWPX에서 Contents/section*.xml을 찾을 수 없습니다: {Path(path).name}"
            )

        for sec_name in section_names:
            # A-2: ZIP 폭탄 방어 — 해제 전 크기 체크
            try:
                info = zf.getinfo(sec_name)
            except KeyError:
                continue

            if info.file_size > _MAX_DECOMPRESSED_BYTES:
                raise IngestIOError(
                    f"decompressed size exceeds limit: {info.file_size} bytes > 1GB "
                    f"({sec_name} in {Path(path).name})"
                )

            try:
                xml_bytes = zf.read(sec_name)
            except Exception as exc:
                raise ParseError(
                    f"HWPX 섹션 읽기 실패: {sec_name} in {Path(path).name}: {exc}"
                ) from exc

            try:
                root = ET.fromstring(xml_bytes)
            except ET.ParseError as exc:
                raise ParseError(
                    f"HWPX XML 파싱 실패: {sec_name} in {Path(path).name}: {exc}"
                ) from exc

            # 2011 네임스페이스 시도
            paragraphs = root.findall(".//hp:p", HWPX_NS)
            ns_used = "hp"

            # 0건이면 2016 fallback
            if not paragraphs:
                paragraphs = root.findall(".//hp10:p", HWPX_NS)
                ns_used = "hp10"

            logger.debug(
                "HWPX 섹션 %s: ns_used=%s, 단락=%d건",
                sec_name,
                ns_used,
                len(paragraphs),
            )

            for p in paragraphs:
                # 해당 네임스페이스의 <t> 텍스트 노드 수집
                if ns_used == "hp":
                    runs = p.findall(".//hp:t", HWPX_NS)
                else:
                    runs = p.findall(".//hp10:t", HWPX_NS)

                text = "".join(t.text or "" for t in runs).strip()
                if text:
                    segments.append(
                        _Segment(
                            text=text,
                            page=None,
                            section=sec_name,
                            bbox=None,
                        )
                    )

    if not segments:
        raise ParseError(f"hwpx: no paragraphs found under known namespaces: {Path(path).name}")

    return segments
