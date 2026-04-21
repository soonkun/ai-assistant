// M_12 P4 §8.3.2 — 비-PDF 포맷 폴백 카드 컴포넌트
import React from 'react';
import type { SearchHit } from './types';

interface FallbackCardProps {
  hit: SearchHit;
}

/**
 * PDF 이외 포맷(docx/pptx/hwpx/md/txt 등)의 인용 폴백 UI.
 * - 원본 경로·페이지·섹션 정보를 텍스트로 표시.
 * - "시스템 기본 앱으로 열기" 버튼 → window.shell.openPath IPC 호출.
 */
export function FallbackCard({ hit }: FallbackCardProps): React.JSX.Element {
  const handleOpen = async (): Promise<void> => {
    const shellApi = (window as unknown as { shell?: { openPath(p: string): Promise<string> } }).shell;
    if (!shellApi?.openPath) {
      console.warn('[FallbackCard] shell.openPath unavailable');
      return;
    }
    try {
      const result = await shellApi.openPath(hit.source_path);
      if (result && result.length > 0) {
        // 결과 문자열이 비어 있지 않으면 에러 (Electron 규약)
        console.error('[FallbackCard] shell.openPath error:', result);
        // toaster가 있으면 에러 표시 — 없는 경우 alert fallback
        const toaster = (window as unknown as { toaster?: { error(msg: string): void } }).toaster;
        if (toaster?.error) {
          toaster.error(`파일을 열 수 없습니다: ${result}`);
        } else {
          alert(`파일을 열 수 없습니다: ${result}`);
        }
      }
    } catch (err) {
      console.error('[FallbackCard] shell.openPath threw:', err);
    }
  };

  return (
    <div
      style={{
        padding: '16px',
        border: '1px solid #ccc',
        borderRadius: '8px',
        background: '#fafafa',
        fontFamily: 'sans-serif',
        fontSize: '14px',
        lineHeight: '1.6',
      }}
    >
      <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>인용 원본 정보</div>
      <div>
        <span style={{ color: '#666' }}>원본 경로: </span>
        <span style={{ wordBreak: 'break-all' }}>{hit.source_path}</span>
      </div>
      <div>
        <span style={{ color: '#666' }}>페이지: </span>
        <span>{hit.page}</span>
      </div>
      {hit.section && (
        <div>
          <span style={{ color: '#666' }}>섹션: </span>
          <span>{hit.section}</span>
        </div>
      )}
      <button
        onClick={handleOpen}
        style={{
          marginTop: '12px',
          padding: '8px 16px',
          border: 'none',
          borderRadius: '4px',
          background: '#0070f3',
          color: '#fff',
          cursor: 'pointer',
          fontSize: '14px',
        }}
      >
        시스템 기본 앱으로 열기
      </button>
    </div>
  );
}
