// M_12 P4 §8.3.1 #4 — PDF bbox → viewport 좌표 변환 순수 함수
// PDF 좌표계: 좌하단 원점, 단위 pt
// viewport 좌표계: 좌상단 원점, 단위 px (scale 적용)

/** 변환된 viewport 좌표 (px) */
export interface ViewportRect {
  x_px: number;
  y_px: number;
  w_px: number;
  h_px: number;
}

/**
 * PDF bbox 좌표를 pdf.js viewport 좌표로 변환한다.
 *
 * @param bbox   PDF 좌하단 원점 좌표 (pt)
 * @param pageHeight  PDF 페이지 높이 (pt)
 * @param scale  렌더 스케일 (예: 1.5)
 * @returns      viewport 좌상단 기준 픽셀 좌표
 *
 * 변환식 (§8.3.1 #4):
 *   x_px = bbox.x * scale
 *   y_px = (page_height - bbox.y - bbox.h) * scale
 *   w_px = bbox.w * scale
 *   h_px = bbox.h * scale
 */
export function pdfBboxToViewport(
  bbox: { x: number; y: number; w: number; h: number },
  pageHeight: number,
  scale: number,
): ViewportRect {
  return {
    x_px: bbox.x * scale,
    y_px: (pageHeight - bbox.y - bbox.h) * scale,
    w_px: bbox.w * scale,
    h_px: bbox.h * scale,
  };
}
