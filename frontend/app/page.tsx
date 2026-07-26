import Link from "next/link";
import { HostelCard } from "../components/HostelCard";
import { getHostels } from "../lib/api";

export default async function HomePage({ searchParams }: { searchParams: Promise<{ location?: string; maxPrice?: string }> }) {
  const { location = "", maxPrice = "" } = await searchParams;
  const hostels = await getHostels(location, Number(maxPrice) || undefined);

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-8 px-4 py-8 sm:px-6 lg:px-8">
      <section className="rounded-[32px] border border-white/15 bg-black/25 p-8 shadow-[0_30px_100px_rgba(0,0,0,0.28)] backdrop-blur-xl">
        <p className="text-sm uppercase tracking-[0.3em] text-zinc-400">Student-first housing vetting</p>
        <h1 className="mt-3 text-4xl font-semibold text-white sm:text-5xl">Browse verified hostels with calm clarity.</h1>
        <p className="mt-4 max-w-2xl text-base leading-8 text-zinc-400">Search by area and budget, then inspect rent fairness, utility reliability, and scam signals in one place.</p>

        <form method="get" className="mt-8 grid gap-3 rounded-[24px] border border-white/10 bg-white/5 p-4 md:grid-cols-[1fr_1fr_auto]">
          <input name="location" defaultValue={location} placeholder="Location" className="rounded-full border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-500" />
          <input name="maxPrice" type="number" defaultValue={maxPrice} placeholder="Max price" className="rounded-full border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-500" />
          <button type="submit" className="rounded-full border border-white/15 bg-white/15 px-5 py-3 text-sm uppercase tracking-[0.24em] text-white transition hover:bg-white/20">Filter</button>
        </form>
      </section>

      <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {hostels.map((hostel) => (
          <HostelCard key={hostel.id} hostel={hostel} />
        ))}
      </section>

      <div className="fixed bottom-5 right-5 z-30">
        <Link href="/chat" className="rounded-full border border-white/15 bg-white/15 px-5 py-3 text-sm uppercase tracking-[0.24em] text-white shadow-[0_14px_40px_rgba(0,0,0,0.35)] backdrop-blur-xl transition hover:bg-white/25">
          Ask the agent
        </Link>
      </div>
    </main>
  );
}
