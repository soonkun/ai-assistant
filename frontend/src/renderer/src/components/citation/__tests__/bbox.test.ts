// M_12 P4 §8.3.1 — pdfBboxToViewport 순수 함수 단위 테스트 (≥6건)
import { describe, it, expect } from 'vitest';
import { pdfBboxToViewport } from '../bbox';

describe('pdfBboxToViewport', () => {
  // 테스트 #1 — 정상: PDF 좌하단 원점 좌표 → viewport 좌상단 변환
  it('#1 정상 변환: (0, 0, 100, 50), pageHeight=1000, scale=1.5', () => {
    // bbox.x=0, bbox.y=0, bbox.w=100, bbox.h=50 → 페이지 맨 아래쪽
    // y_px = (1000 - 0 - 50) * 1.5 = 950 * 1.5 = 1425
    const result = pdfBboxToViewport({ x: 0, y: 0, w: 100, h: 50 }, 1000, 1.5);
    expect(result.x_px).toBeCloseTo(0);
    expect(result.y_px).toBeCloseTo(1425);
    expect(result.w_px).toBeCloseTo(150);
    expect(result.h_px).toBeCloseTo(75);
  });

  // 테스트 #2 — scale=2.0 적용
  it('#2 scale=2.0: (50, 100, 200, 80), pageHeight=842, scale=2.0', () => {
    // x_px = 50 * 2 = 100
    // y_px = (842 - 100 - 80) * 2 = 662 * 2 = 1324
    // w_px = 200 * 2 = 400
    // h_px = 80 * 2 = 160
    const result = pdfBboxToViewport({ x: 50, y: 100, w: 200, h: 80 }, 842, 2.0);
    expect(result.x_px).toBeCloseTo(100);
    expect(result.y_px).toBeCloseTo(1324);
    expect(result.w_px).toBeCloseTo(400);
    expect(result.h_px).toBeCloseTo(160);
  });

  // 테스트 #3 — pageHeight 경계: bbox가 페이지 최하단 → y_px = 0
  it('#3 경계: bbox가 페이지 최하단(y=0, h=pageHeight) → y_px=0', () => {
    // y_px = (500 - 0 - 500) * 1.5 = 0
    const result = pdfBboxToViewport({ x: 0, y: 0, w: 100, h: 500 }, 500, 1.5);
    expect(result.y_px).toBeCloseTo(0);
  });

  // 테스트 #4 — bbox 폭·높이 0 (pass-through, 스펙에 방어 없음)
  it('#4 zero-size bbox: 폭과 높이가 0인 경우 pass-through', () => {
    const result = pdfBboxToViewport({ x: 100, y: 200, w: 0, h: 0 }, 1000, 1.5);
    expect(result.w_px).toBe(0);
    expect(result.h_px).toBe(0);
    // y_px = (1000 - 200 - 0) * 1.5 = 800 * 1.5 = 1200
    expect(result.y_px).toBeCloseTo(1200);
  });

  // 테스트 #5 — 큰 페이지: A3 크기 (842x1191 pt)
  it('#5 A3 페이지 (842x1191pt): bbox 중앙 근방, scale=1.5', () => {
    // bbox: x=200, y=500, w=400, h=100
    // x_px = 200 * 1.5 = 300
    // y_px = (1191 - 500 - 100) * 1.5 = 591 * 1.5 = 886.5
    // w_px = 400 * 1.5 = 600
    // h_px = 100 * 1.5 = 150
    const result = pdfBboxToViewport({ x: 200, y: 500, w: 400, h: 100 }, 1191, 1.5);
    expect(result.x_px).toBeCloseTo(300);
    expect(result.y_px).toBeCloseTo(886.5);
    expect(result.w_px).toBeCloseTo(600);
    expect(result.h_px).toBeCloseTo(150);
  });

  // 테스트 #6 — 소수점 좌표 (OCR 출력 등)
  it('#6 소수점 좌표: OCR 결과 등의 부동소수 bbox', () => {
    // bbox: x=72.5, y=123.75, w=300.25, h=45.5
    // x_px = 72.5 * 1.5 = 108.75
    // y_px = (792 - 123.75 - 45.5) * 1.5 = 622.75 * 1.5 = 934.125
    // w_px = 300.25 * 1.5 = 450.375
    // h_px = 45.5 * 1.5 = 68.25
    const result = pdfBboxToViewport({ x: 72.5, y: 123.75, w: 300.25, h: 45.5 }, 792, 1.5);
    expect(result.x_px).toBeCloseTo(108.75, 3);
    expect(result.y_px).toBeCloseTo(934.125, 3);
    expect(result.w_px).toBeCloseTo(450.375, 3);
    expect(result.h_px).toBeCloseTo(68.25, 3);
  });
});
