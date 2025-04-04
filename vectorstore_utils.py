# vectorstore_utils.py
import os
import time
import uuid
import tempfile
from typing import List, Dict, Any, Tuple, Optional
import streamlit as st

# LangChain 관련 라이브러리
from langchain_community.document_loaders import (
    PyPDFLoader, 
    Docx2txtLoader, 
    CSVLoader, 
    UnstructuredPowerPointLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

@st.cache_resource(show_spinner=False)
def get_embeddings(embedding_model="text-embedding-3-small", _api_key=None):
    """임베딩 모델 초기화 및 캐싱"""
    return OpenAIEmbeddings(model=embedding_model, api_key=_api_key)

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

def process_documents(uploaded_files, 
                     category=None, 
                     description=None, 
                     username=None, 
                     data_dir="./db/document",
                     embedding_model="text-embedding-3-small",
                     api_key=None):
    """문서 처리 및 임베딩 - 버전 관리 개선"""
    documents = []
    file_info = []
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=200
    )
    
    # 진행 상황 표시
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    
    for i, uploaded_file in enumerate(uploaded_files):
        # 진행 상황 업데이트
        progress = (i / len(uploaded_files))
        progress_bar.progress(progress)
        status_text.text(f"처리 중... {uploaded_file.name}")
        
        # 파일 확장자 추출
        file_type = uploaded_file.name.split('.')[-1].lower()
        filename = uploaded_file.name
        
        # 기존 문서 확인 - 동일 파일명의 문서가 있는지 체크
        existing_version = 0
        existing_doc_id = None
        
        if "document_manager" in st.session_state:
            # 카테고리별 문서 가져오기
            category_docs = st.session_state.document_manager.get_documents_by_category(
                category or "기타"
            )
            
            # 동일 파일명 체크
            for doc in category_docs:
                if hasattr(doc, 'filename') and doc.filename == filename:
                    # 기존 문서 중 가장 높은 버전 찾기
                    if hasattr(doc, 'version') and doc.version > existing_version:
                        existing_version = doc.version
                        existing_doc_id = doc.doc_id if hasattr(doc, 'doc_id') else None
        
        # 버전 설정 (기존 문서가 있으면 버전 증가)
        new_version = existing_version + 1
        
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
            vector_store_path = os.path.join(data_dir, f"faiss_index_{uuid.uuid4().hex}")
            
            # 파일 정보 추가 (메타데이터)
            for doc in split_documents:
                if not doc.metadata:
                    doc.metadata = {}
                doc.metadata["source_file"] = filename
                doc.metadata["file_type"] = file_type
                doc.metadata["category"] = category or "기타"
                doc.metadata["doc_id"] = doc_id
                doc.metadata["version"] = new_version
                # 업로더 정보 추가 (사용자별 문서 관리를 위해)
                doc.metadata["uploaded_by"] = username or st.session_state.get("username", "system")
            
            documents.extend(split_documents)
            
            # 문서 메타데이터 생성
            metadata = {
                "doc_id": doc_id,
                "filename": filename,
                "file_type": file_type,
                "category": category or "기타",
                "version": new_version,
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
                
                # 업데이트인 경우 버전 로그 생성
                if existing_version > 0 and existing_doc_id:
                    change_desc = f"새 버전 업로드 - {description or '설명 없음'}"
                    st.session_state.document_manager.create_document_version_log(
                        doc_id=doc_id,
                        previous_version=existing_version,
                        new_version=new_version,
                        change_description=change_desc,
                        changed_by=username or st.session_state.get("username", "system")
                    )
                    
                    # 이전 버전 비활성화 (옵션)
                    st.session_state.document_manager.update_document_status(existing_doc_id, is_active=False)
            
            # 버전 정보 표시
            if existing_version > 0:
                st.sidebar.success(f"{uploaded_file.name} 처리 완료 - 버전 {new_version}로 업데이트됨, {len(split_documents)}개 청크 생성")
            else:
                st.sidebar.success(f"{uploaded_file.name} 처리 완료 - {len(split_documents)}개 청크 생성")
                
        except Exception as e:
            st.sidebar.error(f"{uploaded_file.name} 처리 중 오류 발생: {str(e)}")
        finally:
            # 임시 파일 삭제
            os.unlink(temp_file_path)
    
    # 진행 상황 완료
    progress_bar.progress(1.0)
    status_text.text("문서 처리 완료!")
    
    # 임베딩 및 벡터 저장소 생성
    if documents:
        st.sidebar.info("문서 임베딩 중...")
        # 임베딩 모델 초기화
        embeddings = get_embeddings(embedding_model, api_key)
        
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
                    file_vectorstore.save_local(path, allow_dangerous_deserialization=True)
        
        st.sidebar.success(f"임베딩 완료! {len(documents)}개 문서 처리됨")
        
        # 파일 정보 저장
        if "uploaded_files_info" not in st.session_state:
            st.session_state.uploaded_files_info = []
        st.session_state.uploaded_files_info.extend(file_info)
        
        return vectorstore, file_info
    return None, []

@st.cache_resource(show_spinner=False)
def load_vectorstores(_document_manager, embedding_model="text-embedding-3-small", api_key=None):
    """모든 문서의 벡터 저장소 로드 및 통합"""
    if _document_manager is None:
        return None
    
    # 활성 문서 목록 가져오기
    documents = _document_manager.get_all_active_documents()
    
    if not documents:
        return None
    
    # 임베딩 모델 초기화
    embeddings = get_embeddings(embedding_model, api_key)
    
    # 통합 벡터 저장소
    combined_vectorstore = None
    
    # 로딩 상태 표시
    with st.spinner("벡터 저장소 로드 중..."):
        # 각 문서의 벡터 저장소 로드 및 통합
        for doc in documents:
            # SQLAlchemy 모델의 속성에 직접 접근
            vector_path = doc.vector_store_path if hasattr(doc, 'vector_store_path') else None
            
            if vector_path and os.path.exists(vector_path):
                try:
                    # 벡터 저장소 로드 (보안 옵션 추가)
                    doc_vectorstore = FAISS.load_local(
                        vector_path, 
                        embeddings, 
                        allow_dangerous_deserialization=True  # 신뢰할 수 있는 로컬 파일이므로 허용
                    )
                    
                    if combined_vectorstore is None:
                        combined_vectorstore = doc_vectorstore
                    else:
                        # 벡터 저장소 병합
                        combined_vectorstore.merge_from(doc_vectorstore)
                except Exception as e:
                    filename = doc.filename if hasattr(doc, 'filename') else "알 수 없음"
                    st.warning(f"문서 '{filename}' 벡터 저장소 로드 실패: {str(e)}")
    
    return combined_vectorstore

# vectorstore_utils.py에 추가 #보안이 필요한 상황에 대해서 하단 참고할 것 #현재 미사용
def secure_load_vectorstore(vector_path, embeddings):
    """보안이 강화된 벡터 저장소 로드 함수"""
    # 1. 경로 검증
    if not os.path.exists(vector_path) or not os.path.isdir(vector_path):
        return None
    
    # 2. 필수 파일 존재 확인
    required_files = ['index.faiss', 'index.pkl']
    if not all(os.path.exists(os.path.join(vector_path, f)) for f in required_files):
        return None
    
    # 3. 메타데이터 먼저 검사 (가능하다면)
    try:
        # 제한된 환경에서 FAISS 로드
        return FAISS.load_local(
            vector_path, 
            embeddings, 
            allow_dangerous_deserialization=True
        )
    except Exception as e:
        st.error(f"벡터 저장소 로드 실패: {str(e)}")
        # 로그에 보안 이벤트 기록
        print(f"보안 경고: 벡터 저장소 로드 실패 - {vector_path} - {str(e)}")
        return None

def check_vectorstore_status():
    """벡터 저장소 상태 확인 및 메시지 반환"""
    if "vectorstore" in st.session_state and st.session_state.vectorstore is not None:
        # 벡터 스토어의 총 문서 수 확인
        try:
            doc_count = len(st.session_state.vectorstore.docstore._dict)
            if doc_count > 0:
                return True, f"문서가 임베딩되었습니다. {doc_count}개의 문서 청크가 검색 가능합니다."
        except Exception as e:
            print(f"벡터 스토어 확인 중 오류: {str(e)}")
            
    return False, "아직 업로드된 문서가 없습니다. 일반적인 지식을 기반으로 답변합니다. 더 정확한 답변을 위해 관리자에게 문서 업로드를 요청하세요."