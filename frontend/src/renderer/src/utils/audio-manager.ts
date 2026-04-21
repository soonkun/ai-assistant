/**
 * Global audio manager for handling audio playback and interruption.
 * M_12 §3.3 DROP: Live2D 립싱크 로직 제거됨. 오디오 재생/정지만 관리.
 */
class AudioManager {
  private currentAudio: HTMLAudioElement | null = null;

  setCurrentAudio(audio: HTMLAudioElement) {
    this.currentAudio = audio;
  }

  stopCurrentAudioAndLipSync() {
    if (this.currentAudio) {
      const audio = this.currentAudio;
      audio.pause();
      audio.src = '';
      audio.load();
      this.currentAudio = null;
    }
  }

  clearCurrentAudio(audio: HTMLAudioElement) {
    if (this.currentAudio === audio) {
      this.currentAudio = null;
    }
  }

  hasCurrentAudio(): boolean {
    return this.currentAudio !== null;
  }
}

// Export singleton instance
export const audioManager = new AudioManager();