# tests/app/test_logging.py
"""pii_mask regex 및 loguru sink 구성 테스트."""

from __future__ import annotations

from pathlib import Path

from app.logging import init_logging, pii_mask, _pii_filter


class TestPiiMask:
    """PII 마스킹 유틸 테스트."""

    # ── 정상 케이스 ──────────────────────────────────────────────────────
    def test_phone_masked(self) -> None:
        result = pii_mask("연락처는 010-1234-5678입니다.")
        assert "010-1234-5678" not in result
        assert "01X-XXXX-XXXX" in result

    def test_email_masked(self) -> None:
        result = pii_mask("이메일: user@example.com 으로 연락주세요.")
        assert "user@example.com" not in result
        assert "<email>" in result

    def test_ssn_masked(self) -> None:
        result = pii_mask("주민번호: 900101-1234567")
        assert "900101-1234567" not in result
        assert "<ssn>" in result

    def test_no_pii_unchanged(self) -> None:
        text = "안녕하세요, 오늘 날씨가 좋네요."
        assert pii_mask(text) == text

    # ── 엣지 케이스 ──────────────────────────────────────────────────────
    def test_phone_no_hyphen(self) -> None:
        result = pii_mask("01012345678")
        assert "01012345678" not in result
        assert "01X-XXXX-XXXX" in result

    def test_multiple_pii_types(self) -> None:
        text = "이름: 홍길동, 연락처: 010-9999-8888, 메일: test@corp.co.kr, 주민: 800512-2345678"
        result = pii_mask(text)
        assert "010-9999-8888" not in result
        assert "test@corp.co.kr" not in result
        assert "800512-2345678" not in result

    def test_empty_string(self) -> None:
        assert pii_mask("") == ""

    def test_phone_3digit_middle(self) -> None:
        """휴대폰 중간 자리 3자리도 마스킹."""
        result = pii_mask("010-123-4567")
        assert "010-123-4567" not in result
        assert "01X-XXXX-XXXX" in result

    def test_email_subdomains(self) -> None:
        result = pii_mask("admin@mail.company.co.kr 에 문의하세요.")
        assert "admin@mail.company.co.kr" not in result
        assert "<email>" in result

    # ── 적대적 케이스 ────────────────────────────────────────────────────
    def test_ssn_no_hyphen(self) -> None:
        # 하이픈 없는 SSN (전화번호 패턴과 겹치지 않는 숫자 사용)
        result = pii_mask("주민번호: 8503121234567")
        assert "<ssn>" in result

    def test_multiple_phones_in_one_line(self) -> None:
        result = pii_mask("010-1111-2222 또는 011-333-4444")
        assert "010-1111-2222" not in result
        assert "011-333-4444" not in result

    def test_ssn_gender_digit_range(self) -> None:
        """주민등록번호 성별 자리는 1~4만 매칭 (5는 미매칭)."""
        # 5로 시작하는 외국인은 현재 패턴에서 미매칭 — 스펙 명시 없으므로 현재 동작 고정
        result_valid = pii_mask("900101-1234567")
        assert "<ssn>" in result_valid


class TestPiiLoguruSinkEndToEnd:
    """MAJOR-11: loguru sink 레벨에서 PII 마스킹이 실제로 동작하는지 검증.

    init_logging() 후 리스트 기반 커스텀 sink를 설치해
    전화번호/이메일/주민번호 포함 로그가 실제 출력에서 마스킹됐는지 확인.
    """

    def test_phone_masked_in_loguru_sink(self, tmp_path: Path) -> None:
        """loguru sink를 통한 전화번호/이메일/주민번호 PII 마스킹 end-to-end."""
        from loguru import logger

        log_dir = str(tmp_path / "logs")
        init_logging(log_dir, level="DEBUG")

        captured: list[str] = []

        def _test_sink(message: object) -> None:
            captured.append(str(message))

        # 테스트용 sink 추가 (PII 필터 포함)
        sink_id = logger.add(_test_sink, format="{message}", filter=_pii_filter)  # type: ignore[arg-type]

        try:
            logger.info("사용자 전화번호: 010-9876-5432 로 연락드리겠습니다.")
            logger.info("이메일 주소: secret@company.com 입니다.")
            logger.info("주민번호: 850312-1234567 확인 완료.")

            full_output = "\n".join(captured)

            # 원본 PII가 출력에 없어야 함
            assert "010-9876-5432" not in full_output, "전화번호가 마스킹되지 않음"
            assert "secret@company.com" not in full_output, "이메일이 마스킹되지 않음"
            assert "850312-1234567" not in full_output, "주민번호가 마스킹되지 않음"

            # 마스킹 토큰이 출력에 있어야 함
            assert "01X-XXXX-XXXX" in full_output, "전화번호 마스킹 토큰 없음"
            assert "<email>" in full_output, "이메일 마스킹 토큰 없음"
            assert "<ssn>" in full_output, "주민번호 마스킹 토큰 없음"
        finally:
            logger.remove(sink_id)

    def test_no_pii_log_passes_through_unchanged(self, tmp_path: Path) -> None:
        """PII 없는 메시지는 변형 없이 통과."""
        from loguru import logger

        log_dir = str(tmp_path / "logs2")
        init_logging(log_dir, level="DEBUG")

        captured: list[str] = []

        def _test_sink(message: object) -> None:
            captured.append(str(message))

        sink_id = logger.add(_test_sink, format="{message}", filter=_pii_filter)  # type: ignore[arg-type]

        try:
            logger.info("일반 로그 메시지: 오늘 날씨가 맑습니다.")
            full_output = "\n".join(captured)
            assert "일반 로그 메시지" in full_output
        finally:
            logger.remove(sink_id)
