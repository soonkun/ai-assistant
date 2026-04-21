// M_12 P5 — Playwright E2E 설정
// NOTE: WSL 환경에서는 display server 없어 실제 실행 불가.
//       Windows 환경 또는 GitHub Actions (Windows runner)에서 실행할 것.
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './',
  timeout: 30_000,
  use: {
    headless: false,
  },
});
