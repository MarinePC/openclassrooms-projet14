import os
from models import User
from sqlmodel import SQLModel, Session, create_engine, select
import bcrypt

DATABASE_URL = os.getenv("DATABASE_URL")

# L'engine est créé uniquement si DATABASE_URL est définie
# (les tests injectent leur propre engine via les fixtures)
engine = create_engine(DATABASE_URL, echo=True) if DATABASE_URL else None


def get_session():
    """Dépendance FastAPI pour obtenir une session de base de données."""
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)
    print("Database initialized successfully")

    default_email = "test@test.com"
    default_password = "test"

    with Session(engine) as session:
        statement = select(User).where(User.email == default_email)
        user = session.exec(statement).first()

        if not user:
            session.add(
                User(
                    email=default_email,
                    hashed_password=bcrypt.hashpw(
                        default_password.encode("utf-8"), bcrypt.gensalt()
                    ),
                )
            )
            session.commit()