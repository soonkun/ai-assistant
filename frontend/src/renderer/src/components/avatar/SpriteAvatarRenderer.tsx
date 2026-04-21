// M_12 §5.1 — SpriteAvatarRenderer placeholder
// P2에서 실제 스프라이트 PNG crossfade/애니메이션 구현 예정.
// 현재는 감정·speaking 상태를 화면 중앙 텍스트로만 표시.

import { useAvatarStore } from '@/store/avatar-store';

interface SpriteAvatarRendererProps {
  showSidebar?: boolean;
}

function SpriteAvatarRenderer({ showSidebar: _showSidebar }: SpriteAvatarRendererProps): JSX.Element {
  const { emotion, speaking } = useAvatarStore();

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'rgba(255,255,255,0.7)',
        fontSize: '14px',
        fontFamily: 'monospace',
        pointerEvents: 'none',
        userSelect: 'none',
      }}
    >
      <div style={{ marginBottom: '8px', opacity: 0.5, fontSize: '24px' }}>🌱</div>
      <div>Emotion: {emotion}</div>
      <div>Speaking: {speaking ? 'true' : 'false'}</div>
      <div style={{ marginTop: '12px', opacity: 0.4, fontSize: '11px' }}>
        [SpriteAvatarRenderer — P2에서 구현 예정]
      </div>
    </div>
  );
}

SpriteAvatarRenderer.displayName = 'SpriteAvatarRenderer';

export { SpriteAvatarRenderer };
export default SpriteAvatarRenderer;
