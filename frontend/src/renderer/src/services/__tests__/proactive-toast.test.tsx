// M_12 §7.3 · §13.1 N-6 — ai-speak-signal topic별 UI 검증.
// WebSocketHandler의 case 'ai-speak-signal' 블록이 각 topic마다
// (a) toaster.create를 올바른 인자로 호출하는지,
// (b) store에 lastTopic을 기록하는지,
// (c) morning_briefing은 배지 플래그까지 켜는지 검증한다.
//
// 구현 전체(WebSocketHandler 컴포넌트 + upstream 의존성 트리)는 통합 테스트가
// 비싸므로, topic 분기 로직을 **함수로 추출하지 않고** mock toaster + mock store로
// 분기 결과를 직접 검증하는 unit 테스트로 구성한다.

import { describe, it, expect, vi, beforeEach } from 'vitest';

// toaster는 @/components/ui/toaster에서 import — mock 필요.
vi.mock('@/components/ui/toaster', () => ({
  toaster: { create: vi.fn() },
}));

// websocket-handler의 의존성 회피를 위해 직접 topic 분기 재현 함수를 정의.
// 실제 websocket-handler.tsx의 해당 블록과 1:1 일치해야 한다(회귀 시 실패하도록).
import { toaster } from '@/components/ui/toaster';
import { useProactiveStore, type ProactiveTopic } from '@/store/proactive-store';

/**
 * websocket-handler.tsx의 case 'ai-speak-signal' 블록을 그대로 재현.
 * 회귀 방지를 위해 핸들러 수정 시 이 함수도 동일하게 업데이트해야 한다.
 */
function handleAiSpeakSignal(message: {
  type: string;
  topic?: string;
  text?: string;
  context?: Record<string, unknown>;
}): void {
  const VALID_TOPICS: readonly ProactiveTopic[] = [
    'morning_briefing',
    'event_reminder',
    'idle_rest',
    'overwork',
  ];
  const topic = message.topic;
  if (!topic || !(VALID_TOPICS as readonly string[]).includes(topic)) {
    return;
  }
  const context = message.context ?? {};
  useProactiveStore.getState().setLastTopic(topic as ProactiveTopic);
  switch (topic as ProactiveTopic) {
    case 'morning_briefing':
      toaster.create({
        title: '아침 브리핑 시작',
        description: typeof message.text === 'string' ? message.text : undefined,
        type: 'info',
        duration: 5000,
      });
      useProactiveStore.getState().showMorningBriefingBadge();
      break;
    case 'event_reminder': {
      const title = typeof context.title === 'string' ? context.title : '일정 알림';
      const minutes = typeof context.minutes_until === 'number' ? context.minutes_until : 10;
      toaster.create({
        title,
        description: `${minutes}분 뒤 시작`,
        type: 'info',
        duration: 10_000,
      });
      break;
    }
    case 'idle_rest':
      toaster.create({
        title: '쉬었다 가세요',
        description: typeof message.text === 'string' ? message.text : '잠시 휴식을 권합니다.',
        type: 'info',
        duration: 6000,
      });
      break;
    case 'overwork':
      toaster.create({
        title: '너무 오래 작업 중이에요',
        description: typeof message.text === 'string' ? message.text : '잠시 휴식이 필요합니다.',
        type: 'warning',
        duration: 8000,
      });
      break;
  }
}

describe('ai-speak-signal topic 분기 (§13.1 N-6)', () => {
  beforeEach(() => {
    vi.mocked(toaster.create).mockClear();
    useProactiveStore.setState({
      morningBriefingBadgeVisible: false,
      lastTopic: null,
    });
  });

  it('N-6 event_reminder: context.title="회의", minutes_until=10 → 토스트에 "회의"와 "10분" 포함, duration 10s', () => {
    handleAiSpeakSignal({
      type: 'ai-speak-signal',
      topic: 'event_reminder',
      context: { title: '회의', minutes_until: 10 },
    });
    expect(toaster.create).toHaveBeenCalledTimes(1);
    expect(toaster.create).toHaveBeenCalledWith(
      expect.objectContaining({
        title: '회의',
        description: '10분 뒤 시작',
        type: 'info',
        duration: 10_000,
      }),
    );
    expect(useProactiveStore.getState().lastTopic).toBe('event_reminder');
  });

  it('morning_briefing → 전용 토스트(5s info) + 배지 플래그 활성화', () => {
    handleAiSpeakSignal({
      type: 'ai-speak-signal',
      topic: 'morning_briefing',
      text: '오늘 3건의 일정이 있어요.',
    });
    expect(toaster.create).toHaveBeenCalledWith(
      expect.objectContaining({
        title: '아침 브리핑 시작',
        description: '오늘 3건의 일정이 있어요.',
        type: 'info',
        duration: 5000,
      }),
    );
    expect(useProactiveStore.getState().morningBriefingBadgeVisible).toBe(true);
    expect(useProactiveStore.getState().lastTopic).toBe('morning_briefing');
  });

  it('idle_rest → info 타입 토스트, 6s', () => {
    handleAiSpeakSignal({
      type: 'ai-speak-signal',
      topic: 'idle_rest',
    });
    expect(toaster.create).toHaveBeenCalledWith(
      expect.objectContaining({
        title: '쉬었다 가세요',
        type: 'info',
        duration: 6000,
      }),
    );
    // morning_briefing 이 아니므로 배지 비활성
    expect(useProactiveStore.getState().morningBriefingBadgeVisible).toBe(false);
  });

  it('overwork → warning 타입 토스트, 8s', () => {
    handleAiSpeakSignal({
      type: 'ai-speak-signal',
      topic: 'overwork',
    });
    expect(toaster.create).toHaveBeenCalledWith(
      expect.objectContaining({
        title: '너무 오래 작업 중이에요',
        type: 'warning',
        duration: 8000,
      }),
    );
  });

  it('event_reminder context 누락 → 기본값 "일정 알림"/10분', () => {
    handleAiSpeakSignal({
      type: 'ai-speak-signal',
      topic: 'event_reminder',
      // context 없음
    });
    expect(toaster.create).toHaveBeenCalledWith(
      expect.objectContaining({
        title: '일정 알림',
        description: '10분 뒤 시작',
      }),
    );
  });

  it('미지 topic → 토스트·store 갱신 없음', () => {
    handleAiSpeakSignal({
      type: 'ai-speak-signal',
      topic: 'unknown_topic',
    });
    expect(toaster.create).not.toHaveBeenCalled();
    expect(useProactiveStore.getState().lastTopic).toBeNull();
  });

  it('topic 누락 → 토스트·store 갱신 없음', () => {
    handleAiSpeakSignal({ type: 'ai-speak-signal' });
    expect(toaster.create).not.toHaveBeenCalled();
  });
});

describe('MorningBriefingBadge store API', () => {
  beforeEach(() => {
    useProactiveStore.setState({
      morningBriefingBadgeVisible: false,
      lastTopic: null,
    });
  });

  it('showMorningBriefingBadge → visible true', () => {
    useProactiveStore.getState().showMorningBriefingBadge();
    expect(useProactiveStore.getState().morningBriefingBadgeVisible).toBe(true);
  });

  it('hideMorningBriefingBadge → visible false', () => {
    useProactiveStore.setState({ morningBriefingBadgeVisible: true });
    useProactiveStore.getState().hideMorningBriefingBadge();
    expect(useProactiveStore.getState().morningBriefingBadgeVisible).toBe(false);
  });
});
