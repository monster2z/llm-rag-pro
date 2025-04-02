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