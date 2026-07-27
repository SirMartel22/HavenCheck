import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "HavenCheck",
  description: "A calm, smart housing vetting experience for students.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col text-white">
        <header className="sticky top-0 z-20 border-b border-white/10 bg-black/40 backdrop-blur-xl">
          <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
            <Link href="/" className="text-lg font-semibold tracking-[0.28em] uppercase text-white">
              HavenCheck
            </Link>
            <nav className="flex items-center gap-2 rounded-full border border-white/10 bg-white/10 p-1 text-sm text-zinc-300">
              <Link href="/" className="rounded-full px-4 py-2 transition hover:bg-white/15 hover:text-white">Browse</Link>
              <Link href="/chat" className="rounded-full px-4 py-2 transition hover:bg-white/15 hover:text-white">Ask the Agent</Link>
              <Link href="/submit" className="rounded-full px-4 py-2 transition hover:bg-white/15 hover:text-white">Submit</Link>
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
