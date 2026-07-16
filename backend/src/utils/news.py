# utils/news.py — Récupération et injection des actualités du jour
import os
import httpx
from mistralai.client import Mistral

WORLDNEWSAPI_KEY = os.getenv("WORLDNEWSAPI_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

BASE_PROMPT = (
    "Tu es un assistant spécialisé pour les journalistes et pigistes. "
    "Tu les aides à faire leur veille d'actualité, à analyser des articles "
    "et à préparer des revues de presse. Tes réponses sont claires, "
    "structurées et adaptées à un contexte professionnel journalistique. "
    "Quand un utilisateur demande plus d'informations sur un sujet précis, "
    "utilise l'outil search_news pour chercher des articles récents sur ce sujet."
)


async def fetch_top_news(language: str = "fr", count: int = 20) -> list[dict]:
    """
    Appelle WorldNewsAPI /top-news et retourne une liste d'articles
    avec uniquement le titre et le résumé.
    """
    if not WORLDNEWSAPI_KEY:
        raise ValueError("WORLDNEWSAPI_KEY non définie dans les variables d'environnement")

    url = "https://api.worldnewsapi.com/top-news"
    params = {
        "api-key": WORLDNEWSAPI_KEY,
        "source-country": "fr",
        "language": language,
        "count": count,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

    articles = []
    top_news = data.get("top_news", [])
    for section in top_news:
        for article in section.get("news", []):
            title = article.get("title", "").strip()
            summary = article.get("summary", "").strip()
            if title:
                articles.append({"title": title, "summary": summary})

    return articles


async def search_news(query: str, count: int = 10) -> list[dict]:
    """
    Recherche des articles sur un sujet précis via WorldNewsAPI /search-news.
    Retourne titre, résumé, date, URL et texte complet pour le RAG.
    """
    if not WORLDNEWSAPI_KEY:
        raise ValueError("WORLDNEWSAPI_KEY non définie dans les variables d'environnement")

    url = "https://api.worldnewsapi.com/search-news"
    params = {
        "api-key": WORLDNEWSAPI_KEY,
        "text": query,
        "language": "fr",
        "number": count,
        "sort": "publish-time",
        "sort-direction": "DESC",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

    articles = []
    for article in data.get("news", []):
        title = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        publish_date = article.get("publish_date", "").strip()
        url = article.get("url", "").strip()
        text = article.get("text", "").strip()
        if title:
            articles.append({
                "title": title,
                "summary": summary,
                "publish_date": publish_date,
                "url": url,
                "text": text,
            })

    return articles


async def summarize_news(articles: list[dict]) -> str:
    """
    Synthétise une liste d'articles en un résumé concis via Mistral.
    """
    if not articles:
        return ""

    articles_text = "\n".join(
        f"- {a['title']}: {a['summary']}" if a["summary"] else f"- {a['title']}"
        for a in articles
    )

    client = Mistral(api_key=MISTRAL_API_KEY)
    response = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {
                "role": "user",
                "content": (
                    "Voici une liste d'articles d'actualité du jour. "
                    "Fais-en une synthèse concise (10-15 lignes max) en regroupant "
                    "les thèmes similaires et en éliminant les redondances. "
                    "Format : bullet points, une ligne par thème majeur.\n\n"
                    f"{articles_text}"
                ),
            }
        ],
    )

    return response.choices[0].message.content


async def build_system_prompt() -> str:
    """
    Construit le system prompt complet avec les actualités du jour injectées.
    """
    try:
        articles = await fetch_top_news()
        if not articles:
            return BASE_PROMPT

        summary = await summarize_news(articles)
        if not summary:
            return BASE_PROMPT

        return (
            f"{BASE_PROMPT}\n\n"
            "--- ACTUALITÉS DU JOUR ---\n"
            f"{summary}\n"
            "--------------------------"
        )
    except Exception as e:
        print(f"[news] Impossible de charger les actualités : {e}")
        return BASE_PROMPT