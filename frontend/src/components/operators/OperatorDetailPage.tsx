import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Globe, Envelope, Phone, Play, Stop } from "@phosphor-icons/react";
import {
  useOperator,
  confirmPropertyMatch,
  rejectPropertyMatch,
  confirmPartyMatch,
  rejectPartyMatch,
  runOperatorPipeline,
  killOperatorPipeline,
} from "../../api/operators";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PropertyMatchCard, PartyMatchCard } from "./OperatorMatchCard";
import LinkedInLink from "../shared/LinkedInLink";

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

function fmtTime(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}m ${sec}s`;
}

export default function OperatorDetailPage() {
  const { opId } = useParams<{ opId: string }>();
  const { data: op, loading, error, reload } = useOperator(opId!);
  const [showAllProps, setShowAllProps] = useState(false);
  const [showAllPhotos, setShowAllPhotos] = useState(false);

  // Crawl console state
  const [crawling, setCrawling] = useState(false);
  const [crawlOutput, setCrawlOutput] = useState("");
  const [crawlDone, setCrawlDone] = useState<boolean | null>(null);
  const crawlConsoleRef = useRef<HTMLPreElement>(null);
  const crawlElapsed = useElapsedTimer(crawling);

  async function handleCrawl(slug: string) {
    setCrawling(true);
    setCrawlOutput("");
    setCrawlDone(null);

    try {
      const res = await runOperatorPipeline("crawl-one", slug);
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

          if (text.startsWith("[done: ")) {
            setCrawlDone(text.includes("OK"));
          } else {
            setCrawlOutput((prev) => prev + text + "\n");
          }

          requestAnimationFrame(() => {
            if (crawlConsoleRef.current) {
              crawlConsoleRef.current.scrollTop = crawlConsoleRef.current.scrollHeight;
            }
          });
        }
      }
    } catch (err) {
      setCrawlOutput((prev) => prev + String(err) + "\n");
      setCrawlDone(false);
    } finally {
      setCrawling(false);
      reload();
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading operator...</div>
      </div>
    );
  }

  if (error || !op) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-destructive">Error: {error || "Not found"}</div>
      </div>
    );
  }

  const pendingPropMatches = op.property_matches.filter(
    (m) => m.status === "pending" && m.prop_id,
  );
  const confirmedPropMatches = op.property_matches.filter(
    (m) => m.status === "confirmed",
  );
  const unmatchedProps = op.property_matches.filter(
    (m) => m.status === "no_match",
  );
  const pendingPartyMatches = op.party_matches.filter(
    (m) => m.status === "pending",
  );

  const displayedProps = showAllProps
    ? op.extracted_properties
    : op.extracted_properties.slice(0, 10);
  const displayedPhotos = showAllPhotos
    ? op.photos
    : op.photos.slice(0, 8);

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex-none px-6 py-4 bg-background border-b border-border">
        <div className="flex items-center gap-3 mb-2">
          <Link to="/operators" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft size={18} />
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-foreground">{op.name}</h1>
              <Badge variant="secondary" className="text-[10px]">{op.op_id}</Badge>
            </div>
            <div className="flex items-center gap-3 mt-0.5">
              {op.url && (
                <a
                  href={op.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                >
                  <Globe size={12} /> {op.url}
                </a>
              )}
            </div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={crawling}
            onClick={() => handleCrawl(op.slug)}
            className="shrink-0"
          >
            <Play size={12} className="mr-1" />
            {crawling ? "Crawling..." : "Crawl Site"}
          </Button>
        </div>
        {op.description && (
          <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
            {op.description}
          </p>
        )}
        {op.legal_names.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {op.legal_names.map((ln, i) => (
              <Badge key={i} variant="outline" className="text-[10px]">
                {ln}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Crawl console */}
      {(crawlOutput || crawling) && (
        <div className="flex-none px-6 py-3 border-b border-border">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-medium ${
              crawlDone === null
                ? "text-blue-600 animate-pulse"
                : crawlDone
                  ? "text-green-600"
                  : "text-red-600"
            }`}>
              {crawlDone === null ? "CRAWLING" : crawlDone ? "DONE" : "FAILED"}
            </span>
            {crawling && (
              <>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {fmtTime(crawlElapsed)}
                </span>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={async () => {
                    await killOperatorPipeline().catch(() => {});
                  }}
                >
                  <Stop size={12} className="mr-1" />
                  Stop
                </Button>
              </>
            )}
            {crawlDone !== null && (
              <button
                className="text-xs text-muted-foreground hover:text-foreground"
                onClick={() => { setCrawlOutput(""); setCrawlDone(null); }}
              >
                dismiss
              </button>
            )}
          </div>
          <pre
            ref={crawlConsoleRef}
            className="text-xs whitespace-pre-wrap max-h-48 overflow-auto font-mono bg-black/5 rounded-lg p-3"
          >
            {crawlOutput.trim() || "Starting crawl..."}
          </pre>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">
          {/* Pending matches (most important — show first) */}
          {(pendingPropMatches.length > 0 || pendingPartyMatches.length > 0) && (
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle className="flex items-center gap-2">
                  Pending Matches
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-amber-600 border-amber-300">
                    {pendingPropMatches.length + pendingPartyMatches.length} to review
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 pt-4">
                {pendingPartyMatches.length > 0 && (
                  <div>
                    <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                      Party Matches
                    </h3>
                    <div className="space-y-2">
                      {op.party_matches.map((m, i) =>
                        m.status === "pending" ? (
                          <PartyMatchCard
                            key={i}
                            match={m}
                            index={i}
                            onConfirm={async (idx) => {
                              await confirmPartyMatch(op.op_id, idx);
                              reload();
                            }}
                            onReject={async (idx) => {
                              await rejectPartyMatch(op.op_id, idx);
                              reload();
                            }}
                          />
                        ) : null,
                      )}
                    </div>
                  </div>
                )}
                {pendingPropMatches.length > 0 && (
                  <div>
                    <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                      Property Matches
                    </h3>
                    <div className="space-y-2">
                      {op.property_matches.map((m, i) =>
                        m.status === "pending" && m.prop_id ? (
                          <PropertyMatchCard
                            key={i}
                            match={m}
                            index={i}
                            onConfirm={async (idx) => {
                              await confirmPropertyMatch(op.op_id, idx);
                              reload();
                            }}
                            onReject={async (idx) => {
                              await rejectPropertyMatch(op.op_id, idx);
                              reload();
                            }}
                          />
                        ) : null,
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Contacts */}
          {op.contacts.length > 0 && (
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle>Contacts ({op.contacts.length})</CardTitle>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {op.contacts.map((c, i) => (
                    <div key={i} className="border border-border rounded-lg p-3">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-medium">{c.name}</span>
                        <LinkedInLink name={c.name} />
                      </div>
                      {c.title && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {c.title}
                        </div>
                      )}
                      <div className="flex items-center gap-3 mt-1.5">
                        {c.email && (
                          <a href={`mailto:${c.email}`} className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                            <Envelope size={12} /> {c.email}
                          </a>
                        )}
                        {c.phone && (
                          <span className="text-xs text-muted-foreground flex items-center gap-1">
                            <Phone size={12} /> {c.phone}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Extracted Properties */}
          {op.extracted_properties.length > 0 && (
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle>
                  Extracted Properties ({op.extracted_properties.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2">
                        Address
                      </th>
                      <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2">
                        City
                      </th>
                      <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2">
                        Plaza Name
                      </th>
                      <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2">
                        Tenants
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedProps.map((p, i) => (
                      <tr key={i} className="border-b border-border">
                        <td className="px-3 py-2 text-sm">{p.address}</td>
                        <td className="px-3 py-2 text-sm">{p.city}</td>
                        <td className="px-3 py-2 text-sm text-muted-foreground">
                          {p.plaza_name || "\u2014"}
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex flex-wrap gap-1">
                            {p.tenants.slice(0, 3).map((t, j) => (
                              <Badge key={j} variant="secondary" className="text-[10px] px-1.5 py-0">
                                {t}
                              </Badge>
                            ))}
                            {p.tenants.length > 3 && (
                              <span className="text-[10px] text-muted-foreground">
                                +{p.tenants.length - 3} more
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {op.extracted_properties.length > 10 && !showAllProps && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowAllProps(true)}
                    className="mt-2 text-xs"
                  >
                    Show all {op.extracted_properties.length} properties
                  </Button>
                )}
              </CardContent>
            </Card>
          )}

          {/* Confirmed matches */}
          {confirmedPropMatches.length > 0 && (
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle className="flex items-center gap-2">
                  Confirmed Property Matches
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-green-600 border-green-300">
                    {confirmedPropMatches.length}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 pt-4">
                {confirmedPropMatches.map((m, i) => (
                  <div key={i} className="text-sm">
                    <Link
                      to={`/properties/${m.prop_id}`}
                      className="text-blue-600 hover:underline"
                    >
                      {m.prop_id}
                    </Link>
                    {" \u2014 "}
                    {m.extracted_address}, {m.extracted_city}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Photos */}
          {op.photos.length > 0 && (
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle>Photos ({op.photos.length})</CardTitle>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {displayedPhotos.map((ph, i) => (
                    <div key={i} className="space-y-1">
                      <a href={ph.url} target="_blank" rel="noopener noreferrer">
                        <img
                          src={ph.url}
                          alt={ph.caption || "Property photo"}
                          className="w-full h-32 object-cover rounded-lg border border-border"
                          loading="lazy"
                        />
                      </a>
                      {ph.caption && (
                        <div className="text-[10px] text-muted-foreground truncate">
                          {ph.caption}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {op.photos.length > 8 && !showAllPhotos && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowAllPhotos(true)}
                    className="mt-2 text-xs"
                  >
                    Show all {op.photos.length} photos
                  </Button>
                )}
              </CardContent>
            </Card>
          )}

          {/* Unmatched properties */}
          {unmatchedProps.length > 0 && (
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle className="text-muted-foreground">
                  Unmatched Properties ({unmatchedProps.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="space-y-1">
                  {unmatchedProps.slice(0, 20).map((m, i) => (
                    <div key={i} className="text-sm text-muted-foreground">
                      {m.extracted_address}, {m.extracted_city}
                      {m.reason && (
                        <span className="text-xs ml-2">({m.reason})</span>
                      )}
                    </div>
                  ))}
                  {unmatchedProps.length > 20 && (
                    <div className="text-xs text-muted-foreground mt-1">
                      ...and {unmatchedProps.length - 20} more
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
