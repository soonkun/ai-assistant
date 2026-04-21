// M_12 §3.3 DROP: Live2D 관련 import 제거됨 (useLive2DConfig, scrollToResize 관련).
// useInterrupt는 hooks/utils/use-interrupt로 경로 변경.
import { useEffect, useCallback } from 'react';
import { useInterrupt } from '@/hooks/utils/use-interrupt';
import { useMicToggle } from './use-mic-toggle';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';
import { useForceIgnoreMouse } from '@/hooks/utils/use-force-ignore-mouse';
import { useMode } from '@/context/mode-context';

export function useIpcHandlers() {
  const { handleMicToggle } = useMicToggle();
  const { interrupt } = useInterrupt();
  const { switchCharacter } = useSwitchCharacter();
  const { setForceIgnoreMouse } = useForceIgnoreMouse();
  const { mode } = useMode();
  const isPet = mode === 'pet';

  const micToggleHandler = useCallback(() => {
    handleMicToggle();
  }, [handleMicToggle]);

  const interruptHandler = useCallback(() => {
    interrupt();
  }, [interrupt]);

  // scrollToResizeHandler 제거됨 (M_12 §3.3 DROP — Live2D modelInfo 불필요)

  const switchCharacterHandler = useCallback(
    (_event: Electron.IpcRendererEvent, filename: string) => {
      switchCharacter(filename);
    },
    [switchCharacter],
  );

  // Handler for force ignore mouse state changes from main process
  const forceIgnoreMouseChangedHandler = useCallback(
    (_event: Electron.IpcRendererEvent, isForced: boolean) => {
      console.log('Force ignore mouse changed:', isForced);
      setForceIgnoreMouse(isForced);
    },
    [setForceIgnoreMouse],
  );

  // Handle toggle force ignore mouse from menu
  const toggleForceIgnoreMouseHandler = useCallback(() => {
    (window.api as unknown as { toggleForceIgnoreMouse: () => void }).toggleForceIgnoreMouse();
  }, []);

  useEffect(() => {
    if (!window.electron?.ipcRenderer) return;
    if (!isPet) return;

    window.electron.ipcRenderer.removeAllListeners('mic-toggle');
    window.electron.ipcRenderer.removeAllListeners('interrupt');
    window.electron.ipcRenderer.removeAllListeners('toggle-scroll-to-resize');
    window.electron.ipcRenderer.removeAllListeners('switch-character');
    window.electron.ipcRenderer.removeAllListeners('toggle-force-ignore-mouse');
    window.electron.ipcRenderer.removeAllListeners('force-ignore-mouse-changed');

    window.electron.ipcRenderer.on('mic-toggle', micToggleHandler);
    window.electron.ipcRenderer.on('interrupt', interruptHandler);
    // toggle-scroll-to-resize 핸들러 제거됨 (M_12 §3.3 DROP)
    window.electron.ipcRenderer.on('switch-character', switchCharacterHandler);
    window.electron.ipcRenderer.on('toggle-force-ignore-mouse', toggleForceIgnoreMouseHandler);
    window.electron.ipcRenderer.on('force-ignore-mouse-changed', forceIgnoreMouseChangedHandler);

    return () => {
      window.electron?.ipcRenderer.removeAllListeners('mic-toggle');
      window.electron?.ipcRenderer.removeAllListeners('interrupt');
      window.electron?.ipcRenderer.removeAllListeners('toggle-scroll-to-resize');
      window.electron?.ipcRenderer.removeAllListeners('switch-character');
      window.electron?.ipcRenderer.removeAllListeners('toggle-force-ignore-mouse');
      window.electron?.ipcRenderer.removeAllListeners('force-ignore-mouse-changed');
    };
  }, [
    micToggleHandler,
    interruptHandler,
    switchCharacterHandler,
    toggleForceIgnoreMouseHandler,
    forceIgnoreMouseChangedHandler,
    isPet,
  ]);
}
