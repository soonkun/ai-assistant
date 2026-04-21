// M_12 P3 — PetWindowController IPC wrapper (renderer-side)
// preload(window.petMode)에 위임하는 얇은 wrapper.
// preload 없는 환경(웹 빌드)은 경고 로그 + no-op.
// dragMove·dragEnd 추가: Q-9 B안 mousedown+IPC setPosition 구현에서
// mouseup/dragEnd 시점을 main에 알릴 IPC가 필요하기 때문.

export interface DragStartPayload {
  /** 창 viewport 기준 cursor 좌표. main이 'cursor의 창 내 위치'로 저장. */
  x: number;
  y: number;
}

export interface DragMovePayload {
  /** 절대 스크린 좌표. main이 setPosition(screenX - offsetX, screenY - offsetY) 호출. */
  screenX: number;
  screenY: number;
}

export interface PetModeApi {
  enable(): Promise<void>;
  disable(): Promise<void>;
  setClickThrough(on: boolean, forward: boolean): Promise<void>;
  setAlwaysOnTop(on: boolean): Promise<void>;
  dragStart(payload: DragStartPayload): Promise<void>;
  dragMove(payload: DragMovePayload): Promise<void>;
  dragEnd(): Promise<void>;
}

/** window.petMode 타입 참조용 (contextBridge 노출 객체) */
type WindowPetMode = {
  petMode?: PetModeApi;
};

function getApi(): PetModeApi | undefined {
  return (window as unknown as WindowPetMode).petMode;
}

/**
 * petMode IPC wrapper.
 * preload에서 window.petMode로 노출된 API를 호출한다.
 * preload가 없는 경우(예: 웹 빌드)는 경고 로그 후 resolve.
 */
export const petMode: PetModeApi = {
  enable(): Promise<void> {
    const api = getApi();
    if (api?.enable) return api.enable();
    console.warn('[PetMode] preload unavailable; enable() no-op');
    return Promise.resolve();
  },

  disable(): Promise<void> {
    const api = getApi();
    if (api?.disable) return api.disable();
    console.warn('[PetMode] preload unavailable; disable() no-op');
    return Promise.resolve();
  },

  setClickThrough(on: boolean, forward: boolean): Promise<void> {
    const api = getApi();
    if (api?.setClickThrough) return api.setClickThrough(on, forward);
    console.warn('[PetMode] preload unavailable; setClickThrough() no-op');
    return Promise.resolve();
  },

  setAlwaysOnTop(on: boolean): Promise<void> {
    const api = getApi();
    if (api?.setAlwaysOnTop) return api.setAlwaysOnTop(on);
    console.warn('[PetMode] preload unavailable; setAlwaysOnTop() no-op');
    return Promise.resolve();
  },

  dragStart(payload: DragStartPayload): Promise<void> {
    const api = getApi();
    if (api?.dragStart) return api.dragStart(payload);
    console.warn('[PetMode] preload unavailable; dragStart() no-op');
    return Promise.resolve();
  },

  dragMove(payload: DragMovePayload): Promise<void> {
    const api = getApi();
    if (api?.dragMove) return api.dragMove(payload);
    console.warn('[PetMode] preload unavailable; dragMove() no-op');
    return Promise.resolve();
  },

  dragEnd(): Promise<void> {
    const api = getApi();
    if (api?.dragEnd) return api.dragEnd();
    console.warn('[PetMode] preload unavailable; dragEnd() no-op');
    return Promise.resolve();
  },
};
