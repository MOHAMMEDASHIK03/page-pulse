import PulseWaveform from "./PulseWaveform";

export default function AuditLoading() {
  return (
    <div className="glass-panel mx-auto mt-8 w-full max-w-2xl animate-fade-up px-6 py-10 text-center">
      <div className="mx-auto h-12 w-48">
        <PulseWaveform variant="idle" className="h-full w-full" />
      </div>
      <p className="mt-4 font-mono text-sm text-slate-400">
        Reaching out to the host and timing the response…
      </p>
    </div>
  );
}
