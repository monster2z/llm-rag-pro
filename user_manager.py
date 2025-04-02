# user_manager.py
import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import os
from typing import Dict, List, Optional, Any

class UserManager:
    """사용자 관리 클래스: 사용자 인증, 권한 관리 등 기능 제공"""
    
    def __init__(self, config_path: str = 'config.yaml', db_manager=None):
        self.config_path = config_path
        self.db_manager  = db_manager
        
        # 설정 파일 로드 또는 생성
        if not os.path.exists(config_path):
            self.config = self._create_default_config()
        else:
            with open(config_path, 'r', encoding='utf-8') as file:
                self.config = yaml.load(file, Loader=SafeLoader)
        
        # 인증 객체 생성
        self.authenticator = stauth.Authenticate(
            self.config['credentials'],
            self.config['cookie']['name'],
            self.config['cookie']['key'],
            self.config['cookie']['expiry_days']
        )
    
    def _create_default_config(self) -> Dict[str, Any]:
        """기본 설정 파일 생성"""
        hasher = stauth.Hasher()
        
        # 환경 변수에서 비밀번호 가져오기
        admin_pass = os.environ.get("ADMIN_PASS")
        user_pass = os.environ.get("USER_PASS")
        
        config = {
            'credentials': {
                'usernames': {
                    'admin2': {
                        'email': 'admin@example.com',
                        'name': '관리자',
                        'password': hasher.hash(admin_pass),
                        'role': 'admin'  # 관리자 역할 추가
                    },
                    'user_test': {
                        'email': 'user1@example.com',
                        'name': '테스트사용자',
                        'password': hasher.hash(user_pass),
                        'role': 'user'   # 일반 사용자 역할 추가
                    }
                }
            },
            'cookie': {
                'expiry_days': 30,
                'key': 'some_signature_key',
                'name': 'llm_dashboard_cookie'
            }
        }
        
        # 설정 파일 저장
        with open(self.config_path, 'w', encoding='utf-8') as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
        
        return config
    
    def save_config(self):
        """설정 파일 저장"""
        with open(self.config_path, 'w', encoding='utf-8') as file:
            yaml.dump(self.config, file, default_flow_style=False, allow_unicode=True)
    
    def login(self):
        """로그인 화면 표시 및 처리"""
        self.authenticator.login()
        
        # 로그인 성공 시 사용자 정보 세션 상태에 저장
        if st.session_state["authentication_status"]:
            username = st.session_state["username"]
            
            # 사용자 역할 정보 세션에 저장
            if "user_role" not in st.session_state:
                user_info = self.config['credentials']['usernames'].get(username, {})
                st.session_state["user_role"] = user_info.get('role', 'user')
    
    def logout(self):
        """로그아웃 버튼 표시"""
        self.authenticator.logout('로그아웃', 'sidebar')
    
    def is_admin(self) -> bool:
        """현재 사용자가 관리자인지 확인"""
        return st.session_state.get("user_role") == "admin"
    
    def get_current_user(self) -> Dict[str, Any]:
        """현재 로그인한 사용자 정보 반환"""
        username = st.session_state.get("username")
        if not username:
            return {}
        
        user_info = self.config['credentials']['usernames'].get(username, {})
        return {
            "username": username,
            "name": user_info.get('name', username),
            "email": user_info.get('email', ''),
            "role": user_info.get('role', 'user')
        }
    
    def add_user(self, username: str, name: str, email: str, password: str, role: str = 'user') -> bool:
        """새 사용자 추가 (관리자 전용)"""
        if username in self.config['credentials']['usernames']:
            return False  # 이미 존재하는 사용자
        
        hasher = stauth.Hasher()
        
        # 사용자 정보 추가
        self.config['credentials']['usernames'][username] = {
            'email': email,
            'name': name,
            'password': hasher.hash(password),
            'role': role
        }
        
        # 설정 파일 저장
        self.save_config()
        return True
    
    def update_user(self, username: str, updates: Dict[str, Any]) -> bool:
        """사용자 정보 업데이트 (관리자 전용)"""
        if username not in self.config['credentials']['usernames']:
            return False  # 존재하지 않는 사용자
        
        # 비밀번호 업데이트가 포함된 경우 해싱 처리
        if 'password' in updates:
            hasher = stauth.Hasher()
            updates['password'] = hasher.hash(updates['password'])
        
        # 사용자 정보 업데이트
        for key, value in updates.items():
            self.config['credentials']['usernames'][username][key] = value
        
        # 설정 파일 저장
        self.save_config()
        return True
    
    def delete_user(self, username: str) -> bool:
        """사용자 삭제 (관리자 전용)"""
        if username not in self.config['credentials']['usernames']:
            return False  # 존재하지 않는 사용자
        
        # 사용자 정보 삭제
        del self.config['credentials']['usernames'][username]
        
        # 설정 파일 저장
        self.save_config()
        return True
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """모든 사용자 목록 조회 (관리자 전용)"""
        users = []
        for username, info in self.config['credentials']['usernames'].items():
            users.append({
                "username": username,
                "name": info.get('name', username),
                "email": info.get('email', ''),
                "role": info.get('role', 'user')
            })
        return users

# 관리자 패널 컴포넌트
def admin_panel(user_manager):
    """관리자 전용 패널 UI 컴포넌트"""
    st.title("관리자 패널")
    
    tabs = st.tabs(["사용자 관리", "문서 권한 관리", "시스템 설정"])
    
    # 사용자 관리 탭
    with tabs[0]:
        st.subheader("사용자 목록")
        
        users = user_manager.get_all_users()
        user_df = pd.DataFrame(users)
        st.dataframe(user_df)
        
        st.subheader("사용자 추가")
        with st.form("add_user_form"):
            new_username = st.text_input("사용자 ID")
            new_name = st.text_input("이름")
            new_email = st.text_input("이메일")
            new_password = st.text_input("비밀번호", type="password")
            new_role = st.selectbox("역할", ["user", "admin"])
            
            submit = st.form_submit_button("사용자 추가")
            
            if submit:
                if not new_username or not new_password:
                    st.error("사용자 ID와 비밀번호는 필수입니다.")
                elif user_manager.add_user(new_username, new_name, new_email, new_password, new_role):
                    st.success(f"사용자 '{new_username}'이(가) 추가되었습니다.")
                    st.rerun()
                else:
                    st.error(f"사용자 '{new_username}'이(가) 이미 존재합니다.")
        
        st.subheader("사용자 삭제")
        with st.form("delete_user_form"):
            username_to_delete = st.selectbox(
                "삭제할 사용자 선택", 
                options=[user["username"] for user in users]
            )
            delete_submit = st.form_submit_button("사용자 삭제")
            
            if delete_submit:
                if user_manager.delete_user(username_to_delete):
                    st.success(f"사용자 '{username_to_delete}'이(가) 삭제되었습니다.")
                    st.rerun()
                else:
                    st.error(f"사용자 '{username_to_delete}'을(를) 삭제할 수 없습니다.")
    
    # 문서 권한 관리 탭
    with tabs[1]:
        st.subheader("문서 카테고리 권한 관리")
        st.warning("이 기능은 PostgreSQL과 함께 사용할 때 더 효과적입니다.")
        
        # 여기에 문서 권한 관리 UI 추가
        # PostgreSQL이 설정된 경우, 카테고리별로 사용자에게 권한 부여 기능 구현
    
    # 시스템 설정 탭
    with tabs[2]:
        st.subheader("LLM 모델 설정")
        
        # LLM 모델 선택
        model_options = ["gpt-4o-mini", "gpt-4o", "claude-3-sonnet-20240229", "claude-3-opus-20240229"]
        current_model = st.session_state.get("LLM_MODEL", "gpt-4o-mini")
        
        new_model = st.selectbox("LLM 모델", options=model_options, index=model_options.index(current_model))
        
        # 임베딩 모델 선택
        embedding_options = ["text-embedding-3-small", "text-embedding-3-large"]
        current_embedding = st.session_state.get("EMBEDDING_MODEL", "text-embedding-3-small")
        
        new_embedding = st.selectbox("임베딩 모델", options=embedding_options, index=embedding_options.index(current_embedding))
        
        # 적용 버튼
        if st.button("설정 적용"):
            st.session_state["LLM_MODEL"] = new_model
            st.session_state["EMBEDDING_MODEL"] = new_embedding
            st.success("모델 설정이 업데이트되었습니다.")
            
        # 시스템 성능 모니터링 추가 (선택적)
        st.subheader("시스템 성능")
        st.info("여기에 시스템 성능 통계를 표시할 수 있습니다.")

# 관리자용 문서 업로드 컴포넌트
def admin_document_upload(doc_manager):
    """관리자용 문서 업로드 UI 컴포넌트"""
    st.header("문서 업로드 (관리자 전용)")
    
    # 카테고리 선택 또는 새 카테고리 생성
    existing_categories = doc_manager.get_available_categories()
    
    category_option = st.radio(
        "카테고리 선택",
        ["기존 카테고리 사용", "새 카테고리 생성"]
    )
    
    if category_option == "기존 카테고리 사용" and existing_categories:
        category = st.selectbox("카테고리 선택", options=existing_categories)
    else:
        category = st.text_input("새 카테고리 이름")
    
    # 문서 설명 추가
    description = st.text_area("문서 설명 (선택사항)")
    
    # 파일 업로드
    uploaded_files = st.file_uploader(
        "기업 내부 문서를 업로드하세요", 
        type=['pdf', 'docx', 'csv', 'pptx'], 
        accept_multiple_files=True
    )
    
    # 업로드 버튼
    if uploaded_files and category and st.button("문서 처리 및 임베딩"):
        return uploaded_files, category, description
    
    return None, None, None