export default function Footer() {
  return (
    <footer className="mt-24 border-t border-white/5 py-8">
      <div className="mx-auto max-w-2xl px-6 text-center">
        <p className="font-mono text-xs uppercase tracking-widest text-slate-500">
          Built for{" "}
          <a
            href="https://digitalheroesco.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 underline decoration-white/20 underline-offset-4 transition hover:text-pulse-400 hover:decoration-pulse-400"
          >
            Digital Heroes Software Development Training Task
          </a>
        </p>
      </div>
    </footer>
  );
}
