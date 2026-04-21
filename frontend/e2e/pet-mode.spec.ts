// M_12 P5 §13.3 A-3 — 펫 모드 E2E skeleton
// NOTE: WSL에서 실행 불가 (display server 없음). Windows CI에서 실행.
import { test, expect, _electron as electron } from '@playwright/test';

test.describe('M_12 Pet Mode E2E (§13.3 A-3)', () => {
  test.skip('A-3: hit-region 우회 시도 — click-through 중 button 무반응', async () => {
    // TODO: WSL에서 실행 불가. Windows CI에서 실행.
    //
    // 시나리오:
    // 1. PetWindowController.enable() → 투명·항상 위·click-through 창 생성
    // 2. 발화 버튼 좌표로 합성 click 이벤트 100회 전송
    // 3. click-through ON 상태이므로 click 핸들러 호출 0회 검증
    //
    // const app = await electron.launch({ args: ['.'] });
    // const window = await app.firstWindow();
    // await window.evaluate(() => (window as unknown as { petMode: { enable: () => void } }).petMode.enable());
    // const buttonBBox = await window.locator('[data-testid="speak-btn"]').boundingBox();
    // for (let i = 0; i < 100; i++) {
    //   await window.mouse.click(buttonBBox!.x + 5, buttonBBox!.y + 5);
    // }
    // const clickCount = await window.evaluate(() => globalThis.__speakBtnClickCount ?? 0);
    // expect(clickCount).toBe(0);
    // await app.close();
    expect(true).toBe(true);
  });

  test.skip('pet-mode-01: PetWindowController.enable() → 투명 창 생성', async () => {
    // TODO: §13.1 N-3 구현
    // const app = await electron.launch({ args: ['.'] });
    // const window = await app.firstWindow();
    // await window.evaluate(() => (window as unknown as { petMode: { enable: () => void } }).petMode.enable());
    // const windows = app.windows();
    // expect(windows.length).toBeGreaterThanOrEqual(2);
    // await app.close();
    expect(true).toBe(true);
  });
});
