# routes/review.py — génération et affichage des revues de presse
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter
from models import Chat, Review, User
from database import get_session
from dependencies import get_current_user
from utils.rag import build_index, retrieve_relevant_passages

router = APIRouter(prefix="/api/chats", tags=["reviews"])

# --- Schémas Pydantic pour l'output structuré du LLM ---

class ArticleSummary(BaseModel):
    """Résumé d'un article mentionné dans la revue de presse."""
    title: str
    key_points: str
    relevance: str

class ReviewOutput(BaseModel):
    """Format de sortie structuré de l'agent de revue de presse."""
    title: str
    summary: str
    articles: list[ArticleSummary]

# --- Agent spécialisé revue de presse ---

review_agent = Agent(
    "mistral:mistral-small-latest",
    output_type=ReviewOutput,
    system_prompt=(
        "Tu es un expert en rédaction de revues de presse professionnelles. "
        "À partir d'un historique de discussion, d'extraits d'articles et d'un sujet donné, "
        "tu génères une revue de presse structurée et synthétique. "
        "Tu te bases uniquement sur les informations fournies dans le contexte. "
        "Tes revues de presse sont adaptées à des journalistes et pigistes professionnels."
    ),
)

# --- Schéma de requête ---

class ReviewRequest(BaseModel):
    topic: str

# --- Routes ---

@router.post("/{chat_id}/review", status_code=201)
async def generate_review(
    chat_id: int,
    request: ReviewRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Génère une revue de presse enrichie par RAG à partir de l'historique
    et des articles chargés durant la conversation.
    """
    chat = session.get(Chat, chat_id)

    if not chat:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    if not chat.messages:
        raise HTTPException(
            status_code=400,
            detail="La conversation est vide."
        )

    # RAG : indexe les articles chargés et retrouve les passages pertinents
    rag_context = ""
    if chat.loaded_articles:
        print(f"[rag] Indexation de {len(chat.loaded_articles)} articles...")
        index = build_index(chat.loaded_articles)
        if index:
            rag_context = retrieve_relevant_passages(index, request.topic)
            print(f"[rag] {len(rag_context)} caractères de contexte retrouvés")

    # Prépare le prompt avec le contexte RAG
    user_prompt = f"Génère une revue de presse professionnelle sur le sujet : '{request.topic}'."
    if rag_context:
        user_prompt += (
            f"\n\nVoici des extraits d'articles pertinents issus de notre discussion :\n\n"
            f"{rag_context}\n\n"
            f"Utilise ces extraits pour enrichir ta revue de presse."
        )

    # Convertit l'historique JSON en messages PydanticAI
    history = ModelMessagesTypeAdapter.validate_python(chat.messages)

    result = await review_agent.run(
        user_prompt,
        message_history=history,
    )

    output: ReviewOutput = result.output

    review = Review(
        chat_id=chat_id,
        user_id=current_user.id,
        topic=request.topic,
        title=output.title,
        summary=output.summary,
        articles=[a.model_dump() for a in output.articles],
    )
    session.add(review)
    session.commit()
    session.refresh(review)

    return {
        "id": review.id,
        "topic": review.topic,
        "title": review.title,
        "summary": review.summary,
        "articles": review.articles,
    }


@router.get("/reviews/all", response_model=list)
async def list_reviews(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Retourne toutes les revues de presse de l'utilisateur authentifié."""
    reviews = session.exec(
        select(Review).where(Review.user_id == current_user.id)
    ).all()

    return [
        {
            "id": r.id,
            "chat_id": r.chat_id,
            "topic": r.topic,
            "title": r.title,
            "summary": r.summary,
            "articles": r.articles,
        }
        for r in reviews
    ]


@router.get("/{chat_id}/review/{review_id}")
async def get_review(
    chat_id: int,
    review_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Retourne une revue de presse spécifique."""
    review = session.get(Review, review_id)

    if not review:
        raise HTTPException(status_code=404, detail="Revue de presse introuvable")

    if review.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    return {
        "id": review.id,
        "chat_id": review.chat_id,
        "topic": review.topic,
        "title": review.title,
        "summary": review.summary,
        "articles": review.articles,
    }