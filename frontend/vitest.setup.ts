// M_12 P2/P3 — vitest global setup
// HTMLImageElement.decode() mock: jsdom은 decode()를 지원하지 않으므로 mock으로 대체.
// node 환경(pet-window-persistence.test.ts 등)에서는 HTMLImageElement가 없으므로 guard 추가.
if (typeof HTMLImageElement !== 'undefined') {
  Object.defineProperty(HTMLImageElement.prototype, 'decode', {
    value: () => Promise.resolve(),
    writable: true,
    configurable: true,
  });
}
