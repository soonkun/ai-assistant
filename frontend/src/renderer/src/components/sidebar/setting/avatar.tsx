// M_12 §3.3 DROP: Live2D 설정 패널 → 아바타(스프라이트) placeholder 설정 패널
// 실제 스프라이트 설정은 P2에서 구현 예정.

import { Stack, Text } from '@chakra-ui/react';
import { settingStyles } from './setting-styles';

interface AvatarSettingProps {
  onSave?: (callback: () => void) => () => void;
  onCancel?: (callback: () => void) => () => void;
}

function AvatarSetting({ onSave: _onSave, onCancel: _onCancel }: AvatarSettingProps): JSX.Element {
  return (
    <Stack {...settingStyles.common.container}>
      <Text fontSize="sm" color="gray.400">
        아바타 (스프라이트) 설정
      </Text>
      <Text fontSize="xs" color="gray.500">
        P2에서 구현 예정입니다. 현재는 감정 상태 텍스트 표시만 지원됩니다.
      </Text>
    </Stack>
  );
}

export default AvatarSetting;
