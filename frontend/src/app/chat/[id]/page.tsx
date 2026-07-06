"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useParams } from "next/navigation";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function ChatPage() {
  const router = useRouter();
  const params = useParams();
  const chatId = params.id;

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.push("/login");
      return;
    }
    fetchHistory(token);
  }, [chatId, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function fetchHistory(token: string) {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/chats/${chatId}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!res.ok) {
      router.push("/");
      return;
    }
    const data = await res.json();
    // Reconstruit les messages affichables depuis l'historique PydanticAI
    const displayMessages: Message[] = [];
    for (const msg of data.messages) {
      if (msg.kind === "request") {
        for (const part of msg.parts) {
          if (part.part_kind === "user-prompt") {
            displayMessages.push({ role: "user", content: part.content });
          }
        }
      } else if (msg.kind === "response") {
        for (const part of msg.parts) {
          if (part.part_kind === "text") {
            displayMessages.push({ role: "assistant", content: part.content });
          }
        }
      }
    }
    setMessages(displayMessages);
  }

  async function sendMessage() {
    if (!input.trim() || loading) return;

    const token = localStorage.getItem("access_token");
    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/chats/${chatId}/messages`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ content: userMessage }),
        }
      );
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.response },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Erreur de connexion au serveur." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  return (
    <main>
      <button onClick={() => router.push("/")}>← Retour</button>
      <h1>Conversation #{chatId}</h1>

      <div role="log" aria-live="polite">
        {messages.map((msg, i) => (
          <div key={i}>
            <strong>{msg.role === "user" ? "Vous" : "NewsFoundry"}</strong>
            <p>{msg.content}</p>
          </div>
        ))}
        {loading && <p aria-busy="true">En cours de réponse...</p>}
        <div ref={bottomRef} />
      </div>

      <div>
        <label htmlFor="message-input">Votre message</label>
        <textarea
          id="message-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Posez votre question... (Entrée pour envoyer)"
          disabled={loading}
          rows={3}
        />
        <button onClick={sendMessage} disabled={loading || !input.trim()}>
          {loading ? "En cours..." : "Envoyer"}
        </button>
      </div>
    </main>
  );
}