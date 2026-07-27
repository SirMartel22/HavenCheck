import Link from "next/link";
import { notFound } from "next/navigation";
import { ChatPanel } from "../../../components/ChatPanel";
import { MapEmbed } from "../../../components/MapEmbed";
import { getHostel, getReports, notifyAuthority, alertSecurity, createReport } from "../../../lib/api";

export default async function HostelDetailPage({ params }: { params: Promise<{ hostelId: string }> }) {
  const { hostelId } = await params;
  const hostel = await getHostel(hostelId);
  if (!hostel) return notFound();

  const reports = await getReports(hostelId);

  async function submitReport(formData: FormData) {
    "use server";
    const water_available = formData.get("water_available") === "on";
    const electricity_issue = formData.get("electricity_issue") === "on";
    const comment = String(formData.get("comment") ?? "");
    await createReport(hostelId, { water_available, electricity_issue, comment });
  }

  async function handleAuthority(formData: FormData) {
    "use server";
    const issueType = String(formData.get("issueType") ?? "water");
    const details = String(formData.get("details") ?? "Utility issue reported");
    await notifyAuthority(hostelId, issueType, details);
  }

  async function handleSecurity(formData: FormData) {
    "use server";
    const reason = String(formData.get("reason") ?? "Suspected scam");
    const evidence = String(formData.get("evidence") ?? "");
    await alertSecurity(hostelId, reason, evidence);
  }

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
          <div className="rounded-[28px] border border-white/15 bg-black/25 p-4 shadow-[0_20px_80px_rgba(0,0,0,0.24)] backdrop-blur-xl">
            <h2 className="text-xl font-semibold text-white">Report an issue</h2>
            <form action={submitReport} className="mt-4 space-y-3">
              <label className="flex items-center gap-2 text-sm text-zinc-300">
                <input type="checkbox" name="water_available" defaultChecked />
                Water is available
              </label>
              <label className="flex items-center gap-2 text-sm text-zinc-300">
                <input type="checkbox" name="electricity_issue" />
                Electricity issue reported
              </label>
              <textarea name="comment" rows={3} placeholder="Add detail about the current situation" className="w-full rounded-2xl border border-white/15 bg-white/10 px-3 py-2 text-sm text-white outline-none placeholder:text-zinc-500" />
              <button type="submit" className="rounded-full border border-white/15 bg-white/15 px-4 py-2 text-sm uppercase tracking-[0.2em] text-white transition hover:bg-white/20">Submit report</button>
            </form>
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <ChatPanel hostelId={hostel.id} title="Hostel context chat" subtitle="Ask about rent fairness, utility reliability, or scam warnings for this exact listing." />

        <div className="space-y-4">
          <div className="rounded-[28px] border border-white/15 bg-black/25 p-4 shadow-[0_20px_80px_rgba(0,0,0,0.24)] backdrop-blur-xl">
            <h2 className="text-xl font-semibold text-white">Recent crowd reports</h2>
            <div className="mt-4 space-y-3">
              {reports.length ? reports.map((report) => (
                <div key={report.id} className="rounded-[20px] border border-white/10 bg-white/10 p-3 text-sm text-zinc-300">
                  <p>{report.comment}</p>
                  <p className="mt-2 text-xs uppercase tracking-[0.2em] text-zinc-400">Water: {report.water_available ? "yes" : "no"} • Electricity: {report.electricity_issue ? "issue" : "stable"}</p>
                </div>
              )) : <p className="text-sm text-zinc-400">No reports yet.</p>}
            </div>
          </div>

          <div className="rounded-[28px] border border-white/15 bg-black/25 p-4 shadow-[0_20px_80px_rgba(0,0,0,0.24)] backdrop-blur-xl">
            <h2 className="text-xl font-semibold text-white">Escalation actions</h2>
            <div className="mt-4 space-y-3">
              <form action={handleAuthority} className="space-y-2 rounded-[20px] border border-white/10 bg-white/10 p-3">
                <input name="issueType" defaultValue="water" className="w-full rounded-full border border-white/15 bg-white/10 px-3 py-2 text-sm text-white outline-none" />
                <textarea name="details" rows={2} defaultValue="Water issue reported for this property." className="w-full rounded-2xl border border-white/15 bg-white/10 px-3 py-2 text-sm text-white outline-none" />
                <button type="submit" className="rounded-full border border-white/15 bg-white/15 px-4 py-2 text-sm uppercase tracking-[0.2em] text-white transition hover:bg-white/20">Notify authority</button>
              </form>
              <form action={handleSecurity} className="space-y-2 rounded-[20px] border border-white/10 bg-white/10 p-3">
                <input name="reason" defaultValue="Possible scam listing" className="w-full rounded-full border border-white/15 bg-white/10 px-3 py-2 text-sm text-white outline-none" />
                <textarea name="evidence" rows={2} defaultValue="Suspicious payment language reported by a student." className="w-full rounded-2xl border border-white/15 bg-white/10 px-3 py-2 text-sm text-white outline-none" />
                <button type="submit" className="rounded-full border border-white/15 bg-white/15 px-4 py-2 text-sm uppercase tracking-[0.2em] text-white transition hover:bg-white/20">Alert security</button>
              </form>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
