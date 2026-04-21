// M_12 §8 — SpriteAvatarRenderer 실구현 (P2)
// 설계 결정: React 컴포넌트 + useImperativeHandle로 §5.1 AvatarRenderer 메서드 노출.
// 외부 RendererController 클래스 대신 React ref handle을 택한 이유:
//   App.tsx가 이미 React tree 내에서 JSX로 마운트하므로 별도 DOM mount() 불필요.
//   zustand store 구독도 React hook으로 처리하면 리렌더 최소화 가능.

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import { useAvatarStore } from '@/store/avatar-store';
import { toaster } from '@/components/ui/toaster';
import type { AvatarRendererErrorEvent, Emotion } from './types';
import { VALID_EMOTIONS } from './types';

// ──────────────────────────────────────────────
// 상수
// ──────────────────────────────────────────────
const BASE_PATH = '/assets/character/saessagi';

function emotionPath(emotion: Emotion): string {
  return `${BASE_PATH}/${emotion}.png`;
}

// ──────────────────────────────────────────────
// 공개 handle 타입
// ──────────────────────────────────────────────
export interface SpriteAvatarHandle {
  setEmotion(emotion: string, crossfadeMs?: number): void;
  setSpeaking(on: boolean): void;
  preload(emotions?: readonly string[]): Promise<void>;
  onError(cb: (e: AvatarRendererErrorEvent) => void): () => void;
  dispose(): void;
}

// ──────────────────────────────────────────────
// Props
// ──────────────────────────────────────────────
interface SpriteAvatarRendererProps {
  showSidebar?: boolean;
}

// ──────────────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────────────
const SpriteAvatarRenderer = forwardRef<SpriteAvatarHandle, SpriteAvatarRendererProps>(
  function SpriteAvatarRenderer(_props, ref) {
    // ── 내부 상태 ──
    const [layerA, setLayerA] = useState<Emotion>('neutral'); // 현재 표시 레이어
    const [layerB, setLayerB] = useState<Emotion>('neutral'); // 전환 대상 레이어
    const [activeLayer, setActiveLayer] = useState<'A' | 'B'>('A'); // 현재 최상위 레이어
    const [fadingIn, setFadingIn] = useState(false); // crossfade 진행 중
    const [speaking, setSpeakingState] = useState(false);

    // ── refs: 타이머·에러 구독자·로딩 실패 목록·mount 전 버퍼 ──
    const blinkTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const errorListeners = useRef<Set<(e: AvatarRendererErrorEvent) => void>>(new Set());
    const failedEmotions = useRef<Set<Emotion>>(new Set());
    const mountedRef = useRef(false);
    const pendingEmotion = useRef<{ emotion: Emotion; crossfadeMs: number } | null>(null);
    const [allFailed, setAllFailed] = useState(false);

    // ── zustand store ──
    const storeEmotion = useAvatarStore((s) => s.emotion);
    const storeCrossfadeMs = useAvatarStore((s) => s.crossfadeMs);
    const storeSpeaking = useAvatarStore((s) => s.speaking);

    // (toast는 toaster 모듈 함수 직접 호출 — hook 불필요)

    // ──────────────────────────────────────────
    // 내부 유틸
    // ──────────────────────────────────────────
    const emitError = useCallback((e: AvatarRendererErrorEvent): void => {
      errorListeners.current.forEach((cb) => cb(e));
    }, []);

    /** emotion 문자열을 Emotion 타입으로 좁히기. 유효하지 않으면 neutral 폴백 + onError */
    const resolveEmotion = useCallback(
      (raw: string): Emotion => {
        if ((VALID_EMOTIONS as readonly string[]).includes(raw)) {
          return raw as Emotion;
        }
        console.warn(`[SpriteAvatarRenderer] invalid emotion: "${raw}", falling back to neutral`);
        emitError({ code: 'invalid_emotion', detail: raw, offendingEmotion: raw });
        return 'neutral';
      },
      [emitError],
    );

    /** 실제 표시할 emotion 결정: asset 실패 시 neutral 폴백 */
    const resolveAsset = useCallback(
      (emotion: Emotion): Emotion => {
        if (failedEmotions.current.has(emotion)) {
          if (emotion !== 'neutral') {
            emitError({ code: 'asset_missing', detail: emotion, offendingEmotion: emotion });
          }
          return 'neutral';
        }
        return emotion;
      },
      [emitError],
    );

    // ──────────────────────────────────────────
    // §8.1 자산 프리로드
    // ──────────────────────────────────────────
    const preloadEmotions = useCallback(
      async (emotions: readonly string[] = VALID_EMOTIONS): Promise<void> => {
        const results = await Promise.allSettled(
          emotions.map((e) => {
            const img = new Image();
            img.src = emotionPath(e as Emotion);
            return img.decode().then(() => e);
          }),
        );

        let everyFailed = true;
        results.forEach((result, idx) => {
          const emotion = emotions[idx] as Emotion;
          if (result.status === 'rejected') {
            failedEmotions.current.add(emotion);
            emitError({ code: 'asset_missing', detail: emotion, offendingEmotion: emotion });
          } else {
            everyFailed = false;
          }
        });

        if (everyFailed) {
          setAllFailed(true);
          emitError({ code: 'mount_failed', detail: 'all_assets_failed' });
          toaster.create({
            title: '아바타 로딩 실패',
            description: '스프라이트 이미지를 불러올 수 없습니다.',
            type: 'error',
          });
        }
      },
      [emitError],
    );

    // ──────────────────────────────────────────
    // §8.2.2 숨쉬기 CSS (컨테이너 전체 scaleY)
    // ──────────────────────────────────────────
    // CSS keyframe을 style 태그로 주입 (한 번만)
    useEffect(() => {
      const styleId = 'saessagi-breathe-style';
      if (!document.getElementById(styleId)) {
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
@keyframes saessagi-breathe {
  0%   { transform: scaleY(1.0); }
  50%  { transform: scaleY(1.02); }
  100% { transform: scaleY(1.0); }
}
@keyframes saessagi-speaking-opacity {
  0%   { opacity: 1.0; }
  50%  { opacity: 0.85; }
  100% { opacity: 1.0; }
}
@keyframes saessagi-speaking-shake {
  0%   { transform: rotate(0deg); }
  25%  { transform: rotate(0.5deg); }
  75%  { transform: rotate(-0.5deg); }
  100% { transform: rotate(0deg); }
}
`;
        document.head.appendChild(style);
      }
    }, []);

    // ──────────────────────────────────────────
    // §8.2.3 깜빡임
    // ──────────────────────────────────────────
    const blinkLayerARef = useRef<HTMLImageElement | null>(null);
    const blinkLayerBRef = useRef<HTMLImageElement | null>(null);

    // activeLayer ref: closure stale 방지
    const activeLayerRef = useRef(activeLayer);
    useEffect(() => {
      activeLayerRef.current = activeLayer;
    }, [activeLayer]);

    // scheduleBlinkRef: 재귀 예약 기반 깜빡임 (ref 사용으로 stale closure 방지)
    const scheduleBlinkRef = useRef<() => void>(() => {});
    scheduleBlinkRef.current = (): void => {
      const delay = Math.random() * 5000 + 5000; // 5~10s
      blinkTimerRef.current = setTimeout(() => {
        const layer = activeLayerRef.current;
        const activeImg = layer === 'A' ? blinkLayerARef.current : blinkLayerBRef.current;
        if (activeImg) {
          activeImg.style.opacity = '0.6';
          setTimeout(() => {
            if (activeImg) activeImg.style.opacity = '1';
            scheduleBlinkRef.current();
          }, 75);
        } else {
          scheduleBlinkRef.current();
        }
      }, delay);
    };

    useEffect(() => {
      // mount 시 첫 blink 스케줄
      scheduleBlinkRef.current();
      return () => {
        if (blinkTimerRef.current) clearTimeout(blinkTimerRef.current);
      };
    }, []); // mount 1회만 실행

    // ──────────────────────────────────────────
    // §8.2.1 Crossfade
    // ──────────────────────────────────────────
    const applyEmotion = useCallback(
      (emotion: Emotion, crossfadeMs: number, immediate = false): void => {
        const resolved = resolveAsset(emotion);

        if (immediate) {
          // mount 전 버퍼링된 경우 즉시 적용
          if (activeLayer === 'A') {
            setLayerA(resolved);
          } else {
            setLayerB(resolved);
          }
          return;
        }

        // crossfade_ms 범위 검증 [200, 300]
        if (crossfadeMs < 200 || crossfadeMs > 300) {
          emitError({ code: 'invalid_crossfade_ms', detail: String(crossfadeMs) });
          // 전환 건너뛰기 + 직전 상태 유지
          return;
        }

        // 비활성 레이어에 새 이미지 설정 후 crossfade
        if (activeLayer === 'A') {
          setLayerB(resolved);
        } else {
          setLayerA(resolved);
        }
        setFadingIn(true);

        setTimeout(() => {
          setActiveLayer((prev) => (prev === 'A' ? 'B' : 'A'));
          setFadingIn(false);
        }, crossfadeMs);
      },
      [activeLayer, emitError, resolveAsset],
    );

    // ──────────────────────────────────────────
    // mount 완료 처리 + 버퍼 적용
    // ──────────────────────────────────────────
    useEffect(() => {
      preloadEmotions().then(() => {
        mountedRef.current = true;
        if (pendingEmotion.current) {
          const { emotion } = pendingEmotion.current;
          pendingEmotion.current = null;
          applyEmotion(emotion, 250, true); // immediate
        }
      });
    }, []); // mount 1회만 실행 — preloadEmotions/applyEmotion은 ref 경유로 최신 유지

    // ──────────────────────────────────────────
    // zustand store 구독 → 렌더러 동기화
    // ──────────────────────────────────────────
    useEffect(() => {
      if (!mountedRef.current) {
        pendingEmotion.current = { emotion: storeEmotion, crossfadeMs: storeCrossfadeMs };
        return;
      }
      applyEmotion(storeEmotion, storeCrossfadeMs);
    }, [storeEmotion, storeCrossfadeMs]); // applyEmotion 의존성 제거: stale closure 허용

    useEffect(() => {
      setSpeakingState(storeSpeaking);
    }, [storeSpeaking]);

    // ──────────────────────────────────────────
    // useImperativeHandle — §5.1 AvatarRenderer
    // ──────────────────────────────────────────
    useImperativeHandle(
      ref,
      (): SpriteAvatarHandle => ({
        setEmotion(emotion: string, crossfadeMs = storeCrossfadeMs): void {
          if (!mountedRef.current) {
            const resolved = resolveEmotion(emotion);
            pendingEmotion.current = { emotion: resolved, crossfadeMs };
            return;
          }
          const resolved = resolveEmotion(emotion);
          applyEmotion(resolved, crossfadeMs);
        },
        setSpeaking(on: boolean): void {
          setSpeakingState(on);
        },
        preload(emotions?: readonly string[]): Promise<void> {
          return preloadEmotions(emotions);
        },
        onError(cb: (e: AvatarRendererErrorEvent) => void): () => void {
          errorListeners.current.add(cb);
          return () => errorListeners.current.delete(cb);
        },
        dispose(): void {
          if (blinkTimerRef.current) clearTimeout(blinkTimerRef.current);
          errorListeners.current.clear();
        },
      }),
      [applyEmotion, emitError, preloadEmotions, resolveEmotion, storeCrossfadeMs],
    );

    // ──────────────────────────────────────────
    // 렌더
    // ──────────────────────────────────────────
    if (allFailed) {
      // neutral.png 조차 실패 → 투명 1px placeholder
      return (
        <img
          src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
          width={1}
          height={1}
          alt=""
          style={{ position: 'absolute' }}
        />
      );
    }

    // §8.2.2 숨쉬기 컨테이너 스타일
    const breatheStyle: React.CSSProperties = {
      width: '100%',
      height: '100%',
      position: 'relative',
      animation: 'saessagi-breathe 2s ease-in-out infinite',
      transformOrigin: 'center center',
    };

    // §8.2.4 speaking 오버레이 스타일 (컨테이너 위 별도 레이어)
    const speakingOverlayStyle: React.CSSProperties = speaking
      ? {
          position: 'absolute',
          inset: 0,
          animation:
            'saessagi-speaking-opacity 200ms ease-in-out infinite, saessagi-speaking-shake 400ms ease-in-out infinite',
          transformOrigin: 'center center',
          pointerEvents: 'none',
        }
      : {
          position: 'absolute',
          inset: 0,
          opacity: 1,
          transform: 'rotate(0deg)',
          pointerEvents: 'none',
        };

    const imgBaseStyle: React.CSSProperties = {
      position: 'absolute',
      inset: 0,
      width: '100%',
      height: '100%',
      objectFit: 'contain',
      transition: `opacity ${storeCrossfadeMs}ms ease-in-out`,
    };

    const layerAActive = activeLayer === 'A';
    const layerBActive = activeLayer === 'B';

    // 전환 중(fadingIn): 비활성 레이어가 fade-in, 활성 레이어가 fade-out
    const layerAOpacity =
      fadingIn ? (layerAActive ? 0 : 1) : layerAActive ? 1 : 0;
    const layerBOpacity =
      fadingIn ? (layerBActive ? 0 : 1) : layerBActive ? 1 : 0;

    return (
      <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
        {/* §8.2.2 숨쉬기 컨테이너 */}
        <div style={breatheStyle}>
          {/* §8.2.4 speaking 오버레이 */}
          <div style={speakingOverlayStyle}>
            {/* Layer A */}
            <img
              ref={blinkLayerARef}
              src={emotionPath(layerA)}
              alt={`saessagi-${layerA}`}
              style={{
                ...imgBaseStyle,
                opacity: layerAOpacity,
                zIndex: layerAActive ? 2 : 1,
              }}
              draggable={false}
            />
            {/* Layer B */}
            <img
              ref={blinkLayerBRef}
              src={emotionPath(layerB)}
              alt={`saessagi-${layerB}`}
              style={{
                ...imgBaseStyle,
                opacity: layerBOpacity,
                zIndex: layerBActive ? 2 : 1,
              }}
              draggable={false}
            />
          </div>
        </div>
      </div>
    );
  },
);

SpriteAvatarRenderer.displayName = 'SpriteAvatarRenderer';

export { SpriteAvatarRenderer };
export default SpriteAvatarRenderer;
