# routes/review.py — génération et affichage des revues de presse
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter
from models import Chat, Review, User
from database import get_session
from dependencies import get_current_user
import json

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
        "À partir d'un historique de discussion et d'un sujet donné, tu génères "
        "une revue de presse structurée et synthétique. "
        "Tu identifies les articles et informations clés mentionnés dans la discussion, "
        "tu les analyses et tu produis une synthèse claire et professionnelle. "
        "Tes revues de presse sont adaptées à des journalistes et pigistes professionnels."
    ),
)

# --- Schéma de requête ---

class ReviewRequest(BaseModel):
    """Schéma de requête pour générer une revue de presse."""
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
    Génère une revue de presse structurée à partir de l'historique
    d'une conversation et d'un sujet choisi par l'utilisateur.
    """
    chat = session.get(Chat, chat_id)

    if not chat:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    if not chat.messages:
        raise HTTPException(
            status_code=400,
            detail="La conversation est vide. Discutez d'abord d'un sujet avant de générer une revue de presse."
        )

    # Convertit l'historique JSON en messages PydanticAI
    history = ModelMessagesTypeAdapter.validate_python(chat.messages)

    # Génère la revue de presse avec l'agent spécialisé
    result = await review_agent.run(
        f"Génère une revue de presse professionnelle sur le sujet : '{request.topic}'. "
        f"Utilise les informations et articles mentionnés dans notre discussion.",
        message_history=history,
    )

    output: ReviewOutput = result.output

    # Sauvegarde en base de données
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