// M_12 P3 §9.4 / §10.3 — pet:* IPC 입력 검증 + 좌표 clamp 헬퍼.
// main/index.ts의 핸들러에서 사용. 테스트 가능한 순수 함수로 분리.

export function isBool(v: unknown): v is boolean {
  return typeof v === 'boolean';
}

export function isFiniteNumber(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

export interface DisplayBoundsLike {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * 저장된 pet window (x, y)가 주어진 displays 집합의 virtual screen 안에 있는지
 * 검사한다. 범위 밖이면 null 반환(호출자가 디폴트 위치 폴백).
 *
 * 창 일부만 보여도 드래그로 복구 가능해야 하므로, `maxX - 100`·`maxY - 100`
 * 여유를 두어 완전히 밖으로 나간 경우만 null. (main/index.ts L18~L40 clampToVirtualScreen와 동일 정책.)
 *
 * @param displays screen.getAllDisplays()가 반환한 배열. 빈 배열은 null.
 */
export function clampToVirtualScreen(
  x: number,
  y: number,
  displays: readonly DisplayBoundsLike[],
): { x: number; y: number } | null {
  if (displays.length === 0) return null;
  if (!isFiniteNumber(x) || !isFiniteNumber(y)) return null;
  const minX = Math.min(...displays.map((d) => d.x));
  const minY = Math.min(...displays.map((d) => d.y));
  const maxX = Math.max(...displays.map((d) => d.x + d.width));
  const maxY = Math.max(...displays.map((d) => d.y + d.height));
  if (x < minX || x > maxX - 100 || y < minY || y > maxY - 100) {
    return null;
  }
  return { x, y };
}
