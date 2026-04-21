// M_12 §7.3 #2 — morning_briefing 수신 시 채팅 영역에 표시되는 배지.
// 표시 조건: useProactiveStore.morningBriefingBadgeVisible === true.
// 닫기 버튼으로 hideMorningBriefingBadge 호출.

import React from 'react';
import { useProactiveStore } from '@/store/proactive-store';

export function MorningBriefingBadge(): React.JSX.Element | null {
  const visible = useProactiveStore((s) => s.morningBriefingBadgeVisible);
  const hide = useProactiveStore((s) => s.hideMorningBriefingBadge);

  if (!visible) return null;

  return (
    <div
      data-testid="morning-briefing-badge"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 12px',
        margin: '8px',
        background: 'rgba(255, 215, 0, 0.15)',
        border: '1px solid rgba(255, 215, 0, 0.6)',
        borderRadius: '16px',
        fontSize: '13px',
        fontWeight: 500,
        color: '#333',
      }}
    >
      <span>☀</span>
      <span>아침 브리핑 시작</span>
      <button
        onClick={hide}
        aria-label="배지 닫기"
        style={{
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          fontSize: '14px',
          color: '#666',
          padding: '0 4px',
        }}
      >
        ×
      </button>
    </div>
  );
}
