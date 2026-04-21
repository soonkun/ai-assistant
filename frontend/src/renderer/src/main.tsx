// M_12 §3.3 DROP: Live2D Cubism Core 로딩 및 LAppAdapter 제거됨.
// SpriteAvatarRenderer(P2에서 구현)로 교체됨.
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App';
import './i18n';

const originalConsoleWarn = console.warn;
console.warn = (...args: unknown[]) => {
  if (typeof args[0] === 'string' && args[0].includes('onnxruntime')) {
    return;
  }
  originalConsoleWarn.apply(console, args);
};

// Suppress specific console.error messages from @chatscope/chat-ui-kit-react
const originalConsoleError = console.error;
const errorMessagesToIgnore = ['Warning: Failed'];
console.error = (...args: unknown[]) => {
  if (typeof args[0] === 'string') {
    const shouldIgnore = errorMessagesToIgnore.some((msg) =>
      (args[0] as string).startsWith(msg as string),
    );
    if (shouldIgnore) {
      return;
    }
  }
  originalConsoleError.apply(console, args);
};

createRoot(document.getElementById('root')!).render(<App />);
