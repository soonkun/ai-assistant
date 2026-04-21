// M_12 P2 — vitest global setup
// HTMLImageElement.decode() mock: jsdom은 decode()를 지원하지 않으므로 mock으로 대체.
Object.defineProperty(HTMLImageElement.prototype, 'decode', {
  value: () => Promise.resolve(),
  writable: true,
  configurable: true,
});
