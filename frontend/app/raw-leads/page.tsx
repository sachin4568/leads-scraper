'use client';

import { useState, useMemo, useEffect } from 'react';
import { LeadSheet } from '../lib/data';
import { api } from '../lib/api';
import { LeadCollectionRow } from '../components/LeadCollectionRow';
import { LeadSheetModal } from '../components/LeadSheetModal';
import { SearchBar } from '../components/SearchBar';

type Tab = 'leads' | 'genuines' | 'priority';

export default function LeadsPage() {
  const [sheets, setSheets] = useState<LeadSheet[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('leads');
  const [search, setSearch] = useState('');
  const [selectedSheet, setSelectedSheet] = useState<LeadSheet | null>(null);

  useEffect(() => {
    api.getSheets()
      .then(data => {
        setSheets(data || []);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setSheets([]);
        setLoading(false);
      });
  }, []);

  const totalLeads = sheets.reduce((a, s) => a + s.leads.length, 0);
  const genuinesCount = sheets.reduce((a, s) => a + s.leads.filter(l => l.genuineness >= 90).length, 0);
  const priorityCount = sheets.reduce((a, s) => a + s.leads.filter(l => (l.priorityScore || 0) >= 70).length, 0);

  const displayedSheets = useMemo(() => {
    let list = [...sheets];
    if (activeTab === 'genuines') {
      list = list.map(s => ({ ...s, leads: s.leads.filter(l => l.genuineness >= 90) })).filter(s => s.leads.length > 0);
    } else if (activeTab === 'priority') {
      list = list.map(s => ({ ...s, leads: s.leads.filter(l => (l.priorityScore || 0) >= 70) })).filter(s => s.leads.length > 0);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(s =>
        s.name.toLowerCase().includes(q) ||
        (s.service || '').toLowerCase().includes(q) ||
        s.leads.some(l => l.businessName.toLowerCase().includes(q) || l.location.toLowerCase().includes(q))
      );
    }
    return list;
  }, [sheets, activeTab, search]);

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: 'leads',    label: 'Leads',    count: totalLeads },
    { key: 'genuines', label: 'Genuines', count: genuinesCount },
    { key: 'priority', label: 'Priority', count: priorityCount },
  ];

  if (loading) {
    return (
      <div>
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>Dashboard</h1>
        </div>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Loading lead collections...</p>
      </div>
    );
  }

  return (
    <div>
      {/* Page title */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>Dashboard</h1>
      </div>

      {/* Leads header */}
      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-xl)',
        overflow: 'hidden',
      }}>
        {/* Tab bar + actions */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '18px 24px 0',
          borderBottom: '1px solid var(--border-subtle)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <h2 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginRight: '16px' }}>
              Leads
            </h2>
            {tabs.map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '7px',
                  padding: '8px 14px',
                  borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
                  fontSize: '13px',
                  fontWeight: activeTab === tab.key ? 600 : 400,
                  color: activeTab === tab.key ? 'var(--text-primary)' : 'var(--text-muted)',
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === tab.key ? '2px solid var(--pink-primary)' : '2px solid transparent',
                  cursor: 'pointer',
                  transition: 'color var(--transition)',
                  marginBottom: '-1px',
                }}
              >
                {tab.label}
                <span style={{
                  background: activeTab === tab.key ? 'var(--pink-primary)' : 'var(--bg-glass)',
                  color: activeTab === tab.key ? '#fff' : 'var(--text-muted)',
                  fontSize: '10px',
                  fontWeight: 700,
                  padding: '2px 6px',
                  borderRadius: 'var(--radius-pill)',
                  minWidth: '20px',
                  textAlign: 'center',
                }}>
                  {tab.count}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Search */}
        <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border-subtle)' }}>
          <SearchBar value={search} onChange={setSearch} placeholder="Search lead collections..." />
        </div>

        {/* Table */}
        <div style={{ overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                {['Sheet / Collection', 'Total Leads', 'Sources', 'Warm Rate', 'Avg Score', 'Assigned To', 'Date Added', ''].map(col => (
                  <th key={col} style={{
                    padding: '10px 18px',
                    fontSize: '11px',
                    fontWeight: 600,
                    color: 'var(--text-muted)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    textAlign: 'left',
                    whiteSpace: 'nowrap',
                    background: 'var(--bg-surface)',
                  }}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayedSheets.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{
                    padding: '60px', textAlign: 'center',
                    color: 'var(--text-muted)', fontSize: '14px',
                  }}>
                    No verified leads found.
                  </td>
                </tr>
              ) : (
                displayedSheets.map((sheet, i) => (
                  <LeadCollectionRow
                    key={sheet.id}
                    sheet={sheet}
                    onClick={() => setSelectedSheet(sheet)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div style={{
          padding: '14px 24px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {displayedSheets.length} collection{displayedSheets.length !== 1 ? 's' : ''} ·{' '}
            {displayedSheets.reduce((a, s) => a + s.leads.length, 0)} total leads
          </span>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Click any row to view individual leads
          </span>
        </div>
      </div>

      {/* Sheet modal */}
      {selectedSheet && (
        <LeadSheetModal
          sheet={selectedSheet}
          onClose={() => setSelectedSheet(null)}
        />
      )}
    </div>
  );
}
