import { ChatPanel } from "../../components/ChatPanel";

export default function ChatPage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <section className="rounded-[32px] border border-white/15 bg-black/25 p-8 shadow-[0_30px_100px_rgba(0,0,0,0.28)] backdrop-blur-xl">
        <p className="text-sm uppercase tracking-[0.3em] text-zinc-400">Standalone assistant</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">Ask the agent anything</h1>
        <p className="mt-3 max-w-2xl text-base leading-8 text-zinc-400">Use this for general area questions, suspicious messages, or rent comparisons when you are not looking at one listing.</p>
      </section>
      <ChatPanel title="General chat" subtitle="Compare pricing, test scam checks, or ask about a location." />
    </main>
  );
}
