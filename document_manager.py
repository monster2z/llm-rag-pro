# document_manager.py
import streamlit as st
import pandas as pd
import os
import time
import uuid
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from db_models import DocumentMetadata, CategoryPermission

class DocumentManager:
    """문서 관리 클래스: 문서 업로드, 검색, 권한 관리 등 기능 제공"""
    
    def __init__(self, data_dir: str, db_manager=None):
        self.data_dir = data_dir
        self.db_manager = db_manager
        os.makedirs(data_dir, exist_ok=True)
    
    def add_document(self, doc_metadata: Dict[str, Any]) -> Optional[DocumentMetadata]:
        """문서 메타데이터 추가"""
        if not self.db_manager:
            return None
            
        try:
            return self.db_manager.add_document(doc_metadata)
        except Exception as e:
            print(f"문서 추가 중 오류 발생: {str(e)}")
            return None
    
    def get_all_active_documents(self) -> List[DocumentMetadata]:
        """활성 상태인 모든 문서 조회"""
        if not self.db_manager:
            return []
            
        try:
            return self.db_manager.get_active_documents()
        except Exception as e:
            print(f"문서 조회 중 오류 발생: {str(e)}")
            return []
    
    def get_documents_by_category(self, category: str) -> List[DocumentMetadata]:
        """카테고리별 문서 조회"""
        if not self.db_manager:
            return []
            
        try:
            return self.db_manager.get_documents_by_category(category)
        except Exception as e:
            print(f"카테고리별 문서 조회 중 오류 발생: {str(e)}")
            return []
        
    # DocumentManager 클래스에 추가할 get_document_by_id 메소드 수정
    def get_document_by_id(self, doc_id: str):
        """문서 ID로 문서 정보 조회"""
        if not self.db_manager:
            return None
            
        try:
            # 문서 조회
            from db_models import DocumentMetadata
            doc = self.db_manager.session.query(DocumentMetadata).filter(
                DocumentMetadata.doc_id == doc_id
            ).first()
            
            if not doc:
                return None
                
            # SQLAlchemy 모델을 딕셔너리로 변환
            return {
                "doc_id": doc.doc_id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "category": doc.category,
                "version": doc.version,
                "chunks": doc.chunks,
                "uploaded_by": doc.uploaded_by,
                "upload_time": str(doc.upload_time),
                "is_active": doc.is_active,
                "vector_store_path": doc.vector_store_path,
                "description": doc.description
            }
        except Exception as e:
            print(f"문서 조회 중 오류 발생: {str(e)}")
            return None
    
    def get_available_categories(self) -> List[str]:
        """사용 가능한 모든 카테고리 조회"""
        if not self.db_manager:
            return []
            
        try:
            documents = self.db_manager.get_active_documents()
            categories = set(doc.category for doc in documents)
            return sorted(list(categories))
        except Exception as e:
            print(f"카테고리 조회 중 오류 발생: {str(e)}")
            return []
    
    def check_document_permission(self, username: str, category: str, permission_type: str = 'view') -> bool:
        """문서 접근 권한 확인"""
        if not self.db_manager:
            return True  # DB가 없는 경우 기본적으로 모든 권한 허용
            
        try:
            permissions = self.db_manager.session.query(CategoryPermission).filter(
                CategoryPermission.username == username,
                CategoryPermission.category == category
            ).first()
            
            if not permissions:
                return False
                
            if permission_type == 'view':
                return permissions.can_view
            elif permission_type == 'upload':
                return permissions.can_upload
            return False
        except Exception as e:
            print(f"권한 확인 중 오류 발생: {str(e)}")
            return False
    
    def add_category_permission(self, username: str, category: str, can_view: bool = True, can_upload: bool = False) -> bool:
        """카테고리 권한 추가"""
        if not self.db_manager:
            return False
            
        try:
            permission = CategoryPermission(
                username=username,
                category=category,
                can_view=can_view,
                can_upload=can_upload,
                assigned_by=username,  # 현재 사용자를 할당자로 설정
                assigned_at=time.strftime("%Y-%m-%d %H:%M:%S")
            )
            
            self.db_manager.session.add(permission)
            self.db_manager.session.commit()
            return True
        except Exception as e:
            print(f"권한 추가 중 오류 발생: {str(e)}")
            return False
    
    def update_document_status(self, doc_id: str, is_active: bool) -> bool:
        """문서 상태 업데이트"""
        if not self.db_manager:
            return False
            
        try:
            document = self.db_manager.session.query(DocumentMetadata).filter(
                DocumentMetadata.doc_id == doc_id
            ).first()
            
            if document:
                document.is_active = is_active
                self.db_manager.session.commit()
                return True
            return False
        except Exception as e:
            print(f"문서 상태 업데이트 중 오류 발생: {str(e)}")
            return False
    def delete_document(self, doc_id: str, permanently: bool = False) -> bool:
        """문서 삭제 - permanently가 True면 완전 삭제, False면 비활성화만"""
        if not self.db_manager:
            return False
            
        try:
            # 문서 조회
            from db_models import DocumentMetadata
            document = self.db_manager.session.query(DocumentMetadata).filter(
                DocumentMetadata.doc_id == doc_id
            ).first()
            
            if not document:
                return False
                
            if permanently:
                # 벡터 저장소 경로 저장
                vector_store_path = document.vector_store_path
                
                # 완전 삭제 (DB에서 삭제)
                self.db_manager.session.delete(document)
                
                # 벡터 저장소 파일 삭제 (있는 경우)
                if vector_store_path and os.path.exists(vector_store_path):
                    import shutil
                    shutil.rmtree(vector_store_path, ignore_errors=True)
            else:
                # 비활성화만 (is_active = False로 설정)
                document.is_active = False
                
            self.db_manager.session.commit()
            return True
        except Exception as e:
            print(f"문서 삭제 중 오류 발생: {str(e)}")
            self.db_manager.session.rollback()
            return False
    
    def create_document_version_log(self, doc_id: str, previous_version: int, 
                                  new_version: int, change_description: str,
                                  changed_by: str) -> bool:
        """문서 버전 변경 로그 생성"""
        if not self.db_manager:
            return False
            
        try:
            from db_models import DocumentVersionLog
            
            # 로그 생성
            log = DocumentVersionLog(
                doc_id=doc_id,
                previous_version=previous_version,
                new_version=new_version,
                change_description=change_description,
                changed_by=changed_by,
                changed_at=datetime.datetime.utcnow()
            )
            
            self.db_manager.session.add(log)
            self.db_manager.session.commit()
            return True
        except Exception as e:
            print(f"버전 로그 생성 중 오류 발생: {str(e)}")
            self.db_manager.session.rollback()
            return False
    
    def get_document_version_history(self, doc_id: str) -> list:
        """문서의 버전 변경 기록 조회"""
        if not self.db_manager:
            return []
            
        try:
            from db_models import DocumentVersionLog
            
            # 로그 조회
            logs = self.db_manager.session.query(DocumentVersionLog).filter(
                DocumentVersionLog.doc_id == doc_id
            ).order_by(DocumentVersionLog.changed_at.desc()).all()
            
            # SQLAlchemy 객체를 사전 형태로 변환
            result = []
            for log in logs:
                result.append({
                    "previous_version": log.previous_version,
                    "new_version": log.new_version,
                    "change_description": log.change_description,
                    "changed_by": log.changed_by,
                    "changed_at": str(log.changed_at)
                })
            
            return result
        except Exception as e:
            print(f"버전 기록 조회 중 오류 발생: {str(e)}")
            return []
        
# 문서 탐색 및 관리 컴포넌트 업데이트
def document_explorer(doc_manager):
    """개선된 문서 탐색 컴포넌트 - 삭제 기능 추가"""
    st.title("문서 탐색")
    
    # 사용 가능한 카테고리 목록 가져오기
    categories = doc_manager.get_available_categories()
    
    if not categories:
        st.info("등록된 문서가 없습니다. 관리자에게 문서 등록을 요청하세요.")
        return
    
    # 검색 기능 추가
    search_term = st.text_input("문서 검색", placeholder="파일명 또는 카테고리로 검색")
    
    # 삭제 확인 상태 관리
    if "delete_doc_confirm" not in st.session_state:
        st.session_state.delete_doc_confirm = None
    
    # 선택된 문서 ID 상태 관리
    if "selected_doc_id" not in st.session_state:
        st.session_state.selected_doc_id = None
    
    # 카테고리별 탭 생성
    if len(categories) > 0:
        tabs = st.tabs(categories)
        
        for i, category in enumerate(categories):
            with tabs[i]:
                # 해당 카테고리의 문서 목록 가져오기
                documents = doc_manager.get_documents_by_category(category)
                
                # 검색어로 필터링
                if search_term:
                    filtered_docs = []
                    for doc in documents:
                        filename = doc.filename if hasattr(doc, 'filename') else ""
                        description = doc.description if hasattr(doc, 'description') else ""
                        if (search_term.lower() in filename.lower() or 
                            search_term.lower() in description.lower()):
                            filtered_docs.append(doc)
                else:
                    filtered_docs = documents
                
                if not filtered_docs:
                    st.info(f"'{category}' 카테고리에 {search_term}와(과) 일치하는 문서가 없습니다.")
                    continue
                
                # 문서를 파일명으로 그룹화하여 버전별로 표시
                grouped_docs = {}
                for doc in filtered_docs:
                    filename = doc.filename if hasattr(doc, 'filename') else "Unknown"
                    if filename not in grouped_docs:
                        grouped_docs[filename] = []
                    grouped_docs[filename].append(doc)
                
                # 각 문서 그룹 표시
                for filename, docs in grouped_docs.items():
                    # 버전별 정렬 (SQLAlchemy 객체에 직접 접근)
                    docs.sort(key=lambda x: x.version if hasattr(x, 'version') else 0, reverse=True)
                    
                    # 파일명과 최신 버전 표시
                    col1, col2, col3 = st.columns([2.5, 1, 0.5])
                    
                    with col1:
                        doc_version = docs[0].version if hasattr(docs[0], 'version') else "?"
                        st.markdown(f"### 📄 {filename} (v{doc_version})")
                        
                        # 설명 표시 (있는 경우)
                        doc_description = docs[0].description if hasattr(docs[0], 'description') else ""
                        if doc_description:
                            st.markdown(f"*{doc_description}*")
                    
                    with col2:
                        # 최신 버전 문서 선택 버튼
                        doc_id = docs[0].doc_id if hasattr(docs[0], 'doc_id') else ""
                        if st.button(f"문서 내용 보기", key=f"view_{doc_id}"):
                            st.session_state.selected_doc_id = doc_id
                    
                    with col3:
                        # 관리자인 경우에만 삭제 버튼 표시
                        is_admin = st.session_state.get("user_role") == "admin"
                        if is_admin:
                            if st.button("🗑️", key=f"del_{doc_id}"):
                                st.session_state.delete_doc_confirm = doc_id
                    
                    # 삭제 확인 표시
                    if st.session_state.delete_doc_confirm == doc_id:
                        confirm_col1, confirm_col2, confirm_col3 = st.columns([2, 1, 1])
                        with confirm_col1:
                            st.warning(f"'{filename}' 문서를 정말 삭제하시겠습니까?")
                        with confirm_col2:
                            if st.button("삭제 확인", key=f"confirm_del_{doc_id}"):
                                # 문서 삭제 처리
                                success = doc_manager.delete_document(doc_id, permanently=False)
                                
                                if success:
                                    st.success("문서가 성공적으로 삭제되었습니다.")
                                    # 버전 기록 생성
                                    doc_manager.create_document_version_log(
                                        doc_id=doc_id,
                                        previous_version=doc_version,
                                        new_version=0,  # 삭제됨을 나타내는 버전
                                        change_description="문서 삭제됨",
                                        changed_by=st.session_state.get("username", "unknown")
                                    )
                                    st.session_state.delete_doc_confirm = None
                                    time.sleep(1)  # UI 업데이트를 위한 지연
                                    st.rerun()  # 페이지 새로고침
                                else:
                                    st.error("문서 삭제 중 오류가 발생했습니다.")
                        
                        with confirm_col3:
                            if st.button("취소", key=f"cancel_del_{doc_id}"):
                                st.session_state.delete_doc_confirm = None
                                st.rerun()
                    
                    # 이전 버전 확장 섹션
                    if len(docs) > 1:
                        with st.expander(f"이전 버전 ({len(docs)-1}개)"):
                            for idx, doc in enumerate(docs[1:]):
                                col1, col2, col3 = st.columns([2.5, 1, 0.5])
                                with col1:
                                    doc_version = doc.version if hasattr(doc, 'version') else "?"
                                    doc_upload_time = doc.upload_time if hasattr(doc, 'upload_time') else ""
                                    st.write(f"v{doc_version} - {doc_upload_time}")
                                with col2:
                                    doc_id = doc.doc_id if hasattr(doc, 'doc_id') else ""
                                    if st.button("보기", key=f"view_old_{doc_id}_{idx}"):
                                        st.session_state.selected_doc_id = doc_id
                                with col3:
                                    # 관리자인 경우에만 삭제 버튼 표시 (이전 버전)
                                    is_admin = st.session_state.get("user_role") == "admin"
                                    if is_admin:
                                        if st.button("🗑️", key=f"del_old_{doc_id}_{idx}"):
                                            st.session_state.delete_doc_confirm = doc_id
                    
                    # 버전 기록 표시
                    latest_doc_id = docs[0].doc_id if hasattr(docs[0], 'doc_id') else ""
                    if latest_doc_id:
                        version_logs = doc_manager.get_document_version_history(latest_doc_id)
                        if version_logs:
                            with st.expander(f"변경 기록 ({len(version_logs)}개)"):
                                for log in version_logs:
                                    st.write(f"v{log['previous_version']} → v{log['new_version']} ({log['changed_at']})")
                                    st.write(f"변경 내용: {log['change_description']}")
                                    st.write(f"변경자: {log['changed_by']}")
                                    st.divider()
                    
                    st.divider()
    
    # 선택된 문서 내용 표시
    if st.session_state.selected_doc_id:
        doc_id = st.session_state.selected_doc_id
        st.subheader("문서 내용")
        
        # 문서 내용 표시 함수 호출
        # 이 함수는 conversation_manager.py에 있으므로 import 필요
        from conversation_manager import display_document_content
        display_document_content(doc_manager, doc_id)
        
        # 문서 보기 후 뒤로가기 버튼
        if st.button("← 문서 목록으로 돌아가기"):
            st.session_state.selected_doc_id = None
            st.rerun()
        
# PostgreSQL 연결자 클래스 (선택적 사용)
class PostgreSQLConnector:
    """PostgreSQL 데이터베이스 연결 및 쿼리 실행 클래스"""
    
    def __init__(self, connection_params):
        self.connection_params = connection_params
        self.initialize_tables()
    
    def get_connection(self):
        """데이터베이스 연결 객체 반환"""
        import psycopg2
        import psycopg2.extras
        
        conn = psycopg2.connect(**self.connection_params)
        conn.autocommit = True
        return conn
    
    def initialize_tables(self):
        """필요한 테이블 초기화"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 문서 메타데이터 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_metadata (
                doc_id VARCHAR(50) PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                file_type VARCHAR(20) NOT NULL,
                category VARCHAR(100) NOT NULL,
                version INTEGER NOT NULL,
                chunks INTEGER NOT NULL,
                uploaded_by VARCHAR(100) NOT NULL,
                upload_time TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                vector_store_path VARCHAR(255),
                description TEXT
            )
            """)
            
            # 사용자 대화 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_conversations (
                conversation_id VARCHAR(50) PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                title VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                is_archived BOOLEAN DEFAULT FALSE
            )
            """)
            
            # 대화 메시지 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_messages (
                message_id VARCHAR(50) PRIMARY KEY,
                conversation_id VARCHAR(50) REFERENCES user_conversations(conversation_id),
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL
            )
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            st.error(f"테이블 초기화 중 오류: {str(e)}")
    
    def execute_query(self, query, params=None):
        """쿼리 실행 및 결과 반환"""
        import psycopg2.extras
        
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(query, params)
                
                # SELECT 쿼리인 경우 결과 반환
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    results = cursor.fetchall()
                    
                    # 결과를 딕셔너리 리스트로 변환
                    dict_results = []
                    for row in results:
                        dict_results.append({columns[i]: row[i] for i in range(len(columns))})
                    return dict_results
                
                # 영향받은 행 수 반환
                return cursor.rowcount
        except Exception as e:
            st.error(f"쿼리 실행 중 오류: {query} - {str(e)}")
            raise e
        finally:
            if conn:
                conn.close()