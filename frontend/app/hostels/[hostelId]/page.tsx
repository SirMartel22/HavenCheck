import Link from "next/link";
import { notFound } from "next/navigation";
import { ChatPanel } from "../../../components/ChatPanel";
import { HostelActions } from "../../../components/HostelActions";
import { MapEmbed } from "../../../components/MapEmbed";
import { getHostel, getReports } from "../../../lib/api";

export default async function HostelDetailPage({ params }: { params: Promise<{ hostelId: string }> }) {
  const { hostelId } = await params;
  const hostel = await getHostel(hostelId);
  if (!hostel) return notFound();

  const reports = await getReports(hostelId);

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <Link href="/" className="w-fit rounded-full border border-white/15 bg-white/10 px-4 py-2 text-sm uppercase tracking-[0.24em] text-zinc-300 transition hover:bg-white/15">
        ← Back to browse
      </Link>

      <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-[32px] border border-white/15 bg-black/25 p-6 shadow-[0_30px_100px_rgba(0,0,0,0.28)] backdrop-blur-xl">
          <div className="grid gap-6 md:grid-cols-[1.1fr_0.9fr]">
            <div>
              <p className="text-sm uppercase tracking-[0.3em] text-zinc-400">Featured hostel</p>
              <h1 className="mt-3 text-4xl font-semibold text-white">{hostel.name}</h1>
              <p className="mt-3 text-lg text-zinc-300">{hostel.location} • ₦{hostel.priceNaira.toLocaleString()}</p>
              <p className="mt-4 text-base leading-8 text-zinc-400">{hostel.description}</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {hostel.amenities.map((item) => (
                  <span key={item} className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] uppercase tracking-[0.24em] text-zinc-300">
                    {item}
                  </span>
                ))}
              </div>
            </div>
            <div className="overflow-hidden rounded-[24px] border border-white/15 bg-white/10">
              {hostel.photo_url ? <img src={hostel.photo_url} alt={hostel.name} className="h-full min-h-64 w-full object-cover grayscale" /> : <div className="flex h-full min-h-64 items-center justify-center text-sm uppercase tracking-[0.3em] text-zinc-400">No image</div>}
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-[24px] border border-white/15 bg-white/10 p-4">
              <p className="text-sm uppercase tracking-[0.25em] text-zinc-400">School-managed</p>
              <p className="mt-2 text-lg text-white">{hostel.isSchoolManaged ? "Yes" : "No"}</p>
            </div>
            <div className="rounded-[24px] border border-white/15 bg-white/10 p-4">
              <p className="text-sm uppercase tracking-[0.25em] text-zinc-400">Scam risk</p>
              <p className="mt-2 text-lg text-white">{hostel.scamRiskLevel ?? "pending review"}</p>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <MapEmbed lat={hostel.lat} lng={hostel.lng} title={hostel.name} />
          <HostelActions hostelId={hostel.id} initialReports={reports} />
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <ChatPanel hostelId={hostel.id} title="Hostel context chat" subtitle="Ask about rent fairness, utility reliability, or scam warnings for this exact listing." />
      </section>
    </main>
  );
}
