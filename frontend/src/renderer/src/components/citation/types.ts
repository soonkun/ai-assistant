// M_12 P4 §5.3 — CitationViewer 인터페이스 타입 정의
// SearchHit: 인용 검색 결과 단위 (PDF 좌하단 원점 좌표계)

/** PDF 또는 기타 문서의 인용 위치 정보 */
export interface SearchHit {
  /** 로컬 절대 경로 (file://) */
  source_path: string;
  /** 1-based 페이지 번호 */
  page: number;
  section?: string;
  /** PDF 좌하단 원점 좌표계 (단위: pt) */
  bbox?: { x: number; y: number; w: number; h: number };
  chunk_id?: string;
  score?: number;
}

/** CitationViewer 컴포넌트 명령형 핸들 인터페이스 (§5.3) */
export interface CitationViewerHandle {
  openCitation(hit: SearchHit): Promise<void>;
  close(): void;
}
