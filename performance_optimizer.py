# performance_optimizer.py
import os
import streamlit as st
import time
import psutil
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Tuple, Callable
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_core.documents import Document

class PerformanceOptimizer:
    """성능 최적화 및 향상된 문서 검색 기능을 제공하는 유틸리티 클래스"""
    
    def __init__(self, cache_dir: str = "./.cache"):
        """초기화"""
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # 세션 상태 초기화
        if "performance_metrics" not in st.session_state:
            st.session_state.performance_metrics = {
                "memory_usage": [],
                "response_times": [],
                "query_times": []
            }
    
    @staticmethod
    def get_memory_usage() -> Tuple[float, float]:
        """현재 메모리 사용량 반환 (MB)"""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        return memory_info.rss / 1024 / 1024, psutil.virtual_memory().percent
    
    @staticmethod
    def log_metrics(operation: str, duration: float, memory_before: float, memory_after: float):
        """성능 지표 로깅"""
        print(f"Operation: {operation}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Memory Usage: {memory_before:.2f} MB -> {memory_after:.2f} MB (Delta: {memory_after - memory_before:.2f} MB)")
        print("-" * 50)
    
    @staticmethod
    def timeit(func: Callable) -> Callable:
        """함수 실행 시간 측정 데코레이터"""
        def wrapper(*args, **kwargs):
            start_time = time.time()
            memory_before, _ = PerformanceOptimizer.get_memory_usage()
            
            result = func(*args, **kwargs)
            
            end_time = time.time()
            duration = end_time - start_time
            memory_after, _ = PerformanceOptimizer.get_memory_usage()
            
            PerformanceOptimizer.log_metrics(
                func.__name__, duration, memory_before, memory_after
            )
            
            # 세션 상태에 메트릭 저장
            if "performance_metrics" in st.session_state:
                st.session_state.performance_metrics["memory_usage"].append(memory_after)
                if "query" in func.__name__.lower():
                    st.session_state.performance_metrics["query_times"].append(duration)
                else:
                    st.session_state.performance_metrics["response_times"].append(duration)
            
            return result
        return wrapper
    
    @staticmethod
    def memory_intensive_warning(threshold_mb: float = 1000) -> bool:
        """메모리 사용량이 임계값을 초과하는지 확인"""
        mem_usage, _ = PerformanceOptimizer.get_memory_usage()
        if mem_usage > threshold_mb:
            return True
        return False
    
    @staticmethod
    def clear_cache():
        """Streamlit 캐시 및 임시 데이터 정리"""
        # 특정 캐시된 함수 무효화
        for key in list(st.session_state.keys()):
            if key.startswith("_cache_") or key.endswith("_cache"):
                del st.session_state[key]
        
        # 대용량 데이터는 명시적으로 해제
        if "large_data" in st.session_state:
            del st.session_state["large_data"]
        
        # 파이썬 가비지 컬렉션 강제 실행
        import gc
        gc.collect()
    
    @staticmethod
    async def parallel_document_processing(documents: List[Document], 
                                          process_func: Callable, 
                                          batch_size: int = 10) -> List[Any]:
        """문서를 병렬로 처리"""
        results = []
        
        # 문서를 배치로 분할
        batches = [documents[i:i+batch_size] for i in range(0, len(documents), batch_size)]
        
        async def process_batch(batch):
            with ThreadPoolExecutor() as executor:
                loop = asyncio.get_event_loop()
                batch_results = await asyncio.gather(
                    *[loop.run_in_executor(executor, process_func, doc) for doc in batch]
                )
                return batch_results
        
        # 각 배치를 병렬로 처리
        for batch in batches:
            batch_results = await process_batch(batch)
            results.extend(batch_results)
        
        return results

    @staticmethod
    @st.cache_resource
    def load_vectorstore_cached(vectorstore_path: str, embeddings) -> FAISS:
        """벡터 저장소를 캐시하여 로드"""
        return FAISS.load_local(vectorstore_path, embeddings)
    
    @staticmethod
    def enhance_query(query: str, context: Optional[str] = None) -> str:
        """검색 쿼리를 개선하여 관련성 높은 결과를 검색"""
        """검색 쿼리를 개선하여 관련성 높은 결과를 검색"""
        if not context:
            return query
    
    @staticmethod
    def improved_vector_search(vectorstore, query: str, context: Optional[str] = None, 
                              filters: Optional[Dict[str, Any]] = None, 
                              top_k: int = 5) -> List[Document]:
        """개선된 벡터 검색 기능
        
        벡터 검색과 키워드 검색을 조합하여 더 정확한 결과 도출
        """
        # 쿼리 개선
        enhanced_query = PerformanceOptimizer.enhance_query(query, context)
        
        # 메타데이터 필터 적용
        search_kwargs = {"k": top_k * 2}  # 더 많은 결과 가져와서 후처리
        if filters:
            search_kwargs["filter"] = filters
        
        # 벡터 검색 실행
        try:
            results = vectorstore.similarity_search(enhanced_query, **search_kwargs)
        except Exception as e:
            st.error(f"벡터 검색 중 오류 발생: {str(e)}")
            return []
        
        # 결과 후처리 및 정렬
        if results:
            # 점수 기반 정렬
            scored_results = []
            for doc in results:
                # 기본 유사도 점수 (벡터 기반)
                score = 1.0
                
                # 메타데이터 기반 가중치 조정
                metadata = doc.metadata
                if metadata:
                    # 카테고리 일치 보너스
                    if filters and "category" in filters and metadata.get("category") == filters["category"]:
                        score *= 1.2
                    
                    # 최신 버전 보너스
                    if "version" in metadata:
                        score *= (1.0 + float(metadata["version"]) * 0.05)
                
                # 쿼리 단어 포함 횟수에 따른 가중치
                query_words = [w.lower() for w in query.split() if len(w) > 3]
                content_lower = doc.page_content.lower()
                
                matches = sum(1 for word in query_words if word in content_lower)
                score *= (1.0 + matches * 0.1)
                
                # 결과 기록
                scored_results.append((doc, score))
            
            # 점수 기준 내림차순 정렬 후 상위 k개 반환
            scored_results.sort(key=lambda x: x[1], reverse=True)
            return [doc for doc, _ in scored_results[:top_k]]
        
        return []
    
    @staticmethod
    def create_document_index(documents: List[Document]) -> Dict[str, Any]:
        """빠른 조회를 위한 문서 인덱스 생성"""
        document_index = {
            "by_id": {},
            "by_category": {},
            "by_filename": {},
            "by_content": {}
        }
        
        for doc in documents:
            metadata = doc.metadata
            doc_id = metadata.get("doc_id", "unknown")
            
            # ID별 인덱싱
            document_index["by_id"][doc_id] = doc
            
            # 카테고리별 인덱싱
            category = metadata.get("category", "기타")
            if category not in document_index["by_category"]:
                document_index["by_category"][category] = []
            document_index["by_category"][category].append(doc)
            
            # 파일명별 인덱싱
            filename = metadata.get("source_file", "unknown")
            if filename not in document_index["by_filename"]:
                document_index["by_filename"][filename] = []
            document_index["by_filename"][filename].append(doc)
            
            # 내용 기반 간단한 인덱싱 (중요 키워드)
            content = doc.page_content.lower()
            words = set(w for w in content.split() if len(w) > 4)
            for word in words:
                if word not in document_index["by_content"]:
                    document_index["by_content"][word] = []
                document_index["by_content"][word].append(doc_id)
        
        return document_index
    
    @staticmethod
    def monitor_and_optimize():
        """현재 성능 모니터링 및 최적화 권장사항 제공"""
        memory_usage, memory_percent = PerformanceOptimizer.get_memory_usage()
        
        st.subheader("현재 시스템 상태")
        
        # 메모리 사용량 표시
        col1, col2 = st.columns(2)
        with col1:
            st.metric("메모리 사용량", f"{memory_usage:.2f} MB")
        with col2:
            st.metric("메모리 사용률", f"{memory_percent:.1f}%")
        
        # 성능 지표
        if "performance_metrics" in st.session_state:
            metrics = st.session_state.performance_metrics
            
            if metrics["response_times"]:
                avg_response = sum(metrics["response_times"]) / len(metrics["response_times"])
                st.metric("평균 응답 시간", f"{avg_response:.2f}초")
            
            if metrics["query_times"]:
                avg_query = sum(metrics["query_times"]) / len(metrics["query_times"])
                st.metric("평균 쿼리 시간", f"{avg_query:.2f}초")
        
        # 성능 최적화 제안
        st.subheader("최적화 제안")
        
        if memory_percent > 70:
            st.warning("메모리 사용량이 높습니다. 다음을 시도해보세요:")
            st.markdown("""
            - 캐시 정리하기
            - 문서 청크 크기 줄이기
            - 비활성 벡터스토어 언로드하기
            """)
        
        if memory_usage > 1000:  # 1GB 이상
            st.warning("메모리 사용량이 1GB를 초과했습니다.")
            
            if st.button("캐시 정리"):
                PerformanceOptimizer.clear_cache()
                st.success("캐시를 정리했습니다!")
                st.rerun()
        
        # Docker 설정 최적화
        st.subheader("Docker 설정 최적화")
        st.code("""
        # 메모리 제한 증가
        docker run -d \\
          --name llm-rag-app \\
          --memory=8g \\
          --memory-swap=10g \\
          --cpus=4 \\
          -p 8501:8501 \\
          llm-rag-app:latest
        """)
        
        # PostgreSQL 최적화
        st.subheader("PostgreSQL 최적화")
        st.markdown("""
        1. **공유 버퍼 증가**:
        ```
        shared_buffers = 2GB  # 서버 메모리의 25% 권장
        ```
        
        2. **작업 메모리 증가**:
        ```
        work_mem = 64MB  # 복잡한 쿼리에 도움
        ```
        
        3. **Vacuum 설정 최적화**:
        ```
        autovacuum = on
        ```
        """)
        
        # 일반 성능 팁
        st.subheader("일반 성능 팁")
        st.markdown("""
        1. **벡터 저장소 분할**: 카테고리별로 별도 벡터 저장소 사용
        2. **비동기 처리**: 대량 문서 처리 시 비동기 처리 활용
        3. **캐싱 활용**: `@st.cache_data`와 `@st.cache_resource` 활용
        4. **프리페칭**: 자주 사용하는 데이터 미리 로드
        """)
        
    class DocumentSearchOptimizer:
        """문서 검색 최적화 클래스"""
        
        def __init__(self, vectorstore):
            self.vectorstore = vectorstore
            self.recent_queries = []
            self.query_cache = {}
            
        def search(self, query, filters=None, k=5):
            """최적화된 문서 검색"""
            # 쿼리 캐싱 - 동일한 쿼리에 대해 결과 재사용
            cache_key = f"{query}_{str(filters)}_{k}"
            if cache_key in self.query_cache:
                return self.query_cache[cache_key]
            
            # 최근 쿼리 업데이트
            self.recent_queries.append(query)
            if len(self.recent_queries) > 5:
                self.recent_queries.pop(0)
            
            # 쿼리 컨텍스트 구성
            context = " ".join(self.recent_queries)
            
            # 개선된 벡터 검색 사용
            results = PerformanceOptimizer.improved_vector_search(
                self.vectorstore, query, context, filters, k
            )
            
            # 결과 캐싱
            self.query_cache[cache_key] = results
            
            # 캐시 크기 제한
            if len(self.query_cache) > 100:
                # 가장 오래된 항목 제거
                oldest_key = next(iter(self.query_cache))
                del self.query_cache[oldest_key]
            
            return results
        
        # 이전 대화 맥락을 바탕으로 쿼리 확장
        enhanced_query = f"{query} {context}"
        
        # 특별한 검색 연산자 처리 (필터링)
        if "category:" in query or "filename:" in query or "type:" in query:
            return query  # 사용자가 이미 필터링 쿼리를 사용하고 있으므로 그대로 유지
        
        # 정규화 및 키워드 추출
        import re
        from collections import Counter
        import string
        
        # 불용어 및 일반적인 단어 제거
        stop_words = {"the", "a", "an", "in", "on", "at", "is", "are", "and", "or", "for", "to", "of", "with"}
        
        # 문장 토큰화 및 정규화
        words = re.findall(r'\b\w+\b', query.lower())
        filtered_words = [w for w in words if w not in stop_words and len(w) > 2]
        
        # 컨텍스트에서 중요 키워드 추출
        if context:
            context_words = re.findall(r'\b\w+\b', context.lower())
            context_words = [w for w in context_words if w not in stop_words and len(w) > 2]
            
            # 단어 빈도수로 중요도 계산
            word_counts = Counter(context_words)
            important_words = [word for word, count in word_counts.most_common(3) if count > 1]
            
            # 원래 쿼리와 중요 키워드 결합
            if important_words:
                enhanced_query = f"{query} {' '.join(important_words)}"
                return enhanced_query
        
        return query