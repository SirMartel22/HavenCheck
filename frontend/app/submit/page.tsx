"use client";

import { FormEvent, useState } from "react";
import { createHostel } from "../../lib/api";

const inputClasses = "w-full rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none transition focus:border-white/30 focus:bg-white/15 placeholder:text-zinc-500";

export default function SubmitPage() {
  const [form, setForm] = useState({
    name: "",
    location: "",
    priceNaira: "",
    amenities: "",
    photoUrl: "",
    lat: "",
    lng: "",
    description: "",
  });
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submitHostel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = form.name.trim();
    const location = form.location.trim();
    const priceNaira = Number(form.priceNaira);
    const description = form.description.trim();

    if (!name || !location || !description || !Number.isFinite(priceNaira) || priceNaira <= 0) {
      setStatus({ type: "error", message: "Please fill the name, location, description, and a valid price before submitting." });
      return;
    }

    setSubmitting(true);
    setStatus(null);

    try {
      await createHostel({
        name,
        location,
        priceNaira,
        amenities: form.amenities.split(",").map((item) => item.trim()).filter(Boolean),
        description,
        photoUrl: form.photoUrl.trim(),
        lat: form.lat ? Number(form.lat) : null,
        lng: form.lng ? Number(form.lng) : null,
      });
      setStatus({ type: "success", message: "Your hostel listing was submitted successfully." });
      setForm({ name: "", location: "", priceNaira: "", amenities: "", photoUrl: "", lat: "", lng: "", description: "" });
    } catch (error) {
      setStatus({ type: "error", message: error instanceof Error ? error.message : "Submission failed. Please try again in a moment." });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <section className="rounded-4xl border border-white/15 bg-black/25 p-6 shadow-[0_30px_100px_rgba(0,0,0,0.28)] backdrop-blur-xl sm:p-8">
        <p className="text-sm uppercase tracking-[0.3em] text-zinc-400">Listing submission</p>
        <h1 className="mt-3 text-3xl font-semibold text-white sm:text-4xl">Add a hostel to the map</h1>
        <p className="mt-3 max-w-2xl text-base leading-8 text-zinc-400">This form now validates your data before sending it, so you avoid broken submissions and confusing backend errors.</p>
      </section>

      <form onSubmit={submitHostel} className="grid gap-4 rounded-4xl border border-white/15 bg-black/25 p-4 shadow-[0_30px_100px_rgba(0,0,0,0.26)] backdrop-blur-xl sm:p-6 md:grid-cols-2">
        {status ? (
          <div className={`md:col-span-2 rounded-2xl border px-4 py-3 text-sm ${status.type === "success" ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200" : "border-rose-400/30 bg-rose-500/10 text-rose-200"}`}>
            {status.message}
          </div>
        ) : null}
        <input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} name="name" placeholder="Hostel name" className={inputClasses} />
        <input value={form.location} onChange={(event) => setForm((current) => ({ ...current, location: event.target.value }))} name="location" placeholder="Location" className={inputClasses} />
        <input value={form.priceNaira} onChange={(event) => setForm((current) => ({ ...current, priceNaira: event.target.value }))} name="priceNaira" type="number" min="1" placeholder="Price in naira" className={inputClasses} />
        <input value={form.amenities} onChange={(event) => setForm((current) => ({ ...current, amenities: event.target.value }))} name="amenities" placeholder="Amenities (comma separated)" className={inputClasses} />
        <input value={form.photoUrl} onChange={(event) => setForm((current) => ({ ...current, photoUrl: event.target.value }))} name="photoUrl" placeholder="Photo URL" className={inputClasses} />
        <input value={form.lat} onChange={(event) => setForm((current) => ({ ...current, lat: event.target.value }))} name="lat" type="number" step="0.0001" placeholder="Latitude" className={inputClasses} />
        <input value={form.lng} onChange={(event) => setForm((current) => ({ ...current, lng: event.target.value }))} name="lng" type="number" step="0.0001" placeholder="Longitude" className={inputClasses} />
        <textarea value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} name="description" rows={4} placeholder="Short description" className={`md:col-span-2 ${inputClasses}`} />
        <button type="submit" disabled={submitting} className="md:col-span-2 rounded-full border border-white/15 bg-white/15 px-5 py-3 text-sm uppercase tracking-[0.24em] text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-70">
          {submitting ? "Submitting…" : "Submit listing"}
        </button>
      </form>
    </main>
  );
}
