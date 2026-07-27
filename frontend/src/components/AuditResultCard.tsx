import type { AuditData } from "../types";
import PulseWaveform from "./PulseWaveform";

interface AuditResultCardProps {
  data: AuditData;
}

function resolveVariant(data: AuditData): "healthy" | "slow" | "down" {
  if (!data.status_code || data.status_code >= 500) return "down";
  if ((data.response_time_ms ?? 0) > 1200) return "slow";
  return "healthy";
}

function statusTone(status: number | null): string {
  if (!status) return "text-signal-rose bg-signal-rose/10 border-signal-rose/30";
  if (status < 300) return "text-pulse-400 bg-pulse-500/10 border-pulse-500/30";
  if (status < 400) return "text-signal-amber bg-signal-amber/10 border-signal-amber/30";
  return "text-signal-rose bg-signal-rose/10 border-signal-rose/30";
}

function Stat({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
      <p className="font-mono text-[11px] uppercase tracking-widest text-slate-500">{label}</p>
      <p className={`mt-1.5 truncate text-sm text-slate-200 ${mono ? "font-mono" : "font-medium"}`} title={value}>
        {value}
      </p>
    </div>
  );
}

export default function AuditResultCard({ data }: AuditResultCardProps) {
  const variant = resolveVariant(data);

  return (
    <div className="glass-panel mx-auto mt-8 w-full max-w-2xl animate-fade-up overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 px-6 py-4">
        <div className="min-w-0">
          <p className="truncate font-mono text-sm text-slate-300" title={data.final_url}>
            {data.final_url}
          </p>
          {data.final_url !== data.url && (
            <p className="mt-0.5 truncate text-xs text-slate-500">redirected from {data.url}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {data.cached && (
            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 font-mono text-[11px] uppercase tracking-widest text-slate-400">
              cached
            </span>
          )}
          <span
            className={`rounded-full border px-2.5 py-1 font-mono text-[11px] font-semibold ${statusTone(data.status_code)}`}
          >
            {data.status_code ?? "—"}
          </span>
        </div>
      </div>

      <div className="h-14 px-6 pt-4 opacity-90">
        <PulseWaveform variant={variant} className="h-full w-full" />
      </div>

      <div className="px-6 pb-2 pt-4">
        <p className="font-display text-lg font-semibold text-white">
          {data.title ?? "No title found"}
        </p>
        <p className="mt-1 text-sm text-slate-400">
          {data.meta_description ?? "No meta description found."}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 p-6 sm:grid-cols-3">
        <Stat label="Response time" value={data.response_time_ms != null ? `${data.response_time_ms} ms` : "—"} />
        <Stat label="HTTPS" value={data.https ? "Enabled" : "Not enabled"} />
        <Stat label="Content type" value={data.content_type ?? "Unknown"} mono />
        <Stat label="Server" value={data.server ?? "Not disclosed"} mono />
        <Stat
          label="Content length"
          value={data.content_length != null ? `${(data.content_length / 1024).toFixed(1)} KB` : "—"}
        />
        <Stat label="Audited at" value={new Date(data.timestamp).toLocaleTimeString()} mono />
      </div>
    </div>
  );
}
