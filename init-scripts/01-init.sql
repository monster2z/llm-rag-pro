-- init-scripts/01-init.sql
-- PostgreSQL 초기화 스크립트

-- 확장 모듈 활성화
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 권한 설정
ALTER USER llm_user WITH SUPERUSER;

-- 주석
COMMENT ON DATABASE llm_rag_db IS '기업 내부용 LLM RAG 프로토타입 데이터베이스';