import { ElectronAPI } from '@electron-toolkit/preload';

declare global {
  interface Window {
    electron: ElectronAPI
    api: {
      setIgnoreMouseEvents: (ignore: boolean) => void
      toggleForceIgnoreMouse: () => void
      onForceIgnoreMouseChanged: (callback: (isForced: boolean) => void) => void
      onModeChanged: (callback: (mode: 'pet' | 'window') => void) => void
      showContextMenu: (x: number, y: number) => void
      onMicToggle: (callback: () => void) => void
      onInterrupt: (callback: () => void) => void
      updateComponentHover: (componentId: string, isHovering: boolean) => void
      onToggleInputSubtitle: (callback: () => void) => void
      onToggleScrollToResize: (callback: () => void) => void
      onSwitchCharacter: (callback: (filename: string) => void) => void
      setMode: (mode: 'window' | 'pet') => void
      getConfigFiles: () => Promise<any>
      updateConfigFiles: (files: any[]) => void
    }
    /** M_12 §5.2·§9.4 — PetMode IPC API (P3 실구현, Q-9 B안) */
    petMode: {
      enable(): Promise<void>
      disable(): Promise<void>
      setClickThrough(on: boolean, forward: boolean): Promise<void>
      setAlwaysOnTop(on: boolean): Promise<void>
      /** mousedown 시점 창 viewport 기준 cursor 좌표. main은 offset 저장만 수행. */
      dragStart(payload: { x: number; y: number }): Promise<void>
      /** mousemove 스트림. main이 offset 차감으로 win.setPosition() 호출. */
      dragMove(payload: { screenX: number; screenY: number }): Promise<void>
      /** mouseup/blur 시점. offset 초기화 + 최종 위치 영속화. */
      dragEnd(): Promise<void>
    }
  }
}

interface IpcRenderer {
  on(channel: 'mode-changed', func: (_event: any, mode: 'pet' | 'window') => void): void;
  send(channel: string, ...args: any[]): void;
}
