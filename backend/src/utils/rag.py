# utils/rag.py — Indexation et retrieval des articles via LlamaIndex
from llama_index.core import VectorStoreIndex, Document
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings

# Modèle d'embedding local — léger et efficace pour le français
Settings.embed_model = HuggingFaceEmbedding(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
# Pas de LLM dans LlamaIndex — on utilise PydanticAI pour ça
Settings.llm = None


def build_index(articles: list[dict]) -> VectorStoreIndex:
    """
    Construit un index vectoriel à partir des articles chargés durant le chat.
    Chaque article devient un Document LlamaIndex avec ses métadonnées.
    """
    documents = []
    for article in articles:
        if not article.get("text"):
            continue
        doc = Document(
            text=article["text"],
            metadata={
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "publish_date": article.get("publish_date", ""),
            }
        )
        documents.append(doc)

    if not documents:
        return None

    return VectorStoreIndex.from_documents(documents)


def retrieve_relevant_passages(index: VectorStoreIndex, topic: str, top_k: int = 5) -> str:
    """
    Retrouve les passages les plus pertinents par rapport au sujet
    de la revue de presse.
    """
    if not index:
        return ""

    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(topic)

    if not nodes:
        return ""

    passages = []
    for node in nodes:
        title = node.metadata.get("title", "Article sans titre")
        url = node.metadata.get("url", "")
        text = node.get_content()[:500]  # Limite à 500 chars par passage
        passages.append(f"**{title}**\nURL: {url}\nExtrait: {text}\n")

    return "\n---\n".join(passages)