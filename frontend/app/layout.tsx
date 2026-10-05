import type { Metadata } from "next";
import "./style.css";

export const metadata: Metadata = {
  title: "ControlDeck — Homelab Control Center",
  description: "A lightweight, modular entry point for your homelab.",
};

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="nl"><body>{children}</body></html>;
}
