# db_models.py
from sqlalchemy import (
    create_engine, 
    Column, 
    Integer, 
    String, 
    Float, 
    Boolean, 
    Text, 
    DateTime, 
    ForeignKey, 
    JSON,
    func,
    text
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 필수 환경 변수 확인
required_vars = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
missing_vars = [var for var in required_vars if not os.environ.get(var)]
if missing_vars:
    print(f"경고: 다음 필수 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
    print("기본값을 사용하거나 오류가 발생할 수 있습니다.")

# Base 클래스 생성
Base = declarative_base()

# 사용자 정보 테이블
class User(Base):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'public'}  # 스키마 명시
    
    username = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default='user', nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    last_login = Column(DateTime)
    
    # 관계 정의
    documents = relationship("DocumentMetadata", back_populates="uploader")
    conversations = relationship("UserConversation", back_populates="user")
    permissions = relationship("CategoryPermission", back_populates="user", foreign_keys="CategoryPermission.username")
    assigned_permissions = relationship("CategoryPermission", back_populates="assigner", foreign_keys="CategoryPermission.assigned_by")

# 문서 메타데이터 테이블
class DocumentMetadata(Base):
    __tablename__ = 'document_metadata'
    __table_args__ = {'schema': 'public'}  # 스키마 명시
    
    doc_id = Column(String(50), primary_key=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)
    category = Column(String(100), nullable=False)
    version = Column(Integer, nullable=False)
    chunks = Column(Integer, nullable=False)
    uploaded_by = Column(String(100), ForeignKey('public.users.username'), nullable=False)
    upload_time = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    vector_store_path = Column(String(255))
    description = Column(Text)
    
    # 관계 정의
    uploader = relationship("User", back_populates="documents")
    version_logs = relationship("DocumentVersionLog", back_populates="document")

# 카테고리 권한 테이블
class CategoryPermission(Base):
    __tablename__ = 'category_permissions'
    __table_args__ = {'schema': 'public'}  # 스키마 명시
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(100), nullable=False)
    username = Column(String(100), ForeignKey('public.users.username'))
    can_view = Column(Boolean, default=True)
    can_upload = Column(Boolean, default=False)
    assigned_by = Column(String(100), ForeignKey('public.users.username'))
    assigned_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # 관계 정의
    user = relationship("User", back_populates="permissions", foreign_keys=[username])
    assigner = relationship("User", back_populates="assigned_permissions", foreign_keys=[assigned_by])

# 문서 버전 로그
class DocumentVersionLog(Base):
    __tablename__ = 'document_version_log'
    __table_args__ = {'schema': 'public'}  # 스키마 명시
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(50), ForeignKey('public.document_metadata.doc_id'))
    previous_version = Column(Integer)
    new_version = Column(Integer, nullable=False)
    change_description = Column(Text)
    changed_by = Column(String(100), ForeignKey('public.users.username'))
    changed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # 관계 정의
    document = relationship("DocumentMetadata", back_populates="version_logs")
    changer = relationship("User")

# 사용자 대화 테이블
class UserConversation(Base):
    __tablename__ = 'user_conversations'
    __table_args__ = {'schema': 'public'}  # 스키마 명시
    
    conversation_id = Column(String(50), primary_key=True)
    username = Column(String(100), ForeignKey('public.users.username'), nullable=False)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    is_archived = Column(Boolean, default=False)
    
    # 관계 정의
    user = relationship("User", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation")

# 대화 메시지 테이블
class ConversationMessage(Base):
    __tablename__ = 'conversation_messages'
    __table_args__ = {'schema': 'public'}  # 스키마 명시
    
    message_id = Column(String(50), primary_key=True)
    conversation_id = Column(String(50), ForeignKey('public.user_conversations.conversation_id'))
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    # 관계 정의
    conversation = relationship("UserConversation", back_populates="messages")

# 사용 통계 테이블
class UsageStat(Base):
    __tablename__ = 'usage_stats'
    __table_args__ = {'schema': 'public'}  # 스키마 명시
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), ForeignKey('public.users.username'))
    action_type = Column(String(50), nullable=False)
    resource_id = Column(String(100))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    details = Column(JSON)
    
    # 관계 정의
    user = relationship("User")

# 데이터베이스 연결 및 초기화 함수
def init_db():
    print("init_db 시작")
    """PostgreSQL 데이터베이스 연결 및 테이블 초기화"""
    db_host = os.environ.get("DB_HOST")
    db_port = os.environ.get("DB_PORT")
    db_name = os.environ.get("DB_NAME")
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    
    # SQLAlchemy 연결 문자열
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # 엔진 생성
    # print(f"DB URL: {db_url}로 엔진 생성")
    engine = create_engine(db_url)
    
    # 세션 생성
    print("세션 생성 성공")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # public 스키마가 없으면 생성
        session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        session.execute(text("SET search_path TO public"))
        session.commit()
        
        # 테이블 생성 (순서 중요)
        # Base.metadata.drop_all(engine)  # 기존 테이블 삭제
        Base.metadata.create_all(engine)  # 새 테이블 생성
        
        return engine, session
    except Exception as e:
        session.rollback()
        raise e

# 데이터베이스 관리 클래스
class DBManager:
    """데이터베이스 관리 클래스"""
    
    def __init__(self, engine=None, session=None):
        print("DBManager 초기화 시작")
        if engine is None or session is None:
            self.engine, self.session = init_db()
        else:
            self.engine = engine
            self.session = session
    
    def create_default_admin(self):
        """환경 변수에서 정보를 가져와 기본 관리자 계정 생성"""
        from streamlit_authenticator import Hasher
        
        # 환경 변수에서 관리자 정보 가져오기
        admin_username = os.environ.get("ADMIN_USERNAME")
        admin_password = os.environ.get("ADMIN_PASS")
        admin_name = os.environ.get("ADMIN_NAME")
        admin_email = os.environ.get("ADMIN_EMAIL")
        
        if not admin_password:
            print("경고: ADMIN_PASS 환경 변수가 설정되지 않았습니다!")
            return False
        
        # 이미 존재하는지 확인
        existing_user = self.session.query(User).filter(User.username == admin_username).first()
        if existing_user:
            return False
        
        # 비밀번호 해시 생성
        hasher = Hasher()
        password_hash = hasher.hash(admin_password)
        
        # 관리자 계정 생성
        admin = User(
            username=admin_username,
            name=admin_name,
            email=admin_email,
            password_hash=password_hash,
            role="admin",
            created_at=datetime.datetime.utcnow()
        )
        
        self.session.add(admin)
        self.session.commit()
        return True
    
    def create_default_user(self):
        """환경 변수에서 정보를 가져와 기본 사용자 계정 생성"""
        from streamlit_authenticator import Hasher
        
        # 환경 변수에서 사용자 정보 가져오기
        user_username = os.environ.get("USER_USERNAME")
        user_password = os.environ.get("USER_PASS")
        user_name = os.environ.get("USER_NAME")
        user_email = os.environ.get("USER_EMAIL")
        
        if not user_password:
            print("경고: USER_PASS 환경 변수가 설정되지 않았습니다!")
            return False
        
        # 이미 존재하는지 확인
        existing_user = self.session.query(User).filter(User.username == user_username).first()
        if existing_user:
            return False
        
            # 비밀번호 해시 생성
        hasher = Hasher()
        password_hash = hasher.hash(user_password) 
        
        # 사용자 계정 생성
        user = User(
            username=user_username,
            name=user_name,
            email=user_email,
            password_hash=password_hash,
            role="user",
            created_at=datetime.datetime.utcnow()
        )
        
        self.session.add(user)
        self.session.commit()
        return True
    
    def get_all_users(self):
        """모든 사용자 조회"""
        return self.session.query(User).all()
    
    def add_document(self, doc_metadata):
        """문서 메타데이터 추가"""
        doc = DocumentMetadata(
            doc_id=doc_metadata["doc_id"],
            filename=doc_metadata["filename"],
            file_type=doc_metadata["file_type"],
            category=doc_metadata["category"],
            version=doc_metadata["version"],
            chunks=doc_metadata["chunks"],
            uploaded_by=doc_metadata["uploaded_by"],
            upload_time=doc_metadata["upload_time"],
            is_active=doc_metadata["is_active"],
            vector_store_path=doc_metadata["vector_store_path"],
            description=doc_metadata.get("description", "")
        )
        
        self.session.add(doc)
        self.session.commit()
        return doc
    
    def get_active_documents(self):
        """활성 상태인 모든 문서 조회"""
        return self.session.query(DocumentMetadata).filter(DocumentMetadata.is_active == True).all()
    
    def get_documents_by_category(self, category):
        """카테고리별 문서 조회"""
        return self.session.query(DocumentMetadata).filter(
            DocumentMetadata.category == category,
            DocumentMetadata.is_active == True
        ).all()
    
    def add_conversation(self, conversation_data):
        """새 대화 추가"""
        conv = UserConversation(
            conversation_id=conversation_data["conversation_id"],
            username=conversation_data["username"],
            title=conversation_data["title"],
            created_at=conversation_data["created_at"],
            updated_at=conversation_data["updated_at"],
            is_archived=conversation_data.get("is_archived", False)
        )
        
        self.session.add(conv)
        self.session.commit()
        return conv
    
    def add_message(self, message_data):
        """대화 메시지 추가"""
        msg = ConversationMessage(
            message_id=message_data["message_id"],
            conversation_id=message_data["conversation_id"],
            role=message_data["role"],
            content=message_data["content"],
            timestamp=message_data["timestamp"]
        )
        
        self.session.add(msg)
        self.session.commit()
        return msg
    
    def get_user_conversations(self, username):
        """사용자별 대화 목록 조회"""
        return self.session.query(UserConversation).filter(
            UserConversation.username == username,
            UserConversation.is_archived == False
        ).order_by(UserConversation.updated_at.desc()).all()
    
    def get_conversation_messages(self, conversation_id):
        """대화별 메시지 조회"""
        return self.session.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id
        ).order_by(ConversationMessage.timestamp).all()
    
    def update_conversation_title(self, conversation_id, new_title):
        """대화 제목 업데이트"""
        conv = self.session.query(UserConversation).filter(
            UserConversation.conversation_id == conversation_id
        ).first()
        
        if conv:
            conv.title = new_title
            conv.updated_at = datetime.datetime.utcnow()
            self.session.commit()
            return True
        return False
    
    def log_usage(self, username, action_type, resource_id=None, details=None):
        """사용 통계 기록"""
        log = UsageStat(
            username=username,
            action_type=action_type,
            resource_id=resource_id,
            details=details or {}
        )
        
        self.session.add(log)
        self.session.commit()
        return log
    
    def close(self):
        """세션 종료"""
        self.session.close()

# 이 파일이 직접 실행될 때 데이터베이스 초기화
if __name__ == "__main__":
    # 환경 변수 로드 확인
    if not os.environ.get("ADMIN_PASS") or not os.environ.get("USER_PASS"):
        print("경고: 필수 환경 변수가 설정되지 않았습니다!")
        print("다음 환경 변수를 .env 파일에 설정하세요:")
        print("ADMIN_PASS, USER_PASS, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
        print("선택적으로 다음 환경 변수도 설정할 수 있습니다:")
        print("ADMIN_USERNAME, ADMIN_NAME, ADMIN_EMAIL, USER_USERNAME, USER_NAME, USER_EMAIL")
    
    # 데이터베이스 초기화
    try:
        print("데이터베이스 초기화 시작")
        engine, session = init_db()
        
        # 기본 관리자 및 사용자 생성
        db_manager = DBManager(engine, session)
        admin_created = db_manager.create_default_admin()
        user_created = db_manager.create_default_user()
        
        print("데이터베이스가 성공적으로 초기화되었습니다.")
        if admin_created:
            print(f"관리자 계정이 생성되었습니다: {os.environ.get('ADMIN_USERNAME')}")
        if user_created:
            print(f"사용자 계정이 생성되었습니다: {os.environ.get('USER_USERNAME')}")
    except Exception as e:
        print(f"데이터베이스 초기화 중 오류 발생: {str(e)}")
        print("데이터베이스 연결 설정을 확인하세요.")