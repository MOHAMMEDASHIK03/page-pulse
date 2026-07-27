interface PulseWaveformProps {
  /** When set, the waveform "spikes" reflect a real response time band. */
  variant?: "idle" | "healthy" | "slow" | "down";
  className?: string;
}

const PATHS: Record<NonNullable<PulseWaveformProps["variant"]>, string> = {
  idle: "M0,40 L120,40 L140,20 L160,60 L180,40 L320,40 L340,15 L360,65 L380,40 L700,40",
  healthy: "M0,40 L110,40 L128,10 L146,68 L164,40 L300,40 L318,18 L336,62 L354,40 L700,40",
  slow: "M0,40 L150,40 L170,26 L190,54 L210,40 L450,40 L470,24 L490,56 L510,40 L700,40",
  down: "M0,40 L700,40",
};

export default function PulseWaveform({ variant = "idle", className = "" }: PulseWaveformProps) {
  const path = PATHS[variant];
  const color =
    variant === "down" ? "stroke-signal-rose" : variant === "slow" ? "stroke-signal-amber" : "stroke-pulse-400";

  return (
    <svg
      viewBox="0 0 700 80"
      preserveAspectRatio="none"
      className={className}
      role="img"
      aria-label="Live pulse waveform"
    >
      <path
        d={path}
        fill="none"
        className={`${color} animate-pulse-line`}
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray="1000"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
