// M_12 §7.2·§8.3 D-3·§13.3 A-1 — avatar-state payload 검증 헬퍼 단위 테스트.

import { describe, it, expect } from 'vitest';
import { resolveEmotion, resolveCrossfadeMs } from '../validators';

describe('resolveEmotion', () => {
  it('TC-E1: 8종 유효 emotion은 그대로 반환', () => {
    expect(resolveEmotion('happy')).toBe('happy');
    expect(resolveEmotion('neutral')).toBe('neutral');
    expect(resolveEmotion('study')).toBe('study');
  });

  it('TC-E2: 8종 외 문자열은 neutral 폴백', () => {
    expect(resolveEmotion('joy')).toBe('neutral');
    expect(resolveEmotion('')).toBe('neutral');
  });

  it('TC-E3: 비문자열은 neutral 폴백', () => {
    expect(resolveEmotion(undefined)).toBe('neutral');
    expect(resolveEmotion(null)).toBe('neutral');
    expect(resolveEmotion(42)).toBe('neutral');
    expect(resolveEmotion({ emotion: 'happy' })).toBe('neutral');
  });
});

describe('resolveEmotion — §13.3 A-1 악성 문자열 (WS handler 통합 경로)', () => {
  it('A-1a: XSS 문자열 emotion → neutral 폴백 (DOM 오염 방지)', () => {
    // WS 핸들러가 resolveEmotion을 통과시키므로 여기서 커버.
    // 원본 문자열이 절대 Emotion 값으로 store에 들어가지 않음.
    expect(resolveEmotion('<script>alert(1)</script>')).toBe('neutral');
    expect(resolveEmotion('"><img src=x onerror=alert(1)>')).toBe('neutral');
  });

  it('A-1b: 공백·특수문자 포함 emotion → neutral 폴백', () => {
    expect(resolveEmotion('happy; DROP TABLE')).toBe('neutral');
    expect(resolveEmotion('  happy  ')).toBe('neutral'); // trim 없이 exact match만
  });
});

describe('resolveCrossfadeMs', () => {
  const PREV = 250;

  it('TC-C1: [200,300] 포함 유효값은 그대로 반환', () => {
    expect(resolveCrossfadeMs(200, PREV)).toBe(200);
    expect(resolveCrossfadeMs(250, PREV)).toBe(250);
    expect(resolveCrossfadeMs(300, PREV)).toBe(300);
  });

  it('TC-C2: 범위 밖(199/301/음수/거대값)은 prev 유지', () => {
    expect(resolveCrossfadeMs(199, PREV)).toBe(PREV);
    expect(resolveCrossfadeMs(301, PREV)).toBe(PREV);
    expect(resolveCrossfadeMs(0, PREV)).toBe(PREV);
    expect(resolveCrossfadeMs(-1, PREV)).toBe(PREV);
    expect(resolveCrossfadeMs(9999, PREV)).toBe(PREV);
  });

  it('TC-C3: undefined/null은 prev 유지', () => {
    expect(resolveCrossfadeMs(undefined, PREV)).toBe(PREV);
    expect(resolveCrossfadeMs(null, PREV)).toBe(PREV);
  });

  it('TC-C4: 비숫자는 prev 유지 (store 오염 방지 — MAJOR #2 회귀)', () => {
    expect(resolveCrossfadeMs('250', PREV)).toBe(PREV);
    expect(resolveCrossfadeMs(NaN, PREV)).toBe(PREV);
    expect(resolveCrossfadeMs({ ms: 250 }, PREV)).toBe(PREV);
    expect(resolveCrossfadeMs([250], PREV)).toBe(PREV);
  });
});
