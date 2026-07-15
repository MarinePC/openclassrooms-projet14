# routes/chat.py — routes de gestion des conversations
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter
from models import Chat, User
from database import get_session
from dependencies import get_current_user
from utils.news import build_system_prompt

router = APIRouter(prefix="/api/chats", tags=["chats"])


def serialize_messages(messages: list) -> list:
    """Convertit les objets datetime en strings pour la sérialisation JSON."""
    def default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} non sérialisable")
    return json.loads(json.dumps(messages, default=default))


def get_agent(system_prompt: str) -> Agent:
    """Crée un agent PydanticAI avec le system prompt fourni."""
    return Agent(
        "mistral:mistral-small-latest",
        system_prompt=system_prompt,
    )


class MessageRequest(BaseModel):
    """Schéma d'un message envoyé par l'utilisateur."""
    content: str


@router.post("", status_code=201)
async def create_chat(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Crée une nouvelle conversation pour l'utilisateur authentifié.
    Génère le system prompt avec les actualités du jour et le sauvegarde en DB.
    """
    # Génère le system prompt avec les actualités du jour
    prompt = await build_system_prompt()

    chat = Chat(
        user_id=current_user.id,
        messages=[],
        system_prompt=prompt,
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return {"id": chat.id}


@router.get("")
async def list_chats(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Retourne la liste des conversations de l'utilisateur authentifié."""
    chats = session.exec(
        select(Chat).where(Chat.user_id == current_user.id)
    ).all()
    return [{"id": chat.id, "message_count": len(chat.messages)} for chat in chats]


@router.get("/{chat_id}")
async def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Retourne l'historique complet d'une conversation."""
    chat = session.get(Chat, chat_id)

    if not chat:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    return {"id": chat.id, "messages": chat.messages}


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: int,
    request: MessageRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Ajoute un message utilisateur, obtient la réponse du LLM,
    sauvegarde l'historique et retourne la réponse.
    Utilise le system prompt sauvegardé lors de la création du chat.
    """
    chat = session.get(Chat, chat_id)

    if not chat:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    # Utilise le system prompt sauvegardé (avec les actualités du jour de création)
    agent = get_agent(chat.system_prompt)

    # Envoi du message à l'agent avec l'historique existant
    result = await agent.run(
        request.content,
        message_history=chat.messages,
    )

    # Sérialisation et sauvegarde de l'historique
    chat.messages = serialize_messages(
        ModelMessagesTypeAdapter.dump_python(result.all_messages())
    )
    session.add(chat)
    session.commit()

    return {"response": result.output}