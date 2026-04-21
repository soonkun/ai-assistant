/* eslint-disable no-use-before-define */
import { Subject } from 'rxjs';
import i18next from 'i18next';
// ModelInfo 제거됨 (M_12 §3.3 DROP — Live2D 제거)
import { HistoryInfo } from '@/context/websocket-context';
import { ConfigFile } from '@/context/character-config-context';
import { toaster } from '@/components/ui/toaster';

export interface DisplayText {
  text: string;
  name: string;
  avatar: string;
}

interface BackgroundFile {
  name: string;
  url: string;
}

export interface AudioPayload {
  type: 'audio';
  audio?: string;
  volumes?: number[];
  slice_length?: number;
  display_text?: DisplayText;
  actions?: Actions;
}

export interface Message {
  id: string;
  content: string;
  role: "ai" | "human";
  timestamp: string;
  name?: string;
  avatar?: string;

  // Fields for different message types (make optional)
  type?: 'text' | 'tool_call_status'; // Add possible types, default to 'text' if omitted
  tool_id?: string; // Specific to tool calls
  tool_name?: string; // Specific to tool calls
  status?: 'running' | 'completed' | 'error'; // Specific to tool calls
}

export interface Actions {
  expressions?: string[] | number [];
  pictures?: string[];
  sounds?: string[];
}

export interface MessageEvent {
  tool_id: any;
  tool_name: any;
  name: any;
  status: any;
  content: string;
  timestamp: string;
  type: string;
  audio?: string;
  volumes?: number[];
  slice_length?: number;
  files?: BackgroundFile[];
  actions?: Actions;
  text?: string;
  // model_info 제거됨 (M_12 §3.3 DROP — Live2D 제거)
  conf_name?: string;
  conf_uid?: string;
  uids?: string[];
  messages?: Message[];
  history_uid?: string;
  success?: boolean;
  histories?: HistoryInfo[];
  configs?: ConfigFile[];
  message?: string;
  members?: string[];
  is_owner?: boolean;
  client_uid?: string;
  forwarded?: boolean;
  display_text?: DisplayText;
  browser_view?: {
    debuggerFullscreenUrl: string;
    debuggerUrl: string;
    pages: {
      id: string;
      url: string;
      faviconUrl: string;
      title: string;
      debuggerUrl: string;
      debuggerFullscreenUrl: string;
    }[];
    wsUrl: string;
    sessionId?: string;
  };
  // M_12 P1 — 신규 수신 타입 페이로드 필드 (M_01 §B, §C)
  /** avatar-state: M_08 §7 */
  emotion?: string;
  crossfade_ms?: number;
  speaking?: boolean;
  /** continuous-capture-state: M_01 §C */
  running?: boolean;
  interval_sec?: number;
  /** dnd-state: M_01 §C, CR-10 */
  enabled?: boolean;
  /** ai-speak-signal: M_11 §7.3 */
  topic?: string;
  context?: Record<string, unknown>;
}

// Get translation function for error messages
const getTranslation = () => i18next.t.bind(i18next);

class WebSocketService {
  private static instance: WebSocketService;

  private ws: WebSocket | null = null;

  private messageSubject = new Subject<MessageEvent>();

  private stateSubject = new Subject<'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED'>();

  private currentState: 'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED' = 'CLOSED';

  static getInstance() {
    if (!WebSocketService.instance) {
      WebSocketService.instance = new WebSocketService();
    }
    return WebSocketService.instance;
  }

  private initializeConnection() {
    this.sendMessage({
      type: 'fetch-backgrounds',
    });
    this.sendMessage({
      type: 'fetch-configs',
    });
    this.sendMessage({
      type: 'fetch-history-list',
    });
    this.sendMessage({
      type: 'create-new-history',
    });
  }

  connect(url: string) {
    if (this.ws?.readyState === WebSocket.CONNECTING ||
        this.ws?.readyState === WebSocket.OPEN) {
      this.disconnect();
    }

    try {
      this.ws = new WebSocket(url);
      this.currentState = 'CONNECTING';
      this.stateSubject.next('CONNECTING');

      this.ws.onopen = () => {
        this.currentState = 'OPEN';
        this.stateSubject.next('OPEN');
        this.initializeConnection();
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.messageSubject.next(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
          toaster.create({
            title: `${getTranslation()('error.failedParseWebSocket')}: ${error}`,
            type: "error",
            duration: 2000,
          });
        }
      };

      this.ws.onclose = () => {
        this.currentState = 'CLOSED';
        this.stateSubject.next('CLOSED');
      };

      this.ws.onerror = () => {
        this.currentState = 'CLOSED';
        this.stateSubject.next('CLOSED');
      };
    } catch (error) {
      console.error('Failed to connect to WebSocket:', error);
      this.currentState = 'CLOSED';
      this.stateSubject.next('CLOSED');
    }
  }

  sendMessage(message: object) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not open. Unable to send message:', message);
      toaster.create({
        title: getTranslation()('error.websocketNotOpen'),
        type: 'error',
        duration: 2000,
      });
    }
  }

  onMessage(callback: (message: MessageEvent) => void) {
    return this.messageSubject.subscribe(callback);
  }

  onStateChange(callback: (state: 'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED') => void) {
    return this.stateSubject.subscribe(callback);
  }

  disconnect() {
    this.ws?.close();
    this.ws = null;
  }

  getCurrentState() {
    return this.currentState;
  }

  // M_12 P1 — 송신 헬퍼 메서드 (M_01 §B-1~B-4)

  /**
   * 화면 캡처 트리거 전송 (M_01 §B-1)
   * @param prompt - 캡처 분석 프롬프트
   * @param monitorIndex - 모니터 인덱스 (기본값 0)
   */
  sendScreenshotTrigger(prompt?: string, monitorIndex?: number): void {
    if (this.currentState !== 'OPEN') {
      console.warn('[WS] sendScreenshotTrigger: WebSocket not open');
      return;
    }
    this.ws!.send(JSON.stringify({
      type: 'screenshot-trigger',
      ...(prompt !== undefined && { prompt }),
      ...(monitorIndex !== undefined && { monitor_index: monitorIndex }),
    }));
  }

  /**
   * 연속 캡처 시작 전송 (M_01 §B-2)
   * @param intervalSec - 캡처 간격(초)
   * @param monitorIndex - 모니터 인덱스
   * @param promptTemplate - 프롬프트 템플릿
   */
  sendStartContinuousCapture(
    intervalSec: number,
    monitorIndex?: number,
    promptTemplate?: string,
  ): void {
    if (this.currentState !== 'OPEN') {
      console.warn('[WS] sendStartContinuousCapture: WebSocket not open');
      return;
    }
    this.ws!.send(JSON.stringify({
      type: 'start-continuous-capture',
      interval_sec: intervalSec,
      ...(monitorIndex !== undefined && { monitor_index: monitorIndex }),
      ...(promptTemplate !== undefined && { prompt_template: promptTemplate }),
    }));
  }

  /**
   * 연속 캡처 중지 전송 (M_01 §B-3)
   */
  sendStopContinuousCapture(): void {
    if (this.currentState !== 'OPEN') {
      console.warn('[WS] sendStopContinuousCapture: WebSocket not open');
      return;
    }
    this.ws!.send(JSON.stringify({ type: 'stop-continuous-capture' }));
  }

  /**
   * DND 상태 설정 전송 (M_01 §B-4, CR-10)
   * @param enabled - DND 활성화 여부
   */
  sendSetDnd(enabled: boolean): void {
    if (this.currentState !== 'OPEN') {
      console.warn('[WS] sendSetDnd: WebSocket not open');
      return;
    }
    this.ws!.send(JSON.stringify({ type: 'set-dnd', enabled }));
  }
}

export const wsService = WebSocketService.getInstance();
