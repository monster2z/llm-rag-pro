# rag_utils.py
import os
from typing import List, Dict, Any, Optional, TypedDict, Union
import streamlit as st

# LangChain 관련 라이브러리
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END

# LangGraph 상태 정의
class AgentState(TypedDict):
    question: str
    context: List[str] 
    answer: str
    conversation_history: List[Dict[str, str]]
    sources: List[Dict[str, str]]
    need_more_info: bool
    username: str  # 사용자 식별을 위한 필드 추가

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

def generate_answer(state: AgentState) -> AgentState:
    """검색된 문서를 바탕으로 질문에 대한 답변을 생성하는 함수"""
    # LLM 모델 설정
    llm_model = st.session_state.get("LLM_MODEL", "gpt-4o-mini")
    llm_provider = st.session_state.get("LLM_PROVIDER", "openai")
    api_key = os.environ.get("OPENAI_API_KEY")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    # LLM 모델 초기화
    if llm_provider == "anthropic" and anthropic_api_key:
        llm = ChatAnthropic(model=llm_model, api_key=anthropic_api_key)
    else:
        llm = ChatOpenAI(model=llm_model, api_key=api_key)
    
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

def add_source_information(state: AgentState) -> AgentState:
    """답변에 소스 정보를 추가하는 함수"""
    if not state.get("sources") or len(state["sources"]) == 0:
        # 소스가 없는 경우 일반 정보 추가
        enhanced_answer = state["answer"] + "\n\n*참고: 보다 구체적이고 정확한 답변을 위해서는 관련 문서가 필요합니다.*"
        return {**state, "answer": enhanced_answer}
        
    sources_info = "\n\n**참고 문서:**\n"
    for src in state["sources"]:
        # 딕셔너리 형태로 오는 경우
        if isinstance(src, dict):
            source = src.get('source', 'Unknown')
            page = src.get('page', 'N/A')
            category = src.get('category', '')
            
            sources_info += f"- {source}"
            if page != "N/A":
                sources_info += f" (페이지: {page})"
            if category:
                sources_info += f" [카테고리: {category}]"
            sources_info += "\n"
        # 문자열이나 다른 형태로 오는 경우
        else:
            sources_info += f"- {str(src)}\n"
    
    enhanced_answer = state["answer"] + sources_info
    
    return {**state, "answer": enhanced_answer}

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

@st.cache_data(ttl=600, show_spinner=False)
def generate_response(prompt, username, conversation_id, _conv_manager=None):
    """사용자 질문에 대한 응답 생성"""
    # 대화 기록 가져오기
    conv_manager = _conv_manager or st.session_state.get("conversation_manager")
    if conv_manager:
        messages = conv_manager.get_conversation_messages(username, conversation_id)
        conversation_history = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in messages
        ]
    else:
        conversation_history = []
    
    # 벡터 스토어 상태 확인
    has_vectorstore = "vectorstore" in st.session_state and st.session_state.vectorstore is not None
    
    # LangGraph 워크플로우가 설정되어 있고 벡터 스토어가 있으면 RAG 사용
    if has_vectorstore and 'rag_workflow' in st.session_state:
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
            
            # 디버그 로그
            print(f"RAG 결과: {result.get('sources', [])} 소스 찾음")
            
            # 답변 반환
            return result["answer"]
            
        except Exception as e:
            st.error(f"RAG 응답 생성 중 오류: {str(e)}")
            # 오류 발생 시 기본 응답으로 폴백
            return f"죄송합니다. 질문 처리 중 오류가 발생했습니다. 나중에 다시 시도해주세요."
    else:
        # 기본 LLM 사용 (RAG가 없는 경우)
        llm_model = st.session_state.get("LLM_MODEL", "gpt-4o-mini")
        api_key = os.environ.get("OPENAI_API_KEY")
        llm = ChatOpenAI(model=llm_model, api_key=api_key)
            
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
            response = chain.invoke({
                "question": prompt,
                "conversation_history": str(conversation_history)
            })
            
            # 문서가 없을 때 안내 메시지 추가
            if not has_vectorstore:
                response += "\n\n*참고: 보다 구체적이고 정확한 답변을 위해서는 관련 문서가 필요합니다.*"
            
            return response
        except Exception as e:
            st.error(f"LLM 응답 생성 중 오류: {str(e)}")
            return "죄송합니다. 응답 생성 중 오류가 발생했습니다. 나중에 다시 시도해주세요."