-- Track 4 Step 2 — Phase 1: 화자 주석 컬럼 추가
-- 작성일: 2026-04-20
-- 적용 위치: Supabase SQL Editor

-- 1) media_segments 테이블에 speaker_id 컬럼 추가 (nullable)
ALTER TABLE media_segments
  ADD COLUMN IF NOT EXISTS speaker_id TEXT;

-- 2) 확인
--   실행 후 컬럼이 잘 들어갔는지 아래 쿼리로 검증:
-- SELECT column_name, data_type, is_nullable
--   FROM information_schema.columns
--  WHERE table_name = 'media_segments'
--    AND column_name = 'speaker_id';
--
-- 기존 행의 speaker_id는 NULL 상태로 남는다 (Phase 2 스크립트가 채움).

-- 3) match_segments RPC는 건드리지 않는다
--   - RPC 반환 테이블에 speaker_id를 추가하면 기존 함수 덮어쓰기 리스크 (embedding 차원 등)
--   - 대신 Phase 4에서 검색 결과를 받은 뒤 media_segments에서
--     (media_id, chunk_index)로 speaker_id를 후속 조회해 enrich한다.
