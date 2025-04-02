# 사용자 관리 기능명세서

## 1. 개요
이 문서는 사용자 관리 모듈의 기능을 정의합니다. 사용자 등록, 조회, 수정, 삭제 기능을 포함하며, LLM 통합 기능과 사용자 활동 추적(대화, 문서, 쿼리)을 지원합니다.

## 2. 기능 요구사항

### 2.1 사용자 등록 (Create)
- **기능 ID**: USER-C-001
- **설명**: 새로운 사용자를 시스템에 등록하는 기능
- **입력 파라미터**:
  - 사용자명 (username): 문자열, 3-20자, 영문/숫자/밑줄 허용, 중복 불가
  - 이메일 (email): 유효한 이메일 형식, 중복 불가
  - 비밀번호 (password): 문자열, 8-30자, 영문/숫자/특수문자 조합
  - 이름 (name): 문자열, 2-50자
  - 역할 (role): ENUM ['USER', 'ADMIN', 'MANAGER']
- **처리 과정**:
  1. 입력값 유효성 검증
  2. 사용자명, 이메일 중복 검사
  3. 비밀번호 암호화
  4. 사용자 정보 데이터베이스 저장
  5. 사용자 생성 이벤트 발행
- **출력/결과**:
  - 성공: 201 Created, 생성된 사용자 정보 (비밀번호 제외)
  - 실패: 적절한 오류 코드와 메시지
- **권한 요구사항**: ADMIN 또는 시스템 관리자
- **비기능 요구사항**:
  - 응답 시간: 2초 이내
  - 로깅: 사용자 생성 시도 및 결과 로깅

### 2.2 사용자 조회 (Read)
- **기능 ID**: USER-R-001
- **설명**: 사용자 정보를 조회하는 기능
- **입력 파라미터**:
  - 사용자 ID (id): 숫자 또는 UUID
  - 필터링 옵션 (선택사항): 역할, 상태, 가입일 등
- **처리 과정**:
  1. 권한 검증
  2. 사용자 ID로 데이터베이스 조회
  3. 필터링 조건 적용 (필요시)
- **출력/결과**:
  - 성공: 200 OK, 사용자 정보 (비밀번호 제외)
  - 실패: 404 Not Found 또는 적절한 오류 코드
- **권한 요구사항**: 
  - 자신의 정보: 본인
  - 다른 사용자 정보: ADMIN 또는 MANAGER

### 2.3 사용자 수정 (Update)
- **기능 ID**: USER-U-001
- **설명**: 기존 사용자 정보를 수정하는 기능
- **입력 파라미터**:
  - 사용자 ID (id): 숫자 또는 UUID
  - 수정 가능한 필드:
    - 이메일 (email): 유효한 이메일 형식
    - 비밀번호 (password): 문자열, 8-30자, 영문/숫자/특수문자 조합
    - 이름 (name): 문자열
    - 상태 (status): ENUM ['ACTIVE', 'INACTIVE', 'SUSPENDED']
    - 역할 (role): ENUM ['USER', 'ADMIN', 'MANAGER']
- **처리 과정**:
  1. 사용자 존재 확인
  2. 권한 검증
  3. 입력값 유효성 검증
  4. 이메일 변경 시 중복 검사
  5. 비밀번호 변경 시 암호화
  6. 사용자 정보 업데이트
  7. 사용자 수정 이벤트 발행
- **출력/결과**:
  - 성공: 200 OK, 업데이트된 사용자 정보
  - 실패: 적절한 오류 코드와 메시지
- **권한 요구사항**:
  - 본인 정보: 본인만 수정 가능 (단, 역할 변경 불가)
  - 다른 사용자: ADMIN만 모든 필드 수정 가능

### 2.4 사용자 삭제 (Delete)
- **기능 ID**: USER-D-001
- **설명**: 사용자 계정을 삭제하는 기능
- **입력 파라미터**:
  - 사용자 ID (id): 숫자 또는 UUID
  - 삭제 유형 (deleteType): ENUM ['SOFT', 'HARD']
- **처리 과정**:
  1. 사용자 존재 확인
  2. 권한 검증
  3. 삭제 유형에 따른 처리:
     - SOFT: 사용자 상태를 'DELETED'로 변경, 데이터 보존
     - HARD: 데이터베이스에서 사용자 정보 완전 삭제
  4. 연관된 데이터 처리 (작성 게시물, 댓글 등)
  5. 사용자 삭제 이벤트 발행
- **출력/결과**:
  - 성공: 204 No Content
  - 실패: 적절한 오류 코드와 메시지
- **권한 요구사항**:
  - 본인 계정: 본인만 삭제 가능
  - 다른 사용자: ADMIN만 삭제 가능
- **비기능 요구사항**:
  - 로깅: 모든 삭제 작업은 상세 감사 로그 기록

### 2.5 사용자 대화 관리 (Conversations)
- **기능 ID**: USER-CONV-001
- **설명**: 사용자와 LLM 간의 대화 기록을 관리하는 기능
- **입력 파라미터**:
  - 사용자 ID (id): 숫자 또는 UUID
  - 대화 ID (conversationId): UUID (신규 생성 시 제외)
  - 메시지 (message): 문자열
  - 컨텍스트 (context): JSON 객체 (선택적)
  - 모델 ID (modelId): 문자열 (사용된 LLM 모델 식별자)
- **처리 과정**:
  1. 사용자 존재 확인
  2. 대화 컨텍스트 생성 또는 업데이트
  3. LLM에 메시지 전송 및 응답 수신
  4. 대화 기록 저장
  5. 대화 분석 메타데이터 생성 (감정, 의도, 주제 등)
- **출력/결과**:
  - 성공: 200 OK, LLM 응답 및 대화 메타데이터
  - 실패: 적절한 오류 코드와 메시지
- **권한 요구사항**:
  - 본인 대화: 본인만 접근 가능
  - 타인 대화: ADMIN만 조회 가능 (개인정보 보호 목적)
- **비기능 요구사항**:
  - 응답 시간: 3초 이내 (LLM 응답 시간 포함)
  - 스토리지: 대화 내역 최소 1년 보관

### 2.6 사용자 문서 관리 (Documents)
- **기능 ID**: USER-DOC-001
- **설명**: 사용자가 업로드하거나 생성한 문서를 관리하는 기능
- **입력 파라미터**:
  - 사용자 ID (id): 숫자 또는 UUID
  - 문서 ID (documentId): UUID (업데이트 시)
  - 문서 내용 (content): 문자열 또는 파일
  - 문서 타입 (type): ENUM ['TEXT', 'PDF', 'DOCX', 'MARKDOWN', 'CODE']
  - 메타데이터 (metadata): JSON 객체 (태그, 카테고리 등)
- **처리 과정**:
  1. 사용자 존재 확인
  2. 문서 유효성 검증
  3. 파일 형식에 따른 텍스트 추출 및 벡터 임베딩 생성
  4. 문서 저장 및 인덱싱
  5. 관련 메타데이터 저장
- **출력/결과**:
  - 성공: 201 Created/200 OK, 문서 ID 및 접근 URL
  - 실패: 적절한 오류 코드와 메시지
- **권한 요구사항**:
  - 문서 생성/수정: 본인 또는 적절한 권한 보유자
  - 문서 조회: 본인 또는 공유 권한 보유자
- **비기능 요구사항**:
  - 최대 문서 크기: 50MB
  - 저장 형식: 원본 및 처리된 텍스트 모두 보관

### 2.9 조직 관리 (Organization Management)
- **기능 ID**: ORG-MNG-001
- **설명**: 조직 구조 및 구성원 관리 기능
- **입력 파라미터**:
  - 조직 ID (orgId): UUID (수정/삭제 시)
  - 조직명 (name): 문자열
  - 조직 코드 (code): 문자열
  - 조직 유형 (type): ENUM ['DEPARTMENT', 'TEAM', 'DIVISION', 'COMPANY']
  - 상위 조직 ID (parentId): UUID (선택적)
  - 상태 (status): ENUM ['ACTIVE', 'INACTIVE']
- **처리 과정**:
  1. 요청자의 조직 관리 권한 확인
  2. 조직 정보 유효성 검증
  3. 조직 등록/수정/삭제
  4. 관련 구성원 및 문서 처리
- **출력/결과**:
  - 성공: 200 OK/201 Created, 조직 정보
  - 실패: 적절한 오류 코드와 메시지
- **권한 요구사항**:
  - 조직 생성: 시스템 ADMIN 또는 상위 조직 ADMIN
  - 조직 수정: 조직 ADMIN
  - 조직 삭제: 시스템 ADMIN
  - 조직 조회: 시스템 내 모든 사용자
- **비기능 요구사항**:
  - 최대 계층 구조: 5단계
  - 조직별 최대 구성원 수: 제한 없음

## 3. API 엔드포인트 정의

| 메소드 | 엔드포인트 | 기능 ID | 설명 |
|--------|------------|---------|------|
| POST | /api/users | USER-C-001 | 새 사용자 생성 |
| GET | /api/users/{id} | USER-R-001 | 특정 사용자 조회 |
| GET | /api/users | USER-R-002 | 사용자 목록 조회 |
| PUT | /api/users/{id} | USER-U-001 | 사용자 정보 전체 업데이트 |
| PATCH | /api/users/{id} | USER-U-002 | 사용자 정보 부분 업데이트 |
| DELETE | /api/users/{id} | USER-D-001 | 사용자 삭제 |
| POST | /api/users/{id}/conversations | USER-CONV-001 | 새 대화 시작 또는 메시지 추가 |
| GET | /api/users/{id}/conversations | USER-CONV-002 | 사용자 대화 목록 조회 |
| GET | /api/users/{id}/conversations/{conversationId} | USER-CONV-003 | 특정 대화 조회 |
| DELETE | /api/users/{id}/conversations/{conversationId} | USER-CONV-004 | 대화 삭제 |
| POST | /api/users/{id}/documents | USER-DOC-001 | 새 문서 업로드/생성 |
| GET | /api/users/{id}/documents | USER-DOC-002 | 사용자 문서 목록 조회 |
| GET | /api/users/{id}/documents/{documentId} | USER-DOC-003 | 특정 문서 조회 |
| PUT | /api/users/{id}/documents/{documentId} | USER-DOC-004 | 문서 업데이트 |
| DELETE | /api/users/{id}/documents/{documentId} | USER-DOC-005 | 문서 삭제 |
| POST | /api/users/{id}/queries | USER-QUERY-001 | 새 쿼리 실행 |
| GET | /api/users/{id}/queries | USER-QUERY-002 | 사용자 쿼리 기록 조회 |
| GET | /api/users/{id}/queries/{queryId} | USER-QUERY-003 | 특정 쿼리 결과 조회 |
| POST | /api/organizations | ORG-MNG-001 | 새 조직 생성 |
| GET | /api/organizations | ORG-MNG-002 | 조직 목록 조회 |
| GET | /api/organizations/{orgId} | ORG-MNG-003 | 특정 조직 조회 |
| PUT | /api/organizations/{orgId} | ORG-MNG-004 | 조직 정보 수정 |
| DELETE | /api/organizations/{orgId} | ORG-MNG-005 | 조직 삭제 |
| GET | /api/organizations/{orgId}/members | ORG-MNG-006 | 조직 구성원 목록 조회 |
| POST | /api/organizations/{orgId}/members | ORG-MNG-007 | 조직에 구성원 추가 |
| DELETE | /api/organizations/{orgId}/members/{userId} | ORG-MNG-008 | 조직에서 구성원 제거 |
| POST | /api/organizations/{orgId}/documents | ORG-DOC-001 | 조직 문서 업로드 |
| GET | /api/organizations/{orgId}/documents | ORG-DOC-002 | 조직 문서 목록 조회 |
| GET | /api/organizations/{orgId}/documents/{documentId} | ORG-DOC-003 | 특정 조직 문서 조회 |
| PUT | /api/organizations/{orgId}/documents/{documentId} | ORG-DOC-004 | 조직 문서 수정 |
| DELETE | /api/organizations/{orgId}/documents/{documentId} | ORG-DOC-005 | 조직 문서 삭제 |

## 4. 데이터 모델

### 4.1 주요 엔티티

```
Organization {
  id: UUID (PK)
  name: String
  code: String
  type: Enum ['DEPARTMENT', 'TEAM', 'DIVISION', 'COMPANY']
  parent_id: UUID (FK -> Organization.id, nullable)
  status: Enum ['ACTIVE', 'INACTIVE']
  created_at: Timestamp
  updated_at: Timestamp
}

User {
  id: UUID (PK)
  username: String
  email: String
  password: String (hashed)
  name: String
  role: Enum ['USER', 'ADMIN', 'MANAGER']
  org_id: UUID (FK -> Organization.id)  // 소속 조직
  status: Enum ['ACTIVE', 'INACTIVE', 'SUSPENDED', 'DELETED']
  preferences: JSON  // LLM 선호도, UI 설정 등
  created_at: Timestamp
  updated_at: Timestamp
  last_login_at: Timestamp
}

Conversation {
  id: UUID (PK)
  user_id: UUID (FK -> User.id)
  title: String
  status: Enum ['ACTIVE', 'ARCHIVED', 'DELETED']
  model_id: String  // 사용된 LLM 모델
  metadata: JSON  // 주제, 요약, 태그 등
  embedding: Vector  // 대화 임베딩 (검색용)
  created_at: Timestamp
  updated_at: Timestamp
}

Message {
  id: UUID (PK)
  conversation_id: UUID (FK -> Conversation.id)
  role: Enum ['USER', 'ASSISTANT', 'SYSTEM']
  content: Text
  tokens: Integer
  embedding: Vector  // 메시지 임베딩
  metadata: JSON  // 감정, 의도 등
  created_at: Timestamp
}

Document {
  id: UUID (PK)
  user_id: UUID (FK -> User.id)  // 작성자
  org_id: UUID (FK -> Organization.id, nullable)  // 소속 조직
  doc_type: Enum ['PERSONAL', 'ORGANIZATIONAL', 'PUBLIC']  // 문서 공개 범위
  filename: String
  content_type: String
  content: Text
  raw_content: Binary
  status: Enum ['ACTIVE', 'ARCHIVED', 'DELETED']
  embedding: Vector  // 문서 임베딩
  metadata: JSON  // 태그, 카테고리, 요약 등
  created_at: Timestamp
  updated_at: Timestamp
}

Query {
  id: UUID (PK)
  user_id: UUID (FK -> User.id)
  query_text: String
  query_type: Enum ['SEARCH', 'RAG', 'PROMPT', 'COMMAND']
  result: Text
  context: JSON  // 검색 범위, 필터 등
  document_refs: Array<UUID>  // 참조된 문서 IDs
  created_at: Timestamp
}
```

### 4.2 관계 모델

```
UserPreference {
  id: UUID (PK)
  user_id: UUID (FK -> User.id)
  preference_key: String
  preference_value: String
  created_at: Timestamp
  updated_at: Timestamp
}

UserOrganizationRole {
  id: UUID (PK)
  user_id: UUID (FK -> User.id)
  org_id: UUID (FK -> Organization.id)
  role: Enum ['MEMBER', 'MANAGER', 'ADMIN']  // 조직 내 역할
  is_primary: Boolean  // 주 소속 여부
  created_at: Timestamp
  updated_at: Timestamp
}

DocumentShare {
  id: UUID (PK)
  document_id: UUID (FK -> Document.id)
  shared_type: Enum ['USER', 'ORGANIZATION', 'PUBLIC']
  shared_with_id: UUID (FK -> User.id or Organization.id, nullable)  // 공유 대상 ID
  permission: Enum ['READ', 'WRITE', 'ADMIN']
  created_at: Timestamp
  expires_at: Timestamp (optional)
}

OrganizationalDocument {
  id: UUID (PK)
  org_id: UUID (FK -> Organization.id)
  document_id: UUID (FK -> Document.id)
  doc_category: Enum ['POLICY', 'GUIDELINE', 'REGULATION', 'TEMPLATE', 'REPORT']
  importance: Enum ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
  is_pinned: Boolean
  created_at: Timestamp
  updated_at: Timestamp
}

LLMUsage {
  id: UUID (PK)
  user_id: UUID (FK -> User.id)
  org_id: UUID (FK -> Organization.id, nullable)  // 조직 계정인 경우
  model_id: String
  tokens_input: Integer
  tokens_output: Integer
  cost: Decimal
  created_at: Timestamp
}
```

## 5. 유효성 검증 규칙

### 5.1 사용자 관련 규칙

- **사용자명**:
  - 필수 입력
  - 3-20자 길이
  - 영문, 숫자, 밑줄(_)만 허용
  - 중복 불가
  
- **이메일**:
  - 필수 입력
  - 유효한 이메일 형식
  - 중복 불가
  
- **비밀번호**:
  - 필수 입력
  - 8-30자 길이
  - 영문 대문자, 소문자, 숫자, 특수문자 중 3가지 이상 조합
  - 이전 비밀번호 재사용 금지 (최근 3개)

### 5.2 대화 관련 규칙

- **메시지 내용**:
  - 필수 입력
  - 최대 32,000자 (토큰 제한에 따라 조정 가능)
  - 유해 컨텐츠 필터링 적용
  
- **대화 제목**:
  - 자동 생성 또는 사용자 지정
  - 최대 100자
  
- **모델 ID**:
  - 시스템에 등록된 유효한 LLM 모델 ID

### 5.3 문서 관련 규칙

- **파일 형식**:
  - 허용된 확장자: .txt, .pdf, .docx, .md, .csv, .json, .xlsx, .pptx
  - 최대 파일 크기: 개인 문서 50MB, 조직 문서 100MB
  
- **문서 내용**:
  - 텍스트 추출 가능한 형식
  - 최대 추출 텍스트 크기: 5MB
  - 텍스트 추출 불가 시 메타데이터만 저장
  
- **메타데이터**:
  - 최대 태그 수: 20
  - 태그 길이: 1-30자
  - 필수 메타데이터: 문서 타입, 카테고리

### 5.5 조직 관련 규칙

- **조직명**:
  - 필수 입력
  - 2-50자 길이
  - 특수문자 제한 (괄호, 하이픈, 공백 허용)
  
- **조직 코드**:
  - 필수 입력
  - 2-20자 길이
  - 영문, 숫자, 하이픈(-) 허용
  - 중복 불가
  
- **계층 구조**:
  - 최대 5단계 깊이
  - 순환 참조 불가
  - 상위 조직 삭제 시 하위 조직 처리 규칙 필요

### 5.4 쿼리 관련 규칙

- **쿼리 텍스트**:
  - 필수 입력
  - 최대 4,000자
  - 적절한 쿼리 타입 지정 필요
  
- **참조 문서**:
  - 유효한 문서 ID
  - 최대 참조 문서 수: 10

## 6. 오류 케이스 및 처리

### 6.1 사용자 관련 오류

| 오류 코드 | 설명 | HTTP 상태 코드 |
|-----------|------|----------------|
| USER_001 | 사용자 이름 중복 | 409 Conflict |
| USER_002 | 이메일 중복 | 409 Conflict |
| USER_003 | 사용자 찾을 수 없음 | 404 Not Found |
| USER_004 | 유효하지 않은 비밀번호 형식 | 400 Bad Request |
| USER_005 | 권한 없음 | 403 Forbidden |

### 6.2 조직 관련 오류

| 오류 코드 | 설명 | HTTP 상태 코드 |
|-----------|------|----------------|
| ORG_001 | 조직 코드 중복 | 409 Conflict |
| ORG_002 | 조직 찾을 수 없음 | 404 Not Found |
| ORG_003 | 상위 조직 순환 참조 | 400 Bad Request |
| ORG_004 | 조직 관리 권한 없음 | 403 Forbidden |
| ORG_005 | 하위 조직 존재하여 삭제 불가 | 409 Conflict |
| ORG_006 | 구성원 존재하여 삭제 불가 | 409 Conflict |

### 6.3 문서 관련 오류

| 오류 코드 | 설명 | HTTP 상태 코드 |
|-----------|------|----------------|
| DOC_001 | 파일 형식 지원하지 않음 | 415 Unsupported Media Type |
| DOC_002 | 파일 크기 초과 | 413 Payload Too Large |
| DOC_003 | 문서 찾을 수 없음 | 404 Not Found |
| DOC_004 | 문서 접근 권한 없음 | 403 Forbidden |
| DOC_005 | 저장 공간 부족 | 507 Insufficient Storage |
| DOC_006 | 조직 문서 관리 권한 없음 | 403 Forbidden |

## 7. 보안 요구사항

- 모든 비밀번호는 bcrypt 또는 동등한 알고리즘으로 암호화 저장
- 모든 API 호출은 JWT 인증 필요
- 민감한 작업(역할 변경, 삭제 등)은 추가 인증 필요
- 비밀번호 변경 시 이전 비밀번호 확인 필요

## 8. 성능 요구사항

### 8.1 API 응답 시간
- 단일 사용자 조회: 100ms 이내 응답
- 사용자 목록 조회: 페이지당 500ms 이내 응답
- 사용자 생성/수정: 2초 이내 완료
- 대화 메시지 처리: 3초 이내 (LLM 응답 시간 제외)
- 문서 업로드 및 처리: 문서 크기 10MB당 5초 이내
- 쿼리 실행: 타입에 따라 1-5초 이내

### 8.2 확장성 요구사항
- 동시 사용자: 최소 1,000명 지원
- 대화 확장성: 사용자당 월 500개 대화, 대화당 100개 메시지
- 문서 확장성: 사용자당 총 1GB 저장공간
- 벡터 검색: 초당 50쿼리 처리 능력

### 8.3 LLM 통합 성능
- 토큰 처리 속도: 초당 최소 1,000토큰 (출력 기준)
- 컨텍스트 크기: 최대 128K 토큰 지원
- RAG 처리: 검색 포함 총 3초 이내 응답 시작

## 9. LLM 통합 요구사항

### 9.1 지원 모델
- 내부 호스팅 모델: 경량, 중형, 대형 모델 옵션 제공
- 외부 API 연동: OpenAI, Anthropic, Google 등 주요 LLM 제공자 지원
- 모델 버전 관리: 사용자별 기본 모델 설정 및 버전 전환 지원

### 9.2 프롬프트 관리
- 시스템 프롬프트: 관리자 정의 기본 프롬프트 템플릿
- 사용자 프롬프트: 사용자별 커스텀 프롬프트 저장 및 재사용
- 프롬프트 변수: 동적 컨텍스트 주입 지원

### 9.3 RAG (Retrieval-Augmented Generation)
- 문서 임베딩: 효율적인 벡터 저장 및 검색
- 관련성 랭킹: 컨텍스트 기반 문서 검색 및 순위 지정
- 청크 관리: 최적 문서 분할 및 컨텍스트 조합

### 9.4 안전성 및 제어
- 콘텐츠 필터링: 유해 컨텐츠 감지 및 차단
- 사용량 제한: 사용자별/조직별 토큰 사용량 제한
- 출력 검증: 응답 유효성 검사 및 후처리