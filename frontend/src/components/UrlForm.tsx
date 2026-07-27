import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { urlAuditSchema, type UrlAuditFormValues } from "../schemas/urlSchema";

interface UrlFormProps {
  onSubmit: (url: string) => void;
  isLoading: boolean;
}

export default function UrlForm({ onSubmit, isLoading }: UrlFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<UrlAuditFormValues>({
    resolver: zodResolver(urlAuditSchema),
    defaultValues: { url: "" },
  });

  const submit = handleSubmit((values) => onSubmit(values.url.trim()));

  return (
    <form onSubmit={submit} className="mx-auto w-full max-w-2xl px-6" noValidate>
      <div className="glass-panel flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:p-2 sm:pl-5">
        <label htmlFor="url" className="sr-only">
          URL to audit
        </label>
        <span className="hidden font-mono text-sm text-slate-500 sm:inline" aria-hidden="true">
          ↳
        </span>
        <input
          id="url"
          type="text"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          placeholder="https://example.com/page"
          className="w-full flex-1 bg-transparent px-4 py-3 text-base text-white placeholder:text-slate-500 focus:outline-none sm:px-0 sm:py-4"
          {...register("url")}
        />
        <button
          type="submit"
          disabled={isLoading}
          className="group inline-flex items-center justify-center gap-2 rounded-xl bg-pulse-500 px-6 py-3.5 font-display text-sm font-semibold text-ink-950 shadow-glow-pulse transition hover:bg-pulse-400 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 disabled:shadow-none"
        >
          {isLoading ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-ink-950/40 border-t-ink-950" />
              Checking pulse
            </>
          ) : (
            <>
              Run audit
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                className="transition group-hover:translate-x-0.5"
              >
                <path
                  d="M3 8h10M9 4l4 4-4 4"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </>
          )}
        </button>
      </div>

      <p
        className="mt-3 min-h-[1.25rem] px-2 text-sm text-signal-rose"
        role={errors.url ? "alert" : undefined}
      >
        {errors.url?.message ?? ""}
      </p>
    </form>
  );
}
