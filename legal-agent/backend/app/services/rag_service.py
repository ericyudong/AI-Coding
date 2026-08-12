"""RAG-based contract Q&A."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cms_models import ContractChunk, ManagedContract
from app.services import index_service, retrieval_service
from app.services.cms_service import _keyword_qa_fallback, answer_from_contract_knowledge
from app.services.llm_service import rag_answer


def _format_chunks(chunks: list[ContractChunk]) -> str:
    parts = []
    for ch in chunks:
        title = ch.section_title or f"片段{ch.chunk_index + 1}"
        parts.append(f"【{title}】\n{ch.content}")
    return "\n\n".join(parts)


async def answer_contract_question(
    db: AsyncSession,
    contract: ManagedContract,
    question: str,
) -> dict:
    await index_service.ensure_indexed(db, contract)
    await db.refresh(contract)

    chunks = await retrieval_service.retrieve_chunks_for_contract(db, contract, question)
    if chunks:
        context = _format_chunks(chunks)
        llm_result = await rag_answer(contract.name, context, question)
        if llm_result:
            citations = [ch.section_title or f"片段{ch.chunk_index + 1}" for ch in chunks[:3]]
            details = [
                {
                    "section": ch.section_title or f"片段{ch.chunk_index + 1}",
                    "excerpt": ch.content[:200],
                    "chunk_id": ch.id,
                }
                for ch in chunks[:3]
            ]
            return {
                "answer": llm_result,
                "citations": citations,
                "citation_details": details,
                "confidence": "high",
            }

        rule_answer = answer_from_contract_knowledge(contract, question, chunks)
        if rule_answer:
            return rule_answer

    rule_answer = answer_from_contract_knowledge(contract, question)
    if rule_answer:
        return rule_answer

    return _keyword_qa_fallback(contract, question)
