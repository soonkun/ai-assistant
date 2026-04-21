// M_12 P4 §5.3·§8.3 — CitationViewer React 컴포넌트
// useImperativeHandle로 CitationViewerHandle 인터페이스 노출.
// PDF: pdf.js 렌더 + bbox 하이라이트 오버레이.
// 비-PDF: FallbackCard.
import React, {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  useCallback,
} from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import type { SearchHit, CitationViewerHandle } from './types';
import { pdfBboxToViewport } from './bbox';
import { FallbackCard } from './FallbackCard';

// §8.3.3 — workerSrc는 반드시 로컬 번들 경로. CDN 금지.
// CRITICAL-2 수정: 루트 절대경로 '/assets/...'는 file:// 프로덕션에서 drive-root로
// 오해석돼 실패. window.location.href 기준 상대 URL로 해석하여 dev(vite) + prod(file://)
// 양쪽에서 동일하게 동작. viteStaticCopy가 dist/renderer/assets/pdfjs/에 복사한다.
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'assets/pdfjs/pdf.worker.min.mjs',
  window.location.href,
).href;

/** 기본 렌더 스케일 (V1 고정, V2에서 옵션화) */
const DEFAULT_SCALE = 1.5;

interface CitationViewerProps {
  /** 뷰어 영역 최대 높이 (px, 기본 600) */
  maxHeight?: number;
}

/**
 * CitationViewer — PDF 인용 뷰어 컴포넌트.
 * ref로 CitationViewerHandle을 노출한다.
 *
 * openCitation(hit):
 *   - .pdf → pdf.js 렌더 + bbox 오버레이
 *   - 그 외 → FallbackCard
 *
 * close():
 *   - pdfDocument.destroy() + DOM 정리
 */
export const CitationViewer = forwardRef<CitationViewerHandle, CitationViewerProps>(
  function CitationViewer({ maxHeight = 600 }, ref) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // 현재 열린 PDF 문서 (close 시 destroy)
    const pdfDocRef = useRef<PDFDocumentProxy | null>(null);

    const [fallbackHit, setFallbackHit] = useState<SearchHit | null>(null);
    const [isVisible, setIsVisible] = useState(false);
    const [overlayStyle, setOverlayStyle] = useState<React.CSSProperties | null>(null);
    // CRITICAL-1 수정: openCitation은 pendingHit만 설정하고, 실제 렌더는
    //   useEffect에서 DOM commit 후 canvasRef.current가 유효해진 시점에 수행한다.
    const [pendingPdfHit, setPendingPdfHit] = useState<SearchHit | null>(null);
    const [renderError, setRenderError] = useState<SearchHit | null>(null);

    /** PDF 리소스 해제 + 상태 초기화 */
    const cleanupPdf = useCallback(() => {
      if (pdfDocRef.current) {
        pdfDocRef.current.destroy();
        pdfDocRef.current = null;
      }
      if (canvasRef.current) {
        const ctx = canvasRef.current.getContext('2d');
        if (ctx) {
          ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
        }
      }
      setOverlayStyle(null);
    }, []);

    // CRITICAL-1: pendingPdfHit가 설정되면 DOM commit 후 실제 렌더 파이프라인 실행
    useEffect(() => {
      if (!pendingPdfHit) return undefined;
      let cancelled = false;

      (async () => {
        try {
          // step 2: getDocument (file:// URL)
          const url = pendingPdfHit.source_path.startsWith('file://')
            ? pendingPdfHit.source_path
            : `file://${pendingPdfHit.source_path}`;
          const loadingTask = pdfjsLib.getDocument({ url });
          const pdfDoc = await loadingTask.promise;
          if (cancelled) {
            pdfDoc.destroy();
            return;
          }
          pdfDocRef.current = pdfDoc;

          // step 3: getPage → render
          const page = await pdfDoc.getPage(pendingPdfHit.page);
          if (cancelled) return;
          const viewport = page.getViewport({ scale: DEFAULT_SCALE });

          const canvas = canvasRef.current;
          if (!canvas) {
            // useEffect가 commit 후 실행되므로 여기 도달하면 설계 위반.
            // 방어적으로 로그 후 폴백 전환.
            console.error('[CitationViewer] canvas ref not available after commit');
            setRenderError(pendingPdfHit);
            return;
          }
          canvas.width = viewport.width;
          canvas.height = viewport.height;

          const ctx = canvas.getContext('2d');
          if (!ctx) {
            console.error('[CitationViewer] cannot get 2d context');
            setRenderError(pendingPdfHit);
            return;
          }

          await page.render({ canvasContext: ctx, viewport }).promise;
          if (cancelled) return;

          // step 4-5: bbox 오버레이
          if (pendingPdfHit.bbox) {
            const rect = pdfBboxToViewport(
              pendingPdfHit.bbox,
              viewport.height / DEFAULT_SCALE,
              DEFAULT_SCALE,
            );
            setOverlayStyle({
              position: 'absolute',
              left: `${rect.x_px}px`,
              top: `${rect.y_px}px`,
              width: `${rect.w_px}px`,
              height: `${rect.h_px}px`,
              border: '2px solid rgba(255,200,0,0.9)',
              background: 'rgba(255,200,0,0.25)',
              pointerEvents: 'none',
            });
          } else {
            setOverlayStyle(null);
          }

          // step 5: 페이지 상단으로 스크롤
          if (containerRef.current) {
            containerRef.current.scrollTop = 0;
          }
        } catch (err) {
          if (cancelled) return;
          console.error('[CitationViewer] PDF render error:', err);
          cleanupPdf();
          setRenderError(pendingPdfHit);
        }
      })();

      return () => {
        cancelled = true;
      };
    }, [pendingPdfHit, cleanupPdf]);

    // renderError가 설정되면 폴백 카드로 전환
    useEffect(() => {
      if (renderError) {
        setFallbackHit(renderError);
        setPendingPdfHit(null);
        setRenderError(null);
      }
    }, [renderError]);

    useImperativeHandle(
      ref,
      (): CitationViewerHandle => ({
        async openCitation(hit: SearchHit): Promise<void> {
          // 기존 리소스 해제
          cleanupPdf();
          setFallbackHit(null);
          setRenderError(null);

          const ext = hit.source_path.split('.').pop()?.toLowerCase() ?? '';

          // §8.3.2 — 비-PDF 폴백
          if (ext !== 'pdf') {
            console.info('[CitationViewer] non-PDF fallback:', ext, hit.source_path);
            setPendingPdfHit(null);
            setFallbackHit(hit);
            setIsVisible(true);
            return;
          }

          // §8.3.1 — PDF 렌더 파이프라인 (실제 렌더는 useEffect에서 수행)
          setIsVisible(true);
          setPendingPdfHit(hit);
        },

        close(): void {
          cleanupPdf();
          setFallbackHit(null);
          setPendingPdfHit(null);
          setRenderError(null);
          setIsVisible(false);
        },
      }),
      [cleanupPdf],
    );

    if (!isVisible) {
      return null;
    }

    if (fallbackHit) {
      return <FallbackCard hit={fallbackHit} />;
    }

    return (
      <div
        ref={containerRef}
        style={{
          position: 'relative',
          maxHeight: `${maxHeight}px`,
          overflow: 'auto',
          border: '1px solid #ddd',
          borderRadius: '4px',
          background: '#525659',
        }}
      >
        <div style={{ position: 'relative', display: 'inline-block' }}>
          <canvas ref={canvasRef} style={{ display: 'block' }} />
          {overlayStyle && (
            <div data-testid="citation-overlay" style={overlayStyle} />
          )}
        </div>
      </div>
    );
  },
);

CitationViewer.displayName = 'CitationViewer';
