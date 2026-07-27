import PulseWaveform from "./PulseWaveform";

export default function Hero() {
  return (
    <section className="relative overflow-hidden pt-20 pb-10 sm:pt-28">
      <div className="grid-backdrop pointer-events-none absolute inset-0 -z-10" />

      <div className="mx-auto max-w-3xl px-6 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-mono uppercase tracking-widest text-pulse-400">
          <span className="h-1.5 w-1.5 rounded-full bg-pulse-400 animate-blip" />
          live audit engine
        </div>

        <h1 className="font-display text-4xl font-semibold leading-[1.05] tracking-tight text-white sm:text-6xl">
          Take any URL's
          <span className="block text-pulse-400">vital signs.</span>
        </h1>

        <p className="mx-auto mt-5 max-w-xl text-base text-slate-400 sm:text-lg">
          Page Pulse fetches a page in real time and reads back its heartbeat — status,
          speed, headers, and metadata — before you ever open a tab.
        </p>
      </div>

      <div className="mx-auto mt-10 h-16 w-full max-w-2xl px-6 opacity-80">
        <PulseWaveform variant="healthy" className="h-full w-full" />
      </div>
    </section>
  );
}
