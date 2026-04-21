// M_12 §6 proactiveSlice — ai-speak-signal topic별 UI 상태.
// §7.3 #2 morning_briefing 배지는 본 store를 통해 가시성 토글된다.

import { create } from 'zustand';

export type ProactiveTopic =
  | 'morning_briefing'
  | 'event_reminder'
  | 'idle_rest'
  | 'overwork';

interface ProactiveState {
  /** §7.3 #2: morning_briefing 수신 시 채팅 영역 배지 1회 표시 플래그. */
  morningBriefingBadgeVisible: boolean;
  /** 최근 수신한 topic (디버깅·테스트용). */
  lastTopic: ProactiveTopic | null;

  showMorningBriefingBadge(): void;
  hideMorningBriefingBadge(): void;
  setLastTopic(topic: ProactiveTopic): void;
}

export const useProactiveStore = create<ProactiveState>((set) => ({
  morningBriefingBadgeVisible: false,
  lastTopic: null,

  showMorningBriefingBadge: (): void => set({ morningBriefingBadgeVisible: true }),
  hideMorningBriefingBadge: (): void => set({ morningBriefingBadgeVisible: false }),
  setLastTopic: (topic: ProactiveTopic): void => set({ lastTopic: topic }),
}));
