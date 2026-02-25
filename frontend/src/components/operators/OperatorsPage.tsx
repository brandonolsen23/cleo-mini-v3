import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  MagnifyingGlass,
  ArrowsDownUp,
  ArrowUp,
  ArrowDown,
  Plus,
  Trash,
  Play,
  Stop,
} from "@phosphor-icons/react";
import {
  useOperators,
  addOperator,
  removeOperator,
  runOperatorPipeline,
  killOperatorPipeline,
} from "../../api/operators";
import type { OperatorSummary } from "../../types/operator";
import Pagination from "../shared/Pagination";
import { useTableParams } from "../../hooks/useTableParams";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// SSE console helpers (same pattern as AdminPage)
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

function fmtTime(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}m ${sec}s`;
}

// ---------------------------------------------------------------------------
// Table setup
// ---------------------------------------------------------------------------

const columnHelper = createColumnHelper<OperatorSummary>();

function globalFilterFn(
  row: { original: OperatorSummary },
  _columnId: string,
  filterValue: string,
): boolean {
  const q = filterValue.toLowerCase();
  const o = row.original;
  return (
    o.name.toLowerCase().includes(q) ||
    o.slug.toLowerCase().includes(q) ||
    o.url.toLowerCase().includes(q) ||
    o.op_id.toLowerCase().includes(q)
  );
}

export default function OperatorsPage() {
  const { data, loading, error, reload } = useOperators();
  const {
    globalFilter,
    sorting,
    pagination,
    setGlobalFilter,
    setSorting,
    setPagination,
  } = useTableParams([{ id: "name", desc: false }]);
  const navigate = useNavigate();

  // Add operator form
  const [showAdd, setShowAdd] = useState(false);
  const [addName, setAddName] = useState("");
  const [addUrl, setAddUrl] = useState("");
  const [addLoading, setAddLoading] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  // Pipeline console
  const [running, setRunning] = useState<string | null>(null);
  const [consoleOutput, setConsoleOutput] = useState("");
  const [consoleDone, setConsoleDone] = useState<boolean | null>(null);
  const consoleRef = useRef<HTMLPreElement>(null);
  const elapsed = useElapsedTimer(running !== null);

  // Delete confirmation
  const [deleteSlug, setDeleteSlug] = useState<string | null>(null);

  // Columns — defined inside component so we can access deleteSlug setter
  const columns = [
    columnHelper.accessor("name", {
      header: "Name",
      meta: { grow: true },
      cell: (info) => (
        <div>
          <div className="text-sm font-medium truncate">{info.getValue()}</div>
          <div className="text-xs text-muted-foreground mt-0.5 truncate">
            {info.row.original.url}
          </div>
        </div>
      ),
    }),
    columnHelper.accessor("crawled_pages", {
      header: "Crawled",
      size: 80,
      cell: (info) => (
        <div className="text-sm font-medium">
          {info.getValue() > 0 ? info.getValue() : "\u2014"}
        </div>
      ),
    }),
    columnHelper.accessor("contacts_count", {
      header: "Contacts",
      size: 80,
      cell: (info) => (
        <div className="text-sm font-medium">{info.getValue() || "\u2014"}</div>
      ),
    }),
    columnHelper.accessor("properties_count", {
      header: "Properties",
      size: 90,
      cell: (info) => (
        <div className="text-sm font-medium">{info.getValue() || "\u2014"}</div>
      ),
    }),
    columnHelper.display({
      id: "prop_matches",
      header: "Prop Matches",
      size: 120,
      cell: ({ row }) => {
        const o = row.original;
        return (
          <div className="flex items-center gap-1.5">
            {o.pending_property_matches > 0 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-amber-600 border-amber-300">
                {o.pending_property_matches} pending
              </Badge>
            )}
            {o.confirmed_property_matches > 0 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-green-600 border-green-300">
                {o.confirmed_property_matches} confirmed
              </Badge>
            )}
            {o.pending_property_matches === 0 &&
              o.confirmed_property_matches === 0 && (
                <span className="text-sm text-muted-foreground">{"\u2014"}</span>
              )}
          </div>
        );
      },
    }),
    columnHelper.display({
      id: "party_matches",
      header: "Party Matches",
      size: 120,
      cell: ({ row }) => {
        const o = row.original;
        return (
          <div className="flex items-center gap-1.5">
            {o.pending_party_matches > 0 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-amber-600 border-amber-300">
                {o.pending_party_matches} pending
              </Badge>
            )}
            {o.confirmed_party_matches > 0 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-green-600 border-green-300">
                {o.confirmed_party_matches} confirmed
              </Badge>
            )}
            {o.pending_party_matches === 0 &&
              o.confirmed_party_matches === 0 && (
                <span className="text-sm text-muted-foreground">{"\u2014"}</span>
              )}
          </div>
        );
      },
    }),
    columnHelper.accessor("updated", {
      header: "Updated",
      size: 100,
      cell: (info) => (
        <div className="text-sm">{info.getValue()?.slice(0, 10) || "\u2014"}</div>
      ),
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      size: 40,
      cell: ({ row }) => (
        <button
          className="p-1 text-muted-foreground hover:text-destructive transition-colors"
          title="Remove operator"
          onClick={(e) => {
            e.stopPropagation();
            setDeleteSlug(row.original.slug);
          }}
        >
          <Trash size={14} />
        </button>
      ),
    }),
  ];

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter, pagination },
    globalFilterFn,
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    autoResetPageIndex: false,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const handleRowClick = useCallback(
    (opId: string) => {
      if (opId) navigate(`/operators/${opId}`);
    },
    [navigate],
  );

  const filteredCount = table.getFilteredRowModel().rows.length;

  // Add operator handler
  async function handleAdd() {
    setAddLoading(true);
    setAddError(null);
    try {
      await addOperator(addName, addUrl);
      setAddName("");
      setAddUrl("");
      setShowAdd(false);
      reload();
    } catch (e: unknown) {
      setAddError(e instanceof Error ? e.message : String(e));
    } finally {
      setAddLoading(false);
    }
  }

  // Delete operator handler
  async function handleDelete(slug: string) {
    try {
      await removeOperator(slug);
      setDeleteSlug(null);
      reload();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : String(e));
      setDeleteSlug(null);
    }
  }

  // Pipeline command handler
  async function runPipeline(command: string) {
    setRunning(command);
    setConsoleOutput("");
    setConsoleDone(null);

    try {
      const res = await runOperatorPipeline(command);
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
            setConsoleDone(text.includes("OK"));
          } else {
            setConsoleOutput((prev) => prev + text + "\n");
          }

          requestAnimationFrame(() => {
            if (consoleRef.current) {
              consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
            }
          });
        }
      }
    } catch (err) {
      setConsoleOutput((prev) => prev + String(err) + "\n");
      setConsoleDone(false);
    } finally {
      setRunning(null);
      reload();
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading operators...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-destructive">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Page header */}
      <div className="flex-none px-6 py-4 bg-background border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-foreground">Operators</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {filteredCount.toLocaleString()} operators
              {globalFilter &&
                ` (filtered from ${data.length.toLocaleString()})`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <MagnifyingGlass
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                type="text"
                placeholder="Search name, URL..."
                value={globalFilter}
                onChange={(e) => setGlobalFilter(e.target.value)}
                className="pl-9 pr-4 py-2 w-64 h-9 text-sm"
              />
            </div>
            <Button
              variant="default"
              size="sm"
              onClick={() => setShowAdd(!showAdd)}
            >
              <Plus size={14} className="mr-1" />
              Add Operator
            </Button>
          </div>
        </div>

        {/* Add Operator form */}
        {showAdd && (
          <div className="mt-3 flex items-end gap-3 p-3 bg-muted rounded-lg">
            <div className="flex-1 space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Name</label>
              <Input
                type="text"
                placeholder="e.g. RioCan REIT"
                value={addName}
                onChange={(e) => setAddName(e.target.value)}
                className="h-8 text-sm"
              />
            </div>
            <div className="flex-1 space-y-1">
              <label className="text-xs font-medium text-muted-foreground">URL</label>
              <Input
                type="url"
                placeholder="e.g. https://www.riocan.com"
                value={addUrl}
                onChange={(e) => setAddUrl(e.target.value)}
                className="h-8 text-sm"
              />
            </div>
            <Button
              size="sm"
              disabled={!addName.trim() || !addUrl.trim() || addLoading}
              onClick={handleAdd}
            >
              {addLoading ? "Adding..." : "Add"}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setShowAdd(false)}>
              Cancel
            </Button>
          </div>
        )}
        {addError && (
          <p className="text-xs text-destructive mt-1">{addError}</p>
        )}

        {/* Pipeline action bar */}
        <div className="mt-3 flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={running !== null}
            onClick={() => runPipeline("crawl-all")}
          >
            <Play size={12} className="mr-1" />
            {running === "crawl-all" ? "Crawling..." : "Crawl All Sites"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={running !== null}
            onClick={() => runPipeline("extract")}
          >
            <Play size={12} className="mr-1" />
            {running === "extract" ? "Extracting..." : "Extract (AI)"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={running !== null}
            onClick={() => runPipeline("match")}
          >
            <Play size={12} className="mr-1" />
            {running === "match" ? "Matching..." : "Match Registries"}
          </Button>

          {running && (
            <>
              <span className="text-xs text-muted-foreground tabular-nums ml-2 animate-pulse">
                {fmtTime(elapsed)}
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
        </div>

        {/* Streaming console */}
        {(consoleOutput || running) && (
          <div className="mt-3">
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-medium ${
                consoleDone === null
                  ? "text-blue-600 animate-pulse"
                  : consoleDone
                    ? "text-green-600"
                    : "text-red-600"
              }`}>
                {consoleDone === null ? "RUNNING" : consoleDone ? "DONE" : "FAILED"}
              </span>
              {consoleDone !== null && (
                <button
                  className="text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => { setConsoleOutput(""); setConsoleDone(null); }}
                >
                  dismiss
                </button>
              )}
            </div>
            <pre
              ref={consoleRef}
              className="text-xs whitespace-pre-wrap max-h-48 overflow-auto font-mono bg-black/5 rounded-lg p-3"
            >
              {consoleOutput.trim() || "Starting..."}
            </pre>
          </div>
        )}
      </div>

      {/* Delete confirmation dialog */}
      {deleteSlug && (
        <div className="flex-none px-6 py-2 bg-destructive/5 border-b border-destructive/20">
          <div className="flex items-center gap-3">
            <span className="text-sm">
              Remove operator <strong>{deleteSlug}</strong>?
            </span>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => handleDelete(deleteSlug)}
            >
              Remove
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDeleteSlug(null)}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-muted z-10">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => {
                  const sort = header.column.getIsSorted();
                  const canSort = header.column.getCanSort();
                  const meta = header.column.columnDef.meta as
                    | { grow?: boolean }
                    | undefined;
                  return (
                    <th
                      key={header.id}
                      className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-4 py-2.5 select-none"
                      style={{
                        width: meta?.grow ? undefined : header.getSize(),
                      }}
                      onClick={
                        canSort
                          ? header.column.getToggleSortingHandler()
                          : undefined
                      }
                    >
                      <span
                        className={
                          canSort
                            ? "inline-flex items-center gap-1 cursor-pointer"
                            : ""
                        }
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {canSort &&
                          (sort === "asc" ? (
                            <ArrowUp size={12} />
                          ) : sort === "desc" ? (
                            <ArrowDown size={12} />
                          ) : (
                            <ArrowsDownUp
                              size={12}
                              className="opacity-30"
                            />
                          ))}
                      </span>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-border hover:bg-accent cursor-pointer transition-colors"
                onClick={() => handleRowClick(row.original.op_id)}
              >
                {row.getVisibleCells().map((cell) => {
                  const meta = cell.column.columnDef.meta as
                    | { grow?: boolean }
                    | undefined;
                  return (
                    <td
                      key={cell.id}
                      className="px-4 py-3"
                      style={{
                        width: meta?.grow
                          ? undefined
                          : cell.column.getSize(),
                      }}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {table.getPageCount() > 1 && (
        <div className="flex-none border-t border-border">
          <Pagination table={table} />
        </div>
      )}
    </div>
  );
}
