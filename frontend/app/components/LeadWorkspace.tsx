"use client";

import { LeadCollectionRow } from "./LeadCollectionRow";

interface LeadWorkspaceProps {
  items: any[];
  onDoubleClickRow: (item: any) => void;
  onRename: (id: string, newName: string) => void;
  onExportAs: (id: string, format: string) => void;
  onShowDetails: (item: any) => void;
  onEdit: (item: any) => void;
  onDelete: (id: string) => void;
}

export function LeadWorkspace({
  items,
  onDoubleClickRow,
  onRename,
  onExportAs,
  onShowDetails,
  onEdit,
  onDelete,
}: LeadWorkspaceProps) {
  return (
    <div className="lead-workspace-card">
      <div className="lead-table-header">
        <div>Lead ID</div>
        <div>Name</div>
        <div>Date</div>
        <div>Leads count</div>
        <div></div> {/* Removed colon ':' header symbol */}
      </div>

      {items.length === 0 ? (
        <div style={{ textAlign: "center", padding: "24px", color: "var(--text-muted)", fontSize: "0.9rem" }}>
          No lead collections found. Click "Start scraping" to launch a job.
        </div>
      ) : (
        items.map((item) => (
          <LeadCollectionRow
            key={item.id || item.sheetId}
            sheet={item}
            onClick={() => onDoubleClickRow(item)}
          />
        ))
      )}
    </div>
  );
}
