# conversation_manager.py
import streamlit as st
import pandas as pd
import uuid
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from db_models import UserConversation, ConversationMessage

class ConversationManager:
    """대화 관리 클래스: 대화 생성, 메시지 추가, 대화 목록 조회 등 기능 제공"""
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        
        # 세션 상태 초기화
        if "conversations" not in st.session_state:
            st.session_state.conversations = {}
        if "current_conversation" not in st.session_state:
            st.session_state.current_conversation = None
    
    def create_conversation(self, username: str, title: str = None) -> str:
        """새 대화 생성"""
        conversation_id = str(uuid.uuid4())
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 대화 데이터 생성
        conversation_data = {
            "conversation_id": conversation_id,
            "username": username,
            "title": title or f"새 대화 {current_time}",
            "created_at": current_time,
            "updated_at": current_time,
            "is_archived": False
        }
        
        if self.db_manager:
            try:
                self.db_manager.add_conversation(conversation_data)
            except Exception as e:
                print(f"대화 생성 중 오류 발생: {str(e)}")
        
        # 세션 상태에 저장
        st.session_state.conversations[conversation_id] = {
            "messages": [],
            "title": conversation_data["title"]
        }
        
        return conversation_id
    
    def add_message(self, conversation_id: str, role: str, content: str) -> bool:
        """대화에 메시지 추가"""
        if conversation_id not in st.session_state.conversations:
            return False
        
        message_id = str(uuid.uuid4())
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 메시지 데이터 생성
        message_data = {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "timestamp": current_time
        }
        
        if self.db_manager:
            try:
                self.db_manager.add_message(message_data)
            except Exception as e:
                print(f"메시지 추가 중 오류 발생: {str(e)}")
        
        # 세션 상태에 저장
        st.session_state.conversations[conversation_id]["messages"].append({
            "role": role,
            "content": content,
            "timestamp": current_time
        })
        
        return True
    
    def get_conversation_messages(self, username: str, conversation_id: str) -> List[Dict[str, str]]:
        """대화 메시지 조회"""
        if self.db_manager:
            try:
                messages = self.db_manager.get_conversation_messages(conversation_id)
                return [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    for msg in messages
                ]
            except Exception as e:
                print(f"대화 메시지 조회 중 오류 발생: {str(e)}")
        
        # DB가 없는 경우 세션 상태에서 조회
        return st.session_state.conversations.get(conversation_id, {}).get("messages", [])
    
    def get_user_conversations(self, username: str) -> List[Dict[str, Any]]:
        """사용자의 대화 목록 조회"""
        if self.db_manager:
            try:
                conversations = self.db_manager.get_user_conversations(username)
                return [
                    {
                        "conversation_id": conv.conversation_id,
                        "title": conv.title,
                        "created_at": conv.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "updated_at": conv.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "is_archived": conv.is_archived
                    }
                    for conv in conversations
                ]
            except Exception as e:
                print(f"대화 목록 조회 중 오류 발생: {str(e)}")
        
        # DB가 없는 경우 세션 상태에서 조회
        return [
            {
                "conversation_id": conv_id,
                "title": conv_data["title"],
                "created_at": conv_data.get("created_at", ""),
                "updated_at": conv_data.get("updated_at", ""),
                "is_archived": conv_data.get("is_archived", False)
            }
            for conv_id, conv_data in st.session_state.conversations.items()
        ]
    
    def update_conversation_title(self, conversation_id: str, new_title: str) -> bool:
        """대화 제목 업데이트"""
        if self.db_manager:
            try:
                return self.db_manager.update_conversation_title(conversation_id, new_title)
            except Exception as e:
                print(f"대화 제목 업데이트 중 오류 발생: {str(e)}")
        
        # DB가 없는 경우 세션 상태 업데이트
        if conversation_id in st.session_state.conversations:
            st.session_state.conversations[conversation_id]["title"] = new_title
            return True
        return False
    
    def archive_conversation(self, conversation_id: str) -> bool:
        """대화 아카이브"""
        if self.db_manager:
            try:
                conversation = self.db_manager.session.query(UserConversation).filter(
                    UserConversation.conversation_id == conversation_id
                ).first()
                
                if conversation:
                    conversation.is_archived = True
                    conversation.updated_at = datetime.now()
                    self.db_manager.session.commit()
                    return True
            except Exception as e:
                print(f"대화 아카이브 중 오류 발생: {str(e)}")
        
        # DB가 없는 경우 세션 상태 업데이트
        if conversation_id in st.session_state.conversations:
            st.session_state.conversations[conversation_id]["is_archived"] = True
            return True
        return False

# UI 컴포넌트: 편집 가능한 대화 목록
def editable_conversation_list(conversation_manager, username):
    """편집 가능한 대화 목록 컴포넌트"""
    st.sidebar.title("대화 목록")
    
    # 사용자별 대화 목록 관리
    conversations = conversation_manager.get_user_conversations(username)
    
    # 현재 대화 상태 관리
    if f"current_conversation_id_{username}" not in st.session_state:
        if conversations:
            st.session_state[f"current_conversation_id_{username}"] = conversations[0]["conversation_id"]
        else:
            # 대화가 없으면 새 대화 생성
            new_id = conversation_manager.create_conversation(username)
            st.session_state[f"current_conversation_id_{username}"] = new_id
            st.rerun()
    
    current_conv_id = st.session_state[f"current_conversation_id_{username}"]
    
    # 새 대화 버튼
    if st.sidebar.button("➕ 새 대화 시작", key="new_conversation"):
        new_id = conversation_manager.create_conversation(username)
        st.session_state[f"current_conversation_id_{username}"] = new_id
        st.rerun()
    
    st.sidebar.divider()
    
    # 편집 모드 상태 관리
    if "edit_mode_conversation" not in st.session_state:
        st.session_state.edit_mode_conversation = None
    
    # 대화 목록 표시
    for conv in conversations:
        col1, col2, col3 = st.sidebar.columns([0.7, 0.15, 0.15])
        
        # 편집 모드 상태에 따라 표시 방식 변경
        if st.session_state.edit_mode_conversation == conv["conversation_id"]:
            # 편집 모드
            with col1:
                new_title = st.text_input(
                    "대화명 편집",
                    value=conv["title"],
                    key=f"edit_title_{conv['conversation_id']}"
                )
            
            with col2:
                if st.button("✓", key=f"save_{conv['conversation_id']}"):
                    conversation_manager.update_conversation_title(conv["conversation_id"], new_title)
                    st.session_state.edit_mode_conversation = None
                    st.rerun()
            
            with col3:
                if st.button("✕", key=f"cancel_{conv['conversation_id']}"):
                    st.session_state.edit_mode_conversation = None
                    st.rerun()
        else:
            # 일반 모드
            with col1:
                # 현재 선택된 대화는 강조 표시
                if conv["conversation_id"] == current_conv_id:
                    if st.button(f"**{conv['title']}**", key=f"conv_{conv['conversation_id']}"):
                        st.session_state[f"current_conversation_id_{username}"] = conv["conversation_id"]
                        st.rerun()
                else:
                    if st.button(f"{conv['title']}", key=f"conv_{conv['conversation_id']}"):
                        st.session_state[f"current_conversation_id_{username}"] = conv["conversation_id"]
                        st.rerun()
            
            with col2:
                # 편집 버튼
                if st.button("✏️", key=f"edit_{conv['conversation_id']}"):
                    st.session_state.edit_mode_conversation = conv["conversation_id"]
                    st.rerun()
            
            with col3:
                # 삭제(보관) 버튼
                if st.button("🗑️", key=f"delete_{conv['conversation_id']}"):
                    # 삭제 확인을 위한 상태 관리
                    if "delete_confirm" not in st.session_state:
                        st.session_state.delete_confirm = None
                    
                    if st.session_state.delete_confirm == conv["conversation_id"]:
                        # 삭제 확인
                        conversation_manager.archive_conversation(conv["conversation_id"])
                        
                        # 현재 선택된 대화가 삭제되는 경우 다른 대화 선택
                        if current_conv_id == conv["conversation_id"] and conversations:
                            # 다른 대화가 있으면 첫 번째 대화 선택
                            other_convs = [c for c in conversations if c["conversation_id"] != conv["conversation_id"]]
                            if other_convs:
                                st.session_state[f"current_conversation_id_{username}"] = other_convs[0]["conversation_id"]
                            else:
                                # 다른 대화가 없으면 새 대화 생성
                                new_id = conversation_manager.create_conversation(username)
                                st.session_state[f"current_conversation_id_{username}"] = new_id
                        
                        st.session_state.delete_confirm = None
                        st.rerun()
                    else:
                        # 삭제 확인 요청
                        st.session_state.delete_confirm = conv["conversation_id"]
                        st.sidebar.warning(f"'{conv['title']}' 대화를 삭제하시겠습니까? 다시 클릭하면 삭제됩니다.")
    
    # 구분선 추가
    st.sidebar.divider()
    
    return current_conv_id

# 대화 인터페이스 컴포넌트
def chat_interface(conversation_manager, username, conversation_id, generate_response_func):
    """대화 인터페이스 컴포넌트"""
    # 현재 대화의 메시지 가져오기
    messages = conversation_manager.get_conversation_messages(username, conversation_id)
    
    # 메시지 표시
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # 사용자 입력
    prompt = st.chat_input("메시지를 입력하세요...")
    
    # 입력 처리
    if prompt:
        # 사용자 메시지 추가
        conversation_manager.add_message(conversation_id, "user", prompt)
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # 어시스턴트 응답
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            with st.spinner("응답 생성 중..."):
                # 응답 생성 함수 호출
                response = generate_response_func(prompt, username, conversation_id)
            
            message_placeholder.markdown(response)
        
        # 어시스턴트 메시지 저장
        conversation_manager.add_message(conversation_id, "assistant", response)
        
        # 스크롤 최하단으로 이동하기 위한 JavaScript 실행
        st.write(
            """
            <script>
                window.scrollTo(0, document.body.scrollHeight);
            </script>
            """,
            unsafe_allow_html=True
        )

# 문서 트리 컴포넌트
def document_tree_view(doc_manager, selected_category=None):
    """문서 트리 뷰 컴포넌트"""
    st.title("문서 카테고리 탐색")
    
    # 사용 가능한 카테고리 목록 가져오기
    categories = doc_manager.get_available_categories()
    
    if not categories:
        st.info("등록된 문서가 없습니다. 관리자에게 문서 등록을 요청하세요.")
        return None, None
    
    # 카테고리 선택 (사이드바)
    if not selected_category:
        selected_category = st.selectbox(
            "카테고리 선택", 
            options=categories
        )
    
    st.subheader(f"{selected_category} 카테고리 문서")
    
    # 선택된 카테고리의 문서 목록 가져오기
    documents = doc_manager.get_documents_by_category(selected_category)
    
    # 문서를 파일명으로 그룹화하여 버전별로 표시
    grouped_docs = {}
    for doc in documents:
        filename = doc["filename"]
        if filename not in grouped_docs:
            grouped_docs[filename] = []
        grouped_docs[filename].append(doc)
    
    # 선택된 문서 ID
    selected_doc_id = None
    
    # 각 문서 그룹 표시
    for filename, docs in grouped_docs.items():
        # 버전별 정렬
        docs.sort(key=lambda x: x["version"], reverse=True)
        
        # 파일명과 최신 버전 표시
        st.markdown(f"### 📄 {filename} (v{docs[0]['version']})")
        
        # 설명 표시 (있는 경우)
        if "description" in docs[0] and docs[0]["description"]:
            st.markdown(f"*{docs[0]['description']}*")
        
        # 최신 버전 문서 선택 버튼
        if st.button(f"이 문서 내용 보기", key=f"view_{docs[0]['doc_id']}"):
            selected_doc_id = docs[0]["doc_id"]
        
        # 이전 버전 확장 섹션
        if len(docs) > 1:
            with st.expander(f"이전 버전 ({len(docs)-1}개)"):
                for doc in docs[1:]:
                    col1, col2 = st.columns([0.8, 0.2])
                    with col1:
                        st.write(f"v{doc['version']} - {doc['upload_time']}")
                    with col2:
                        if st.button("보기", key=f"view_{doc['doc_id']}"):
                            selected_doc_id = doc["doc_id"]
    
    return selected_category, selected_doc_id

# 선택된 문서 내용 표시 컴포넌트
def display_document_content(doc_manager, doc_id):
    """선택된 문서의 내용을 표시하는 컴포넌트"""
    if not doc_id:
        return
    
    # 문서 정보 가져오기
    doc_info = doc_manager.get_document_by_id(doc_id)
    
    if not doc_info:
        st.error("문서를 찾을 수 없습니다.")
        return
    
    # 문서 정보 표시
    st.subheader(f"📄 {doc_info['filename']} (v{doc_info['version']})")
    st.write(f"**카테고리:** {doc_info['category']}")
    st.write(f"**업로드 날짜:** {doc_info['upload_time']}")
    
    # 문서 내용 표시 - 벡터스토어에서 청크 검색
    if "vectorstore" in st.session_state:
        vectorstore = st.session_state.vectorstore
        
        # 벡터 저장소에서 문서 청크 검색
        docs = vectorstore.similarity_search(
            f"filename:{doc_info['filename']} category:{doc_info['category']} version:{doc_info['version']}",
            k=100  # 더 많은 청크 검색
        )
        
        if docs:
            # 청크들을 표시
            st.subheader("문서 내용 미리보기")
            
            with st.expander("문서 청크 보기", expanded=True):
                for i, chunk in enumerate(docs):
                    st.markdown(f"**청크 {i+1}:**")
                    st.markdown(chunk.page_content)
                    st.divider()
        else:
            st.info("이 문서의 내용을 찾을 수 없습니다.")
    else:
        st.warning("벡터 저장소가 아직 초기화되지 않았습니다.")