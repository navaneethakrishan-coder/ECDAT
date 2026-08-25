type HealthResponse = {
  status: string;
  service: string;
  version: string;
};

async function getBackendHealth(): Promise<HealthResponse | null> {
  const baseUrl = process.env.NEXT_PUBLIC_ECDAT_API_BASE_URL ?? "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${baseUrl}/api/v1/health`, { cache: "no-store" });
    return response.ok ? (await response.json() as HealthResponse) : null;
  } catch {
    return null;
  }
}

export default async function Home() {
  const health = await getBackendHealth();
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl items-center px-6">
      <section className="w-full rounded-xl border border-slate-700 bg-slate-900 p-8 shadow-2xl">
        <p className="text-sm font-semibold tracking-[0.2em] text-cyan-400">SIH 26164</p>
        <h1 className="mt-3 text-4xl font-bold">ECDAT</h1>
        <p className="mt-3 text-slate-300">Explainable Cryptographic Discovery, Quantum Risk Assessment and Migration Planning Platform</p>
        <div className="mt-8 rounded-lg bg-slate-800 p-4 text-sm">
          <p className="font-semibold">Backend connection</p>
          <p className="mt-1 text-slate-300">
            {health ? `${health.service} is ${health.status} (v${health.version})` : "Unavailable — start the FastAPI backend to enable live analysis."}
          </p>
        </div>
        <p className="mt-6 text-sm text-slate-400">Phase 1 foundation is ready. Analysis workflows will appear as their deterministic backend phases are implemented.</p>
      </section>
    </main>
  );
}
