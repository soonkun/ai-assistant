// M_12 P5 §A-2 — RSS 감시 헬퍼
// 렌더러 프로세스의 JS 힙 사용량을 측정해 PDF 렌더 강제 중단 임계 판단에 사용.
// Chromium performance.memory API(Electron 렌더러에서 제공).

/** PDF 뷰어를 강제 닫는 기준 RSS (바이트). §13.3 A-2: 1.2 GB */
export const RSS_LIMIT_BYTES = 1.2 * 1024 * 1024 * 1024;

/**
 * Chromium 렌더러의 JS 힙 사용량(바이트)을 반환한다.
 * `performance.memory` API를 제공하지 않는 환경(표준 jsdom, Node 등)에서는 `null`.
 */
export function readRendererRSS(): number | null {
  const perf = performance as unknown as { memory?: { usedJSHeapSize: number } };
  return perf.memory?.usedJSHeapSize ?? null;
}

/**
 * 현재 RSS가 임계(기본 RSS_LIMIT_BYTES)를 초과하면 true를 반환한다.
 * `current === null`이면 측정 불가로 간주하고 false(중단 안 함)를 반환한다.
 *
 * @param current - readRendererRSS() 결과
 * @param limit   - 중단 임계 (바이트, 기본 RSS_LIMIT_BYTES)
 */
export function shouldAbortPdfRender(
  current: number | null,
  limit: number = RSS_LIMIT_BYTES,
): boolean {
  if (current === null) return false;
  return current > limit;
}
