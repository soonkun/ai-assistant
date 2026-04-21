// M_12 §3.3 DROP: useLive2DConfig/setModelInfo 제거됨.
// useInterrupt 경로 변경: canvas/live2d → hooks/utils/use-interrupt.
import { useCallback } from 'react';
import { useWebSocket } from '@/context/websocket-context';
import { useConfig } from '@/context/character-config-context';
import { useInterrupt } from '@/hooks/utils/use-interrupt';
import { useVAD } from '@/context/vad-context';
import { useSubtitle } from '@/context/subtitle-context';
import { useAiState } from '@/context/ai-state-context';

export function useSwitchCharacter() {
  const { sendMessage } = useWebSocket();
  const { confName, getFilenameByName } = useConfig();
  const { interrupt } = useInterrupt();
  const { stopMic } = useVAD();
  const { setSubtitleText } = useSubtitle();
  const { setAiState } = useAiState();

  const switchCharacter = useCallback(
    (fileName: string) => {
      const currentFilename = getFilenameByName(confName);

      if (currentFilename === fileName) {
        console.log('Skipping character switch - same configuration file');
        return;
      }

      setSubtitleText('New Character Loading...');
      interrupt();
      stopMic();
      setAiState('loading');
      // setModelInfo(undefined) 제거됨 (M_12 §3.3 DROP — Live2D 불필요)
      sendMessage({
        type: 'switch-config',
        file: fileName,
      });
      console.log('Switch Character fileName: ', fileName);
    },
    [confName, getFilenameByName, sendMessage, interrupt, stopMic, setSubtitleText, setAiState],
  );

  return { switchCharacter };
}
