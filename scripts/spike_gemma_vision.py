#!/usr/bin/env python3
# scripts/spike_gemma_vision.py
"""R-06 스파이크: Gemma 4 E4B vision 변형 멀티모달 입력 검증.

실행 전 준비:
  1. Ollama가 실행 중이어야 함: `ollama serve`
  2. 모델이 준비되어 있어야 함: `ollama pull gemma4:e4b`
  3. 테스트용 이미지 파일이 필요함: `test_image.png` 또는 base64 직접 제공

실행 방법:
  cd /mnt/c/projects/ai-assistant
  python scripts/spike_gemma_vision.py --base-url http://127.0.0.1:11434 --image path/to/image.png

확인 항목:
  1. Ollama /api/version 및 /api/tags 응답 확인
  2. gemma4:e4b 모델이 멀티모달 입력(image_url)을 지원하는지 확인
  3. OpenAI 호환 /v1/chat/completions 엔드포인트에서 이미지 포함 메시지 전송
  4. 스트리밍 응답 정상 수신 확인
  5. TTFT(Time To First Token) 측정
  6. 응답에 이미지 내용이 반영됐는지 확인

결과 기록 위치:
  docs/research/gemma_vision_spike.md

주의:
  - 실제 Ollama 서버 연결이 필요하므로 오프라인 테스트 환경에서는 실행 불가
  - 이 스크립트는 스텁입니다. 실제 Ollama 연결 후 아래 TODO를 구현하세요.
"""

# TODO: 실제 구현 필요
# 아래는 스파이크 구현 가이드 골격입니다.

# import argparse
# import asyncio
# import base64
# import time
# from pathlib import Path
#
# import httpx
#
#
# OLLAMA_BASE_URL = "http://127.0.0.1:11434"
# MODEL = "gemma4:e4b"
#
#
# async def check_health(base_url: str) -> dict:
#     """Ollama 헬스체크."""
#     async with httpx.AsyncClient(timeout=10.0) as client:
#         version_resp = await client.get(f"{base_url}/api/version")
#         tags_resp = await client.get(f"{base_url}/api/tags")
#         return {
#             "version": version_resp.json().get("version"),
#             "models": [m["name"] for m in tags_resp.json().get("models", [])],
#         }
#
#
# async def test_vision_chat(base_url: str, model: str, image_path: str) -> None:
#     """이미지 포함 채팅 요청으로 멀티모달 지원 확인."""
#     # 이미지를 base64로 인코딩
#     image_bytes = Path(image_path).read_bytes()
#     image_b64 = base64.b64encode(image_bytes).decode()
#     image_url = f"data:image/png;base64,{image_b64}"
#
#     messages = [
#         {
#             "role": "user",
#             "content": [
#                 {"type": "text", "text": "이 이미지에서 무엇을 볼 수 있나요?"},
#                 {"type": "image_url", "image_url": {"url": image_url, "detail": "auto"}},
#             ],
#         }
#     ]
#
#     # TODO: OpenAI 호환 스트리밍 요청 전송
#     # TODO: TTFT 측정
#     # TODO: 응답 내용 기록
#
#
# if __name__ == "__main__":
#     # TODO: argparse로 --base-url, --model, --image 인자 처리
#     # TODO: asyncio.run(main())
#     pass

print("R-06 스파이크 스크립트 스텁입니다.")
print("실제 Ollama gemma4:e4b 모델 연결 후 위 TODO 항목을 구현하세요.")
print("결과는 docs/research/gemma_vision_spike.md에 기록합니다.")
