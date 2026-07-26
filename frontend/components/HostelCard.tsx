import Link from "next/link";
import type { Hostel } from "../lib/api";

interface HostelCardProps {
  hostel: Hostel;
}

export function HostelCard({ hostel }: HostelCardProps) {
  const riskTone = hostel.scamRiskLevel === "high" ? "border-white/25 bg-white/15" : "border-white/10 bg-white/10";

  return (
    <Link href={`/hostels/${hostel.id}`} className={`group block overflow-hidden rounded-[28px] border ${riskTone} p-4 shadow-[0_20px_80px_rgba(0,0,0,0.25)] backdrop-blur-xl transition hover:-translate-y-1`}>
      <div className="aspect-[4/3] overflow-hidden rounded-[20px] bg-zinc-900">
        {hostel.photo_url ? (
          <img src={hostel.photo_url} alt={hostel.name} className="h-full w-full object-cover grayscale transition duration-300 group-hover:scale-105" />
        ) : (
          <div className="flex h-full items-center justify-center text-sm uppercase tracking-[0.3em] text-zinc-400">No image</div>
        )}
      </div>
      <div className="mt-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-2xl font-semibold text-white">{hostel.name}</p>
            <p className="text-sm text-zinc-400">{hostel.location}</p>
          </div>
          <span className="rounded-full border border-white/15 bg-black/30 px-3 py-1 text-[11px] uppercase tracking-[0.24em] text-zinc-200">
            ₦{hostel.priceNaira.toLocaleString()}
          </span>
        </div>
        <p className="text-sm leading-6 text-zinc-300">{hostel.description}</p>
        <div className="flex flex-wrap gap-2">
          {hostel.amenities.slice(0, 3).map((item) => (
            <span key={item} className="rounded-full border border-white/15 bg-white/10 px-2.5 py-1 text-[11px] uppercase tracking-[0.24em] text-zinc-300">
              {item}
            </span>
          ))}
        </div>
        {hostel.scamRiskLevel && hostel.scamRiskLevel !== "low" ? (
          <div className="rounded-2xl border border-white/15 bg-black/30 px-3 py-2 text-xs uppercase tracking-[0.2em] text-zinc-300">
            Scam signal: {hostel.scamRiskLevel}
          </div>
        ) : null}
      </div>
    </Link>
  );
}
