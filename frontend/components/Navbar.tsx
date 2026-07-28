"use client";

import Link from "next/link";
import { useState } from "react";

const navLinks = [
  { href: "/", label: "Browse" },
  { href: "/chat", label: "Ask the Agent" },
  { href: "/submit", label: "Submit" },
];

export function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-20 border-b border-white/10 bg-black/40 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <Link href="/" className="text-lg font-semibold uppercase tracking-[0.28em] text-white">
          HavenCheck
        </Link>

        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/10 text-white transition hover:bg-white/20 md:hidden"
          aria-label="Toggle navigation"
          aria-expanded={open}
        >
          <span className="flex flex-col gap-1.5">
            <span className="h-0.5 w-5 rounded-full bg-white" />
            <span className="h-0.5 w-5 rounded-full bg-white" />
            <span className="h-0.5 w-5 rounded-full bg-white" />
          </span>
        </button>

        <nav className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/10 p-1 text-sm text-zinc-300 md:flex">
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href} className="rounded-full px-4 py-2 transition hover:bg-white/15 hover:text-white">
              {link.label}
            </Link>
          ))}
        </nav>
      </div>

      {open ? (
        <div className="border-t border-white/10 bg-black/50 px-4 py-3 md:hidden">
          <div className="flex flex-col gap-2">
            {navLinks.map((link) => (
              <Link key={link.href} href={link.href} onClick={() => setOpen(false)} className="rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-sm text-zinc-200 transition hover:bg-white/15 hover:text-white">
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      ) : null}
    </header>
  );
}
