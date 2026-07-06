"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface Chat {
  id: number;
  message_count: number;
}

export default function HomePage() {
  const router = useRouter();
  const [chats, setChats] = useState<Chat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.push("/login");
      return;
    }
    fetchChats(token);
  }, [router]);

  async function fetchChats(token: string) {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/chats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) {
        router.push("/login");
        return;
      }
      const data = await res.json();
      setChats(data);
    } finally {
      setLoading(false);
    }
  }

  async function createChat() {
    const token = localStorage.getItem("access_token");
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/chats`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json();
    router.push(`/chat/${data.id}`);
  }

  if (loading) return <main><p>Chargement...</p></main>;

  return (
    <main>
      <h1>NewsFoundry</h1>
      <button onClick={createChat}>+ Nouvelle conversation</button>
      {chats.length === 0 ? (
        <p>Aucune conversation. Démarrez-en une !</p>
      ) : (
        <ul>
          {chats.map((chat) => (
            <li key={chat.id}>
              <button onClick={() => router.push(`/chat/${chat.id}`)}>
                Conversation #{chat.id} — {chat.message_count} message(s)
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}