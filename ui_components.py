# ui_components.py
import streamlit as st
import time
from datetime import datetime

def add_fixed_header_style():
    """상단 고정 헤더를 위한 CSS 스타일 추가"""
    st.markdown("""
    <style>
        /* 상단 고정 헤더 스타일 */
        .fixed-header {
            position: sticky;
            top: 0;
            background-color: white;
            z-index: 999;
            padding: 10px 0;
            border-bottom: 1px solid #e6e6e6;
            width: 100%;
            margin-bottom: 1rem;
        }
        
        /* 구분선 스타일 */
        .divider {
            border-bottom: 1px solid #e6e6e6;
            margin: 10px 0;
            width: 100%;
        }
        
        /* 콘텐츠 영역 패딩 */
        .content-area {
            padding-top: 80px;  /* 헤더 높이에 맞게 조정 */
        }
        
        /* 선택된 탭 강조 */
        .stTabs [aria-selected="true"] {
            background-color: #f0f2f6;
            border-bottom: 2px solid #4e8cff;
            font-weight: bold;
        }
        
        /* 대화 컨테이너 최대 높이 설정 */
        .chat-container {
            max-height: 70vh;
            overflow-y: auto;
            padding: 10px;
            border-radius: 5px;
        }
        
        /* 탭 고정 스타일 */
        .fixed-tabs {
            position: sticky;
            top: 0;
            z-index: 998;
            background-color: white;
            padding-bottom: 1px;
            border-bottom: 1px solid #f0f2f6;
            margin-bottom: 10px;
        }
        
        /* 탭 컨테이너 바로 밑의 내용에 대한 마진 */
        .stTabs + div {
            margin-top: 20px;
        }
        
        /* 문서 카드 스타일 */
        .doc-card {
            border: 1px solid #e6e6e6;
            border-radius: 5px;
            padding: 10px;
            margin-bottom: 10px;
            transition: all 0.2s ease;
        }
        
        .doc-card:hover {
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        /* 버튼 스타일 개선 */
        .stButton button {
            border-radius: 4px;
            padding: 2px 8px;
            transition: all 0.2s ease;
        }
        
        .stButton button:hover {
            transform: translateY(-1px);
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        /* 메시지 스타일 */
        .user-message {
            background-color: #e6f7ff;
            border-radius: 5px;
            padding: 8px 12px;
            margin: 5px 0;
            align-self: flex-end;
        }
        
        .assistant-message {
            background-color: #f0f2f6;
            border-radius: 5px;
            padding: 8px 12px;
            margin: 5px 0;
            align-self: flex-start;
        }
    </style>
    """, unsafe_allow_html=True)

def render_header(username=None, user_role=None):
    """앱 헤더 렌더링"""
    with st.container():
        st.markdown('<div class="fixed-header">', unsafe_allow_html=True)
        
        # 상단 헤더 컬럼 레이아웃
        col1, col2 = st.columns([3, 1])
        with col1:
            st.title(f"기업 내부용 AI 어시스턴트")
        with col2:
            if username:
                st.write(f"사용자: {username} ({user_role or '일반'})")
        
        # 구분선
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)  # 고정 헤더 닫기

def render_fixed_tabs():
    """고정 탭 렌더링 - 스크롤해도 상단에 고정되도록 개선"""
    # 고정 컨테이너 시작
    fixed_header = st.container()
    
    with fixed_header:
        # CSS로 고정 스타일 적용
        st.markdown('''
        <style>
            [data-testid="stVerticalBlock"] div:has([data-testid="stTabs"]) {
                position: sticky;
                top: 0;
                background-color: white;
                z-index: 999;
                padding: 3px 0px;
                border-bottom: 1px solid #f0f2f6;
            }
        </style>
        ''', unsafe_allow_html=True)
        
        # 탭 생성
        tabs = st.tabs(["대화하기", "문서 탐색", "설정"])
    
    return tabs

def render_document_stats(vectorstore=None):
    """문서 통계 정보 표시"""
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if vectorstore:
            try:
                doc_count = len(vectorstore.docstore._dict)
                st.success(f"문서가 임베딩되었습니다. {doc_count}개의 문서 청크가 검색 가능합니다.")
            except Exception as e:
                st.info("문서 정보를 불러오는 중 오류가 발생했습니다.")
        else:
            st.info("아직 업로드된 문서가 없습니다. 일반적인 지식을 기반으로 답변합니다.")
    
    return col1, col2

def render_document_list(document_manager):
    """문서 목록 표시"""
    if not document_manager:
        return
        
    available_docs = document_manager.get_all_active_documents()
    if available_docs:
        with st.expander("업로드된 문서 목록", expanded=False):
            for doc in available_docs[:10]:  # 최대 10개만 표시
                if hasattr(doc, 'filename') and hasattr(doc, 'category'):
                    st.write(f"📄 {doc.filename} ({doc.category})")
            if len(available_docs) > 10:
                st.write(f"...외 {len(available_docs)-10}개 더 있음")

def render_file_uploader(document_manager, username=None):
    """파일 업로드 UI 컴포넌트"""
    st.sidebar.header("문서 업로드 (관리자 전용)")
    
    uploaded_files = st.sidebar.file_uploader(
        "기업 내부 문서를 업로드하세요", 
        type=['pdf', 'docx', 'csv', 'pptx'], 
        accept_multiple_files=True,
        key="file_uploader_key"
    )
    
    # 카테고리 선택 또는 생성
    existing_categories = document_manager.get_available_categories()
    category_option = st.sidebar.radio(
        "카테고리", 
        ["기존 카테고리 사용", "새 카테고리 생성"],
        horizontal=True,
        key="category_option_key"
    )
    
    selected_category = None
    
    if category_option == "기존 카테고리 사용" and existing_categories:
        selected_category = st.sidebar.selectbox(
            "카테고리 선택", 
            options=existing_categories,
            key="category_select_key"
        )
    else:
        selected_category = st.sidebar.text_input(
            "새 카테고리 이름",
            key="new_category_key"
        )
    
    # 문서 설명 추가
    description = st.sidebar.text_area(
        "문서 설명 (선택사항)", 
        height=100,
        key="description_key"
    )
    
    # 업로드 버튼
    process_button = st.sidebar.button(
        "문서 처리 및 임베딩",
        key="process_button_key"
    )
    
    return uploaded_files, selected_category, description, process_button

def create_scrollable_chat_container():
    """스크롤 가능한 채팅 컨테이너 생성"""
    container = st.container()
    
    # 스크롤 최하단으로 이동하기 위한 JavaScript 실행
    js_code = """
    <script>
        function scrollToBottom() {
            const mainContainer = document.querySelector('.chat-container');
            if (mainContainer) {
                mainContainer.scrollTop = mainContainer.scrollHeight;
            }
        }
        
        // 페이지 로드 후 실행
        window.addEventListener('load', scrollToBottom);
        
        // 약간의 지연을 두고 한 번 더 실행 (콘텐츠가 완전히 로드된 후)
        setTimeout(scrollToBottom, 500);
    </script>
    """
    
    st.markdown(js_code, unsafe_allow_html=True)
    
    return container

def render_performance_tips():
    """성능 최적화 팁 표시"""
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