# RISKS — 사내 오프라인 AI 비서

Phase 1 Planner 산출물. 현재 시점(2026-04-18)까지 확인된 리스크를 모두 기록하고 완화 방안을 함께 명시한다. 구현 중 새로 발견되는 리스크는 본 문서에 append-only로 추가한다(삭제 금지, 상태만 갱신).

- 심각도: **HIGH**(스펙 불충족 또는 기동 실패 가능), **MEDIUM**(성능 저하·UX 열화), **LOW**(보완 가능 여지 큼).
- 상태: OPEN, MITIGATING, ACCEPTED, CLOSED.

---

## R-01 CPU 추론 지연이 §9 "2초 이내" 목표를 위배한다 (HIGH, OPEN)

- **증상**: `docs/research/gemma_function_calling_spike.md` 관측치 기준 `gemma4:e4b`의 CPU-only 단일 쿼리 응답 시간은 **17~80초**. REQUIREMENTS.md §9는 "발화 끝 → AI 첫 음성 2초 이내"를 목표로 명시.
- **원인**: 4B 파라미터 모델 CPU 추론은 토큰당 수십 ms 수준이어서 TTFT가 10초를 초과. GPU가 없으면 회피 불가.
- **영향 범위**: 음성 대화(§1.1), 일정 등록(§4), RAG(§2.2), 프로액티브 발화 모두.
- **완화 방안**
  1. GPU 보유 여부를 기동 시 감지하고, GPU 없으면 UI에서 "CPU 모드(응답 지연 있음)" 뱃지를 상시 표출.
  2. "생각 중…" 자막을 즉시 송출해 체감 지연을 줄인다(실지연은 바뀌지 않음).
  3. `faster_first_response=True`로 첫 문장 TTS 시작을 조기화(upstream 옵션 그대로).
  4. V2에서 양자화(Q4_K_M, IQ3 등) 도입 또는 더 작은 모델(Gemma 4 E2B 가정) 교체 검토 — V1 범위 밖.
  5. 성능 SLA 문서에 "2초 이내 목표는 GPU 환경(NVIDIA 8GB+) 한정" 단서를 명기하는 변경요청을 사용자에게 제안.
- **담당**: M_05 LLMAgent 스펙 작성 시 SLA 명시.

## R-02 MIN 프로파일(16GB RAM)에서 상주 메모리가 여유분을 초과할 수 있다 (MEDIUM, MITIGATING)

> **2026-04-18 갱신**: 하드웨어 프로파일 도입(ARCHITECTURE.md §6.0)으로 리스크 범위를 재조정.
> RECOMMENDED 프로파일(32GB RAM)에서는 ~13.6 GB → 여유 18 GB 이상으로 리스크 없음.
> 본 리스크는 **MIN 프로파일(16GB RAM)에만 해당**.

- **증상**: MIN 프로파일 상주 예산 ~12.6 GB (Whisper medium 기준). 배경 앱(Teams, Slack 등) 포함 시 16 GB 중 여유 ~3.4 GB만 남음.
- **원인**: Gemma 4 E4B(8.5 GB) + BGE-M3(2.2 GB) + Whisper medium(0.6 GB) + 기타 컴포넌트의 동시 상주.
- **영향 범위**: MIN 프로파일(개발 노트북) 한정. RECOMMENDED 프로파일 불해당.
- **완화 방안 (MIN 프로파일 전용, 우선순위 순)**
  1. Ollama `keep_alive=300` (5분)으로 무대화 시 모델 언로드 → 상시 ~4 GB 수준. 첫 응답 재로딩 10~20초 비용 수용.
  2. XTTS v2 기본 OFF 유지. 옵트인 시 +1.8 GB(총 ~14.4 GB).
  3. BGE-M3 int8 양자화 버전(약 570 MB) 교체 가능성 조사 — 한국어 성능 저하 수치 필요(R-07 연계).
  4. 메모리 상한 초과 시 경고 UI 표출("메모리 부족 — 불필요한 앱을 종료하세요").
- **담당**: M_01 AppCore 스펙에 `psutil` 기반 메모리 감시기 포함. 피크 14 GB 초과 시 경고 로그 + 자동 Ollama 언로드 시도.

## R-03 HWPX XML 네임스페이스가 실제 한글과컴퓨터 파일과 다를 수 있다 (MEDIUM, OPEN)

- **증상**: `docs/research/hwpx_spike.md`의 파싱 전략은 테스트 목적 합성 HWPX 3종으로 검증. 실제 한글 오피스가 생성한 HWPX의 네임스페이스 URI가 `urn:hancom:names:tc:opendocument:xmlns:paragraph:1.0`와 상이할 가능성 있음.
- **영향 범위**: M_06 DocumentIngest의 HWPX 경로. 실 문서 파싱 시 단락 추출 0건 가능.
- **완화 방안**
  1. M_06 구현 전에 사용자에게 **실제 사내 HWPX 샘플 5건**을 받아 네임스페이스 실측.
  2. 네임스페이스를 하드코딩하지 말고 파일 내 `Contents/content.hpf` 또는 루트 엘리먼트의 `xmlns`를 동적으로 추출하는 구조로 구현.
  3. 파싱 실패 시 "텍스트 추출 실패: 네임스페이스 X 미지원" 로그를 남기고 해당 파일만 skip.
  4. 회귀 테스트 세트에 실 샘플 5건을 fixture로 추가(PII 제거 필수).
- **담당**: M_06 스펙 작성 단계에서 사용자 샘플 확보 TODO 명시.

## R-04 `frontend` 서브모듈이 미체크아웃되어 펫 모드 구현이 검증되지 않았다 (MEDIUM, OPEN)

- **증상**: `docs/research/frontend_structure.md` — `upstream/Open-LLM-VTuber/frontend/` 비어 있음. 펫 모드(투명 배경, 항상 위, 클릭 관통, 드래그) 실제 구현이 Electron/Tauri/CSS 중 무엇인지 미확인.
- **영향 범위**: M_12 Frontend 공수. fork 전략이 잘못될 경우 scratch에 가까운 공수 발생 가능.
- **완화 방안**
  1. M_12 착수 전 `git submodule update --init upstream/Open-LLM-VTuber/frontend`로 체크아웃 후 `package.json`, 메인 프로세스 파일 분석 보고서 작성(researcher 에이전트).
  2. 체크아웃이 외부 네트워크 필요하므로 빌드 머신에서 미리 clone해 번들로 이관.
  3. 만약 upstream이 웹 전용이라 펫 모드가 데스크톱 앱(별도 프로젝트)에 있다면 Electron으로 래핑하는 얇은 shell을 새로 작성(공수 +3 인일 추정).
- **담당**: researcher 에이전트 → M_12 SPEC 선행 조사.

## R-05 MeloTTS 한국어 음질이 사용자 기준을 충족하지 못할 수 있다 (MEDIUM, OPEN)

- **증상**: REQUIREMENTS.md §1.1은 "한국어 여성 목소리 기본"만 명시, 음질 기준 부재. MeloTTS 한국어 화자의 자연스러움·발화 속도·고유명사 발음이 사내 사용자 기대를 못 맞출 가능성.
- **영향 범위**: M_04 TTSEngine, 음성 대화 전체.
- **완화 방안**
  1. M_04 구현 초기에 **주관 평가 표본 테스트**: 회사 고유명사 10종(팀명, 제품명), 숫자/단위, 한자 혼용 문장 각 5개 합성 후 사용자 청취 평가(5점 척도).
  2. 평가 점수가 3점 미만이면 XTTS v2(음성 클로닝)로 기본 엔진 전환 CR 발행 또는 CosyVoice 2 재검토.
  3. TTS 출력 전 전처리: 한자 → 한글 변환, 숫자 → 한국어 숫자 읽기(upstream `tts_preprocessor` 재사용 + 한국어 규칙 추가).
- **담당**: M_04 스펙에 품질 평가 체크리스트 포함.

## R-06 Gemma 4 E4B가 vision(이미지 입력) 변형을 지원하는지 미확인 (HIGH, OPEN)

- **증상**: `docs/research/gemma4_function_calling.md` — E4B 변형이 text-only인지 vision 포함인지 직접 확인되지 않음. REQUIREMENTS.md §6은 화면 인식에 Gemma 4 E4B의 vision을 요구.
- **영향 범위**: M_05 LLMAgent, M_05b ToolRouter(`take_screenshot`). vision 미지원이면 §6이 불가능.
- **완화 방안**
  1. M_05 착수 시 즉시 vision 검증 스파이크 실행: 임의 PNG를 `image_url` 필드로 Ollama 호출 → 응답 확인.
  2. 미지원 판명 시:
     - (a) Ollama 모델 태그를 `gemma4:e4b-vision` 등 vision 지원 변형으로 교체할 수 있는지 사용자·모델 카드 확인.
     - (b) 대안: `moondream2`, `llava-phi-3` 등 소형 vision LLM을 보조 모델로 적재(메모리 +3~5 GB → R-02와 충돌).
     - (c) 화면 인식 기능의 V1 제외를 제안하는 CR 발행.
  3. 검증 결과는 `docs/research/gemma_vision_spike.md`로 보관.
- **담당**: M_05 SPEC 작성 착수 시 최우선 스파이크.

## R-07 BGE-M3 한국어 성능이 공개 수치로 검증되지 않았다 (MEDIUM, OPEN)

- **증상**: `docs/research/bge_m3_korean.md` — MIRACL-ko nDCG@10, BEIR 등 한국어 벤치마크 수치 직접 확인 실패(외부망 차단). 리랭커 없이 단일 검색만 쓰기로 결정(D-05)한 상태에서 기준치 미상.
- **영향 범위**: M_07 VectorSearch 품질, §2.2 RAG 정확도.
- **완화 방안**
  1. M_07 통합 테스트 단계에서 **사내 문서 20~30건으로 인스턴스 벤치마크**: 수동 작성한 Q&A 20쌍으로 top-1 정확도와 `min_score` 캘리브레이션.
  2. `min_score` 기본값 0.35는 초기값일 뿐, 사용자 인스턴스에서 튜닝해 보관(`conf.yaml`의 `rag.min_score`).
  3. V2에서 리랭커(Qwen3-Reranker-8B) 도입 여부 재검토 — 메모리 여유가 확보되는 조건(R-02 완화 후).
- **담당**: M_07 DoD에 인스턴스 벤치마크 단계 포함.

## R-08 Ollama tool calling에서 한국어 tool 응답 메시지의 일관성이 미검증 (MEDIUM, OPEN)

- **증상**: 스파이크(10/10, 100%)에서 tool 선택과 인자 추출은 완벽했으나, **tool 실행 후 최종 자연어 응답**이 한국어로 일관되게 반환되는지, 영어 섞임이 없는지는 추가 검증 필요.
- **영향 범위**: M_05 + M_05b. 사용자 체감 품질.
- **완화 방안**
  1. M_05 통합 테스트에 "tool 호출 → 결과 주입 → 한국어 응답" 10건 회귀 테스트 추가.
  2. 시스템 프롬프트에 "모든 응답은 한국어로 답하되, 기술 용어는 영어 원문 유지" 규칙 명시.
  3. 영어 응답 비율이 5%를 넘으면 프롬프트를 강화하거나 `temperature`를 0.3~0.5로 낮춘다.
- **담당**: M_05 스펙 내 시스템 프롬프트 설계.

## R-09 AGPL·비상업 라이선스 코드/모델 혼입 우려 (MEDIUM, OPEN)

- **증상**: pyhwp(AGPL-3.0), neurlang Piper 한국어 모델(CC-BY-NC-SA-4.0), 일부 Live2D 자산(Live2D 상업 라이선스) 등이 실수로 혼입될 수 있음.
- **영향 범위**: 사내 배포 및 사용 적법성.
- **완화 방안**
  1. `scripts/check_licenses.py`를 CI에 추가해 `pip-licenses` + 번들 파일 메타데이터에서 AGPL·NC·SA·비상업 키워드 검출 시 빌드 실패.
  2. 번들되는 모델 파일에 `assets/models/<name>/LICENSE.txt`를 함께 포함해 추적.
  3. Gemma Terms of Use도 사내 법무 검토 후 `docs/LICENSES.md`에 요약 기재.
- **담당**: Integrator 단계에서 CI에 포함.

## R-10 Windows 전역 키보드 훅(pynput)이 기업용 EDR/백신에 의해 차단될 수 있다 (MEDIUM, MITIGATING)

- **증상**: 일부 사내 PC에 설치된 EDR(CrowdStrike, SentinelOne 등)이 전역 키보드/마우스 훅을 의심 행위로 탐지·차단할 가능성.
- **영향 범위**: M_10 IdleMonitor → M_11 Proactive 전체 기능(§5 휴식 권고).
- **완화 방안** (M_10에서 구현 완료, 2026-04-19)
  1. 초기 설치 시 사용자에게 "키보드·마우스 활동 감지 권한 필요" 공지 및 방해 금지 모드 안내. — 프론트(M_12) 오너십.
  2. **[구현됨]** pynput 실패 시 Windows `GetLastInputInfo()` API(pywin32)로 자동 폴백. 둘 다 실패하면 NoopBackend로 강등해 앱 기동 자체는 계속. `src/idle_monitor/backends/` 3계층 체인. 회귀 테스트: `tests/idle_monitor/test_adversarial.py::test_a1_*`, `test_a2_*` (Linux CI에서도 monkeypatch로 실행).
  3. IT 부서와 협의하여 본 프로세스의 바이너리 해시를 EDR 예외 목록에 등록. — 배포 단계 오너십.
- **담당**: Integrator 단계에서 Windows VM 실지 검증 남음. 이후 CLOSED로 이행 검토.

## R-11 `OLLAMA_BASE_URL`이 사설 IP인지 런타임 검증 누락 시 외부 송신 위험 (LOW, OPEN)

- **증상**: 개발 중 실수로 공용 IP 또는 도메인을 환경변수에 설정하면 사내 프라이버시 정책 위반.
- **영향 범위**: REQUIREMENTS.md §9, CLAUDE.md 네트워크 금지 규칙.
- **완화 방안**
  1. M_01 AppCore 기동 시 URL의 호스트를 `ipaddress.ip_address()`로 파싱해 `is_private` 또는 `is_loopback`인지 확인. 아니면 `SystemExit`.
  2. CI 단계에서 `grep -rE "https?://"` 패턴을 소스 전체에 실행해 허용 호스트 화이트리스트 외 URL 검출 시 실패.
  3. 로그에 최초 연결 시 사용된 Ollama URL을 마스킹 없이 기록(내부 IP는 PII 아님).
- **담당**: M_01 AppCore DoD에 URL 검증기 포함.

## R-12 Phase 2 일정 추정의 불확실성 (LOW, ACCEPTED)

- **증상**: `docs/MILESTONES.md`의 공수 추정은 1인 기준이며, 스파이크로 검증 안 된 모듈(M_04, M_12)이 다수.
- **영향 범위**: 출시 일정.
- **완화 방안**
  1. 각 모듈 착수 전 SPEC 리뷰에서 공수를 재추정.
  2. 크리티컬 패스(M_05 → M_05b → M_11)에 우선 투입, 나머지는 주차별 슬랙 확보.
- **담당**: 프로젝트 리드.

## R-PROA-1 upstream `proactive_speak_prompt`가 토픽 무관 단일 템플릿 — 어조 미분리 (MEDIUM, OPEN)

- **증상**: upstream `conversation_handler.py`의 `ai-speak-signal` 수신 경로는 `tool_prompts["proactive_speak_prompt"]` 단일 템플릿을 로드한다(`data.get("text")`를 읽지 않음). 따라서 `morning_briefing` / `event_reminder` / `idle_rest` / `overwork` 4종 토픽의 어조가 구분되지 않는다.
- **영향 범위**: M_11 ProactiveDispatcher V1 기능 전체. 사용자는 4종 토픽 모두 동일한 AI 발화 스타일을 경험.
- **완화 방안**
  1. M_11 payload의 `topic` + `text` 필드를 이미 실어 보내므로(D-5), V2에서 upstream `conversation_handler.py`에 `data.get("topic")` 분기를 추가해 토픽별 프롬프트 선택 가능.
  2. V1에서는 `proactive_speak_prompt`를 최대한 범용적으로 작성해 4종 토픽에서 자연스러운 발화가 나오도록 캐릭터 YAML 조정.
- **담당**: M_12 또는 통합 단계에서 캐릭터 YAML 검토.

## R-PROA-2 한 틱에 10분 이내 이벤트가 여러 건이면 첫 건만 알림 (LOW, OPEN)

- **증상**: `event_reminder` 토픽은 토픽 단위 쿨다운이 적용되어, 같은 1분 틱에 10분 이내 이벤트가 여러 건 있어도 첫 1건만 사용자에게 알림이 나간다(D-3 trade-off). 나머지 9건은 쿨다운으로 드롭.
- **영향 범위**: 여러 일정이 겹치는 오전 회의 집중 시간대. 실무상 동일 10분 내 이벤트 중복은 드물지만 발생 가능.
- **완화 방안**
  1. V1 허용 범위 — 드문 시나리오, UX 충격 낮음.
  2. V2에서 `event_reminder` 토픽만 `(topic, event_id)` 복합 키로 쿨다운 확장(D-3 내 명시된 확장 경로). M_11 `_last_emitted_at` dict를 `dict[(topic, Optional[int]), datetime]`으로 교체.
- **담당**: M_11 V2 스펙 개정.

## R-PROA-3 M_01 `AppWebSocketHandler`에 `_active_ws` 추적 로직 추가 필요 (LOW, OPEN)

- **증상**: M_11 ProactiveDispatcher의 `send_text` 콜러블은 단일 사용자의 활성 WebSocket에 송신해야 한다(D-13). M_01 `AppWebSocketHandler.handle_new_connection` 오버라이드에서 `AppServiceContext._active_ws`를 업데이트하는 5줄 내외 코드가 추가됐으나, M_01 SPEC 본문에 이 계약이 명시되지 않았다.
- **영향 범위**: M_01 코드 변경 범위 추적. Critic 검수 시 M_01 SPEC 갱신 여부 결정 필요.
- **완화 방안**
  1. M_11 builder 커밋에 M_01 수정 포함 (완료).
  2. Critic 검수에서 M_01 SPEC `specs/M_01_AppCore_SPEC.md`에 `AppWebSocketHandler.handle_new_connection` 오버라이드 및 `_active_ws` 계약 추가 여부 판단.
- **담당**: Critic (M_11 리뷰 시).

## R-PROA-4 `start()` 시점에 활성 WebSocket이 없으면 기동 직후 브리핑이 누락될 수 있음 (LOW, OPEN)

- **증상**: ProactiveDispatcher가 `start()`되는 시점(FastAPI startup)에는 아직 클라이언트가 연결되지 않은 경우가 많다. APScheduler의 Cron이 09:00 직후 기동하면 `send_text`가 호출되지만 `_active_ws=None`으로 조용히 drop된다.
- **영향 범위**: 서버가 09:00 이전에 기동된 경우 정상(09:00에 클라이언트가 이미 연결됨). 09:00 직후 기동 시 10분의 misfire_grace_time 이내에 클라이언트가 연결되지 않으면 당일 morning briefing 누락.
- **완화 방안**
  1. `misfire_grace_time=600`(10분)으로 완화 (D-4, 이미 구현). 기동 후 10분 이내 클라이언트 연결이 오면 잡이 실행됨.
  2. 10분 초과 지연 시 다음 날 09:00까지 대기 — V1 수용.
  3. V2: ProactiveDispatcher에 "클라이언트 연결 이벤트 시 missed briefing 재전송" 로직 추가 가능(AppServiceContext._active_ws 변경 감지).
- **담당**: M_11 V2 스펙.

---

## 변경 로그

| 날짜 | 이벤트 | 영향 리스크 |
|---|---|---|
| 2026-04-18 | 초안 작성 (Phase 1 Planner) | R-01 ~ R-12 |
| 2026-04-18 | 하드웨어 프로파일(MIN/RECOMMENDED) 도입으로 R-02 재조정 — HIGH→MEDIUM, OPEN→MITIGATING. RECOMMENDED 프로파일 범위 제외. | R-02 |
| 2026-04-19 | M_11 ProactiveDispatcher 구현 완료. R-PROA-1~4 신규 등록. | R-PROA-1~4 |
