// @vitest-environment node
// M_12 P3 §9.4 — pet-ipc-validators 단위 테스트 (MAJOR-2/MAJOR-4 회귀 방지).

import { describe, it, expect } from 'vitest';
import { isBool, isFiniteNumber, clampToVirtualScreen } from '../pet-ipc-validators';

describe('isBool', () => {
  it('정상 boolean만 true', () => {
    expect(isBool(true)).toBe(true);
    expect(isBool(false)).toBe(true);
  });
  it('문자열·숫자·undefined는 false', () => {
    expect(isBool('true')).toBe(false);
    expect(isBool(1)).toBe(false);
    expect(isBool(0)).toBe(false);
    expect(isBool(undefined)).toBe(false);
    expect(isBool(null)).toBe(false);
    expect(isBool({})).toBe(false);
  });
});

describe('isFiniteNumber', () => {
  it('정상 유한 숫자만 true', () => {
    expect(isFiniteNumber(0)).toBe(true);
    expect(isFiniteNumber(-100)).toBe(true);
    expect(isFiniteNumber(3.14)).toBe(true);
  });
  it('NaN / Infinity / 문자열 / undefined는 false', () => {
    expect(isFiniteNumber(NaN)).toBe(false);
    expect(isFiniteNumber(Infinity)).toBe(false);
    expect(isFiniteNumber(-Infinity)).toBe(false);
    expect(isFiniteNumber('100')).toBe(false);
    expect(isFiniteNumber(undefined)).toBe(false);
  });
});

describe('clampToVirtualScreen', () => {
  const singleDisplay = [{ x: 0, y: 0, width: 1920, height: 1080 }];
  const dualDisplay = [
    { x: 0, y: 0, width: 1920, height: 1080 },
    { x: 1920, y: 0, width: 2560, height: 1440 },
  ];

  it('TC-V1: displays 빈 배열 → null', () => {
    expect(clampToVirtualScreen(100, 100, [])).toBeNull();
  });

  it('TC-V2: 단일 모니터 내부 좌표 → 그대로 반환', () => {
    expect(clampToVirtualScreen(500, 500, singleDisplay)).toEqual({ x: 500, y: 500 });
  });

  it('TC-V3: 단일 모니터 범위 밖(x 음수) → null', () => {
    expect(clampToVirtualScreen(-50, 500, singleDisplay)).toBeNull();
  });

  it('TC-V4: 단일 모니터 범위 밖(y 초과) → null', () => {
    expect(clampToVirtualScreen(500, 1081, singleDisplay)).toBeNull();
  });

  it('TC-V5: 듀얼 모니터 — 두 번째 모니터 내부 좌표 허용', () => {
    expect(clampToVirtualScreen(3000, 500, dualDisplay)).toEqual({ x: 3000, y: 500 });
  });

  it('TC-V6: 듀얼 모니터 — 두 번째 모니터도 아닌 오른쪽 밖 → null (토폴로지 변경 시나리오)', () => {
    // 이전에 외장 모니터(x=1920~4480)에 있었으나 현재는 단일 모니터(x=0~1920)만 연결된 상황.
    expect(clampToVirtualScreen(3000, 500, singleDisplay)).toBeNull();
  });

  it('TC-V7: NaN / Infinity → null (저장 JSON 오염 방어)', () => {
    expect(clampToVirtualScreen(NaN, 100, singleDisplay)).toBeNull();
    expect(clampToVirtualScreen(100, Infinity, singleDisplay)).toBeNull();
  });
});
