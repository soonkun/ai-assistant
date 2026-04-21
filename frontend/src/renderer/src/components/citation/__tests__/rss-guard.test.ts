// M_12 P5 §13.3 A-2 — rss-guard.ts 단위 테스트
// shouldAbortPdfRender 경계 케이스 5건.

import { describe, it, expect } from 'vitest';
import { shouldAbortPdfRender, RSS_LIMIT_BYTES } from '../rss-guard';

describe('shouldAbortPdfRender (§13.3 A-2)', () => {
  // 경계 #1: null → 측정 불가, 중단 안 함
  it('#1 current=null → false (측정 불가, 중단 금지)', () => {
    expect(shouldAbortPdfRender(null)).toBe(false);
  });

  // 경계 #2: 0 → 중단 안 함
  it('#2 current=0 → false', () => {
    expect(shouldAbortPdfRender(0)).toBe(false);
  });

  // 경계 #3: 1.1 GB (< 1.2 GB) → false
  it('#3 current=1.1 GB (< limit) → false', () => {
    const bytes = 1.1 * 1024 * 1024 * 1024;
    expect(shouldAbortPdfRender(bytes)).toBe(false);
  });

  // 경계 #4: 정확히 RSS_LIMIT_BYTES → false (> 이므로 등호는 허용)
  it('#4 current=RSS_LIMIT_BYTES (equal, not exceeded) → false', () => {
    expect(shouldAbortPdfRender(RSS_LIMIT_BYTES)).toBe(false);
  });

  // 경계 #5: 1.3 GB (> 1.2 GB) → true (중단)
  it('#5 current=1.3 GB (> limit) → true (PDF 렌더 중단)', () => {
    const bytes = 1.3 * 1024 * 1024 * 1024;
    expect(shouldAbortPdfRender(bytes)).toBe(true);
  });
});
