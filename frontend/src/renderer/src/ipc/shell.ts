// M_12 P4 §8.3.2 — shell IPC wrapper (renderer-side)
// preload(window.shell)에 위임하는 얇은 wrapper.
// preload 없는 환경(웹 빌드)은 경고 로그 + no-op.

export interface ShellApi {
  /** 로컬 절대 경로의 파일을 시스템 기본 앱으로 열기. 실패 시 에러 메시지 문자열 반환. */
  openPath(absolutePath: string): Promise<string>;
}

type WindowShell = {
  shell?: ShellApi;
};

function getApi(): ShellApi | undefined {
  return (window as unknown as WindowShell).shell;
}

/**
 * shell IPC wrapper.
 * preload에서 window.shell로 노출된 API를 호출한다.
 * preload가 없는 경우(예: 웹 빌드)는 경고 로그 후 resolve('').
 */
export const shellIpc: ShellApi = {
  openPath(absolutePath: string): Promise<string> {
    const api = getApi();
    if (api?.openPath) return api.openPath(absolutePath);
    console.warn('[ShellIpc] preload unavailable; openPath() no-op');
    return Promise.resolve('');
  },
};
