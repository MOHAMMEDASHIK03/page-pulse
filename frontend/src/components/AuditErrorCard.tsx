interface AuditErrorCardProps {
  code: string;
  message: string;
}

export default function AuditErrorCard({ code, message }: AuditErrorCardProps) {
  return (
    <div
      role="alert"
      className="glass-panel mx-auto mt-8 w-full max-w-2xl animate-fade-up border-signal-rose/30 px-6 py-6"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-signal-rose/15">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path
              d="M8 5v4M8 11h.01M14 8A6 6 0 1 1 2 8a6 6 0 0 1 12 0Z"
              stroke="#FF5C7A"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-signal-rose">{code}</p>
          <p className="mt-1 text-sm text-slate-300">{message}</p>
        </div>
      </div>
    </div>
  );
}
