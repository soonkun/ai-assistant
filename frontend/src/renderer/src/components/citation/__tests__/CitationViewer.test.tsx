// M_12 P4 §8.3 — CitationViewer 컴포넌트 단위 테스트 (≥4건)
// pdf.js는 vi.mock으로 대체. jsdom 환경에서 canvas는 mock 처리.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import React from 'react';
import type { CitationViewerHandle, SearchHit } from '../types';
import { CitationViewer } from '../CitationViewer';

// pdf.js mock — vi.mock은 파일 최상단으로 hoisting됨
vi.mock('pdfjs-dist', () => {
  const mockDestroy = vi.fn().mockResolvedValue(undefined);
  const mockRenderPromise = { promise: Promise.resolve() };
  const mockGetPage = vi.fn().mockResolvedValue({
    getViewport: vi.fn().mockReturnValue({ width: 595, height: 842, scale: 1.5 }),
    render: vi.fn().mockReturnValue(mockRenderPromise),
  });
  const mockPdfDoc = {
    getPage: mockGetPage,
    destroy: mockDestroy,
  };
  const mockGetDocument = vi.fn().mockReturnValue({
    promise: Promise.resolve(mockPdfDoc),
  });

  return {
    GlobalWorkerOptions: { workerSrc: '' },
    getDocument: mockGetDocument,
    _mocks: { mockGetDocument, mockGetPage, mockDestroy },
  };
});

// canvas.getContext mock — jsdom은 2d context 지원 안 함
beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    drawImage: vi.fn(),
    putImageData: vi.fn(),
    getImageData: vi.fn(),
    scale: vi.fn(),
    translate: vi.fn(),
    transform: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    stroke: vi.fn(),
    fill: vi.fn(),
  } as unknown as CanvasRenderingContext2D);
});

async function getPdfjsMocks() {
  const mod = await import('pdfjs-dist') as unknown as {
    _mocks: {
      mockGetDocument: ReturnType<typeof vi.fn>;
      mockGetPage: ReturnType<typeof vi.fn>;
      mockDestroy: ReturnType<typeof vi.fn>;
    };
  };
  return mod._mocks;
}

describe('CitationViewer', () => {
  // 테스트 #1 — .pdf 확장자 → pdf.js 파이프라인 호출
  it('#1 .pdf 확장자 → getDocument 호출', async () => {
    const { mockGetDocument, mockGetPage } = await getPdfjsMocks();
    mockGetDocument.mockClear();
    mockGetPage.mockClear();

    const ref = React.createRef<CitationViewerHandle>();
    render(<CitationViewer ref={ref} />);

    const hit: SearchHit = {
      source_path: '/home/user/docs/report.pdf',
      page: 1,
    };

    await act(async () => {
      await ref.current?.openCitation(hit);
    });

    expect(mockGetDocument).toHaveBeenCalledTimes(1);
    expect(mockGetDocument).toHaveBeenCalledWith(
      expect.objectContaining({ url: 'file:///home/user/docs/report.pdf' }),
    );
    expect(mockGetPage).toHaveBeenCalledWith(1);
  });

  // 테스트 #2 — .docx 확장자 → FallbackCard 렌더
  it('#2 .docx 확장자 → FallbackCard 렌더 (getDocument 호출 없음)', async () => {
    const { mockGetDocument } = await getPdfjsMocks();
    mockGetDocument.mockClear();

    const ref = React.createRef<CitationViewerHandle>();
    render(<CitationViewer ref={ref} />);

    const hit: SearchHit = {
      source_path: '/home/user/docs/report.docx',
      page: 3,
      section: '3장 결론',
    };

    await act(async () => {
      await ref.current?.openCitation(hit);
    });

    // FallbackCard가 렌더되어 원본 경로와 페이지 정보가 표시되어야 함
    expect(screen.getByText(/원본 경로/i)).toBeTruthy();
    expect(screen.getByText(/\/home\/user\/docs\/report\.docx/)).toBeTruthy();
    expect(screen.getByText(/3장 결론/)).toBeTruthy();
    expect(mockGetDocument).not.toHaveBeenCalled();
  });

  // 테스트 #3 — openCitation 호출 후 페이지 번호·bbox 검증 + 오버레이 DOM 확인 (MAJOR-1 회귀)
  it('#3 bbox 있을 때 getPage(N) 호출 + 오버레이 DOM 생성', async () => {
    const { mockGetDocument, mockGetPage } = await getPdfjsMocks();
    mockGetDocument.mockClear();
    mockGetPage.mockClear();

    const ref = React.createRef<CitationViewerHandle>();
    const { container } = render(<CitationViewer ref={ref} />);

    const hit: SearchHit = {
      source_path: '/docs/file.pdf',
      page: 5,
      bbox: { x: 100, y: 200, w: 300, h: 50 },
    };

    await act(async () => {
      await ref.current?.openCitation(hit);
    });
    // useEffect 내부 비동기 렌더가 완료될 때까지 microtask/promise flush
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    // 5페이지를 getPage로 요청해야 함
    expect(mockGetPage).toHaveBeenCalledWith(5);
    // MAJOR-1 회귀: bbox 제공 시 citation-overlay DOM이 실제로 존재해야 함
    const overlay = container.querySelector('[data-testid="citation-overlay"]');
    expect(overlay).not.toBeNull();
  });

  // 테스트 #5 — bbox 누락 시 오버레이 DOM 없음 (§13.2 E-7)
  it('#5 bbox 누락 시 스크롤만 수행하고 오버레이 DOM 없음', async () => {
    const { mockGetDocument, mockGetPage } = await getPdfjsMocks();
    mockGetDocument.mockClear();
    mockGetPage.mockClear();

    const ref = React.createRef<CitationViewerHandle>();
    const { container } = render(<CitationViewer ref={ref} />);

    const hit: SearchHit = {
      source_path: '/docs/file.pdf',
      page: 3,
      // bbox 없음
    };

    await act(async () => {
      await ref.current?.openCitation(hit);
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockGetPage).toHaveBeenCalledWith(3);
    // 오버레이 DOM 없어야 함
    const overlay = container.querySelector('[data-testid="citation-overlay"]');
    expect(overlay).toBeNull();
  });

  // 테스트 #4 — close() → pdfDocument.destroy() 호출
  it('#4 close() → pdfDocument.destroy() 호출', async () => {
    const { mockGetDocument, mockGetPage, mockDestroy } = await getPdfjsMocks();
    mockGetDocument.mockClear();
    mockGetPage.mockClear();
    mockDestroy.mockClear();

    const ref = React.createRef<CitationViewerHandle>();
    render(<CitationViewer ref={ref} />);

    const hit: SearchHit = {
      source_path: '/docs/report.pdf',
      page: 2,
    };

    await act(async () => {
      await ref.current?.openCitation(hit);
    });

    await act(async () => {
      ref.current?.close();
    });

    expect(mockDestroy).toHaveBeenCalledTimes(1);
  });
});
