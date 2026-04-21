// M_12 P5 — 기본 Electron 창 E2E skeleton
// NOTE: WSL에서 실행 불가 (display server 없음). Windows CI에서 실행.
import { test, expect, _electron as electron } from '@playwright/test';

test.describe('M_12 기본 창 E2E', () => {
  test.skip('basic-01: Electron 앱 기동 → 채팅 창 렌더', async () => {
    // TODO: Windows 환경에서 실행.
    // const app = await electron.launch({ args: ['.'] });
    // const window = await app.firstWindow();
    // await expect(window).toHaveTitle(/새싹이/);
    // await app.close();
    expect(true).toBe(true);
  });

  test.skip('basic-02: WebSocket 연결 → wsState=OPEN', async () => {
    // TODO: 백엔드 mock WS server 기동 후 연결 상태 검증.
    expect(true).toBe(true);
  });
});
