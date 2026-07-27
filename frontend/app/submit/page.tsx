import { createHostel } from "../../lib/api";

export default function SubmitPage() {
  async function submitHostel(formData: FormData) {
    "use server";
    const payload = {
      name: String(formData.get("name") ?? ""),
      location: String(formData.get("location") ?? ""),
      priceNaira: Number(formData.get("priceNaira") ?? 0),
      amenities: String(formData.get("amenities") ?? "").split(",").map((item) => item.trim()).filter(Boolean),
      description: String(formData.get("description") ?? ""),
      photoUrl: String(formData.get("photoUrl") ?? ""),
      lat: Number(formData.get("lat") ?? 0),
      lng: Number(formData.get("lng") ?? 0),
    };
    await createHostel(payload);
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <section className="rounded-[32px] border border-white/15 bg-black/25 p-8 shadow-[0_30px_100px_rgba(0,0,0,0.28)] backdrop-blur-xl">
        <p className="text-sm uppercase tracking-[0.3em] text-zinc-400">Listing submission</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">Add a hostel to the map</h1>
        <p className="mt-3 max-w-2xl text-base leading-8 text-zinc-400">This form is ready for a live demo and can be extended with uploads once your backend image pipeline is configured.</p>
      </section>

      <form action={submitHostel} className="grid gap-4 rounded-[32px] border border-white/15 bg-black/25 p-6 shadow-[0_30px_100px_rgba(0,0,0,0.26)] backdrop-blur-xl md:grid-cols-2">
        <input name="name" placeholder="Hostel name" className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-500" />
        <input name="location" placeholder="Location" className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-500" />
        <input name="priceNaira" type="number" placeholder="Price in naira" className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-500" />
        <input name="amenities" placeholder="Amenities (comma separated)" className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-500" />
        <input name="photoUrl" placeholder="Photo URL" className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-500" />
        <input name="lat" type="number" step="0.0001" placeholder="Latitude" className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-500" />
        <input name="lng" type="number" step="0.0001" placeholder="Longitude" className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-500" />
        <textarea name="description" rows={4} placeholder="Short description" className="md:col-span-2 rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none placeholder:text-zinc-500" />
        <button type="submit" className="md:col-span-2 rounded-full border border-white/15 bg-white/15 px-5 py-3 text-sm uppercase tracking-[0.24em] text-white transition hover:bg-white/20">Submit listing</button>
      </form>
    </main>
  );
}
