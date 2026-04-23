"use client";

import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";

import type { Finding } from "@/features/dashboard/types";

type Props = {
  data: Finding[];
};

export function FindingsTable(props: Props) {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("");

  const columns = useMemo<ColumnDef<Finding>[]>(
    () => [
      { accessorKey: "rule_code", header: "Rule" },
      { accessorKey: "severity", header: "Severity" },
      { accessorKey: "level", header: "Level" },
      { accessorKey: "status", header: "Status" },
      { accessorKey: "issue_location", header: "Location" },
      {
        accessorKey: "suspected_sabotage",
        header: "Sabotage",
        cell: (ctx) => (ctx.getValue<boolean>() ? "yes" : "no"),
      },
      {
        accessorKey: "created_at",
        header: "Created",
        cell: (ctx) => new Date(ctx.getValue<string>()).toLocaleString("ru-RU"),
      },
    ],
    []
  );

  const filteredData = useMemo(() => {
    return props.data.filter((item) => {
      if (statusFilter && item.status !== statusFilter) return false;
      if (severityFilter && item.severity !== severityFilter) return false;
      return true;
    });
  }, [props.data, severityFilter, statusFilter]);

  const table = useReactTable({
    data: filteredData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <select
          className="rounded border px-2 py-1 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">all statuses</option>
          <option value="new">new</option>
          <option value="existing">existing</option>
          <option value="fixed">fixed</option>
          <option value="reopened">reopened</option>
        </select>
        <select
          className="rounded border px-2 py-1 text-sm"
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
        >
          <option value="">all severities</option>
          <option value="warning">warning</option>
          <option value="high">high</option>
          <option value="critical">critical</option>
        </select>
      </div>
      <div className="overflow-x-auto rounded border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th key={header.id} className="px-3 py-2 text-left">
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="border-t">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2">
                    {cell.column.columnDef.cell
                      ? flexRender(cell.column.columnDef.cell, cell.getContext())
                      : String(cell.getValue() ?? "")}
                  </td>
                ))}
              </tr>
            ))}
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td className="px-3 py-6 text-muted-foreground" colSpan={columns.length}>
                  No findings yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
