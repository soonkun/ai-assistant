// M_12 P1 — PetWindowController IPC wrapper (renderer-side)
// preload로 노출된 window.petMode API의 TypeScript wrapper.
// 실제 IPC handler(main 프로세스)는 P3에서 구현 예정.
// 현재는 console.log + Promise.resolve() placeholder.

export interface DragStartPayload {
  x: number;
  y: number;
}

export interface PetModeApi {
  enable(): Promise<void>;
  disable(): Promise<void>;
  setClickThrough(on: boolean, forward: boolean): Promise<void>;
  setAlwaysOnTop(on: boolean): Promise<void>;
  dragStart(payload: DragStartPayload): Promise<void>;
}

/**
 * petMode IPC wrapper.
 * preload에서 window.petMode로 노출된 API를 호출한다.
 * P3 이전에는 wrapper가 preload 존재를 확인하고 그대로 위임한다.
 * preload가 없는 경우(예: 웹 빌드)는 경고 로그 후 resolve.
 */
export const petMode: PetModeApi = {
  enable(): Promise<void> {
    const api = (window as unknown as { petMode?: PetModeApi }).petMode;
    if (api?.enable) return api.enable();
    console.warn('[PetMode] preload unavailable; enable() no-op');
    return Promise.resolve();
  },

  disable(): Promise<void> {
    const api = (window as unknown as { petMode?: PetModeApi }).petMode;
    if (api?.disable) return api.disable();
    console.warn('[PetMode] preload unavailable; disable() no-op');
    return Promise.resolve();
  },

  setClickThrough(on: boolean, forward: boolean): Promise<void> {
    const api = (window as unknown as { petMode?: PetModeApi }).petMode;
    if (api?.setClickThrough) return api.setClickThrough(on, forward);
    console.warn('[PetMode] preload unavailable; setClickThrough() no-op');
    return Promise.resolve();
  },

  setAlwaysOnTop(on: boolean): Promise<void> {
    const api = (window as unknown as { petMode?: PetModeApi }).petMode;
    if (api?.setAlwaysOnTop) return api.setAlwaysOnTop(on);
    console.warn('[PetMode] preload unavailable; setAlwaysOnTop() no-op');
    return Promise.resolve();
  },

  dragStart(payload: DragStartPayload): Promise<void> {
    const api = (window as unknown as { petMode?: PetModeApi }).petMode;
    if (api?.dragStart) return api.dragStart(payload);
    console.warn('[PetMode] preload unavailable; dragStart() no-op');
    return Promise.resolve();
  },
};
