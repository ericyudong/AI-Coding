"""
LangChain-based RAG (Retrieval-Augmented Generation) System
"""
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from loguru import logger

from backend.config import settings


class LangChainRAGConfig(BaseModel):
    """Configuration for LangChain RAG."""
    chunk_size: int = Field(default=1000, description="Chunk size for text splitting")
    chunk_overlap: int = Field(default=200, description="Chunk overlap")
    embedding_model: str = Field(default="text-embedding-ada-002", description="Embedding model")
    vector_store_type: str = Field(default="faiss", description="Vector store type")
    top_k: int = Field(default=5, description="Number of documents to retrieve")


class DocumentChunk(BaseModel):
    """Represents a chunk of a document."""
    id: str
    content: str
    metadata: Dict[str, Any] = {}


class RAGResponse(BaseModel):
    """Response from RAG query."""
    answer: str
    source_documents: List[Dict[str, Any]]
    context: str


class LangChainRAG:
    """
    LangChain-based RAG system for retrieval-augmented generation.
    Supports multiple vector stores and document loaders.
    """
    
    def __init__(self, config: Optional[LangChainRAGConfig] = None):
        self.config = config or LangChainRAGConfig()
        self.vector_store = None
        self.llm = None
        self.chain = None
        self._initialized = False
    
    def _get_embedding_model(self):
        """Get the embedding model for LangChain."""
        try:
            from langchain_openai import OpenAIEmbeddings
            
            # Check if using Qwen or other custom embedding model
            embedding_model = settings.embedding_model or self.config.embedding_model
            embedding_base_url = settings.embedding_base_url
            embedding_api_key = settings.embedding_api_key or settings.openai_api_key or os.environ.get("OPENAI_API_KEY") or ""
            
            # If Qwen or custom model, use custom base_url
            if "qwen" in embedding_model.lower() or "embedding" in embedding_model.lower() or embedding_base_url:
                logger.info(f"Using custom embedding model: {embedding_model} with base_url: {embedding_base_url}")
                return OpenAIEmbeddings(
                    model=embedding_model,
                    openai_api_key=embedding_api_key,
                    base_url=embedding_base_url
                )
            else:
                return OpenAIEmbeddings(
                    model=embedding_model,
                    openai_api_key=embedding_api_key
                )
        except ImportError:
            logger.error("langchain-openai not installed")
            raise
    
    def _get_llm(self):
        """Get the LLM for LangChain."""
        try:
            from langchain_openai import ChatOpenAI
            model_name = settings.openai_model
            
            # Map to LangChain model names
            if model_name == "gpt-4":
                model_name = "gpt-4"
            elif model_name == "gpt-3.5-turbo":
                model_name = "gpt-3.5-turbo"
            
            return ChatOpenAI(
                model=model_name,
                temperature=0.7,
                openai_api_key=settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
            )
        except ImportError:
            logger.error("langchain-openai not installed")
            raise
    
    def _get_text_splitter(self):
        """Get the text splitter for LangChain."""
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            return RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                length_function=len,
            )
        except ImportError:
            logger.error("langchain not installed")
            raise
    
    def _get_pdf_loader(self, file_path: str):
        """Get PDF loader for LangChain."""
        try:
            from langchain_community.document_loaders import PyPDFLoader
            return PyPDFLoader(file_path)
        except ImportError:
            logger.error("langchain-community not installed")
            raise
    
    def _get_docx_loader(self, file_path: str):
        """Get DOCX loader for LangChain."""
        try:
            from langchain_community.document_loaders import Docx2txtLoader
            return Docx2txtLoader(file_path)
        except ImportError:
            logger.error("langchain-community not installed")
            raise
    
    def _get_txt_loader(self, file_path: str):
        """Get text loader for LangChain."""
        try:
            from langchain_community.document_loaders import TextLoader
            return TextLoader(file_path, encoding="utf-8")
        except ImportError:
            logger.error("langchain-community not installed")
            raise
    
    def _get_csv_loader(self, file_path: str):
        """Get CSV loader for LangChain."""
        try:
            from langchain_community.document_loaders import CSVLoader
            return CSVLoader(file_path, encoding="utf-8")
        except ImportError:
            logger.error("langchain-community not installed")
            raise
    
    def initialize(self):
        """Initialize the RAG system."""
        if self._initialized:
            return
        
        try:
            from langchain_community.vectorstores import FAISS
            from langchain.schema import Document
            
            # Create empty vector store
            embedding_model = self._get_embedding_model()
            self.vector_store = FAISS.from_texts(
                texts=[""],  # Start with empty index
                embedding=embedding_model
            )
            # Remove the placeholder
            del self.vector_store.index_to_docstore_id[0]
            
            self._initialized = True
            logger.info("LangChain RAG system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RAG: {e}")
            raise
    
    def load_document(self, file_path: str) -> int:
        """Load a document into the RAG system."""
        self.initialize()
        
        file_ext = os.path.splitext(file_path)[1].lower()
        loader = None
        
        if file_ext == ".pdf":
            loader = self._get_pdf_loader(file_path)
        elif file_ext == ".docx":
            loader = self._get_docx_loader(file_path)
        elif file_ext == ".txt":
            loader = self._get_txt_loader(file_path)
        elif file_ext == ".csv":
            loader = self._get_csv_loader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        # Load document
        documents = loader.load()
        
        # Split text
        text_splitter = self._get_text_splitter()
        splits = text_splitter.split_documents(documents)
        
        # Add to vector store
        embedding_model = self._get_embedding_model()
        
        if self.vector_store is None:
            from langchain_community.vectorstores import FAISS
            self.vector_store = FAISS.from_documents(splits, embedding_model)
        else:
            self.vector_store.add_documents(splits)
        
        logger.info(f"Loaded {len(splits)} chunks from {os.path.basename(file_path)}")
        return len(splits)
    
    def add_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """Add text directly to the RAG system."""
        self.initialize()
        
        text_splitter = self._get_text_splitter()
        splits = text_splitter.split_text(text)
        
        # Convert to documents
        from langchain.schema import Document
        docs = [
            Document(page_content=split, metadata=metadata or {})
            for split in splits
        ]
        
        # Add to vector store
        embedding_model = self._get_embedding_model()
        
        if self.vector_store is None:
            from langchain_community.vectorstores import FAISS
            self.vector_store = FAISS.from_documents(docs, embedding_model)
        else:
            self.vector_store.add_documents(docs)
        
        logger.info(f"Added {len(docs)} text chunks")
        return len(docs)
    
    async def query(self, question: str, use_rag: bool = True) -> RAGResponse:
        """Query the RAG system."""
        if not use_rag or self.vector_store is None:
            # Return without RAG context
            return RAGResponse(
                answer="",
                source_documents=[],
                context=""
            )
        
        try:
            from langchain.chains import RetrievalQA
            from langchain.prompts import PromptTemplate
            
            # Get retriever
            retriever = self.vector_store.as_retriever(
                search_kwargs={"k": self.config.top_k}
            )
            
            # Get documents for context
            docs = retriever.get_relevant_documents(question)
            
            # Build context
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Create prompt
            prompt_template = """Use the following context to answer the question. 
If you don't know the answer based on the context, say so.

Context:
{context}

Question: {question}

Answer:"""

            # Get LLM
            llm = self._get_llm()
            
            # Create chain
            prompt = PromptTemplate(
                template=prompt_template,
                input_variables=["context", "question"]
            )
            
            # Use LCEL for chain
            from langchain.schema import StrOutputParser
            chain = (
                {"context": lambda x: context, "question": lambda x: question}
                | prompt
                | llm
                | StrOutputParser()
            )
            
            # Get answer
            answer = chain.invoke({})
            
            # Format source documents
            source_docs = [
                {
                    "content": doc.page_content[:200] + "...",
                    "metadata": doc.metadata
                }
                for doc in docs
            ]
            
            return RAGResponse(
                answer=answer,
                source_documents=source_docs,
                context=context
            )
        
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise
    
    def similarity_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Perform similarity search."""
        if self.vector_store is None:
            return []
        
        docs = self.vector_store.similarity_search(query, k=k)
        
        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata
            }
            for doc in docs
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG statistics."""
        return {
            "initialized": self._initialized,
            "chunk_size": self.config.chunk_size,
            "chunk_overlap": self.config.chunk_overlap,
            "embedding_model": self.config.embedding_model,
            "top_k": self.config.top_k,
            "vector_store_type": self.config.vector_store_type
        }
    
    def clear(self):
        """Clear all documents."""
        self.vector_store = None
        self._initialized = False
        logger.info("Cleared all RAG documents")
    
    def save_index(self, path: str):
        """Save the vector store index to disk."""
        if self.vector_store is not None:
            self.vector_store.save_local(path)
            logger.info(f"Saved vector store to {path}")
    
    def load_index(self, path: str):
        """Load the vector store index from disk."""
        if os.path.exists(path):
            embedding_model = self._get_embedding_model()
            from langchain_community.vectorstores import FAISS
            self.vector_store = FAISS.load_local(path, embedding_model)
            self._initialized = True
            logger.info(f"Loaded vector store from {path}")


# Global instance - use settings from config
langchain_rag = LangChainRAG(
    config=LangChainRAGConfig(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        embedding_model=settings.embedding_model,
        vector_store_type=settings.vector_store_type,
        top_k=settings.rag_top_k
    )
)
