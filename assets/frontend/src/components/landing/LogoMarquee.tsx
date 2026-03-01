const brands = [
  "Combos",
  "Aiberm",
  "Geddle",
  "VibeFriends",
  "PPT.ai",
  "Novaflow",
  "Arcademia",
  "Syncr",
];

export default function LogoMarquee() {
  return (
    <section className="border-y border-border bg-background py-6">
      <p className="mb-4 text-center text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
        Trusted by top-tier startups
      </p>

      <div className="relative overflow-hidden">
        {/* Fade edges */}
        <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-16 bg-gradient-to-r from-background to-transparent" />
        <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-16 bg-gradient-to-l from-background to-transparent" />

        <div className="animate-marquee flex w-max items-center gap-12 px-4">
          {[...brands, ...brands].map((brand, i) => (
            <span
              key={`${brand}-${i}`}
              className="whitespace-nowrap text-lg font-semibold text-muted-foreground/50 sm:text-xl"
            >
              {brand}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
