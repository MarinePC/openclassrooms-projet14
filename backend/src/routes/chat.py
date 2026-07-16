# routes/chat.py — routes de gestion des conversations
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessagesTypeAdapter
from models import Chat, User
from database import get_session
from dependencies import get_current_user
from utils.news import build_system_prompt, search_news

router = APIRouter(prefix="/api/chats", tags=["chats"])


def serialize_messages(messages: list) -> list:
    """Convertit les objets datetime en strings pour la sérialisation JSON."""
    def default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} non sérialisable")
    return json.loads(json.dumps(messages, default=default))


def get_agent(system_prompt: str) -> Agent:
    """Crée un agent PydanticAI avec le system prompt et les tools fournis."""
    agent = Agent(
        "mistral:mistral-small-latest",
        system_prompt=system_prompt,
    )

    @agent.tool_plain
    async def search_news_tool(query: str) -> str:
        """
        Recherche des articles de presse récents sur un sujet précis.
        Utilise cet outil quand l'utilisateur demande plus d'informations
        sur un sujet spécifique ou veut approfondir un thème d'actualité.

        Args:
            query: Le sujet ou les mots-clés à rechercher (ex: "intelligence artificielle", "élections France")

        Returns:
            Une liste d'articles récents avec leur titre, résumé et date de publication.
        """
        articles = await search_news(query)
        if not articles:
            return f"Aucun article trouvé pour la recherche : '{query}'"

        result = f"Articles trouvés pour '{query}' :\n\n"
        for i, article in enumerate(articles, 1):
            result += f"{i}. **{article['title']}**\n"
            if article.get("publish_date"):
                result += f"   Date : {article['publish_date']}\n"
            if article.get("summary"):
                result += f"   Résumé : {article['summary']}\n"
            result += "\n"

        return result

    return agent


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
    Ajoute un message utilisateur, obtient la réponse de l'agent,
    sauvegarde l'historique et retourne la réponse.
    L'agent peut appeler search_news_tool pour approfondir un sujet.
    """
    chat = session.get(Chat, chat_id)

    if not chat:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    agent = get_agent(chat.system_prompt)

    result = await agent.run(
        request.content,
        message_history=chat.messages,
    )

    chat.messages = serialize_messages(
        ModelMessagesTypeAdapter.dump_python(result.all_messages())
    )
    session.add(chat)
    session.commit()

    return {"response": result.output}