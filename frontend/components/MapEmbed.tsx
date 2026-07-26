interface MapEmbedProps {
  lat: number | null;
  lng: number | null;
  title: string;
}

export function MapEmbed({ lat, lng, title }: MapEmbedProps) {
  if (lat == null || lng == null) {
    return <div className="rounded-[24px] border border-white/15 bg-white/10 p-6 text-sm text-zinc-400">Map pin unavailable.</div>;
  }

  const src = `https://www.google.com/maps?q=${lat},${lng}&z=14&output=embed`;

  return (
    <div className="overflow-hidden rounded-[24px] border border-white/15 bg-white/10">
      <iframe title={title} src={src} className="h-72 w-full grayscale" loading="lazy" referrerPolicy="no-referrer-when-downgrade" />
    </div>
  );
}
