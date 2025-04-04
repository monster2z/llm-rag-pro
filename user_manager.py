# user_manager.py
import streamlit as st
import hashlib
import os
from typing import Dict, List, Optional, Any
import datetime

class UserManager:
    """사용자 관리 클래스: DB 기반 사용자 인증, 권한 관리 등 기능 제공"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # DBManager 객체에서 세션 접근
        self.db_session = db_manager.session
    
    def _hash_password(self, password: str) -> str:
        """비밀번호 해싱 처리 - bcrypt 직접 사용"""
        try:
            import bcrypt
            return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        except ImportError:
            # bcrypt가 설치되지 않은 경우 기본 해시 사용 (개발용, 프로덕션에는 권장하지 않음)
            return hashlib.sha256(password.encode()).hexdigest()
    # 이전 streamlit_authenticator 사용했을 때    
    # def _hash_password(self, password: str) -> str:
    #     """비밀번호 해싱 처리 - streamlit_authenticator와 호환되게 유지"""
    #     from streamlit_authenticator import Hasher
    #     hasher = Hasher()
    #     return hasher.hash(password)
    
    # user_manager.py의 login 함수 수정
    def login(self):
        """로그인 화면 표시 및 처리"""
        # 이미 로그인된 경우 함수 종료
        if st.session_state.get("authentication_status") == True:
            return
            
        st.header("로그인")
        
        # 세션 상태 초기화
        if "authentication_status" not in st.session_state:
            st.session_state["authentication_status"] = None  # None으로 초기화 (미인증 상태)
        
        # 로그인 폼
        with st.form("login_form"):
            username = st.text_input("사용자 ID")
            password = st.text_input("비밀번호", type="password")
            remember_me = st.checkbox("로그인 정보 기억하기")
            submit = st.form_submit_button("로그인")
            
            if submit:
                print(f"폼 제출됨: {username}")
                self._authenticate_user(username, password)
                
                # 로그인 정보 기억하기가 체크되지 않은 경우
                if not remember_me:
                    # 폼 값 초기화를 위한 쿼리 파라미터 추가
                    st.query_params["clear_form"] = True
                
                # 로그인 성공 시 페이지 새로고침 (폼을 숨기기 위해)
                if st.session_state.get("authentication_status") == True:
                    st.rerun()
        
        # 인증 결과 표시
        if st.session_state["authentication_status"] == True:
            print(f"인증 성공: {st.session_state.get('username')}")
            st.success(f"{st.session_state.get('username')}님 환영합니다!")
        elif st.session_state["authentication_status"] == False:
            print("인증 실패")
            st.error("아이디 또는 비밀번호가 잘못되었습니다.")
        else:
            # 초기 상태 (None)일 때는 메시지 없음 또는 안내 메시지 표시
            st.info("로그인 정보를 입력해주세요.")
    
    def _authenticate_user(self, username: str, password: str):
        """사용자 인증 처리 - SQLAlchemy 모델 사용"""
        if not username or not password:
            st.session_state["authentication_status"] = False
            return
    
    # 해당 사용자 정보 조회 (SQLAlchemy 모델 사용)
        from db_models import User
        user = self.db_session.query(User).filter(User.username == username).first()
        print(f"사용자 인증 시도: {username}")  # 로그 추가
        if user:
            # 비밀번호 검증 (직접 해시 비교)
            try:
                stored_password = user.password_hash
                # streamlit_authenticator의 Hasher는 bcrypt를 사용하므로 bcrypt로 직접 검증
                import bcrypt
                # 저장된 해시가 이미 bcrypt 형식이면 직접 체크
                if stored_password.startswith('$2'):
                    password_match = bcrypt.checkpw(password.encode(), stored_password.encode())
                else:
                    # 그렇지 않으면 간단한 해시 비교 (실제 환경에서는 더 안전한 방법 사용 필요)
                    hashed_password = hashlib.sha256(password.encode()).hexdigest()
                    password_match = (hashed_password == stored_password)
                
                if password_match:
                    # 인증 성공
                    print("인증 성공")
                    st.session_state["authentication_status"] = True
                    st.session_state["username"] = user.username
                    st.session_state["name"] = user.name
                    st.session_state["user_role"] = user.role
                    
                    # 마지막 로그인 시간 업데이트
                    user.last_login = datetime.datetime.utcnow()
                    self.db_session.commit()
                    return
                else:
                    print("비밀번호 불일치")
            except Exception as e:
                print(f"비밀번호 검증 중 오류: {str(e)}")
        else:
            print("사용자 없음")
        # 인증 실패
        st.session_state["authentication_status"] = False
    
    def logout(self):
        """로그아웃 버튼 표시 (위치 개선)"""
        # 사이드바 대신 제목 옆에 로그아웃 버튼 배치
        col1, col2 = st.sidebar.columns([1, 1])
        
        with col1:
            st.write(f"{st.session_state.get('name', '')}님")
        
        with col2:
            if st.button("로그아웃", key="logout_btn"):
                for key in ["authentication_status", "username", "name", "user_role"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
    
    def is_admin(self) -> bool:
        """현재 사용자가 관리자인지 확인"""
        return st.session_state.get("user_role") == "admin"
    
    def get_current_user(self) -> Dict[str, Any]:
        """현재 로그인한 사용자 정보 반환"""
        if not st.session_state.get("authentication_status", False):
            return {}
        
        # 세션에서 기본 정보 가져오기
        username = st.session_state.get("username", "")
        
        # DB에서 최신 정보 조회 (필요시)
        from db_models import User
        user = self.db_session.query(User).filter(User.username == username).first()
        
        if user:
            return {
                "username": user.username,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "created_at": user.created_at,
                "last_login": user.last_login
            }
        
        # 기본 세션 정보로 폴백
        return {
            "username": username,
            "name": st.session_state.get("name", ""),
            "role": st.session_state.get("user_role", "")
        }
    
    def add_user(self, username: str, name: str, email: str, password: str, role: str = 'user') -> bool:
        """새 사용자 추가 - SQLAlchemy 모델 사용"""
        try:
            # DB 모델 가져오기
            from db_models import User
            
            # 사용자 존재 여부 확인
            existing_user = self.db_session.query(User).filter(User.username == username).first()
            if existing_user:
                return False  # 이미 존재하는 사용자
            
            # 비밀번호 해싱
            password_hash = self._hash_password(password)
            
            # 사용자 추가
            new_user = User(
                username=username,
                name=name,
                email=email,
                password_hash=password_hash,
                role=role,
                created_at=datetime.datetime.utcnow()
            )
            
            self.db_session.add(new_user)
            self.db_session.commit()
            return True
            
        except Exception as e:
            self.db_session.rollback()
            st.error(f"사용자 추가 중 오류 발생: {e}")
            return False
    
    def update_user(self, username: str, updates: Dict[str, Any]) -> bool:
        """사용자 정보 업데이트 - SQLAlchemy 모델 사용"""
        try:
            # DB 모델 가져오기
            from db_models import User
            
            # 사용자 조회
            user = self.db_session.query(User).filter(User.username == username).first()
            if not user:
                return False  # 존재하지 않는 사용자
            
            # 업데이트할 필드 처리
            for key, value in updates.items():
                if key == 'password':
                    user.password_hash = self._hash_password(value)
                elif key in ['name', 'email', 'role']:
                    setattr(user, key, value)
            
            # 변경사항 저장
            self.db_session.commit()
            return True
            
        except Exception as e:
            self.db_session.rollback()
            st.error(f"사용자 업데이트 중 오류 발생: {e}")
            return False
    
    def delete_user(self, username: str) -> bool:
        """사용자 삭제 - SQLAlchemy 모델 사용"""
        try:
            # DB 모델 가져오기
            from db_models import User
            
            # 사용자 조회
            user = self.db_session.query(User).filter(User.username == username).first()
            if not user:
                return False  # 존재하지 않는 사용자
            
            # 사용자 삭제
            self.db_session.delete(user)
            self.db_session.commit()
            return True
            
        except Exception as e:
            self.db_session.rollback()
            st.error(f"사용자 삭제 중 오류 발생: {e}")
            return False
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """모든 사용자 목록 조회 - SQLAlchemy 모델 사용"""
        try:
            # DB 모델 가져오기
            from db_models import User
            
            # 모든 사용자 조회
            users_query = self.db_session.query(User).all()
            
            # 결과를 사전 목록으로 변환
            users = []
            for user in users_query:
                users.append({
                    "username": user.username,
                    "name": user.name,
                    "email": user.email,
                    "role": user.role,
                    "created_at": user.created_at,
                    "last_login": user.last_login
                })
            return users
            
        except Exception as e:
            st.error(f"사용자 목록 조회 중 오류 발생: {e}")
            return []
        
    
# admin_panel 함수 오류 수정
def admin_panel(user_manager):
    """관리자 전용 패널 UI 컴포넌트"""
    import pandas as pd
    
    st.title("관리자 패널")
    
    tabs = st.tabs(["사용자 관리", "문서 권한 관리", "시스템 설정"])
    
    # 사용자 관리 탭
    with tabs[0]:
        st.subheader("사용자 목록")
        
        users = user_manager.get_all_users()
        if users:
            user_df = pd.DataFrame(users)
            st.dataframe(user_df)
        else:
            st.info("사용자 정보를 불러올 수 없습니다.")
        
        st.subheader("사용자 추가")
        with st.form("add_user_form"):
            new_username = st.text_input("사용자 ID", key="new_user_id")
            new_name = st.text_input("이름", key="new_user_name")
            new_email = st.text_input("이메일", key="new_user_email")
            new_password = st.text_input("비밀번호", type="password", key="new_user_pw")
            new_role = st.selectbox("역할", ["user", "admin"], key="new_user_role")
            
            submit = st.form_submit_button("사용자 추가")
            
            if submit:
                if not new_username or not new_password:
                    st.error("사용자 ID와 비밀번호는 필수입니다.")
                elif hasattr(user_manager, 'add_user') and user_manager.add_user(new_username, new_name, new_email, new_password, new_role):
                    st.success(f"사용자 '{new_username}'이(가) 추가되었습니다.")
                    st.rerun()
                else:
                    st.error(f"사용자 추가에 실패했습니다.")
    
    # 문서 권한 관리 탭
    with tabs[1]:
        st.subheader("문서 카테고리 권한 관리")
        
        try:
            # 카테고리 조회 - execute_query 대신 안전하게 수정
            if hasattr(user_manager.db_manager, 'session'):
                from sqlalchemy import text
                from db_models import DocumentMetadata
                
                # SQLAlchemy를 사용하여 카테고리 목록 조회
                categories_query = user_manager.db_manager.session.query(
                    DocumentMetadata.category
                ).distinct()
                
                categories = [cat[0] for cat in categories_query]
                
                if categories:
                    selected_category = st.selectbox(
                        "카테고리 선택", 
                        categories,
                        key="admin_category_select"
                    )
                    
                    # 사용자 목록
                    users = user_manager.get_all_users()
                    
                    st.subheader(f"{selected_category} 카테고리 접근 권한")
                    
                    # 권한 관리 UI - 간소화된 버전
                    for user in users:
                        username = user.get("username", "") if isinstance(user, dict) else (
                            user.username if hasattr(user, "username") else ""
                        )
                        
                        if username:
                            st.checkbox(
                                f"{username}",
                                key=f"perm_{username}_{selected_category}"
                            )
                else:
                    st.info("등록된 문서 카테고리가 없습니다.")
            else:
                st.warning("데이터베이스 세션이 초기화되지 않았습니다.")
        except Exception as e:
            st.error(f"권한 관리 오류: {str(e)}")
            st.info("데이터베이스 연결 상태를 확인하세요.")
    
    # 시스템 설정 탭
    with tabs[2]:
        st.subheader("LLM 모델 설정")
        
        # LLM 모델 선택
        model_options = ["gpt-4o-mini", "gpt-4o", "claude-3-sonnet-20240229", "claude-3-opus-20240229"]
        current_model = st.session_state.get("LLM_MODEL", "gpt-4o-mini")
        
        new_model = st.selectbox(
            "LLM 모델", 
            options=model_options, 
            index=model_options.index(current_model) if current_model in model_options else 0,
            key="llm_model_select"
        )
        
        # 임베딩 모델 선택
        embedding_options = ["text-embedding-3-small", "text-embedding-3-large"]
        current_embedding = st.session_state.get("EMBEDDING_MODEL", "text-embedding-3-small")
        
        new_embedding = st.selectbox(
            "임베딩 모델", 
            options=embedding_options, 
            index=embedding_options.index(current_embedding) if current_embedding in embedding_options else 0,
            key="embedding_model_select"
        )
        
        # 적용 버튼
        if st.button("설정 적용", key="apply_settings_btn"):
            st.session_state["LLM_MODEL"] = new_model
            st.session_state["EMBEDDING_MODEL"] = new_embedding
            st.success("모델 설정이 업데이트되었습니다.")