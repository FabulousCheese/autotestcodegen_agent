"""RAG (Retrieval-Augmented Generation) 模块"""
from typing import List, Optional, Dict, Any
from pydantic import Field
import os
from loguru import logger

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置模型下载目录到项目文件夹
os.environ.setdefault("HF_HOME", os.path.join(PROJECT_ROOT, "models", "hf_cache"))
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", os.path.join(PROJECT_ROOT, "models", "sentence_transformers"))

# 尝试导入 ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB 未安装，RAG 功能将受限")


class RAGMemory:
    """
    RAG 记忆模块
    
    支持:
    - 向量存储和检索
    - 文档索引
    - 相似度搜索
    """
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "test_cases",
    ):
        if persist_directory is None:
            persist_directory = os.path.join(PROJECT_ROOT, "data", "chroma_db")
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        
        if CHROMADB_AVAILABLE:
            self._init_chroma()
    
    def _init_chroma(self):
        """初始化 ChromaDB"""
        try:
            os.makedirs(self.persist_directory, exist_ok=True)
            
            self.client = chromadb.Client(Settings(
                persist_directory=self.persist_directory,
                anonymized_telemetry=False,
            ))
            
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "测试用例知识库"},
            )
            
            logger.info(f"ChromaDB 初始化完成: {self.persist_directory}")
            
        except Exception as e:
            logger.error(f"ChromaDB 初始化失败: {e}")
            self.client = None
            self.collection = None
    
    def add_document(
        self,
        content: str,
        metadata: Dict[str, Any],
        document_id: Optional[str] = None,
    ) -> bool:
        """
        添加文档到知识库
        
        Args:
            content: 文档内容
            metadata: 文档元数据
            document_id: 文档 ID
        """
        if not self.collection:
            logger.warning("ChromaDB 未初始化，文档添加失败")
            return False
        
        try:
            import hashlib
            from datetime import datetime
            
            if document_id is None:
                document_id = hashlib.md5(
                    f"{content}{datetime.now()}".encode()
                ).hexdigest()
            
            self.collection.add(
                documents=[content],
                metadatas=[metadata],
                ids=[document_id],
            )
            
            logger.info(f"文档添加成功: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"文档添加失败: {e}")
            return False
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        搜索相似文档
        
        Args:
            query: 查询文本
            n_results: 返回数量
            where: 过滤条件
        """
        if not self.collection:
            return []
        
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
            )
            
            documents = []
            if results.get('documents') and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    documents.append({
                        "content": doc,
                        "metadata": results['metadatas'][0][i] if results.get('metadatas') else {},
                        "distance": results['distances'][0][i] if results.get('distances') else 0,
                    })
            
            return documents
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
    
    def get_by_metadata(
        self,
        metadata_filter: Dict[str, Any],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """根据元数据获取文档"""
        if not self.collection:
            return []
        
        try:
            results = self.collection.get(
                where=metadata_filter,
                limit=limit,
            )
            
            documents = []
            if results.get('documents'):
                for i, doc in enumerate(results['documents']):
                    documents.append({
                        "content": doc,
                        "metadata": results['metadatas'][i] if results.get('metadatas') else {},
                        "id": results['ids'][i] if results.get('ids') else None,
                    })
            
            return documents
            
        except Exception as e:
            logger.error(f"元数据查询失败: {e}")
            return []
    
    def delete(self, document_id: str) -> bool:
        """删除文档"""
        if not self.collection:
            return False
        
        try:
            self.collection.delete(ids=[document_id])
            return True
        except Exception as e:
            logger.error(f"文档删除失败: {e}")
            return False
    
    def count(self) -> int:
        """获取文档数量"""
        if not self.collection:
            return 0
        
        try:
            return self.collection.count()
        except Exception:
            return 0


class SimpleMemory:
    """
    简单内存实现 (不使用向量数据库)
    
    用于轻量级场景或作为后备
    """
    
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
    
    def add_document(self, content: str, metadata: Dict[str, Any]) -> bool:
        """添加文档"""
        self.documents.append({
            "content": content,
            "metadata": metadata,
        })
        return True
    
    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """简单关键词匹配搜索"""
        query_words = set(query.lower().split())
        
        scored = []
        for doc in self.documents:
            content_words = set(doc['content'].lower().split())
            # 计算交集
            common = query_words & content_words
            if common:
                score = len(common) / max(len(query_words), 1)
                scored.append((score, doc))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:n_results]]
    
    def get_by_metadata(self, metadata_filter: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
        """根据元数据获取"""
        results = []
        for doc in self.documents:
            match = all(
                doc['metadata'].get(k) == v
                for k, v in metadata_filter.items()
            )
            if match:
                results.append(doc)
        
        return results[:limit]
    
    def count(self) -> int:
        return len(self.documents)
