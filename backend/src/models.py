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
    # Historique complet au format PydanticAI (liste de messages JSON)
    messages: list = Field(default=[], sa_column=Column(JSON))