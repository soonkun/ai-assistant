# Research: HWPX Python 파서 라이브러리

## 질문

1. HWP/HWPX를 Python으로 파싱하는 오픈소스 라이브러리가 있는가?
2. 각 라이브러리의 라이선스는? 사내 오프라인 상업적 사용에 허용되는가?
3. HWPX(XML 기반 신규 포맷)와 HWP(바이너리 구포맷) 각각 지원 여부?
4. 텍스트 추출 외에 페이지 번호·섹션·바운딩 박스 메타데이터도 추출 가능한가?
5. 마지막 커밋 날짜와 활성 유지보수 여부.
6. Docling(IBM)이 HWP/HWPX를 지원하는가?

> **주의:** WebSearch/WebFetch 도구가 이 환경에서 차단되어 학습 지식(컷오프 2025-08) 기반 조사. 미확인 항목은 온라인 환경에서 직접 확인 필요.

---

## 후보 목록

| 라이브러리 | 라이선스 | HWP 지원 | HWPX 지원 | 메타데이터 | 마지막 커밋 | 비고 |
|---|---|---|---|---|---|---|
| pyhwp | AGPL-3.0 | O (바이너리) | 미확인 | 제한적 (텍스트·구조) | 미확인 | 상업 사용 시 AGPL 의무 발생 |
| hwplib (Java) | Apache-2.0 | O | O | 미확인 | 미확인 | Python 바인딩 없음, JVM 필요 |
| Docling (IBM) | Apache-2.0 | X | X | - | 2025년 활성 | HWP/HWPX 공식 미지원 (2025-08 기준) |
| olefile + 직접 파싱 | BSD-2-Clause | 부분 | X | 없음 | N/A | OLE 컨테이너 열기만 가능, 완전 파서 직접 구현 필요 |
| zipfile + lxml (직접) | 표준 라이브러리 | X | 부분 | 미확인 | N/A | HWPX ZIP+XML 직접 파싱, 공수 큼 |

---

## 후보별 상세

### A. pyhwp

- 출처: `https://github.com/mete0r/pyhwp` (접근 미확인, 학습 지식 기반)
- 라이선스: **AGPL-3.0**
  - 네트워크 서비스 제공 없는 사내 오프라인 도구는 소스 공개 의무 경감 가능하나 법무 검토 필요.
- HWP (바이너리 5.0 OLE 구조) 파싱 지원.
- HWPX 지원: **미확인** — pyhwp는 바이너리 HWP 대상으로 설계됨.
- 메타데이터: 텍스트 추출, 단락·섹션 계층 구조 일부 지원. 페이지 번호·바운딩 박스 **미확인**.
  - HWP 계열 포맷 특성상 페이지 레이아웃은 렌더러가 계산하는 구조로, 파서 단에서 바운딩 박스 추출이 근본적으로 어려울 수 있음.
- CLI 도구: `hwp5txt`(텍스트 추출), `hwp5xml`(XML 변환), `hwp5html`(HTML 변환) 동봉.
- 마지막 커밋: **미확인** (PyPI 기준 2010년대 중반 릴리스 이력 있음, 2024~2025 활성 여부 미확인).
- 단점: AGPL 라이선스, 유지보수 불확실, HWPX 미지원 가능성.

### B. hwplib (Java)

- 출처: `https://github.com/neolord0/hwplib` (접근 미확인, 학습 지식 기반)
- 라이선스: **Apache-2.0** (상업적 사용 허용, 소스 공개 의무 없음).
- HWP·HWPX 모두 지원 (Java 생태계에서 가장 완성도 높은 HWP 파서로 알려짐).
- Python에서 사용하려면 JPype, subprocess(jar 호출), 또는 별도 서비스 래퍼 필요.
- 메타데이터 추출 범위: **미확인**.
- 단점: Java 런타임 필수, 오프라인 번들에 JVM 포함 필요, Python 직접 임포트 불가.

### C. Docling (IBM Research)

- 출처: `https://github.com/DS4SD/docling` (접근 미확인, 학습 지식 기반)
- 라이선스: **Apache-2.0**.
- HWP/HWPX 지원: **X** (2025-08 기준 공식 미지원).
- 지원 포맷: PDF, DOCX, PPTX, HTML, XLSX, 이미지 등.
- PDF·DOCX에서는 페이지 번호, 바운딩 박스, 섹션, 테이블 구조 추출 지원 (DoclingDocument 구조).
- HWP 지원 GitHub Issues 요청 존재하나 2025-08 기준 로드맵 미포함.
- **우회 방안**: LibreOffice headless로 HWP→DOCX/PDF 변환 후 Docling으로 처리하는 방식 실용성 **미확인**.

### D. zipfile + lxml (HWPX 직접 파싱)

- HWPX 포맷은 ZIP 컨테이너 내 XML 파일들의 묶음 (OOXML 계열과 유사).
- Python 표준 라이브러리(`zipfile`, `xml.etree`) 또는 `lxml`으로 직접 파싱 가능.
- 라이선스 문제 없음 (표준 라이브러리).
- 텍스트 추출: XML 태그 분석으로 가능.
- 바운딩 박스: HWPX XML 스펙에 레이아웃 좌표 포함 여부 **미확인** (HWP 계열은 렌더러가 페이지 분할 계산하는 구조상 어려울 가능성 있음).
- 단점: 한글과컴퓨터 HWPX 공개 스펙 문서 완성도 및 접근성 **미확인**. 구현 공수 큼.

---

## HWPX vs HWP 포맷 구조

| 항목 | HWP 5.0 (구포맷) | HWPX (신포맷) |
|---|---|---|
| 컨테이너 | OLE2 복합 문서 | ZIP 압축 |
| 인코딩 | 바이너리 | XML |
| 페이지 레이아웃 | 렌더러 계산 | 렌더러 계산 (동일) |
| Python 접근 | olefile, pyhwp | zipfile + lxml |

---

## 미해결 의문

1. pyhwp GitHub 최신 커밋 날짜 및 HWPX 지원 여부 (`https://github.com/mete0r/pyhwp`).
2. hwplib Python 래퍼 존재 여부 (`https://github.com/neolord0/hwplib`).
3. Docling HWP 지원 로드맵 추가 여부 (`https://github.com/DS4SD/docling/issues`).
4. HWPX XML 스펙에서 페이지 번호·섹션 정보의 정확한 XML 태그 구조.
5. AGPL-3.0이 사내 오프라인 도구에 적용될 때 법적 의무 범위 (법무 검토 필요).
6. LibreOffice headless를 통한 HWP→PDF/DOCX 변환 후 Docling 처리 우회 방식 실용성.

---

## 참조 링크·파일

- `https://github.com/mete0r/pyhwp` (접근 미확인)
- `https://github.com/neolord0/hwplib` (접근 미확인)
- `https://github.com/DS4SD/docling` (접근 미확인)
- `/mnt/c/projects/ai-assistant/REQUIREMENTS.md:26-27` — §2.1 지원 포맷 HWP/HWPX 명시
- `/mnt/c/projects/ai-assistant/docs/GAP_ANALYSIS.md` — N01 문서 파싱 NEW 분류
