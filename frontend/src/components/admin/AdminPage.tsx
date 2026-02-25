import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

interface CommandDef {
  key: string;
  label: string;
  description: string;
  variant: "default" | "secondary" | "destructive";
}

const commands: CommandDef[] = [
  {
    key: "clear-caches",
    label: "Clear Caches",
    description: "Flush in-memory caches. Run this after any rebuild so the app shows fresh data.",
    variant: "secondary",
  },
  {
    key: "rebuild-properties",
    label: "Rebuild Properties",
    description: "Rebuild the property registry from parsed data (cleo properties).",
    variant: "default",
  },
  {
    key: "rebuild-parties",
    label: "Rebuild Companies",
    description: "Rebuild the company registry (cleo parties).",
    variant: "default",
  },
  {
    key: "rebuild-all",
    label: "Rebuild All",
    description: "Rebuild properties, then parties, then clear caches.",
    variant: "default",
  },
  {
    key: "frontend-build",
    label: "Build Frontend (Production)",
    description: "Run npm run build to compile the React SPA for production. Not needed in dev — Vite hot-reloads.",
    variant: "secondary",
  },
];

const geocodeCommands: CommandDef[] = [
  {
    key: "apply-geocodes",
    label: "Apply Geocodes",
    description: "Fill in lat/lng for properties missing coordinates. Safe to run anytime — skips properties that already have coords.",
    variant: "default",
  },
  {
    key: "refresh-geocodes",
    label: "Refresh All Coords",
    description: "Re-compute coordinates for ALL properties using the best multi-provider median (Mapbox/Geocodio/HERE). Also generates a divergence report for addresses where providers disagree by 500m+.",
    variant: "default",
  },
];

// ---------------------------------------------------------------------------
// Persist last-known durations in localStorage so we can show estimates
// ---------------------------------------------------------------------------
const DURATIONS_KEY = "cleo-admin-durations";

const DEFAULT_ESTIMATES: Record<string, number> = {
  "rebuild-properties": 300,
  "rebuild-parties": 120,
  "rebuild-all": 420,
  "frontend-build": 30,
  "apply-geocodes": 60,
  "refresh-geocodes": 120,
};

function loadDurations(): Record<string, number> {
  try {
    return { ...DEFAULT_ESTIMATES, ...JSON.parse(localStorage.getItem(DURATIONS_KEY) || "{}") };
  } catch {
    return { ...DEFAULT_ESTIMATES };
  }
}

function saveDuration(command: string, seconds: number) {
  const d = loadDurations();
  d[command] = seconds;
  localStorage.setItem(DURATIONS_KEY, JSON.stringify(d));
}

// ---------------------------------------------------------------------------
// Live elapsed timer hook
// ---------------------------------------------------------------------------
function useElapsedTimer(running: boolean): number {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(0);

  useEffect(() => {
    if (!running) {
      setElapsed(0);
      return;
    }
    startRef.current = Date.now();
    setElapsed(0);
    const id = setInterval(() => {
      setElapsed((Date.now() - startRef.current) / 1000);
    }, 200);
    return () => clearInterval(id);
  }, [running]);

  return elapsed;
}

// ---------------------------------------------------------------------------
// Format seconds as "1m 23s" or "45s"
// ---------------------------------------------------------------------------
function fmtTime(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}m ${sec}s`;
}

interface LogEntry {
  command: string;
  ts: string;
  ok: boolean | null; // null = still running
  output: string;
  elapsed?: number;
}

export default function AdminPage() {
  const [running, setRunning] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const consoleRef = useRef<HTMLPreElement>(null);
  const elapsed = useElapsedTimer(running !== null);
  const durations = useRef(loadDurations());

  // Load server-side log on mount so history survives page navigation
  useEffect(() => {
    fetch("/api/admin/log")
      .then((r) => r.json())
      .then((entries: LogEntry[]) => {
        setLog((prev) => {
          if (prev.length > 0) return prev; // don't clobber active session log
          return [...entries].reverse(); // server returns oldest-first, we show newest-first
        });
      })
      .catch(() => {});
  }, []);

  async function runCommand(key: string) {
    setRunning(key);
    const startTime = Date.now();

    // Instant commands (no streaming)
    if (key === "clear-caches") {
      try {
        const res = await fetch("/api/admin/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: key }),
        });
        const entry = await res.json();
        entry.elapsed = (Date.now() - startTime) / 1000;
        saveDuration(key, entry.elapsed);
        durations.current = loadDurations();
        setLog((prev) => [entry, ...prev]);
      } catch (err) {
        setLog((prev) => [
          { command: key, ts: new Date().toISOString(), ok: false, output: String(err) },
          ...prev,
        ]);
      } finally {
        setRunning(null);
      }
      return;
    }

    // Streaming commands via SSE
    const entry: LogEntry = {
      command: key,
      ts: new Date().toISOString(),
      ok: null,
      output: "",
    };
    setLog((prev) => [entry, ...prev]);

    try {
      const res = await fetch("/api/admin/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: key }),
      });

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No response body");

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const text = line.slice(6);

          setLog((prev) => {
            const updated = [...prev];
            const current = { ...updated[0] };
            current.output += text + "\n";

            if (text.startsWith("[done: ")) {
              current.ok = text.includes("OK");
              current.elapsed = (Date.now() - startTime) / 1000;
              saveDuration(key, current.elapsed);
              durations.current = loadDurations();
            }
            updated[0] = current;
            return updated;
          });

          requestAnimationFrame(() => {
            if (consoleRef.current) {
              consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
            }
          });
        }
      }
    } catch (err) {
      setLog((prev) => {
        const updated = [...prev];
        updated[0] = { ...updated[0], ok: false, output: updated[0].output + String(err) + "\n" };
        return updated;
      });
    } finally {
      setRunning(null);
    }
  }

  const estimate = running ? durations.current[running] : undefined;

  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-h4 font-semibold mb-1">Admin</h1>
      <p className="text-body-2 text-t-secondary mb-1">
        Run backend commands without the terminal.
      </p>
      <p className="text-xs text-t-secondary mb-6">
        Backend auto-reloads on Python file changes when started with <code className="bg-black/5 px-1 rounded">./dev.sh</code>.
        These buttons are for data rebuilds.
      </p>

      <h2 className="text-h5 font-semibold mb-3">Review Tools</h2>
      <div className="space-y-3 mb-8">
        <div className="flex items-center gap-4 p-4 bg-b-surface2 rounded-xl">
          <div className="flex-1 min-w-0">
            <p className="text-body-1 font-medium">Party Review</p>
            <p className="text-body-2 text-t-secondary">
              Investigate party clustering decisions. Search names, view appearances side by side, confirm or split groups.
            </p>
          </div>
          <Button
            variant="default"
            size="sm"
            className="shrink-0"
            onClick={() => window.open("/api/party-review-page", "_blank")}
          >
            Open
          </Button>
        </div>
      </div>

      <h2 className="text-h5 font-semibold mb-3">Dev Server</h2>
      <div className="space-y-3 mb-8">
        <div className="flex items-center gap-4 p-4 bg-b-surface2 rounded-xl">
          <div className="flex-1 min-w-0">
            <p className="text-body-1 font-medium">Restart Backend</p>
            <p className="text-body-2 text-t-secondary">
              Trigger uvicorn reload to pick up Python code changes. Requires <code className="bg-black/5 px-1 rounded">./dev.sh</code>.
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={running !== null}
            onClick={() => runCommand("restart-backend")}
            className="shrink-0"
          >
            {running === "restart-backend" ? "Running..." : "Restart"}
          </Button>
        </div>
      </div>

      <h2 className="text-h5 font-semibold mb-3">Geocoding</h2>
      <div className="space-y-3 mb-8">
        {geocodeCommands.map((cmd) => (
          <div
            key={cmd.key}
            className="flex items-center gap-4 p-4 bg-b-surface2 rounded-xl"
          >
            <div className="flex-1 min-w-0">
              <p className="text-body-1 font-medium">{cmd.label}</p>
              <p className="text-body-2 text-t-secondary">{cmd.description}</p>
            </div>
            <Button
              variant={cmd.variant}
              size="sm"
              disabled={running !== null}
              onClick={() => runCommand(cmd.key)}
              className="shrink-0"
            >
              {running === cmd.key ? "Running..." : "Run"}
            </Button>
          </div>
        ))}
      </div>

      <h2 className="text-h5 font-semibold mb-3">Commands</h2>
      <div className="space-y-3 mb-8">
        {commands.map((cmd) => (
          <div
            key={cmd.key}
            className="flex items-center gap-4 p-4 bg-b-surface2 rounded-xl"
          >
            <div className="flex-1 min-w-0">
              <p className="text-body-1 font-medium">{cmd.label}</p>
              <p className="text-body-2 text-t-secondary">{cmd.description}</p>
            </div>
            <Button
              variant={cmd.variant}
              size="sm"
              disabled={running !== null}
              onClick={() => runCommand(cmd.key)}
              className="shrink-0"
            >
              {running === cmd.key ? "Running..." : "Run"}
            </Button>
          </div>
        ))}
      </div>

      {log.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-h5 font-semibold">Log</h2>
            {log.length > 1 && (
              <Button variant="ghost" size="sm" className="text-xs" onClick={() => setLog([])}>
                Clear log
              </Button>
            )}
          </div>
          <div className="space-y-3">
            {log.map((entry, i) => (
              <div
                key={`${entry.ts}-${i}`}
                className={`rounded-xl border p-4 ${
                  entry.ok === null
                    ? "border-blue-500/30 bg-blue-500/5"
                    : entry.ok
                      ? "border-green-500/30 bg-green-500/5"
                      : "border-red-500/30 bg-red-500/5"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-body-1 font-medium">{entry.command}</span>
                  <span className={`text-xs font-medium ${
                    entry.ok === null
                      ? "text-blue-600 animate-pulse"
                      : entry.ok
                        ? "text-green-600"
                        : "text-red-600"
                  }`}>
                    {entry.ok === null ? "RUNNING" : entry.ok ? "OK" : "FAILED"}
                  </span>

                  {/* Live timer while running */}
                  {entry.ok === null && i === 0 && (
                    <span className="text-xs text-t-secondary tabular-nums">
                      {fmtTime(elapsed)}
                      {estimate != null && (
                        <span className="text-t-secondary/60"> / ~{fmtTime(estimate)}</span>
                      )}
                    </span>
                  )}

                  {/* Final elapsed when done */}
                  {entry.ok !== null && entry.elapsed != null && (
                    <span className="text-xs text-t-secondary">{fmtTime(entry.elapsed)}</span>
                  )}

                  <span className="text-xs text-t-secondary ml-auto">
                    {new Date(entry.ts).toLocaleTimeString()}
                  </span>
                </div>

                {/* Progress bar while running */}
                {entry.ok === null && i === 0 && estimate != null && (
                  <div className="w-full h-1.5 bg-black/5 rounded-full mt-2 mb-1 overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full transition-all duration-200"
                      style={{ width: `${Math.min(100, (elapsed / estimate) * 100)}%` }}
                    />
                  </div>
                )}

                {entry.output && (
                  <pre
                    ref={i === 0 ? consoleRef : undefined}
                    className="text-xs text-t-secondary mt-2 whitespace-pre-wrap max-h-64 overflow-auto font-mono bg-black/5 rounded-lg p-3"
                  >
                    {entry.output.trim()}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
