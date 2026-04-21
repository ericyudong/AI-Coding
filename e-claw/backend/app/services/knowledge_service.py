"""
E-Claw 知识库服务
文档处理、向量化、RAG检索
"""
import os
import uuid
import asyncio
import hashlib
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import settings
from app.models import Document, KnowledgeBase


class KnowledgeService:
    """知识库服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def process_document_async(self, document_id: str):
        """异步处理文档（向量化）"""
        # 在后台任务中处理
        asyncio.create_task(self._process_document(document_id))
    
    async def _process_document(self, document_id: str):
        """处理文档（读取、向量化、存储）"""
        try:
            # 获取文档
            result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                return
            
            # 更新状态为处理中
            document.status = "processing"
            await self.db.commit()
            
            # 读取文件内容（简化实现）
            content = await self._read_document_content(document)
            
            # 分块
            chunks = self._chunk_text(content, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP)
            
            # 向量化（简化实现 - 实际应该调用embedding模型）
            embeddings = await self._generate_embeddings(chunks)
            
            # 保存向量（简化实现 - 实际应该存储到向量数据库）
            vector_ids = await self._store_vectors(document_id, embeddings)
            
            # 更新文档状态
            document.vector_ids = vector_ids
            document.chunk_count = len(chunks)
            document.status = "indexed"
            document.updated_at = datetime.utcnow()
            
            # 更新知识库统计
            await self._update_knowledge_base_stats(document.knowledge_base_id)
            
            await self.db.commit()
            
        except Exception as e:
            # 更新文档状态为失败
            result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            if document:
                document.status = "failed"
                await self.db.commit()
            print(f"Error processing document: {e}")
    
    async def _read_document_content(self, document: Document) -> str:
        """读取文档内容"""
        if not document.file_path or not os.path.exists(document.file_path):
            # 如果文件不存在，返回占位内容
            return f"Sample content for {document.filename}"
        
        try:
            with open(document.file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            # 如果无法读取，返回占位内容
            return f"Sample content for {document.filename}"
    
    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """将文本分块"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap
        
        return chunks
    
    async def _generate_embeddings(self, chunks: List[str]) -> List[List[float]]:
        """生成文本嵌入（简化实现）"""
        # 简化实现 - 实际应该调用embedding模型
        # 这里使用文本的hash作为占位符
        embeddings = []
        for chunk in chunks:
            # 生成一个固定大小的伪嵌入向量
            hash_val = hashlib.md5(chunk.encode()).digest()
            embedding = [float(b) / 255.0 for b in hash_val]
            # 扩展到所需维度
            while len(embedding) < 384:
                embedding.append(0.0)
            embeddings.append(embedding[:384])
        
        return embeddings
    
    async def _store_vectors(self, document_id: str, embeddings: List[List[float]]) -> List[str]:
        """存储向量（简化实现）"""
        # 简化实现 - 实际应该存储到向量数据库（如Milvus、Qdrant等）
        vector_ids = []
        for i, embedding in enumerate(embeddings):
            vector_id = f"{document_id}_{i}"
            vector_ids.append(vector_id)
        
        return vector_ids
    
    async def _update_knowledge_base_stats(self, knowledge_base_id: str):
        """更新知识库统计"""
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
        )
        kb = result.scalar_one_or_none()
        
        if not kb:
            return
        
        # 统计文档数和大小
        docs_result = await self.db.execute(
            select(Document).where(
                and_(
                    Document.knowledge_base_id == knowledge_base_id,
                    Document.status != "deleted"
                )
            )
        )
        documents = docs_result.scalars().all()
        
        kb.doc_count = len(documents)
        kb.total_size = sum(d.file_size or 0 for d in documents)
        kb.updated_at = datetime.utcnow()
    
    async def search(
        self,
        query: str,
        kb_ids: List[str],
        top_k: int = 5
    ) -> List[Dict]:
        """搜索知识库"""
        # 生成查询向量
        query_embedding = await self._generate_embeddings([query])
        
        # 从向量数据库搜索（简化实现）
        results = []
        
        # 获取相关文档
        for kb_id in kb_ids:
            docs_result = await self.db.execute(
                select(Document).where(
                    and_(
                        Document.knowledge_base_id == kb_id,
                        Document.status == "indexed"
                    )
                )
            )
            documents = docs_result.scalars().all()
            
            for doc in documents:
                # 简化实现 - 返回文档内容片段
                content = await self._read_document_content(doc)
                if content:
                    # 返回内容片段
                    snippet = content[:500] if len(content) > 500 else content
                    results.append({
                        "document_id": str(doc.id),
                        "filename": doc.filename,
                        "content": snippet,
                        "score": 0.9  # 简化实现
                    })
        
        # 排序并返回top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    async def delete_document_vectors(self, document_id: str):
        """删除文档向量"""
        # 从向量数据库删除（简化实现）
        pass
    
    async def rebuild_knowledge_base_index(self, knowledge_base_id: str):
        """重建知识库索引"""
        # 获取所有文档
        docs_result = await self.db.execute(
            select(Document).where(
                and_(
                    Document.knowledge_base_id == knowledge_base_id,
                    Document.status != "deleted"
                )
            )
        )
        documents = docs_result.scalars().all()
        
        # 重新处理每个文档
        for doc in documents:
            await self._process_document(str(doc.id))


class RAGService:
    """RAG检索增强生成服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.knowledge_service = KnowledgeService(db)
    
    async def retrieve_context(
        self,
        query: str,
        knowledge_base_ids: List[str],
        top_k: int = 5
    ) -> List[Dict]:
        """检索相关上下文"""
        return await self.knowledge_service.search(
            query=query,
            kb_ids=knowledge_base_ids,
            top_k=top_k
        )
    
    async def generate_answer(
        self,
        query: str,
        context: List[Dict],
        model: str = None
    ) -> str:
        """生成答案（需要LLM服务）"""
        # 构建提示词
        context_text = "\n\n".join([
            f"Document: {c['filename']}\n{c['content']}"
            for c in context
        ])
        
        prompt = f"""Based on the following context, answer the question.

Context:
{context_text}

Question: {query}

Answer:"""
        
        # 实际应该调用LLM服务
        # 这里返回简化答案
        if context:
            return f"Based on the retrieved context, the answer to '{query}' can be found in the documents. (RAG generation would happen here with LLM)"
        else:
            return "No relevant context found."