// @vitest-environment node
// M_12 P3 — pet-window-persistence 단위 테스트
// app.getPath('userData')를 vi.mock으로 os.tmpdir 하위 경로로 리다이렉트.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import os from 'os';
import path from 'path';
import fs from 'fs';

// ── electron mock ─────────────────────────────────────────────────────────────
// app.getPath('userData')를 임시 디렉터리로 치환.
const TEST_USER_DATA = path.join(os.tmpdir(), `vitest-pet-window-${Date.now()}`);

vi.mock('electron', () => ({
  app: {
    getPath: (key: string): string => {
      if (key === 'userData') return TEST_USER_DATA;
      return os.tmpdir();
    },
  },
}));

// ── import (mock 등록 후) ─────────────────────────────────────────────────────
import {
  getPetWindowStatePath,
  loadPetWindowState,
  savePetWindowState,
  type PetWindowPersisted,
} from '../pet-window-persistence';

// ─────────────────────────────────────────────────────────────────────────────
describe('pet-window-persistence', () => {
  const statePath = path.join(TEST_USER_DATA, 'saessagi', 'pet-window.json');
  const stateDir = path.dirname(statePath);

  beforeEach(() => {
    // 각 테스트 전 saessagi 디렉터리 초기화
    if (fs.existsSync(stateDir)) {
      fs.rmSync(stateDir, { recursive: true });
    }
  });

  afterEach(() => {
    // 테스트 후 정리
    if (fs.existsSync(TEST_USER_DATA)) {
      fs.rmSync(TEST_USER_DATA, { recursive: true, force: true });
    }
  });

  // ── 정상 케이스 1: getPetWindowStatePath 경로 형식 ──────────────────────────
  it('TC-P1: getPetWindowStatePath는 userData/saessagi/pet-window.json을 반환한다', () => {
    const result = getPetWindowStatePath();
    expect(result).toBe(statePath);
    expect(result).toContain('saessagi');
    expect(result).toContain('pet-window.json');
  });

  // ── 정상 케이스 2: 저장 후 로드하면 동일 값 반환 ──────────────────────────────
  it('TC-P2: savePetWindowState 저장 후 loadPetWindowState 로드 시 동일 값 반환', () => {
    const bounds = { x: 100, y: 200, width: 800, height: 600 };

    savePetWindowState(bounds);

    const loaded = loadPetWindowState();
    expect(loaded).not.toBeNull();
    expect(loaded!.x).toBe(100);
    expect(loaded!.y).toBe(200);
    expect(loaded!.width).toBe(800);
    expect(loaded!.height).toBe(600);
    // savedAt은 ISO 8601 형식이어야 함
    expect(loaded!.savedAt).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
  });

  // ── 정상 케이스 3: 존재하지 않는 파일 로드 시 null ──────────────────────────
  it('TC-P3: state 파일이 없을 때 loadPetWindowState는 null을 반환한다', () => {
    const result = loadPetWindowState();
    expect(result).toBeNull();
  });

  // ── 정상 케이스 4: 손상된 JSON 파일 로드 시 null + console.warn ─────────────
  it('TC-P4: 손상된 JSON 파일 로드 시 null 반환 + warn 로그 출력', () => {
    // parent dir 생성 + 손상 파일 생성
    fs.mkdirSync(stateDir, { recursive: true });
    fs.writeFileSync(statePath, '{ invalid json !!!', 'utf-8');

    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const result = loadPetWindowState();
    expect(result).toBeNull();
    expect(warnSpy).toHaveBeenCalled();

    warnSpy.mockRestore();
  });

  // ── 정상 케이스 5: savePetWindowState 호출 시 parent dir 자동 생성 ──────────
  it('TC-P5: parent directory가 없어도 savePetWindowState 호출 시 자동 생성됨', () => {
    // stateDir이 존재하지 않는 상태 (beforeEach에서 삭제됨)
    expect(fs.existsSync(stateDir)).toBe(false);

    const bounds = { x: 50, y: 75, width: 1920, height: 1080 };
    expect(() => savePetWindowState(bounds)).not.toThrow();

    // 파일과 디렉터리가 생성되어야 함
    expect(fs.existsSync(stateDir)).toBe(true);
    expect(fs.existsSync(statePath)).toBe(true);
  });

  // ── 엣지 케이스: 덮어쓰기 시 최신 값으로 갱신 ────────────────────────────────
  it('TC-P6: 두 번 저장하면 최신 값으로 덮어쓴다', () => {
    savePetWindowState({ x: 10, y: 20, width: 800, height: 600 });
    savePetWindowState({ x: 999, y: 888, width: 1024, height: 768 });

    const loaded = loadPetWindowState() as PetWindowPersisted;
    expect(loaded.x).toBe(999);
    expect(loaded.y).toBe(888);
  });
});
