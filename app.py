# app.py
import streamlit as st
import os
import time
import tempfile
import uuid
from typing import List, Dict, Any, Annotated, Sequence, TypedDict, Union
import pandas as pd



# 추가 모듈 임포트
from user_manager import UserManager, admin_panel
from document_manager import DocumentManager, PostgreSQLConnector
from conversation_manager import (
    ConversationManager, 
    editable_conversation_list, 
    chat_interface,
    document_tree_view,
    display_document_content
)
from db_models import DBManager

# 기존 LangChain 및 LangGraph 임포트
from langchain_community.document_loaders import (
    PyPDFLoader, 
    Docx2txtLoader, 
    CSVLoader, 
    UnstructuredPowerPointLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

# LangGraph 임포트
from langgraph.graph import StateGraph, END

# .env 파일 로드
from dotenv import load_dotenv
load_dotenv()

# langsmith로 로깅 설정
try:
    from langchain_teddynote import logging
    logging.langsmith("llm_rag_prototype")
except ImportError:
    print("langchain_teddynote 라이브러리를 설치하지 않았습니다. 로깅 기능이 비활성화됩니다.")

# SQLite 문제 해결을 위한 pysqlite3 설정
try:
    import pysqlite3
    import sys
    sys.modules['sqlite3'] = pysqlite3
except ImportError:
    print("pysqlite3 라이브러리를 설치하지 않았습니다. sqlite3 관련 문제가 발생할 수 있습니다.")

# API 키 설정 (환경 변수에서 로드)
api_key = os.environ.get("OPENAI_API_KEY")
anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")  # 필요시 활성화
admin_pass = os.environ.get("ADMIN_PASS")
user_pass = os.environ.get("USER_PASS")

# 임베딩 모델 선택 (세션 상태에서 가져오거나 기본값 사용)
EMBEDDING_MODEL = st.session_state.get("EMBEDDING_MODEL", "text-embedding-3-small")

# LLM 모델 선택 (세션 상태에서 가져오거나 기본값 사용)
LLM_MODEL = st.session_state.get("LLM_MODEL", "gpt-4o-mini")
LLM_PROVIDER = "openai"  # 또는 "anthropic"

# 임시 데이터 저장 디렉토리
DATA_DIR = "./db/document"
os.makedirs(DATA_DIR, exist_ok=True)

# 페이지 설정
st.set_page_config(
    page_title="기업 내부용 LLM 프로토타입", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 설정
st.markdown("""
<style>
    .sidebar .sidebar-content {
        width: 300px;
    }
    .main .block-container {
        max-width: 1200px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1, h2, h3 {
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    .stButton button {
        width: 100%;
        border-radius: 5px;
    }
    .stExpander {
        border-radius: 5px;
    }
    .css-1kyxreq {
        justify-content: flex-start;
    }
</style>
""", unsafe_allow_html=True)

# LangGraph 상태 정의
class AgentState(TypedDict):
    question: str
    context: List[str] 
    answer: str
    conversation_history: List[Dict[str, str]]
    sources: List[Dict[str, str]]
    need_more_info: bool
    username: str  # 사용자 식별을 위한 필드 추가

# PostgreSQL 연결 설정 (옵션)
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

# 파일 타입에 따른 로더 선택 함수
def get_loader(file_path, file_type):
    """파일 타입에 맞는 로더 반환"""
    if file_type == 'pdf':
        return PyPDFLoader(file_path)
    elif file_type == 'docx':
        return Docx2txtLoader(file_path)
    elif file_type == 'csv':
        return CSVLoader(file_path)
    elif file_type == 'pptx':
        return UnstructuredPowerPointLoader(file_path)
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {file_type}")

# 문서 처리 및 임베딩 함수
def process_documents(uploaded_files, category=None, description=None, username=None):
    """문서 처리 및 임베딩"""
    documents = []
    file_info = []
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=200
    )
    
    for uploaded_file in uploaded_files:
        # 파일 확장자 추출
        file_type = uploaded_file.name.split('.')[-1].lower()
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_type}') as temp_file:
            temp_file.write(uploaded_file.getvalue())
            temp_file_path = temp_file.name
            
        try:
            # 로더 선택 및 문서 로드
            loader = get_loader(temp_file_path, file_type)
            loaded_documents = loader.load()
            
            # 문서 분할
            split_documents = text_splitter.split_documents(loaded_documents)
            
            # 문서 고유 ID 생성
            doc_id = str(uuid.uuid4())
            
            # 벡터 저장소 경로 생성
            vector_store_path = os.path.join(DATA_DIR, f"faiss_index_{uuid.uuid4().hex}")
            
            # 파일 정보 추가 (메타데이터)
            for doc in split_documents:
                if not doc.metadata:
                    doc.metadata = {}
                doc.metadata["source_file"] = uploaded_file.name
                doc.metadata["file_type"] = file_type
                doc.metadata["category"] = category or "기타"
                doc.metadata["doc_id"] = doc_id
                doc.metadata["version"] = 1  # 문서 버전 정보
                # 업로더 정보 추가 (사용자별 문서 관리를 위해)
                doc.metadata["uploaded_by"] = username or st.session_state.get("username", "system")
            
            documents.extend(split_documents)
            
            # 문서 메타데이터 생성
            metadata = {
                "doc_id": doc_id,
                "filename": uploaded_file.name,
                "file_type": file_type,
                "category": category or "기타",
                "version": 1,  # 초기 버전
                "chunks": len(split_documents),
                "uploaded_by": username or st.session_state.get("username", "system"),
                "upload_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "is_active": True,
                "vector_store_path": vector_store_path,
                "description": description or ""
            }
            
            file_info.append(metadata)
            
            # 문서 관리자에 메타데이터 추가
            if "document_manager" in st.session_state:
                st.session_state.document_manager.add_document(metadata)
            
            st.sidebar.success(f"{uploaded_file.name} 처리 완료 - {len(split_documents)}개 청크 생성")
        except Exception as e:
            st.sidebar.error(f"{uploaded_file.name} 처리 중 오류 발생: {str(e)}")
        finally:
            # 임시 파일 삭제
            os.unlink(temp_file_path)
    
    # 임베딩 및 벡터 저장소 생성
    if documents:
        st.sidebar.info("문서 임베딩 중...")
        # 임베딩 모델 초기화
        embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=api_key)
        
        # 기존 벡터스토어가 있으면 추가, 없으면 새로 생성
        if "vectorstore" in st.session_state:
            try:
                # 기존 벡터스토어에 문서 추가
                st.session_state.vectorstore.add_documents(documents)
                vectorstore = st.session_state.vectorstore
            except Exception as e:
                st.sidebar.warning(f"기존 벡터스토어에 추가 실패, 새로 생성합니다: {str(e)}")
                # FAISS 벡터스토어 생성
                vectorstore = FAISS.from_documents(documents, embeddings)
        else:
            # 새 FAISS 벡터스토어 생성
            vectorstore = FAISS.from_documents(documents, embeddings)
        
        # 로컬에 벡터스토어 저장 (나중에 로드할 수 있도록)
        # 각 파일별 벡터스토어 경로 사용
        for file_meta in file_info:
            path = file_meta.get("vector_store_path")
            if path:
                os.makedirs(path, exist_ok=True)
                # 이 파일과 관련된 벡터만 저장
                docs_for_file = [doc for doc in documents if doc.metadata.get("doc_id") == file_meta.get("doc_id")]
                if docs_for_file:
                    file_vectorstore = FAISS.from_documents(docs_for_file, embeddings)
                    file_vectorstore.save_local(path)
        
        st.sidebar.success(f"임베딩 완료! {len(documents)}개 문서 처리됨")
        
        # 파일 정보 저장
        if "uploaded_files_info" not in st.session_state:
            st.session_state.uploaded_files_info = []
        st.session_state.uploaded_files_info.extend(file_info)
        
        return vectorstore, file_info
    return None, []

# LangGraph 노드 함수들

# 문서 검색 함수
def retrieve_documents(state: AgentState) -> AgentState:
    """문서 저장소에서 관련 문서를 검색하는 함수"""
    # 세션 상태에서 벡터 저장소 가져오기
    vectorstore = st.session_state.get("vectorstore")
    
    if not vectorstore:
        return {**state, "context": [], "sources": []}
    
    # 검색 수행
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 5})
    docs = retriever.get_relevant_documents(state["question"])
    
    # 컨텍스트 구성
    contexts = []
    sources = []
    
    for doc in docs:
        contexts.append(doc.page_content)
        sources.append({
            "source": doc.metadata.get("source_file", "Unknown"),
            "page": doc.metadata.get("page", "N/A"),
            "category": doc.metadata.get("category", "기타")
        })
    
    return {**state, "context": contexts, "sources": sources}

# 질문 응답 생성 함수
def generate_answer(state: AgentState) -> AgentState:
    """검색된 문서를 바탕으로 질문에 대한 답변을 생성하는 함수"""
    # LLM 모델 초기화
    if LLM_PROVIDER == "anthropic" and anthropic_api_key:
        llm = ChatAnthropic(model=LLM_MODEL, api_key=anthropic_api_key)
    else:
        llm = ChatOpenAI(model=LLM_MODEL, api_key=api_key)
    
    # 프롬프트 템플릿 정의
    template = """
    당신은 기업 내부 문서에 대한 질문에 답변하는 AI 어시스턴트입니다.
    사용자의 질문에 대해 아래 문맥 정보를 참고하여 정확하게 답변하세요.
    문맥 정보에 답이 없는 경우, "제공된 문서에서 관련 정보를 찾을 수 없습니다"라고 답하고 
    need_more_info를 True로 설정하세요. 그렇지 않으면 False로 설정하세요.
    
    이전 대화 기록: {conversation_history}
    
    문맥 정보:
    {context}
    
    질문: {question}
    
    답변:
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    
    # 컨텍스트 구성
    context_text = "\n\n".join(state["context"]) if state["context"] else "관련 문서가 없습니다."
    
    # 이전 대화 기록
    conversation_history = state.get("conversation_history", [])
    
    # 입력 구성
    inputs = {
        "question": state["question"],
        "context": context_text,
        "conversation_history": str(conversation_history)
    }
    
    # 답변 생성
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke(inputs)
    
    # 추가 정보 필요 여부 판단
    need_more_info = "제공된 문서에서 관련 정보를 찾을 수 없습니다" in answer
    
    return {
        **state, 
        "answer": answer, 
        "need_more_info": need_more_info
    }

# 소스 정보 추가 함수
def add_source_information(state: AgentState) -> AgentState:
    """답변에 소스 정보를 추가하는 함수"""
    if not state["sources"]:
        return state
        
    sources_info = "\n\n**참고 문서:**\n"
    for src in state["sources"]:
        sources_info += f"- {src['source']}"
        if src['page'] != "N/A":
            sources_info += f" (페이지: {src['page']})"
        if 'category' in src and src['category']:
            sources_info += f" [카테고리: {src['category']}]"
        sources_info += "\n"
    
    enhanced_answer = state["answer"] + sources_info
    
    return {**state, "answer": enhanced_answer}

# LangGraph 워크플로우 생성 함수
def create_rag_workflow():
    """RAG 워크플로우 생성"""
    # 워크플로우 정의
    workflow = StateGraph(AgentState)
    
    # 노드 추가
    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("generate", generate_answer)
    workflow.add_node("add_sources", add_source_information)
    
    # 엣지 설정
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "add_sources")
    workflow.add_edge("add_sources", END)
    
    # 시작 노드 설정
    workflow.set_entry_point("retrieve")
    
    # 그래프 컴파일
    return workflow.compile()

# 응답 생성 함수
def generate_response(prompt, username, conversation_id):
    """사용자 질문에 대한 응답 생성"""
    # 대화 기록 가져오기
    conv_manager = st.session_state.get("conversation_manager")
    if conv_manager:
        messages = conv_manager.get_conversation_messages(username, conversation_id)
        conversation_history = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in messages
        ]
    else:
        conversation_history = []
    
    # LangGraph 워크플로우가 설정되어 있으면 해당 워크플로우 사용
    if 'rag_workflow' in st.session_state and 'vectorstore' in st.session_state:
        try:
            # 초기 상태 설정
            initial_state = {
                "question": prompt,
                "context": [],
                "answer": "",
                "conversation_history": conversation_history,
                "sources": [],
                "need_more_info": False,
                "username": username
            }
            
            # 워크플로우 실행
            result = st.session_state.rag_workflow.invoke(initial_state)
            
            # 답변 반환
            return result["answer"]
            
        except Exception as e:
            st.error(f"RAG 응답 생성 중 오류: {str(e)}")
            # 오류 발생 시 기본 응답으로 폴백
            return f"죄송합니다. 질문 처리 중 오류가 발생했습니다. 나중에 다시 시도해주세요."
    else:
        # 기본 LLM 사용 (RAG가 없는 경우)
        llm = ChatOpenAI(model=LLM_MODEL, api_key=api_key)
            
        template = """
        당신은 기업 내부 AI 어시스턴트입니다. 
        사용자의 질문에 정확하게 답변하세요.
        
        현재 업로드된 문서가 없습니다. 일반적인 지식을 바탕으로 답변합니다.
        다만, 사용자에게 더 정확한 답변을 위해 관련 문서를 업로드하면 좋을 것이라고 알려주세요.
        
        이전 대화 기록: {conversation_history}
        
        질문: {question}
        
        답변:
        """
        
        prompt_template = ChatPromptTemplate.from_template(template)
        chain = prompt_template | llm | StrOutputParser()
        
        try:
            return chain.invoke({
                "question": prompt,
                "conversation_history": str(conversation_history)
            })
        except Exception as e:
            st.error(f"LLM 응답 생성 중 오류: {str(e)}")
            return "죄송합니다. 응답 생성 중 오류가 발생했습니다. 나중에 다시 시도해주세요."

# 벡터 저장소 로드 함수
def load_vectorstores():
    """모든 문서의 벡터 저장소 로드 및 통합"""
    if "document_manager" not in st.session_state:
        return None
    
    # 활성 문서 목록 가져오기
    documents = st.session_state.document_manager.get_all_active_documents()
    
    if not documents:
        return None
    
    # 임베딩 모델 초기화
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=api_key)
    
    # 통합 벡터 저장소
    combined_vectorstore = None
    
    # 각 문서의 벡터 저장소 로드 및 통합
    for doc in documents:
        vector_path = doc.get("vector_store_path")
        if vector_path and os.path.exists(vector_path):
            try:
                # 벡터 저장소 로드
                doc_vectorstore = FAISS.load_local(vector_path, embeddings)
                
                if combined_vectorstore is None:
                    combined_vectorstore = doc_vectorstore
                else:
                    # 벡터 저장소 병합
                    combined_vectorstore.merge_from(doc_vectorstore)
            except Exception as e:
                st.warning(f"문서 '{doc['filename']}' 벡터 저장소 로드 실패: {str(e)}")
    
    return combined_vectorstore

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
    
    # 벡터 저장소 로드 (아직 로드되지 않은 경우에만)
    if "vectorstore" not in st.session_state:
        st.session_state.vectorstore = load_vectorstores()
        
        # RAG 워크플로우 생성 (벡터스토어가 있는 경우에만)
        if st.session_state.vectorstore:
            st.session_state.rag_workflow = create_rag_workflow()

# 성능 최적화 팁
def performance_tips():
    """성능 최적화 팁 보여주기"""
    st.title("성능 최적화 팁")
    
    st.markdown("""
    ### 1. 메모리 사용량 최적화
    - Docker 이미지 실행 시 메모리 제한을 높여주세요 (최소 8GB 권장)
    ```bash
    docker run --memory=8g --memory-swap=10g ...
    ```
    
    ### 2. 벡터 저장소 최적화
    - 대용량 문서의 경우 청크 크기를 조정하세요 (기본값 1000)
    - 문서가 많은 경우 카테고리별로 벡터 저장소를 분리하세요
    
    ### 3. 데이터베이스 최적화
    - PostgreSQL 사용 시 인덱스를 적절히 설정하세요
    - 대화 이력이 많은 경우 정기적으로 아카이빙하세요
    
    ### 4. 배포 환경 권장사항
    - CPU: 4코어 이상
    - RAM: 16GB 이상
    - 스토리지: SSD 권장
    - GPU: 대용량 처리 시 권장
    
    ### 5. Streamlit 성능 개선
    - 캐싱을 활용하세요: `@st.cache_data`, `@st.cache_resource`
    - 세션 상태 최적화: 불필요한 데이터는 저장하지 마세요
    """)

# 메인 앱 실행
def main():
    """메인 앱 함수"""
    # 성능 팁 페이지 (URL 파라미터로 접근)
    if "tips" in st.query_params:
        performance_tips()
        return

    # 앱 초기화
    initialize_app()
    
    # 사용자 인증
    if "authentication_status" not in st.session_state:
        st.session_state["authentication_status"] = False
    
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
    
    # 로그인 상태에 따른 화면 전환
    if st.session_state["authentication_status"]:
        # 현재 사용자 정보
        username = st.session_state["username"]
        is_admin = st.session_state.user_manager.is_admin()
        
        st.sidebar.title(f'{st.session_state["name"]} 님 환영합니다')
        st.sidebar.write(f"역할: {'관리자' if is_admin else '일반 사용자'}")
        
        # 화면 선택 탭
        tabs = st.tabs(["대화하기", "문서 탐색", "설정"])
        
        # 대화하기 탭
        with tabs[0]:
            # 업로드된 문서가 없는 경우 알림
            if "vectorstore" not in st.session_state or st.session_state.vectorstore is None:
                st.info("아직 업로드된 문서가 없습니다. 일반적인 지식을 기반으로 답변합니다. 더 정확한 답변을 위해 관리자에게 문서 업로드를 요청하세요.")
            else:
                st.success("문서가 임베딩되었습니다. 기업 내부 문서를 기반으로 질문에 답변합니다.")
            
            # 사이드바 - 대화 목록 영역
            current_conv_id = editable_conversation_list(
                st.session_state.conversation_manager, 
                username
            )
            
            # 관리자인 경우 문서 업로드 영역 표시
            if is_admin:
                st.sidebar.divider()
                
                # 파일 업로드 섹션
                st.sidebar.header("문서 업로드 (관리자 전용)")
                uploaded_files = st.sidebar.file_uploader(
                    "기업 내부 문서를 업로드하세요", 
                    type=['pdf', 'docx', 'csv', 'pptx'], 
                    accept_multiple_files=True
                )
                
                # 카테고리 선택 또는 생성
                existing_categories = st.session_state.document_manager.get_available_categories()
                category_option = st.sidebar.radio(
                    "카테고리", 
                    ["기존 카테고리 사용", "새 카테고리 생성"],
                    horizontal=True
                )
                
                if category_option == "기존 카테고리 사용" and existing_categories:
                    selected_category = st.sidebar.selectbox(
                        "카테고리 선택", 
                        options=existing_categories
                    )
                else:
                    selected_category = st.sidebar.text_input("새 카테고리 이름")
                
                # 문서 설명 추가
                description = st.sidebar.text_area("문서 설명 (선택사항)", height=100)
                
                # 파일 처리 버튼
                if uploaded_files and st.sidebar.button("문서 처리 및 임베딩"):
                    with st.spinner("문서 처리 중..."):
                        vectorstore, file_info = process_documents(
                            uploaded_files, 
                            selected_category, 
                            description, 
                            username
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
            st.title("기업 내부용 AI 어시스턴트")
            
            # 대화 인터페이스 표시
            chat_interface(
                st.session_state.conversation_manager,
                username,
                current_conv_id,
                generate_response
            )
    
    # 로그아웃 버튼은 로그인 상태일 때만 표시
    if st.session_state["authentication_status"]:
        st.session_state.user_manager.logout()

if __name__ == "__main__":
    main()