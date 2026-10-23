"use client";

import dynamic from "next/dynamic";

const ResearchDashboard = dynamic(
  () =>
    import("@/components/viewer/ResearchDashboard").then((mod) => mod.ResearchDashboard),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-sm text-slate-400">
        Loading Galveston Digital Twin…
      </div>
    ),
  },
);

export default function Home() {
  return <ResearchDashboard />;
}
