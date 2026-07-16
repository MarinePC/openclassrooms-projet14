from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: bytes = Field()


class Chat(SQLModel, table=True):
    """Représente une conversation entre un utilisateur et le LLM."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    messages: list = Field(default=[], sa_column=Column(JSON))
    system_prompt: Optional[str] = Field(default=None)


class Review(SQLModel, table=True):
    """Revue de presse générée à partir d'une conversation."""
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_id: int = Field(foreign_key="chat.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # Sujet choisi par l'utilisateur
    topic: str = Field()
    # Titre généré par le LLM
    title: str = Field()
    # Synthèse générale de la revue de presse
    summary: str = Field()
    # Liste des articles mentionnés avec leur analyse
    articles: list = Field(default=[], sa_column=Column(JSON))