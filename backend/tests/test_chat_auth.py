# tests/test_chat_auth.py — tests d'isolation des conversations par utilisateur
import os
os.environ["MISTRAL_API_KEY"] = "test-key-fake" 

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool
import bcrypt

from main import app
from database import get_session
from models import User


# --- Base de données en mémoire pour les tests ---

@pytest.fixture(name="session")
def session_fixture():
    """Crée une base SQLite en mémoire pour chaque test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Client de test FastAPI avec la session de test injectée."""
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# --- Fixtures utilisateurs ---

@pytest.fixture
def user_a(session: Session) -> User:
    """Crée l'utilisateur A en base."""
    user = User(
        email="user_a@test.com",
        hashed_password=bcrypt.hashpw(b"password_a", bcrypt.gensalt()),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def user_b(session: Session) -> User:
    """Crée l'utilisateur B en base."""
    user = User(
        email="user_b@test.com",
        hashed_password=bcrypt.hashpw(b"password_b", bcrypt.gensalt()),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_token(client: TestClient, email: str, password: str) -> str:
    """Helper pour récupérer un JWT via /api/auth/login."""
    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


# --- Tests ---

def test_login_succes(client, user_a):
    """Un utilisateur valide peut se connecter et reçoit un token."""
    token = get_token(client, "user_a@test.com", "password_a")
    assert token is not None


def test_login_mauvais_mot_de_passe(client, user_a):
    """Un mauvais mot de passe retourne une 401."""
    res = client.post(
        "/api/auth/login",
        json={"email": "user_a@test.com", "password": "mauvais"},
    )
    assert res.status_code == 401


def test_creer_chat(client, user_a):
    """Un utilisateur authentifié peut créer un chat."""
    token = get_token(client, "user_a@test.com", "password_a")
    res = client.post("/api/chats", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    assert "id" in res.json()


def test_acces_chat_autre_utilisateur_interdit(client, user_a, user_b):
    """Un utilisateur ne peut pas accéder au chat d'un autre utilisateur."""
    # User A crée un chat
    token_a = get_token(client, "user_a@test.com", "password_a")
    res = client.post("/api/chats", headers={"Authorization": f"Bearer {token_a}"})
    chat_id = res.json()["id"]

    # User B essaie d'y accéder
    token_b = get_token(client, "user_b@test.com", "password_b")
    res = client.get(
        f"/api/chats/{chat_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 403


def test_liste_chats_isolee_par_utilisateur(client, user_a, user_b):
    """Chaque utilisateur ne voit que ses propres conversations."""
    token_a = get_token(client, "user_a@test.com", "password_a")
    token_b = get_token(client, "user_b@test.com", "password_b")

    # User A crée 2 chats
    client.post("/api/chats", headers={"Authorization": f"Bearer {token_a}"})
    client.post("/api/chats", headers={"Authorization": f"Bearer {token_a}"})

    # User B crée 1 chat
    client.post("/api/chats", headers={"Authorization": f"Bearer {token_b}"})

    # User A doit voir 2 chats, pas 3
    res_a = client.get("/api/chats", headers={"Authorization": f"Bearer {token_a}"})
    assert len(res_a.json()) == 2

    # User B doit voir 1 chat
    res_b = client.get("/api/chats", headers={"Authorization": f"Bearer {token_b}"})
    assert len(res_b.json()) == 1


def test_sans_token_retourne_401(client):
    """Une route protégée sans token retourne une 403."""
    res = client.get("/api/chats")
    assert res.status_code == 403