// M_12 §7.2·§8.2.1 — avatar-state payload 검증 헬퍼.
// WS 핸들러와 렌더러 양쪽에서 동일 정책을 적용해야 하므로 순수 함수로 추출.

import { VALID_EMOTIONS, type Emotion } from './types';

/**
 * emotion 문자열 2차 방어. 8종 외 값은 'neutral' 폴백.
 */
export function resolveEmotion(raw: unknown): Emotion {
  if (typeof raw !== 'string') return 'neutral';
  return (VALID_EMOTIONS as readonly string[]).includes(raw) ? (raw as Emotion) : 'neutral';
}

/**
 * crossfade_ms 검증. 범위 [200, 300] 포함. 범위 밖·비숫자·undefined는
 * 이전 값 유지(무시 정책, §7.2). 값이 유효하면 그대로 반환.
 * 반환값이 prev와 같아도 undefined만 제외하면 호출자가 분기를 생략해도 됨.
 *
 * @param raw - 수신 페이로드의 crossfade_ms (unknown)
 * @param prev - store에 저장된 이전 crossfade_ms (fallback)
 * @returns 적용할 crossfade_ms. 범위 밖이면 prev.
 */
export function resolveCrossfadeMs(raw: unknown, prev: number): number {
  if (raw === undefined || raw === null) return prev;
  if (typeof raw !== 'number' || Number.isNaN(raw)) return prev;
  if (raw < 200 || raw > 300) return prev;
  return raw;
}
