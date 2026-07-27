import { useState } from "react";
import Hero from "./components/Hero";
import UrlForm from "./components/UrlForm";
import AuditLoading from "./components/AuditLoading";
import AuditResultCard from "./components/AuditResultCard";
import AuditErrorCard from "./components/AuditErrorCard";
import Footer from "./components/Footer";
import { auditUrl, ApiError } from "./lib/api";
import type { AuditData } from "./types";

type ViewState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: AuditData }
  | { status: "error"; code: string; message: string };

export default function App() {
  const [view, setView] = useState<ViewState>({ status: "idle" });

  async function handleAudit(url: string) {
    setView({ status: "loading" });
    try {
      const data = await auditUrl(url);
      setView({ status: "success", data });
    } catch (error) {
      if (error instanceof ApiError) {
        setView({ status: "error", code: error.code, message: error.message });
      } else {
        setView({ status: "error", code: "UNKNOWN_ERROR", message: "Something unexpected happened." });
      }
    }
  }

  return (
    <div className="min-h-screen">
      <main>
        <Hero />
        <UrlForm onSubmit={handleAudit} isLoading={view.status === "loading"} />

        {view.status === "loading" && <AuditLoading />}
        {view.status === "success" && <AuditResultCard data={view.data} />}
        {view.status === "error" && <AuditErrorCard code={view.code} message={view.message} />}
      </main>
      <Footer />
    </div>
  );
}
