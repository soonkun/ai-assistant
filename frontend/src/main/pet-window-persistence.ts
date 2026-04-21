// M_12 P3 — 펫 모드 창 위치 영속화 (Q-12)
// 저장 경로: app.getPath('userData')/saessagi/pet-window.json
// 스키마: PetWindowPersisted { x, y, width, height, savedAt }

import { app } from 'electron';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import type { Rectangle } from 'electron';

// Electron main 프로세스 내부 로거 — console은 main 프로세스에서 electron 로그로 리다이렉트됨.
// electron-log 미설치 환경에서는 console로 충분.
const logger = {
  info: (...args: unknown[]): void => { console.info('[pet-window-persistence]', ...args); },
  warn: (...args: unknown[]): void => { console.warn('[pet-window-persistence]', ...args); },
};

/** §3 위치 영속화 스키마 */
export interface PetWindowPersisted {
  x: number;
  y: number;
  width: number;   // V1에서는 가상 스크린 span이므로 참고용
  height: number;
  savedAt: string; // ISO 8601
}

/**
 * userData 하위 saessagi/pet-window.json 절대 경로를 반환한다.
 * Electron app 준비 후에 호출해야 한다.
 */
export function getPetWindowStatePath(): string {
  return join(app.getPath('userData'), 'saessagi', 'pet-window.json');
}

/**
 * 파일에서 PetWindowPersisted를 읽어 반환한다.
 * - 파일이 없으면 null.
 * - JSON 파싱 실패 시 warn 로그 + null.
 */
export function loadPetWindowState(): PetWindowPersisted | null {
  const filePath = getPetWindowStatePath();

  if (!existsSync(filePath)) {
    logger.info(`[PetWindowPersistence] state file not found: ${filePath}`);
    return null;
  }

  try {
    const raw = readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(raw) as PetWindowPersisted;
    logger.info(`[PetWindowPersistence] loaded state x=${parsed.x} y=${parsed.y}`);
    return parsed;
  } catch (err) {
    logger.warn(`[PetWindowPersistence] failed to parse state file: ${err}`);
    return null;
  }
}

/**
 * BrowserWindow.getBounds() 결과를 pet-window.json에 저장한다.
 * parent directory가 없으면 mkdir -p로 생성한다.
 */
export function savePetWindowState(bounds: Rectangle): void {
  const filePath = getPetWindowStatePath();
  const dir = dirname(filePath);

  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
    logger.info(`[PetWindowPersistence] created directory: ${dir}`);
  }

  const state: PetWindowPersisted = {
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    savedAt: new Date().toISOString(),
  };

  writeFileSync(filePath, JSON.stringify(state, null, 2), 'utf-8');
  logger.info(`[PetWindowPersistence] saved state x=${bounds.x} y=${bounds.y}`);
}
