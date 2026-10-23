"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Building2,
  Calendar,
  Car,
  CloudSun,
  HeartPulse,
  Leaf,
  Mountain,
  Plane,
  Radio,
  Satellite,
  Search,
  ShieldAlert,
  Ship,
  Users,
  Waves,
  Workflow,
  Zap,
  MessagesSquare,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  createScenario,
  datasetDownloadUrl,
  getAgent,
  getObservations,
  listAgents,
  publishDataset,
  runOperation,
  waitForJob,
  type AgentCard,
  type DatasetContract,
  type ObservationRow,
  type SubagentInfo,
} from "@/lib/agents/api";
import { exitResearchScene } from "@/lib/agents/exit-scene";
import { valueRgb } from "@/lib/cesium/weather-layer";
import {
  useResearchAgentStore,
  type AgentSelection,
  type SceneSeries,
  type WeatherMapLayer,
} from "@/stores/research-agent-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

const FAMILIES: { id: string; short: string; icon: LucideIcon }[] = [
  { id: "weather", short: "Weather", icon: CloudSun },
  { id: "satellite", short: "Satellite", icon: Satellite },
  { id: "geospatial_survey", short: "Geo Survey", icon: Mountain },
  { id: "population", short: "Population", icon: Users },
  { id: "coastal", short: "Coastal", icon: Waves },
  { id: "transportation", short: "Transportation", icon: Car },
  { id: "urban_infrastructure", short: "Infrastructure", icon: Building2 },
  { id: "energy", short: "Energy", icon: Zap },
  { id: "wireless", short: "Wireless & IoT", icon: Radio },
  { id: "environmental", short: "Environment", icon: Leaf },
  { id: "seasonal", short: "Seasonal", icon: Calendar },
  { id: "community_reports", short: "Forums", icon: MessagesSquare },
  { id: "disaster", short: "Disaster", icon: ShieldAlert },
  { id: "autonomous_vehicles", short: "UAV / UGV", icon: Plane },
  { id: "maritime", short: "Maritime", icon: Ship },
  { id: "public_health", short: "Public Health", icon: HeartPulse },
  { id: "economic", short: "Economics", icon: BarChart3 },
  { id: "orchestration", short: "Orchestration", icon: Workflow },
];

interface Choice {
  key: string;
  subagentId: string;
  variableId: string;
  label: string;
  available: boolean;
  detail?: string | null;
}

export function AgentMode() {
  const [query, setQuery] = useState("");
  const [cards, setCards] = useState<AgentCard[]>([]);
  const [activeId, setActiveId] = useState("weather");
  const [subagents, setSubagents] = useState<SubagentInfo[]>([]);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const selections = useResearchAgentStore((state) => state.selections);
  const toggleSelection = useResearchAgentStore((state) => state.toggleSelection);
  const configureOpen = useResearchAgentStore((state) => state.configureOpen);
  const setConfigureOpen = useResearchAgentStore((state) => state.setConfigureOpen);

  useEffect(() => {
    let cancelled = false;
    listAgents()
      .then((payload) => {
        if (!cancelled) setCards(payload.agents);
      })
      .catch((error: Error) => {
        if (!cancelled) setApiError(error.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setDetailError(null);
    getAgent(activeId)
      .then((payload) => {
        if (!cancelled) setSubagents(payload.subagents);
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setSubagents([]);
          setDetailError(error.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  const visibleFamilies = FAMILIES.filter((family) => {
    const card = cards.find((item) => item.agent_id === family.id);
    const haystack = `${family.short} ${card?.name ?? ""} ${card?.description ?? ""}`.toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });
  const active = FAMILIES.find((family) => family.id === activeId) ?? FAMILIES[0];
  const activeCard = cards.find((item) => item.agent_id === active.id);
  const choices = useMemo(() => choicesFor(active.id, subagents), [active.id, subagents]);

  function onToggle(choice: Choice) {
    const selection: AgentSelection = {
      key: `${active.id}:${choice.key}`,
      agentId: active.id,
      agentLabel: active.short,
      subagentId: choice.subagentId,
      variableId: choice.variableId,
      label: choice.label,
      available: choice.available,
    };
    toggleSelection(selection);
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-6">
      <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-slate-100">Research Agents</h1>
            <p className="text-xs text-slate-400">
              Choose the agents and variables for this research scenario. Unavailable entries stay registered and are not filled with estimated data.
            </p>
          </div>
          <span className="rounded-full border border-slate-700 px-2 py-1 text-[11px] text-slate-300">
            18 families
          </span>
        </div>
        <label className="relative block">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search agent families..."
            className="h-10 w-full rounded-full border border-slate-700 bg-slate-900 pl-9 pr-3 text-sm text-slate-100 outline-none focus:border-sky-500"
          />
        </label>
        {apiError && (
          <p className="mt-3 rounded-md border border-amber-700/60 bg-amber-950/40 px-3 py-2 text-xs text-amber-100">
            {apiError}
          </p>
        )}
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {visibleFamilies.map((family) => {
            const Icon = family.icon;
            const card = cards.find((item) => item.agent_id === family.id);
            const selected = family.id === activeId;
            return (
              <button
                key={family.id}
                type="button"
                onClick={() => setActiveId(family.id)}
                className={`rounded-xl border px-3 py-4 text-center transition ${
                  selected
                    ? "border-sky-500 bg-slate-900"
                    : "border-slate-800 bg-slate-950 hover:border-slate-600"
                }`}
              >
                <Icon className="mx-auto h-5 w-5 text-slate-200" />
                <span className="mt-2 block text-xs font-medium text-slate-100">{family.short}</span>
                {card && (
                  <span className="mt-1 block text-[10px] text-slate-500">
                    {card.available_subagent_count}/{card.subagent_count} ready · {card.health_status.replaceAll("_", " ")}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
        <div className="mb-3 flex items-center gap-2">
          <active.icon className="h-4 w-4 text-slate-300" />
          <div>
            <h2 className="text-sm font-semibold text-slate-100">{activeCard?.name ?? `${active.short} Agent`}</h2>
            <p className="text-xs text-slate-400">
              {activeCard?.description ?? "Select variables to include in a research scenario."}
            </p>
          </div>
        </div>
        {detailError && <p className="mb-3 text-xs text-amber-200">{detailError}</p>}
        <ul className="space-y-1">
          {choices.map((choice) => {
            const key = `${active.id}:${choice.key}`;
            const checked = selections.some((item) => item.key === key);
            return (
              <li key={choice.key}>
                <label className="flex cursor-pointer items-start gap-3 rounded-md px-2 py-2 hover:bg-slate-900">
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-sky-500"
                    checked={checked}
                    onChange={() => onToggle(choice)}
                  />
                  <span>
                    <span className="text-sm text-slate-100">{choice.label}</span>
                    {!choice.available && (
                      <span className="ml-2 text-[10px] uppercase tracking-wide text-amber-300">
                        Not available
                      </span>
                    )}
                    {choice.detail && <span className="mt-0.5 block text-[11px] text-slate-500">{choice.detail}</span>}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-100">Scenario data selections</h2>
          <span className="flex items-center gap-2 text-[11px] text-slate-500">
            {selections.length} variable{selections.length === 1 ? "" : "s"}
            {selections.length > 0 && (
              <button type="button" className="text-slate-300 underline" onClick={exitResearchScene}>
                Clear selections
              </button>
            )}
          </span>
        </div>
        {selections.length === 0 ? (
          <p className="text-xs text-slate-500">Nothing is selected yet.</p>
        ) : (
          <div className="mb-4 flex flex-wrap gap-2">
            {selections.map((selection) => (
              <button
                key={selection.key}
                type="button"
                onClick={() => toggleSelection(selection)}
                className={`rounded-full border px-2 py-1 text-[11px] ${
                  selection.available
                    ? "border-slate-600 text-slate-200"
                    : "border-amber-700 text-amber-200"
                }`}
              >
                {selection.agentLabel} / {selection.label}
                {!selection.available ? " · gap" : ""}
              </button>
            ))}
          </div>
        )}
        <Button
          type="button"
          className="h-11 w-full rounded-full"
          disabled={selections.length === 0}
          onClick={() => setConfigureOpen(true)}
        >
          Configure selected simulation data →
        </Button>
        {configureOpen && <ConfigurePanel selections={selections} />}
      </section>
    </div>
  );
}

function choicesFor(agentId: string, subagents: SubagentInfo[]): Choice[] {
  if (agentId === "weather") {
    const fromApi = subagents.flatMap((subagent) => {
      if (subagent.supported_variables.length > 0) {
        return subagent.supported_variables.map((variable) => ({
          key: variable.id,
          subagentId: subagent.id,
          variableId: variable.id,
          label: variable.name,
          available: variable.implemented && subagent.implementation_status === "available",
          detail: variable.note ?? (variable.implemented ? null : subagent.unavailable_reason),
        }));
      }
      return [
        {
          key: subagent.id,
          subagentId: subagent.id,
          variableId: subagent.id,
          label: subagent.name,
          available: subagent.implementation_status === "available",
          detail: subagent.unavailable_reason,
        },
      ];
    });
    if (fromApi.length > 0) return fromApi;
  }
  if (subagents.length === 0) {
    return [
      {
        key: "pending",
        subagentId: "pending",
        variableId: "pending",
        label: "Subagents load from the research API",
        available: false,
        detail: "The family list is local. Variable status comes from the API.",
      },
    ];
  }
  return subagents.map((subagent) => ({
    key: subagent.id,
    subagentId: subagent.id,
    variableId: subagent.id,
    label: subagent.name,
    available: subagent.implementation_status === "available",
    detail: subagent.description,
  }));
}

function ConfigurePanel({ selections }: { selections: AgentSelection[] }) {
  const [provider, setProvider] = useState("iem_asos");
  const [start, setStart] = useState("2024-07-07T00:00:00Z");
  const [end, setEnd] = useState("2024-07-09T00:00:00Z");
  const [lookback, setLookback] = useState(false);
  const [failover, setFailover] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [results, setResults] = useState<Array<{ contract: DatasetContract; rows: ObservationRow[] }>>([]);
  const [scenarioNote, setScenarioNote] = useState<string | null>(null);
  const [scenarioName, setScenarioName] = useState("Galveston station meteorology");
  const setMode = useWorkspaceStore((state) => state.setMode);
  const setMapLayer = useResearchAgentStore((state) => state.setMapLayer);
  const ready = selections.filter((item) => item.available && item.agentId === "weather");
  const gaps = selections.filter((item) => !item.available || item.agentId !== "weather");

  async function acquire() {
    setBusy(true);
    setError(null);
    setScenarioNote(null);
    setResults([]);
    try {
      if (!lookback && start >= end) {
        throw new Error("The UTC end time must be after the start time.");
      }
      const groups = new Map<string, AgentSelection>();
      for (const selection of ready) {
        groups.set(selection.subagentId, selection);
      }
      const collected: Array<{ contract: DatasetContract; rows: ObservationRow[] }> = [];
      for (const selection of groups.values()) {
        setStatus(`Requesting ${selection.label} from ${provider}.`);
        const response = await runOperation({
          agent_id: "weather",
          subagent_id: selection.subagentId,
          operation: "acquire",
          region_id: "galveston-downtown",
          time_range: lookback ? undefined : { start, end },
          parameters: {
            workflow: "acquire_and_process",
            provider,
            station_id: "KGLS",
            preferred_unit: selection.subagentId === "rainfall" ? "mm" : "m/s",
            ...(lookback ? { lookback_hours: 24 } : {}),
            ...(provider === "noaa_nws" && selection.subagentId === "rainfall" && failover
              ? { failover_provider: "iem_asos" }
              : {}),
          },
        });
        for (const job of response.jobs ?? []) {
          setStatus(`${selection.label}: ${job.kind} ${job.status}.`);
          const finished = await waitForJob(job.job_id);
          if (finished.status !== "completed") {
            throw new Error(finished.error || `${selection.label} ${finished.status}.`);
          }
          if (finished.kind === "process") {
            for (const item of finished.result?.datasets ?? []) {
              const observations = await getObservations(item.dataset_id);
              collected.push({ contract: item.contract, rows: observations.observations });
            }
          }
        }
      }
      setResults(collected);
      setStatus(collected.length ? "Observations stored with provenance." : "The provider returned no processed series.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Acquisition failed.");
      setStatus(null);
    } finally {
      setBusy(false);
    }
  }

  async function saveScenario() {
    setError(null);
    try {
      const manifest = await createScenario({
        name: scenarioName,
        objective:
          "Inspect the selected Galveston datasets. Station series are observations at the reporting site. This record is not a numerical simulation.",
        category: "data_inspection",
        region_id: "galveston-downtown",
        dataset_ids: results.map((item) => item.contract.dataset_id),
        parameters: {
          requested_selections: selections.map((item) => ({
            agent_id: item.agentId,
            subagent_id: item.subagentId,
            variable: item.variableId,
            label: `${item.agentLabel} / ${item.label}`,
            available: item.available,
          })),
        },
      });
      const warning = manifest.compatibility.warnings[0];
      setScenarioNote(
        `Saved ${manifest.scenario_id}. ${manifest.statement}${warning ? ` ${warning}` : ""}`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The scenario was not saved.");
    }
  }

  async function showOnMap(items: Array<{ contract: DatasetContract; rows: ObservationRow[] }>) {
    const published = await Promise.all(items.map((item) => publishDataset(item.contract.dataset_id)));
    const anchor = published[0];
    const coordinates = items[0]?.contract.spatial.geometry?.coordinates;
    const series: SceneSeries[] = items.map((item) => ({
      datasetId: item.contract.dataset_id,
      variable: item.contract.variable,
      unit: item.contract.measurement.unit,
      aggregation: item.contract.measurement.aggregation,
      title: item.contract.variable.replaceAll("_", " "),
      observations: item.rows,
    }));
    const clock = [...new Set(series.flatMap((item) => item.observations.map((row) => row.observed_at)))].sort();
    const primary = series.find((item) => item.variable.includes("precip")) ?? series[0];
    const layer: WeatherMapLayer = {
      datasetId: series.map((item) => item.datasetId).join("+"),
      title: series.length > 1 ? "Scholes Field scene" : (anchor?.title ?? primary?.title ?? "Station series"),
      variable: primary?.variable ?? "weather",
      unit: primary?.unit ?? "",
      aggregation: primary?.aggregation ?? "",
      dataKind: items[0]?.contract.data_kind ?? "observation",
      sourceLabel: anchor?.source_label ?? "",
      license: items[0]?.contract.provenance.license ?? null,
      stationId: items[0]?.contract.source.station_id ?? anchor?.station_id ?? "KGLS",
      stationName: items[0]?.contract.source.station_name ?? anchor?.station_name ?? "",
      longitude: coordinates?.[0] ?? anchor?.longitude ?? 0,
      latitude: coordinates?.[1] ?? anchor?.latitude ?? 0,
      representativeness: items[0]?.contract.spatial.representativeness ?? "station_point",
      displayNote: anchor?.display_height_note ?? "",
      observations: primary?.observations ?? [],
      series,
      clock,
      index: 0,
      playing: true,
      stepsPerSecond: 2,
    };
    setMapLayer(layer);
    setMode("map");
  }

  return (
    <div className="mt-5 space-y-4 border-t border-slate-800 pt-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-100">Observation window</h3>
        <p className="text-xs text-slate-400">
          Times are UTC. The default window is 7–9 July 2024 at Galveston Scholes Field, which includes Hurricane Beryl’s Texas landfall. The series is the station report, not a map of the storm.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant={lookback ? "outline" : "secondary"}
          onClick={() => {
            setLookback(false);
            setProvider("iem_asos");
            setStart("2024-07-07T00:00:00Z");
            setEnd("2024-07-09T00:00:00Z");
          }}
        >
          7–9 July 2024 ASOS
        </Button>
        <Button
          type="button"
          size="sm"
          variant={lookback ? "secondary" : "outline"}
          onClick={() => {
            setLookback(true);
            setProvider("noaa_nws");
          }}
        >
          Last 24 hours, NOAA NWS
        </Button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-slate-400">
          Provider
          <select
            value={provider}
            onChange={(event) => setProvider(event.target.value)}
            className="mt-1 h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-2 text-sm text-slate-100"
          >
            <option value="iem_asos">IEM ASOS (NOAA hourly reports)</option>
            <option value="noaa_nws">NOAA NWS API (recent station observations)</option>
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Station
          <input
            value="KGLS — Galveston Scholes Field"
            readOnly
            className="mt-1 h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-2 text-sm text-slate-300"
          />
        </label>
        {!lookback && (
          <>
            <label className="text-xs text-slate-400">
              Start (UTC)
              <input
                value={start}
                onChange={(event) => setStart(event.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-2 text-sm text-slate-100"
              />
            </label>
            <label className="text-xs text-slate-400">
              End (UTC)
              <input
                value={end}
                onChange={(event) => setEnd(event.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-2 text-sm text-slate-100"
              />
            </label>
          </>
        )}
      </div>
      {provider === "noaa_nws" && ready.some((item) => item.subagentId === "rainfall") && (
        <label className="flex items-center gap-2 text-xs text-slate-300">
          <input
            type="checkbox"
            checked={failover}
            onChange={(event) => setFailover(event.target.checked)}
            className="accent-sky-500"
          />
          If NOAA NWS precipitation is empty, request IEM ASOS hourly accumulation and record the switch.
        </label>
      )}
      {gaps.length > 0 && (
        <p className="text-xs text-amber-200">
          These selections have no connector and will be saved as gaps, not as data:{" "}
          {gaps.map((item) => `${item.agentLabel} / ${item.label}`).join(", ")}.
        </p>
      )}
      <Button type="button" disabled={busy || ready.length === 0} onClick={() => void acquire()}>
        {busy ? "Working…" : "Acquire and process observations"}
      </Button>
      {ready.length === 0 && (
        <p className="text-xs text-slate-500">
          Select rainfall or a wind variable to request observations. Other families cannot be acquired yet.
        </p>
      )}
      {results.length > 0 && (
        <Button type="button" className="h-11 w-full" onClick={() => void showOnMap(results)}>
          Play scene on the 3D map
        </Button>
      )}
      {status && <p className="text-xs text-slate-300">{status}</p>}
      {error && <p className="text-xs text-red-300">{error}</p>}
      {results.map((item) => (
        <article key={item.contract.dataset_id} className="rounded-xl border border-slate-800 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-medium text-slate-100">{item.contract.variable}</p>
              <p className="text-[11px] text-slate-400">
                {item.contract.data_kind} · {item.contract.measurement.aggregation} · {item.contract.measurement.unit}
              </p>
            </div>
            <span className="rounded-full border border-emerald-800 px-2 py-0.5 text-[10px] uppercase text-emerald-300">
              {item.contract.data_kind}
            </span>
          </div>
          <SeriesChart rows={item.rows} variable={item.contract.variable} unit={item.contract.measurement.unit} />
          <dl className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-400">
            <div>
              <dt>Quality</dt>
              <dd className="text-slate-200">{item.contract.quality.status}</dd>
            </div>
            <div>
              <dt>Missing fraction</dt>
              <dd className="text-slate-200">
                {item.contract.quality.missing_fraction == null
                  ? "—"
                  : item.contract.quality.missing_fraction.toFixed(2)}
              </dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd className="text-slate-200">{item.contract.source.provider}</dd>
            </div>
            <div>
              <dt>Station</dt>
              <dd className="text-slate-200">{item.contract.source.station_id}</dd>
            </div>
          </dl>
          {item.contract.quality.notes?.map((note) => (
            <p key={note} className="mt-1 text-[11px] text-slate-500">
              {note}
            </p>
          ))}
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" size="sm" onClick={() => void showOnMap([item])}>
              Load to 3D map
            </Button>
            <a
              className="inline-flex h-8 items-center rounded-md border border-slate-600 px-3 text-xs text-slate-100"
              href={datasetDownloadUrl(item.contract.dataset_id)}
            >
              Download CSV
            </a>
          </div>
        </article>
      ))}
      <label className="block text-xs text-slate-400">
        Scenario name
        <input
          value={scenarioName}
          onChange={(event) => setScenarioName(event.target.value)}
          className="mt-1 h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-2 text-sm text-slate-100"
        />
      </label>
      <Button type="button" variant="secondary" onClick={() => void saveScenario()}>
        Add processed data to scenario
      </Button>
      {scenarioNote && <p className="text-xs text-slate-300">{scenarioNote}</p>}
    </div>
  );
}

function SeriesChart({
  rows,
  variable,
  unit,
}: {
  rows: ObservationRow[];
  variable: string;
  unit: string;
}) {
  const numeric = rows.map((row) => row.value).filter((value): value is number => value != null);
  const max = Math.max(...numeric, 0.001);
  if (rows.length === 0) {
    return <p className="text-xs text-slate-500">No observations were returned.</p>;
  }
  return (
    <div className="flex h-24 items-end gap-px overflow-hidden rounded bg-slate-900 p-1">
      {rows.map((row) => {
        const [red, green, blue] = valueRgb(variable, row.value);
        const height = row.value == null ? 8 : Math.max(8, (row.value / max) * 100);
        return (
          <div
            key={`${row.observed_at}-${row.variable}`}
            title={`${row.observed_at}: ${row.value == null ? (row.quality_flag ?? "missing") : `${row.value} ${unit}`}`}
            className="min-w-0 flex-1 rounded-sm"
            style={{
              height: `${height}%`,
              background: `rgb(${red}, ${green}, ${blue})`,
              opacity: row.value == null ? 0.35 : 1,
            }}
          />
        );
      })}
    </div>
  );
}
