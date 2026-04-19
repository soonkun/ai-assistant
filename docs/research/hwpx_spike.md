# Spike: HWPX 파싱 검증

## 환경
- 파싱 방식: Python 표준 라이브러리 `zipfile` + `xml.etree.ElementTree`
- LibreOffice: 불필요 (회사 환경이 HWPX 전용 — 구포맷 HWP 미사용)
- 테스트 샘플: 3종 직접 생성 (회의록, 정책문서, 보고서)

## 결과 요약

| 파일 | 섹션 수 | 단락 수 | 텍스트 추출 | 판정 |
|---|---|---|---|---|
| sample1_meeting.hwpx | 1 | 4 | O | PASS |
| sample2_policy.hwpx | 1 | 3 | O | PASS |
| sample3_report.hwpx | 1 | 5 | O | PASS |

**전체: 3/3 PASS**

## 추출 텍스트 샘플

**sample1_meeting.hwpx**:
- `일시: 2026년 4월 18일 오전 10시`
- `참석자: 김철수, 이영희, 박민준`
- `안건 1: 1분기 실적 검토`
- `결론: 목표 대비 105% 달성. 2분기 목표 상향 조정.`

**sample2_policy.hwpx**:
- `제1조 목적: 본 정책은 사내 정보 보안을 강화하기 위함이다.`
- `제2조 적용 범위: 전 임직원 및 협력업체 직원에게 적용된다.`
- `제3조 비밀번호 정책: 비밀번호는 90일마다 변경해야 한다.`

## HWPX 파싱 전략 (확정)

HWPX는 ZIP 컨테이너 + XML 구조이므로 외부 도구 없이 직접 파싱 가능하다.

```python
import zipfile
from xml.etree import ElementTree as ET

NS = {"hp": "urn:hancom:names:tc:opendocument:xmlns:paragraph:1.0"}

with zipfile.ZipFile("doc.hwpx") as z:
    sections = sorted(n for n in z.namelist() if n.startswith("Contents/section"))
    for sec in sections:
        root = ET.fromstring(z.read(sec).decode("utf-8"))
        for para in root.findall(".//hp:p", NS):
            text = "".join(t.text for t in para.findall(".//hp:t", NS) if t.text)
```

## 결정 변경 (원래 결정 2 갱신)

| 항목 | 원래 결정 | 갱신 결정 |
|---|---|---|
| HWPX 읽기 (RAG) | LibreOffice headless → PDF → PyMuPDF | **zipfile + lxml 직접 파싱** |
| HWP 구포맷 지원 | LibreOffice h2orestart | **불필요 — 회사 환경 HWPX 전용** |
| LibreOffice 의존성 | 필수 | **제거** |

LibreOffice는 M_03 스펙에서 제외한다. 의존성 1개 감소.

## 미확인 사항
- 실제 한글과컴퓨터 작성 HWPX의 XML 네임스페이스가 테스트 파일과 동일한지 검증 필요
- 표·그림·머리글/바닥글 포함 복잡한 문서의 파싱 완성도 미확인
- 바운딩 박스(페이지 좌표): HWPX 구조상 렌더러가 계산하는 방식이라 파서 단에서 추출 어려움 — RAG에서는 단락 인덱스로 대체

## 참조
- `tests/fixtures/hwpx/` — 테스트 샘플 3종
- `REQUIREMENTS.md §2.1` — HWP/HWPX 파싱 요구사항
