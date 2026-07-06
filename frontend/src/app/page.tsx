"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Page d'accueil — redirige vers /login si l'utilisateur n'est pas authentifié.
 */
export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.push("/login");
    }
  }, [router]);

  return (
    <main>
      <h1>Bienvenue sur NewsFoundry</h1>
      <p>Votre outil de revue de presse IA.</p>
    </main>
  );
}