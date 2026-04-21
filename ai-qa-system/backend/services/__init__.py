"""Services module."""

# Lazy imports to avoid circular dependencies and missing packages
def get_llm_service():
    from backend.services.llm_service import llm_service, LLMService
    return llm_service

def get_session_manager():
    from backend.services.session_service import session_manager
    return session_manager

def get_rag_service():
    from backend.services.rag_service import rag_service
    return rag_service

__all__ = [
    "get_llm_service",
    "get_session_manager", 
    "get_rag_service"
]
