// M_12 P5 §13.3 A-4 — Citation Viewer CSP E2E skeleton
// NOTE: WSL에서 실행 불가 (display server 없음). Windows CI에서 실행.
import { test, expect, _electron as electron } from '@playwright/test';

test.describe('M_12 Citation Viewer E2E (§13.3 A-4 CSP)', () => {
  test.skip('A-4: CSP 위반 시도 — 외부 이미지 로드 차단', async () => {
    // TODO: WSL에서 실행 불가. Windows CI에서 실행.
    //
    // 시나리오:
    // 1. Electron 렌더러에서 new Image().src = "https://evil.example/x.gif" 실행
    // 2. CSP 로그에 "Refused to load the image" 포함 확인
    // 3. playwright route intercept로 실제 네트워크 요청 0건 검증
    //
    // const app = await electron.launch({ args: ['.'] });
    // const window = await app.firstWindow();
    // const cspViolations: string[] = [];
    // window.on('console', (msg) => {
    //   if (msg.text().includes('Refused to load')) cspViolations.push(msg.text());
    // });
    // await window.route('https://evil.example/**', route => route.abort());
    // await window.evaluate(() => { new Image().src = 'https://evil.example/x.gif'; });
    // await window.waitForTimeout(500);
    // expect(cspViolations.length).toBeGreaterThan(0);
    // await app.close();
    expect(true).toBe(true);
  });
});
