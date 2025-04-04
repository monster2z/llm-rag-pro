# app.py (리팩토링 버전)
import streamlit as st
import os
import time
from typing import List, Dict, Any, Annotated, Sequence, TypedDict, Union
import pandas as pd

# .env 파일 로드
from dotenv import load_dotenv
load_dotenv()

# 모듈 임포트
from user_manager import UserManager, admin_panel
# 새로운 document_explorer 함수 임포트
from document_manager import DocumentManager,document_explorer
from conversation_manager import (
    ConversationManager, 
    editable_conversation_list, 
    chat_interface,
    document_tree_view,
    display_document_content
)
from db_models import DBManager

# 새로 추가된 유틸리티 모듈 임포트
from vectorstore_utils import (
    process_documents, 
    load_vectorstores, 
    check_vectorstore_status
)
from rag_utils import (
    create_rag_workflow,
    generate_response
)
from ui_components import (
    add_fixed_header_style, 
    render_header, 
    render_fixed_tabs,
    render_document_stats,
    render_document_list,
    render_file_uploader,
    render_performance_tips
)

# langsmith로 로깅 설정 (선택 사항)
try:
    from langchain_teddynote import logging
    logging.langsmith("llm_rag_prototype")
except ImportError:
    print("langchain_teddynote 라이브러리를 설치하지 않았습니다. 로깅 기능이 비활성화됩니다.")

# SQLite 문제 해결을 위한 pysqlite3 설정 (필요시 활성화)
try:
    import pysqlite3
    import sys
    sys.modules['sqlite3'] = pysqlite3
except ImportError:
    print("pysqlite3 라이브러리를 설치하지 않았습니다. sqlite3 관련 문제가 발생할 수 있습니다.")

# API 키 설정 (환경 변수에서 로드)
api_key = os.environ.get("OPENAI_API_KEY")
anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
admin_pass = os.environ.get("ADMIN_PASS")
user_pass = os.environ.get("USER_PASS")

# 임베딩 모델 선택 (세션 상태에서 가져오거나 기본값 사용)
EMBEDDING_MODEL = st.session_state.get("EMBEDDING_MODEL", "text-embedding-3-small")

# LLM 모델 선택 (세션 상태에서 가져오거나 기본값 사용)
LLM_MODEL = st.session_state.get("LLM_MODEL", "gpt-4o-mini")
LLM_PROVIDER = st.session_state.get("LLM_PROVIDER", "openai")

# 임시 데이터 저장 디렉토리
DATA_DIR = "./db/document"
os.makedirs(DATA_DIR, exist_ok=True)

# 페이지 설정
st.set_page_config(
    page_title="기업 내부용 LLM 프로토타입", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 데이터베이스 연결 설정 (옵션)
def setup_database_connector():
    """데이터베이스 연결 설정"""
    print("데이터베이스 연결 시도")

    try:
        # DBManager 초기화
        db_manager = DBManager()
        print("DB 연결 성공, 기본 계정 생성 시작")

        # 기본 관리자 및 사용자 계정 생성
        db_manager.create_default_admin()
        db_manager.create_default_user()
        
        return db_manager
    except Exception as e:
        st.warning(f"데이터베이스 연결 실패: {str(e)}. 세션 기반 저장소를 사용합니다.")
        return None

# 앱 초기화 함수
def initialize_app():
    """앱 초기화 및 세션 상태 설정"""
    # 데이터베이스 연결은 한 번만 설정
    if "db_manager" not in st.session_state:
        print("앱 초기화 시작")
        db_manager = setup_database_connector()
        st.session_state.db_manager = db_manager
    else:
        db_manager = st.session_state.db_manager
    
    # 사용자 관리자 초기화
    if "user_manager" not in st.session_state:
        st.session_state.user_manager = UserManager(db_manager=db_manager)
    
    # 문서 관리자 초기화
    if "document_manager" not in st.session_state:
        st.session_state.document_manager = DocumentManager(DATA_DIR, db_manager)
    
    # 대화 관리자 초기화
    if "conversation_manager" not in st.session_state:
        st.session_state.conversation_manager = ConversationManager(db_manager)
    
            # 벡터 저장소 로드 - 로그인 후에만 필요
    if "vectorstore" not in st.session_state and st.session_state.get("authentication_status") == True:
        document_manager = st.session_state.document_manager
        st.session_state.vectorstore = load_vectorstores(
            document_manager,  # _document_manager로 전달됨
            EMBEDDING_MODEL,
            api_key
        )
        
        # RAG 워크플로우 생성 (벡터스토어가 있는 경우에만)
        if st.session_state.vectorstore:
            st.session_state.rag_workflow = create_rag_workflow()

# 메인 앱 실행
def main():
    """메인 앱 함수"""
    # 성능 팁 페이지 (URL 파라미터로 접근)
    params = st.query_params
    if "tips" in params:
        render_performance_tips()
        return

    # URL 파라미터에서 폼 초기화 여부 확인
    if "clear_form" in st.query_params:
        # 쿼리 파라미터 제거
        st.query_params.clear()
        # 만약 로그인에 실패했다면 폼 값 초기화
        if not st.session_state.get("authentication_status", False):
            # 폼 관련 세션 상태 초기화
            if "form_username" in st.session_state:
                del st.session_state.form_username
            if "form_password" in st.session_state:
                del st.session_state.form_password

    # 앱 초기화
    initialize_app()
    
    # 고정 헤더용 스타일 추가
    add_fixed_header_style()
    
    # 사용자 인증 상태 확인
    if "authentication_status" not in st.session_state:
        st.session_state["authentication_status"] = None  # None으로 초기화
    
    # 로그인 상태에 따른 화면 전환
    if st.session_state.get("authentication_status") != True:
        # 로그인되지 않은 경우에만 로그인 폼 표시
        try:
            print("로그인 시도")
            st.session_state.user_manager.login()
        except Exception as e:
            st.error(f"로그인 처리 중 오류가 발생했습니다: {str(e)}")
            st.info("기본 사용자로 로그인합니다.")
            st.session_state["authentication_status"] = True
            st.session_state["username"] = "user_test"
            st.session_state["name"] = "테스트사용자"
            st.session_state["user_role"] = "user"
            print(f"로그인 오류: {str(e)}")
            st.rerun()  # 로그인 성공 시 페이지 새로고침
    
    # 로그인 상태인 경우 메인 인터페이스 표시
    if st.session_state.get("authentication_status") == True:
        # 현재 사용자 정보
        username = st.session_state["username"]
        name = st.session_state["name"]
        user_role = st.session_state.get("user_role", "일반")
        is_admin = st.session_state.user_manager.is_admin()
        
        # 고정 헤더 렌더링
        # render_header(name, user_role)
        
        # 사이드바 내 정보
        col1, col2 = st.sidebar.columns([4, 1])
        with col1:
            st.sidebar.title(f'환영합니다')
            # 로그아웃 버튼
            st.session_state.user_manager.logout()
            st.sidebar.write(f"역할: {'관리자' if is_admin else '일반 사용자'}")
        
        # 로그아웃 버튼은 별도 함수가 처리
        
        # 고정 탭 생성
        tabs = render_fixed_tabs()
        
        # 대화하기 탭
        with tabs[0]:
            # 문서 상태 확인 및 문서 목록 표시
            col1, col2 = render_document_stats(st.session_state.get("vectorstore"))
            
            with col2:
                if "document_manager" in st.session_state:
                    render_document_list(st.session_state.document_manager)
            
            # 사이드바 - 대화 목록 영역
            current_conv_id = editable_conversation_list(
                st.session_state.conversation_manager, 
                username
            )
            
            # 관리자인 경우 문서 업로드 영역 표시
            if is_admin:
                st.sidebar.divider()
                
                # 파일 업로드 섹션
                uploaded_files, selected_category, description, process_button = render_file_uploader(
                    st.session_state.document_manager,
                    username
                )
                
                # 파일 처리 버튼 클릭시
                if uploaded_files and process_button:
                    with st.spinner("문서 처리 중..."):
                        vectorstore, file_info = process_documents(
                            uploaded_files, 
                            selected_category, 
                            description, 
                            username,
                            DATA_DIR,
                            EMBEDDING_MODEL,
                            api_key
                        )
                        
                        if vectorstore:
                            st.session_state.vectorstore = vectorstore
                            # LangGraph 워크플로우 생성
                            st.session_state.rag_workflow = create_rag_workflow()
                            st.success("문서가 성공적으로 처리되었습니다.")
                            
                            # 처리된 파일 정보 표시
                            if file_info:
                                st.subheader("처리된 파일")
                                for file in file_info:
                                    st.write(f"📄 {file['filename']} - {file['chunks']}개 청크")
            
            # 메인 컨테이너 - 채팅 영역
            st.title(f"안녕하세요? {name}님!")
            
            # 대화 인터페이스 표시
            # conversation_manager를 명시적으로 전달
            conv_manager = st.session_state.conversation_manager
            
            # generate_response에 대한 래퍼 함수 생성
            def response_wrapper(prompt, username, conversation_id):
                return generate_response(prompt, username, conversation_id, _conv_manager=conv_manager)
            
            chat_interface(
                conv_manager,
                username,
                current_conv_id,
                response_wrapper
            )
        
        # 문서 탐색 탭
        with tabs[1]:
            if "document_manager" in st.session_state:
                # 개선된 문서 탐색 컴포넌트 사용
                try:
                    document_explorer(st.session_state.document_manager)
                except Exception as e:
                    st.error(f"문서 탐색 오류: {str(e)}")
                    # 기존 문서 탐색 컴포넌트로 폴백
                    selected_category, selected_doc_id = document_tree_view(st.session_state.document_manager)
                    if selected_doc_id:
                        display_document_content(st.session_state.document_manager, selected_doc_id)
            else:
                st.info("문서 관리자가 초기화되지 않았습니다.")
        
        # 설정 탭
        with tabs[2]:
            st.title("설정")
            
            # 관리자인 경우 관리자 패널 표시
            if is_admin and st.session_state.user_manager:
                admin_panel(st.session_state.user_manager)
            else:
                st.info("관리자만 접근할 수 있는 페이지입니다.")

if __name__ == "__main__":
    main()