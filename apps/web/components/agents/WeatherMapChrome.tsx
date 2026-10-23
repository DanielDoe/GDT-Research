"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { exitResearchScene } from "@/lib/agents/exit-scene";
import { clockTime, rowAt, seriesByVariable, valueRgb } from "@/lib/cesium/weather-layer";
import { useResearchAgentStore } from "@/stores/research-agent-store";

export function WeatherMapChrome() {
  const layer = useResearchAgentStore((state) => state.mapLayer);
  const setIndex = useResearchAgentStore((state) => state.setMapIndex);
  const setPlaying = useResearchAgentStore((state) => state.setPlaying);
  const setSteps = useResearchAgentStore((state) => state.setStepsPerSecond);

  useEffect(() => {
    if (!layer?.playing) return undefined;
    const timer = window.setInterval(() => {
      const current = useResearchAgentStore.getState().mapLayer;
      if (!current?.playing) return;
      const length = current.clock?.length || current.observations.length;
      if (current.index >= length - 1) {
        useResearchAgentStore.getState().setPlaying(false);
        return;
      }
      useResearchAgentStore.getState().setMapIndex(current.index + 1);
    }, 1000 / Math.max(layer.stepsPerSecond, 0.25));
    return () => window.clearInterval(timer);
  }, [layer?.playing, layer?.stepsPerSecond, layer?.datasetId]);

  if (!layer) return null;
  const time = clockTime(layer);
  const rain = rowAt(seriesByVariable(layer, "precip"), time);
  const speed = rowAt(seriesByVariable(layer, "wind_speed"), time);
  const direction = rowAt(seriesByVariable(layer, "wind_direction"), time);
  const gust = rowAt(seriesByVariable(layer, "wind_gust"), time);
  const current = rain ?? speed ?? layer.observations[layer.index];
  const stamps = (layer.clock?.length ? layer.clock : layer.observations.map((row) => row.observed_at)).slice(
    0,
    layer.index + 1,
  );
  const runningRain = rain
    ? stamps.reduce((sum, stamp) => {
        const row = rowAt(seriesByVariable(layer, "precip"), stamp);
        return sum + (row?.value ?? 0);
      }, 0)
    : null;
  const [red, green, blue] = valueRgb(rain ? "precip" : layer.variable, current?.value ?? null);
  const localTime =
    time &&
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/Chicago",
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(time));

  return (
    <>
      <div className="absolute bottom-3 left-3 z-20 max-w-sm rounded-md border border-slate-700 bg-slate-950/90 p-3 text-[11px] text-slate-300 shadow-lg">
        <p className="font-medium text-slate-100">{layer.title}</p>
        <p>
          {layer.dataKind} · gauge playback · {layer.stationId}
        </p>
        <ul className="mt-1 space-y-0.5 text-slate-200">
          {rain && (
            <li>
              Rain {rain.value == null ? rain.quality_flag ?? "missing" : `${rain.value} ${rain.unit}`} hourly
              {runningRain != null ? ` · ${runningRain.toFixed(1)} ${rain.unit} summed` : ""}
            </li>
          )}
          {speed && <li>Wind {speed.value == null ? "missing" : `${speed.value} ${speed.unit}`}</li>}
          {direction && (
            <li>From {direction.value == null ? direction.quality_flag ?? "missing" : `${direction.value}°`}</li>
          )}
          {gust && <li>Gust {gust.value == null ? gust.quality_flag ?? "missing" : `${gust.value} ${gust.unit}`}</li>}
        </ul>
        <p className="mt-1">{layer.sourceLabel}</p>
        <p className="mt-1 text-slate-400">
          The column is 400 m tall per millimetre of hourly accumulation so a gauge report is visible beside the
          city. The disc stays 220 m across. Neither is water depth or flood extent. The arrow points downwind.
          FlowsDT animates PCSWMM flood depth and velocity; that model is not connected, so no water surface is drawn
          on downtown.
        </p>
        <div className="mt-2 h-2 rounded" style={{ background: `linear-gradient(90deg, rgb(186,214,232), rgb(${red},${green},${blue}))` }} />
      </div>
      <div className="absolute bottom-3 left-1/2 z-20 flex -translate-x-1/2 items-center gap-2 rounded-md border border-slate-700 bg-slate-950/90 px-2 py-1 text-[11px] text-slate-200 shadow-lg">
        <Button type="button" size="sm" variant="ghost" onClick={() => setIndex(layer.index - 1)}>
          Step back
        </Button>
        <Button type="button" size="sm" variant="secondary" onClick={() => setPlaying(!layer.playing)}>
          {layer.playing ? "Pause" : "Play"}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setIndex(layer.index + 1)}>
          Step forward
        </Button>
        <Button type="button" size="sm" variant="secondary" onClick={exitResearchScene}>
          Exit scene
        </Button>
        <label className="flex items-center gap-1 text-slate-400">
          Speed
          <select
            value={layer.stepsPerSecond}
            onChange={(event) => setSteps(Number(event.target.value))}
            className="rounded border border-slate-700 bg-slate-900 px-1"
          >
            <option value={1}>1×</option>
            <option value={2}>2×</option>
            <option value={5}>5×</option>
          </select>
        </label>
        <span className="max-w-[220px] truncate">
          {time ?? "—"} UTC
          {localTime ? ` · ${localTime} CT` : ""}
        </span>
      </div>
    </>
  );
}
