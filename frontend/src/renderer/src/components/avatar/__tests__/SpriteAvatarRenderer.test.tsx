// M_12 §8 — SpriteAvatarRenderer 단위 테스트 (P2)
// vitest + @testing-library/react + jsdom

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act } from '@testing-library/react';
import React from 'react';

// ── 외부 의존성 mock ──────────────────────────────────────────────────────────

// zustand avatar-store mock
vi.mock('@/store/avatar-store', async () => {
  const { create } = await import('zustand');
  type StoreState = {
    emotion: string;
    crossfadeMs: number;
    speaking: boolean;
    setAvatarState: (s: Partial<StoreState>) => void;
  };
  const store = create<StoreState>((set) => ({
    emotion: 'neutral',
    crossfadeMs: 250,
    speaking: false,
    setAvatarState: (s: Partial<StoreState>) =>
      set((prev: StoreState) => ({ ...prev, ...s })),
  }));
  return {
    useAvatarStore: store,
  };
});

// chakra-ui toaster mock
vi.mock('@/components/ui/toaster', () => ({
  toaster: {
    create: vi.fn(),
  },
}));

// ── import (mock 등록 후) ─────────────────────────────────────────────────────
import { SpriteAvatarRenderer, type SpriteAvatarHandle } from '../SpriteAvatarRenderer';
import { useAvatarStore } from '@/store/avatar-store';
import { toaster } from '@/components/ui/toaster';

// ── 헬퍼 ─────────────────────────────────────────────────────────────────────
function renderRenderer() {
  const ref = React.createRef<SpriteAvatarHandle>();
  const { container, unmount } = render(
    <SpriteAvatarRenderer ref={ref} />,
  );
  return { ref, container, unmount };
}

/** preload + 첫 blink 예약(5~10s 범위) 완료까지 시간 진행 */
async function waitForMount(): Promise<void> {
  // preload는 Promise.allSettled → microtask. 10s 진행하면 첫 blink도 처리됨.
  // 단, blink는 재귀이므로 runAllTimers 사용 금지 — 10s만 진행.
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10001);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
describe('SpriteAvatarRenderer', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // store 초기화
    useAvatarStore.setState({ emotion: 'neutral', crossfadeMs: 250, speaking: false });
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  // ── 정상 케이스 1: mount 후 default emotion(neutral) 렌더 ───────────────────
  it('TC-01: mount 후 neutral 이미지가 렌더링된다', async () => {
    const { container } = renderRenderer();

    await waitForMount();

    const imgs = container.querySelectorAll('img');
    const hasNeutral = Array.from(imgs).some((img) =>
      (img as HTMLImageElement).src.includes('neutral.png'),
    );
    expect(hasNeutral).toBe(true);
  });

  // ── 정상 케이스 2: setEmotion("happy", 250) → happy.png 레이어 전환 ─────────
  it('TC-02: setEmotion("happy", 250) 호출 시 happy.png 레이어가 준비된다', async () => {
    const { ref, container } = renderRenderer();

    await waitForMount();

    // setEmotion 호출
    act(() => {
      ref.current?.setEmotion('happy', 250);
    });

    // crossfade 타이머 진행
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    const imgs = container.querySelectorAll('img');
    const hasHappy = Array.from(imgs).some((img) =>
      (img as HTMLImageElement).src.includes('happy.png'),
    );
    expect(hasHappy).toBe(true);
  });

  // ── 정상 케이스 3: setEmotion("joy") → neutral 폴백 + onError(invalid_emotion) ─
  it('TC-03: setEmotion("joy") → neutral 폴백 + onError({code:"invalid_emotion"}) 발행', async () => {
    const { ref } = renderRenderer();

    await waitForMount();

    const errors: Array<{ code: string; detail: string }> = [];
    const unsub = ref.current?.onError((e) => errors.push(e));

    act(() => {
      ref.current?.setEmotion('joy', 250);
    });

    expect(errors).toHaveLength(1);
    expect(errors[0].code).toBe('invalid_emotion');
    expect(errors[0].detail).toBe('joy');

    unsub?.();
  });

  // ── 정상 케이스 4: setEmotion("happy", 150) → 전환 건너뛰기 + onError(invalid_crossfade_ms) ─
  it('TC-04: crossfade_ms=150(범위 밖) → 전환 건너뛰기 + onError({code:"invalid_crossfade_ms"})', async () => {
    const { ref, container } = renderRenderer();

    await waitForMount();

    const errors: Array<{ code: string; detail: string }> = [];
    const unsub = ref.current?.onError((e) => errors.push(e));

    // 현재 상태 캡처 (neutral)
    const imgsBefore = Array.from(container.querySelectorAll('img')).map(
      (img) => (img as HTMLImageElement).src,
    );

    act(() => {
      ref.current?.setEmotion('happy', 150);
    });

    // 전환이 발생하지 않아야 함 (상태 유지)
    const imgsAfter = Array.from(container.querySelectorAll('img')).map(
      (img) => (img as HTMLImageElement).src,
    );
    expect(imgsAfter).toEqual(imgsBefore);

    expect(errors).toHaveLength(1);
    expect(errors[0].code).toBe('invalid_crossfade_ms');
    expect(errors[0].detail).toBe('150');

    unsub?.();
  });

  // ── 정상 케이스 5: setSpeaking(true/false) ─────────────────────────────────
  it('TC-05: setSpeaking(true) → speaking animation 스타일 적용; setSpeaking(false) → 복원', async () => {
    const { ref, container } = renderRenderer();

    await waitForMount();

    // speaking=false: saessagi-speaking animation이 없어야 함
    const overlayBefore = container.querySelector(
      '[style*="saessagi-speaking-opacity"]',
    );
    expect(overlayBefore).toBeNull();

    // setSpeaking(true)
    act(() => {
      ref.current?.setSpeaking(true);
    });

    // speaking animation이 적용된 요소가 있어야 함
    const overlayAfter = container.querySelector(
      '[style*="saessagi-speaking-opacity"]',
    );
    expect(overlayAfter).not.toBeNull();

    // setSpeaking(false) → 복원
    act(() => {
      ref.current?.setSpeaking(false);
    });

    const overlayRestored = container.querySelector(
      '[style*="saessagi-speaking-opacity"]',
    );
    expect(overlayRestored).toBeNull();
  });

  // ── 엣지 케이스 6: crossfade_ms=300 경계값 → 유효 ────────────────────────────
  it('TC-06(edge): crossfade_ms=300 경계값은 유효하며 에러 없이 전환된다', async () => {
    const { ref, container } = renderRenderer();

    await waitForMount();

    const errors: Array<{ code: string }> = [];
    const unsub = ref.current?.onError((e) => errors.push(e));

    act(() => {
      ref.current?.setEmotion('happy', 300);
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });

    // invalid_crossfade_ms 에러가 없어야 함
    const crossfadeErrors = errors.filter((e) => e.code === 'invalid_crossfade_ms');
    expect(crossfadeErrors).toHaveLength(0);

    const imgs = container.querySelectorAll('img');
    const hasHappy = Array.from(imgs).some((img) =>
      (img as HTMLImageElement).src.includes('happy.png'),
    );
    expect(hasHappy).toBe(true);

    unsub?.();
  });

  // ── 엣지 케이스 7: mount 전 버퍼링 ──────────────────────────────────────────
  it('TC-07(edge): store가 happy로 설정된 후 mount하면 happy가 적용된다', async () => {
    // store를 mount 전에 happy로 설정
    useAvatarStore.setState({ emotion: 'happy', crossfadeMs: 250 });

    const { container } = renderRenderer();

    // preload 완료 대기 (Promise.allSettled 완료 + mountedRef 설정)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    const imgs = container.querySelectorAll('img');
    const hasHappy = Array.from(imgs).some((img) =>
      (img as HTMLImageElement).src.includes('happy.png'),
    );
    expect(hasHappy).toBe(true);
  });

  // ── 엣지 케이스 8: dispose() 후 타이머 정리 ──────────────────────────────────
  it('TC-08(edge): dispose() 호출 후 unmount 시 에러 없이 종료된다', async () => {
    const { ref, unmount } = renderRenderer();

    await waitForMount();

    // dispose 명시 호출
    act(() => {
      ref.current?.dispose();
    });

    // unmount 후 clearAllTimers 실행해도 에러 없어야 함
    expect(() => {
      unmount();
      vi.clearAllTimers();
    }).not.toThrow();
  });

  // ── 엣지 케이스 9: all_assets_failed → mount_failed 에러 + toaster 호출 ─────
  it('TC-09(edge): 모든 에셋 로딩 실패 시 mount_failed 에러 + toaster 호출 + 1px placeholder 렌더', async () => {
    // decode()를 실패하도록 override
    const originalDecode = Object.getOwnPropertyDescriptor(
      HTMLImageElement.prototype,
      'decode',
    );
    Object.defineProperty(HTMLImageElement.prototype, 'decode', {
      value: () => Promise.reject(new Error('load failed')),
      writable: true,
      configurable: true,
    });

    const { container } = renderRenderer();

    // preload promise 실행
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(toaster.create).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'error' }),
    );

    // MAJOR #1 회귀: allFailed=true 상태가 리렌더를 트리거해 1px placeholder가 실제로 DOM에 나타나야 한다
    const placeholder = container.querySelector('img[width="1"]');
    expect(placeholder).not.toBeNull();

    // 복원
    if (originalDecode) {
      Object.defineProperty(HTMLImageElement.prototype, 'decode', originalDecode);
    }
  });
});
