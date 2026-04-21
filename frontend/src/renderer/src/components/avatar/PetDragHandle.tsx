// M_12 P3 — 펫 모드 드래그 핸들 UI (Q-9 B안)
// 펫 모드일 때만 렌더되는 투명 핸들. 아바타 상단 중앙에 위치.
// mousedown → dragStart IPC, mousemove → dragMove IPC (throttle 16ms), mouseup/blur → dragEnd IPC.

import { useEffect, useRef, useCallback } from 'react';
import { useMode } from '@/context/mode-context';
import { petMode } from '@/ipc/pet-mode';

/** mousemove 이벤트를 최소 intervalMs 간격으로 throttle */
function throttle<T extends (...args: Parameters<T>) => void>(
  fn: T,
  intervalMs: number,
): T {
  let lastCall = 0;
  return ((...args: Parameters<T>) => {
    const now = Date.now();
    if (now - lastCall >= intervalMs) {
      lastCall = now;
      fn(...args);
    }
  }) as T;
}

const THROTTLE_MS = 16; // ~60fps

/**
 * PetDragHandle
 * 펫 모드일 때만 렌더. 아바타 상단 중앙에 20x20 원형 핸들을 표시.
 * CSS: -webkit-app-region: no-drag (electron 기본 drag 비활성화), pointer-events: auto.
 * cursor: grab, :active: grabbing.
 */
export function PetDragHandle(): JSX.Element | null {
  const { mode } = useMode();
  const isDraggingRef = useRef(false);

  // throttle된 dragMove handler (컴포넌트 생명주기 동안 안정)
  const throttledDragMove = useRef(
    throttle((screenX: number, screenY: number) => {
      petMode.dragMove({ screenX, screenY }).catch(() => {
        // IPC 실패는 무시 (드래그 중 간헐적 실패 허용)
      });
    }, THROTTLE_MS),
  ).current;

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault(); // 기본 드래그/선택 방지 (MINOR-6)
    isDraggingRef.current = true;
    // MAJOR-1 수정: offsetX/Y는 핸들 div(20x20) 기준 상대좌표가 아닌,
    // 창 viewport 기준 cursor 좌표(clientX/Y)가 필요하다. frame:false이므로
    // clientX ≈ screenX - window.screenX (창 안의 cursor 위치).
    // main은 이 값을 'cursor의 창 내 오프셋'으로 저장하고 dragMove 시 뺀다.
    petMode.dragStart({ x: e.clientX, y: e.clientY }).catch(() => {});
  }, []);

  const handleDragEnd = useCallback(() => {
    if (!isDraggingRef.current) return;
    isDraggingRef.current = false;
    petMode.dragEnd().catch(() => {});
  }, []);

  // window 레벨 이벤트 (mousemove, mouseup, blur) 등록 — 드래그 중 핸들 밖으로 커서가 나가도 추적
  useEffect(() => {
    if (mode !== 'pet') return undefined;

    const onMouseMove = (e: MouseEvent): void => {
      if (!isDraggingRef.current) return;
      throttledDragMove(e.screenX, e.screenY);
    };

    const onMouseUp = (): void => {
      handleDragEnd();
    };

    const onBlur = (): void => {
      handleDragEnd();
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    window.addEventListener('blur', onBlur);

    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('blur', onBlur);
    };
  }, [mode, throttledDragMove, handleDragEnd]);

  // 펫 모드가 아니면 렌더하지 않음
  if (mode !== 'pet') return null;

  return (
    <div
      onMouseDown={handleMouseDown}
      style={
        {
          position: 'absolute',
          top: '8px',
          left: '50%',
          transform: 'translateX(-50%)',
          width: '20px',
          height: '20px',
          borderRadius: '50%',
          backgroundColor: 'rgba(255, 255, 255, 0.3)',
          border: '1px solid rgba(255, 255, 255, 0.5)',
          cursor: 'grab',
          // Electron 전용 CSS 속성 — CSSProperties 타입 확장 없이 캐스팅
          WebkitAppRegion: 'no-drag',
          pointerEvents: 'auto',
          zIndex: 100,
          userSelect: 'none',
        } as React.CSSProperties & { WebkitAppRegion: string }
      }
      title="드래그하여 이동"
      aria-label="펫 모드 드래그 핸들"
    />
  );
}
