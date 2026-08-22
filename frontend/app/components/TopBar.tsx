'use client';
import { useState, useEffect, useRef } from 'react';
import { SERVICE_LABELS, ServiceType } from '../lib/data';

interface ScrapeHistoryEntry {
  id: string;
  type: 'scrape';
  createdAt: string;
  jobId: string;
  niche: string;
  location: string;
  requested: number;
  scraped: number;
  status: string;
}

interface SegregationHistoryEntry {
  id: string;
  type: 'segregation';
  createdAt: string;
  jobId: string;
  sheetName: string;
  service: string;
  processedCount: number;
  status: string;
}

interface ExportHistoryEntry {
  id: string;
  type: 'export';
  createdAt: string;
  leadId: string;
  leadName: string;
  service: string;
  processedCount: number;
  format: string;
  status: string;
}

interface NotificationEntry {
  id: string;
  message: string;
  sheetId: string;
  timestamp: string;
  read: boolean;
}

export function TopBar() {
  const [showHistory, setShowHistory] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfile, setShowProfile] = useState(false);

  const [activeTab, setActiveTab] = useState<'scraping' | 'segregation' | 'exports'>('scraping');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);

  // History filter/sort state
  const [histFilterOpen, setHistFilterOpen] = useState(false);
  const [histSortField, setHistSortField] = useState<'none' | 'date' | 'leads' | 'status'>('none');
  const [histSortDir, setHistSortDir] = useState<'asc' | 'desc'>('desc');
  const [histStatusFilter, setHistStatusFilter] = useState<string[]>(['completed', 'failed', 'cancelled', 'partial', 'stopped_saved']);
  const histFilterRef = useRef<HTMLDivElement>(null);

  // History & Notifications lists
  const [scrapeHistory, setScrapeHistory] = useState<ScrapeHistoryEntry[]>([]);
  const [segregationHistory, setSegregationHistory] = useState<SegregationHistoryEntry[]>([]);
  const [exportHistory, setExportHistory] = useState<ExportHistoryEntry[]>([]);
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);

  // Selected history item for detail modal
  const [detailItem, setDetailItem] = useState<any>(null);

  // Refs for closing on click outside
  const historyRef = useRef<HTMLDivElement>(null);
  const notificationsRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  // Context menu states
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);

  const loadHistory = () => {
    if (typeof window !== 'undefined') {
      const scr = localStorage.getItem('lead_system_scrape_history');
      const seg = localStorage.getItem('lead_system_segregation_history');
      const exp = localStorage.getItem('lead_system_export_history');
      
      setScrapeHistory(scr ? JSON.parse(scr) : []);
      setSegregationHistory(seg ? JSON.parse(seg) : []);
      setExportHistory(exp ? JSON.parse(exp) : []);
    }
  };

  const loadNotifications = () => {
    if (typeof window !== 'undefined') {
      const notifs = localStorage.getItem('lead_system_notifications');
      setNotifications(notifs ? JSON.parse(notifs) : []);
    }
  };

  useEffect(() => {
    loadHistory();
    loadNotifications();

    const handleHistoryUpdate = () => loadHistory();
    const handleNotifUpdate = () => loadNotifications();

    window.addEventListener('history-updated', handleHistoryUpdate);
    window.addEventListener('notifications-updated', handleNotifUpdate);

    // Click outside handler
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (historyRef.current && !historyRef.current.contains(target)) setShowHistory(false);
      if (notificationsRef.current && !notificationsRef.current.contains(target)) setShowNotifications(false);
      if (profileRef.current && !profileRef.current.contains(target)) setShowProfile(false);
    };

    document.addEventListener('mousedown', handleClickOutside);

    const handleHistFilterOutside = (e: MouseEvent) => {
      if (histFilterRef.current && !histFilterRef.current.contains(e.target as Node)) {
        setHistFilterOpen(false);
      }
    };
    document.addEventListener('mousedown', handleHistFilterOutside);

    return () => {
      window.removeEventListener('history-updated', handleHistoryUpdate);
      window.removeEventListener('notifications-updated', handleNotifUpdate);
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('mousedown', handleHistFilterOutside);
    };
  }, []);



  const formatHistoryDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = String(d.getFullYear()).slice(-2);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${day}/${month}/${year} · ${hh}:${mm}`;
  };

  const handleMarkAllNotificationsAsRead = () => {
    const updated = notifications.map(n => ({ ...n, read: true }));
    setNotifications(updated);
    localStorage.setItem('lead_system_notifications', JSON.stringify(updated));
  };

  const handleDeleteNotification = (id: string) => {
    const updated = notifications.filter(n => n.id !== id);
    setNotifications(updated);
    localStorage.setItem('lead_system_notifications', JSON.stringify(updated));
  };

  const handleNotificationClick = (item: NotificationEntry) => {
    // Mark as read
    const updated = notifications.map(n => n.id === item.id ? { ...n, read: true } : n);
    setNotifications(updated);
    localStorage.setItem('lead_system_notifications', JSON.stringify(updated));
    setShowNotifications(false);
    
    // Redirect
    window.location.href = `/leads?highlight=${item.sheetId}`;
  };

  const hasUnreadNotifications = notifications.some(n => !n.read);

  // Search filter
  const q = searchQuery.toLowerCase().trim();

  const statusColor = (s: string) =>
    s === 'completed' ? '#10b981'
    : s === 'partial' ? '#6366f1'
    : s === 'cancelled' || s === 'stopped_saved' ? '#f59e0b'
    : '#ef4444';

  const applyHistSort = <T extends { createdAt: string; status: string }>(list: T[], countFn: (item: T) => number) => {
    let sorted = [...list];
    if (histStatusFilter.length < 5) {
      sorted = sorted.filter(i => histStatusFilter.includes(i.status));
    }
    if (histSortField === 'date') {
      sorted.sort((a, b) => histSortDir === 'asc'
        ? new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
        : new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      );
    } else if (histSortField === 'leads') {
      sorted.sort((a, b) => histSortDir === 'asc' ? countFn(a) - countFn(b) : countFn(b) - countFn(a));
    } else if (histSortField === 'status') {
      sorted.sort((a, b) => histSortDir === 'asc' ? a.status.localeCompare(b.status) : b.status.localeCompare(a.status));
    }
    return sorted;
  };

  const filteredScrapes = applyHistSort(
    scrapeHistory.filter(h =>
      !q || h.jobId.toLowerCase().includes(q) || h.niche.toLowerCase().includes(q) || h.location.toLowerCase().includes(q)
    ),
    i => i.scraped
  ) as ScrapeHistoryEntry[];

  const filteredSegregations = applyHistSort(
    segregationHistory.filter(h =>
      !q || h.jobId.toLowerCase().includes(q) || h.sheetName.toLowerCase().includes(q) || (SERVICE_LABELS[h.service as ServiceType] || h.service).toLowerCase().includes(q)
    ),
    i => i.processedCount
  ) as SegregationHistoryEntry[];

  const filteredExports = applyHistSort(
    exportHistory.filter(h =>
      !q || h.leadId.toLowerCase().includes(q) || h.leadName.toLowerCase().includes(q) || (SERVICE_LABELS[h.service as ServiceType] || h.service).toLowerCase().includes(q)
    ),
    i => i.processedCount
  ) as ExportHistoryEntry[];

  const histActiveFilterCount = (histSortField !== 'none' ? 1 : 0) + (histStatusFilter.length < 5 ? 1 : 0);

  const cycleHistSort = (field: typeof histSortField) => {
    if (histSortField !== field) { setHistSortField(field); setHistSortDir('desc'); }
    else if (histSortDir === 'desc') setHistSortDir('asc');
    else { setHistSortField('none'); setHistSortDir('desc'); }
  };

  const toggleHistStatus = (s: string) => {
    setHistStatusFilter(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);
  };

  return (
    <header style={{
      height: 'var(--topbar)', background: 'transparent',
      borderBottom: 'none',
      display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
      padding: '0 24px', gap: '12px', flexShrink: 0,
      position: 'relative', zIndex: 50
    }}>

      {/* ── History Button ── */}
      <div style={{ position: 'relative' }}>
        <IconBtn label="History" onClick={() => { setShowHistory(true); setShowNotifications(false); setShowProfile(false); }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
            <polyline points="3 3 3 8 8 8"/>
            <line x1="12" y1="7" x2="12" y2="12"/>
            <line x1="12" y1="12" x2="16" y2="14"/>
          </svg>
        </IconBtn>
      </div>

      {/* ── Full Screen History Modal ── */}
      {showHistory && (
        <div style={{ position: 'fixed', inset: 0, background: 'var(--bg-base)', zIndex: 1000, display: 'flex', flexDirection: 'column' }}>
          
          {/* Header */}
          <div style={{ padding: '20px 40px', borderBottom: '1px solid var(--border-faint)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-1)', margin: 0 }}>History</h2>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>

              {/* Expandable search */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: 'var(--bg-input)', border: `1px solid ${searchFocused ? 'var(--border-pink)' : 'var(--border-subtle)'}`,
                borderRadius: 'var(--r-md)', padding: '0 10px',
                width: searchFocused || searchQuery ? '240px' : '36px',
                height: 32, transition: 'width 0.25s ease, border-color 0.15s',
                overflow: 'hidden', cursor: 'text',
              }} onClick={() => { (document.getElementById('hist-search') as HTMLInputElement)?.focus(); }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2" style={{ flexShrink: 0 }}><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
                <input
                  id="hist-search"
                  type="text"
                  placeholder="Search history..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  onBlur={() => setSearchFocused(false)}
                  style={{ background: 'transparent', border: 'none', outline: 'none', color: 'var(--text-1)', fontSize: '12px', flex: 1, minWidth: 0 }}
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery('')} style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', padding: 0, fontSize: '14px', lineHeight: 1, flexShrink: 0 }}>×</button>
                )}
              </div>

              {/* Filter button */}
              <div ref={histFilterRef} style={{ position: 'relative' }}>
                <button
                  onClick={() => setHistFilterOpen(o => !o)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    height: 32, padding: '0 10px', borderRadius: 'var(--r-md)',
                    background: histFilterOpen || histActiveFilterCount > 0 ? 'var(--bg-active)' : 'var(--bg-input)',
                    border: `1px solid ${histActiveFilterCount > 0 ? 'var(--border-pink)' : 'var(--border-subtle)'}`,
                    color: histActiveFilterCount > 0 ? 'var(--pink)' : 'var(--text-2)',
                    fontSize: '12px', fontWeight: 500, cursor: 'pointer', transition: 'all var(--ease)',
                  }}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="22,3 2,3 10,12.46 10,19 14,21 14,12.46 22,3"/></svg>
                  Filter
                  {histActiveFilterCount > 0 && (
                    <span style={{ background: 'var(--pink)', color: '#fff', borderRadius: 'var(--r-pill)', fontSize: '10px', fontWeight: 700, padding: '1px 5px', lineHeight: '14px' }}>
                      {histActiveFilterCount}
                    </span>
                  )}
                </button>

                {histFilterOpen && (
                  <div style={{
                    position: 'absolute', right: 0, top: 'calc(100% + 8px)',
                    width: 220, background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)',
                    boxShadow: 'var(--shadow-drop)', zIndex: 300, overflow: 'hidden',
                  }}>
                    {/* Sort */}
                    <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border-faint)' }}>
                      <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.07em', marginBottom: 8 }}>Sort By</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {([{ key: 'date', label: 'Date' }, { key: 'leads', label: 'Leads Count' }, { key: 'status', label: 'Status' }] as const).map(opt => {
                          const active = histSortField === opt.key;
                          return (
                            <button key={opt.key} onClick={() => cycleHistSort(opt.key)} style={{
                              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              width: '100%', padding: '7px 10px', borderRadius: 'var(--r-sm)',
                              fontSize: '12px', cursor: 'pointer', border: 'none',
                              background: active ? 'var(--bg-active)' : 'transparent',
                              color: active ? 'var(--pink)' : 'var(--text-2)',
                              fontWeight: active ? 600 : 400, transition: 'background var(--ease)',
                            }}
                            onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'var(--bg-hover)'; }}
                            onMouseLeave={e => { if (!active) e.currentTarget.style.background = active ? 'var(--bg-active)' : 'transparent'; }}
                            >
                              <span>{opt.label}</span>
                              {active && <span style={{ fontSize: '11px', opacity: 0.8 }}>{histSortDir === 'desc' ? '↓ New' : '↑ Old'}</span>}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                    {/* Status filter */}
                    <div style={{ padding: '12px 14px' }}>
                      <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.07em', marginBottom: 8 }}>Filter by Status</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {(['completed', 'partial', 'failed', 'cancelled', 'stopped_saved'] as const).map(s => (
                          <label key={s} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 4px', fontSize: '12px', color: 'var(--text-2)', cursor: 'pointer' }}>
                            <input type="checkbox" checked={histStatusFilter.includes(s)} onChange={() => toggleHistStatus(s)} style={{ accentColor: 'var(--pink)', width: 13, height: 13 }} />
                            <span style={{ textTransform: 'capitalize' }}>{s.replace('_', ' ')}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                    {/* Reset */}
                    {histActiveFilterCount > 0 && (
                      <div style={{ padding: '8px 14px', borderTop: '1px solid var(--border-faint)', display: 'flex', justifyContent: 'flex-end' }}>
                        <button onClick={() => { setHistSortField('none'); setHistSortDir('desc'); setHistStatusFilter(['completed', 'failed', 'cancelled', 'partial', 'stopped_saved']); }} style={{ background: 'none', border: 'none', fontSize: '11px', color: 'var(--pink)', fontWeight: 600, cursor: 'pointer', padding: 0 }}>Reset</button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* X close */}
              <button
                onClick={() => setShowHistory(false)}
                title="Close"
                style={{
                  width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  borderRadius: 'var(--r-md)', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)',
                  color: 'var(--text-3)', fontSize: '18px', cursor: 'pointer', transition: 'all var(--ease)', flexShrink: 0,
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(200,9,171,0.08)'; e.currentTarget.style.color = 'var(--pink)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-input)'; e.currentTarget.style.color = 'var(--text-3)'; }}
              >
                ×
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--border-faint)', padding: '0 40px' }}>
            {(['scraping', 'segregation', 'exports'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => { setActiveTab(tab); setActiveMenuId(null); }}
                style={{
                  padding: '14px 28px', fontSize: '12px', fontWeight: 600,
                  textTransform: 'uppercase', letterSpacing: '0.05em',
                  color: activeTab === tab ? 'var(--pink)' : 'var(--text-3)',
                  borderTop: 'none', borderLeft: 'none', borderRight: 'none',
                  borderBottom: activeTab === tab ? '2px solid var(--pink)' : '2px solid transparent',
                  background: 'none', cursor: 'pointer', transition: 'color 0.2s',
                }}
                onMouseEnter={e => { if (activeTab !== tab) e.currentTarget.style.color = 'var(--text-2)'; }}
                onMouseLeave={e => { if (activeTab !== tab) e.currentTarget.style.color = 'var(--text-3)'; }}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* List — table-like, full width */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '20px 40px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0, border: '1px solid var(--border-faint)', borderRadius: 'var(--r-lg)', overflow: 'hidden', background: 'var(--bg-surface)' }}>

              {/* Column header */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 160px 120px 100px 36px', gap: 0, padding: '8px 20px', borderBottom: '1px solid var(--border-faint)', background: 'var(--bg-nav)' }}>
                {['Name', 'Location / Service', 'Date', 'Status / Leads', ''].map(c => (
                  <span key={c} style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.07em' }}>{c}</span>
                ))}
              </div>

              {activeTab === 'scraping' && (
                filteredScrapes.length === 0 ? (
                  <div style={emptyStyle}>No scraping history yet.</div>
                ) : (
                  filteredScrapes.map((item, i) => (
                    <div key={item.id} style={{
                      display: 'grid', gridTemplateColumns: '1fr 160px 120px 100px 36px',
                      alignItems: 'center', padding: '12px 20px',
                      borderBottom: i < filteredScrapes.length - 1 ? '1px solid var(--border-faint)' : 'none',
                      transition: 'background var(--ease)',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>Scrape: {item.niche}</span>
                      <span style={{ fontSize: '12px', color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.location}</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-3)', whiteSpace: 'nowrap' }}>{formatHistoryDate(item.createdAt)}</span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: '10px', color: statusColor(item.status), textTransform: 'uppercase', fontWeight: 700 }}>{item.status}</span>
                        <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>{item.scraped}/{item.requested}</span>
                      </div>
                      <ThreeDot historyId={item.id} activeId={activeMenuId} setActiveId={setActiveMenuId} actions={[
                        { label: 'View Details', onClick: () => setDetailItem(item) },
                        { label: 'View Lead Sheet', onClick: () => { window.location.href = `/operations?highlight=${item.jobId}`; setShowHistory(false); } }
                      ]} />
                    </div>
                  ))
                )
              )}

              {activeTab === 'segregation' && (
                filteredSegregations.length === 0 ? (
                  <div style={emptyStyle}>No segregation history yet.</div>
                ) : (
                  filteredSegregations.map((item, i) => (
                    <div key={item.id} style={{
                      display: 'grid', gridTemplateColumns: '1fr 160px 120px 100px 36px',
                      alignItems: 'center', padding: '12px 20px',
                      borderBottom: i < filteredSegregations.length - 1 ? '1px solid var(--border-faint)' : 'none',
                      transition: 'background var(--ease)',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>Segregate: {item.sheetName}</span>
                      <span style={{ fontSize: '12px', color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{SERVICE_LABELS[item.service as ServiceType] || item.service}</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-3)', whiteSpace: 'nowrap' }}>{formatHistoryDate(item.createdAt)}</span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: '10px', color: statusColor(item.status), textTransform: 'uppercase', fontWeight: 700 }}>{item.status}</span>
                        <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>{item.processedCount} leads</span>
                      </div>
                      <ThreeDot historyId={item.id} activeId={activeMenuId} setActiveId={setActiveMenuId} actions={[
                        { label: 'View Details', onClick: () => setDetailItem(item) },
                        { label: 'View Leads', onClick: () => { window.location.href = `/leads?highlight=${item.jobId}`; setShowHistory(false); } }
                      ]} />
                    </div>
                  ))
                )
              )}

              {activeTab === 'exports' && (
                filteredExports.length === 0 ? (
                  <div style={emptyStyle}>No export history yet.</div>
                ) : (
                  filteredExports.map((item, i) => (
                    <div key={item.id} style={{
                      display: 'grid', gridTemplateColumns: '1fr 160px 120px 100px 36px',
                      alignItems: 'center', padding: '12px 20px',
                      borderBottom: i < filteredExports.length - 1 ? '1px solid var(--border-faint)' : 'none',
                      transition: 'background var(--ease)',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>Export: {item.leadName}</span>
                      <span style={{ fontSize: '12px', color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{SERVICE_LABELS[item.service as ServiceType] || item.service}</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-3)', whiteSpace: 'nowrap' }}>{formatHistoryDate(item.createdAt)}</span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: '10px', color: 'var(--pink)', fontWeight: 700 }}>{item.format}</span>
                        <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>{item.processedCount} leads</span>
                      </div>
                      <ThreeDot historyId={item.id} activeId={activeMenuId} setActiveId={setActiveMenuId} actions={[
                        { label: 'View Details', onClick: () => setDetailItem(item) },
                        { label: 'Download Again', onClick: () => {
                          const headers = ['Lead ID','Business','Location','Website','Phone','Priority Score','Status'];
                          const csv = [headers.join(',')].join('\n');
                          const blob = new Blob([csv], {type:'text/csv'});
                          const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${item.leadName}.csv`; a.click();
                        }}
                      ]} />
                    </div>
                  ))
                )
              )}

            </div>
          </div>
        </div>
      )}

      {/* ── Notifications Button & Popover ── */}
      <div ref={notificationsRef} style={{ position: 'relative' }}>
        <IconBtn label="Notifications" onClick={() => { setShowNotifications(!showNotifications); setShowHistory(false); setShowProfile(false); }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>
            <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>
          </svg>
        </IconBtn>
        {hasUnreadNotifications && (
          <span style={{
            position: 'absolute', top: '6px', right: '6px',
            width: '6px', height: '6px', background: 'var(--pink)',
            borderRadius: '50%', border: '1.5px solid var(--bg-surface)',
          }} />
        )}

        {showNotifications && (
          <div style={{ ...popoverStyle, width: '280px' }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-faint)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-1)' }}>Notifications</span>
              {hasUnreadNotifications && (
                <button onClick={handleMarkAllNotificationsAsRead} style={{ background: 'none', border: 'none', color: 'var(--pink)', fontSize: '11px', fontWeight: 600, cursor: 'pointer' }}>
                  Mark all read
                </button>
              )}
            </div>
            <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
              {notifications.length === 0 ? (
                <div style={emptyStyle}>No notifications.</div>
              ) : (
                notifications.map(item => (
                  <div key={item.id} onClick={() => handleNotificationClick(item)} style={{
                    padding: '12px 16px', borderBottom: '1px solid var(--border-faint)',
                    background: item.read ? 'transparent' : 'rgba(236,72,153,0.04)',
                    transition: 'background 0.2s', cursor: 'pointer'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <p style={{ fontSize: '12px', color: 'var(--text-1)', marginBottom: 8, lineHeight: 1.4, flex: 1 }}>{item.message}</p>
                      <button onClick={(e) => { e.stopPropagation(); handleDeleteNotification(item.id); }} style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', padding: 0, fontSize: '14px', lineHeight: 1 }}>×</button>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '10px', color: 'var(--text-3)' }}>Just now</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Profile Dropdown ── */}
      <div ref={profileRef} style={{ position: 'relative' }}>
        <div
          onClick={() => { setShowProfile(!showProfile); setShowHistory(false); setShowNotifications(false); }}
          style={{
            display: 'flex', alignItems: 'center', gap: '7px',
            padding: '4px 8px', borderRadius: 'var(--r-md)', cursor: 'pointer',
            transition: 'background var(--ease)',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'var(--bg-hover)'; }}
          onMouseLeave={e => { if(!showProfile) (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
        >
          <div style={{
            width: '30px', height: '30px', borderRadius: '50%',
            background: 'linear-gradient(135deg,#ec4899,#a855f7)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '12px', fontWeight: 700, color: '#fff',
          }}>A</div>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2" style={{ transform: showProfile ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
            <polyline points="6,9 12,15 18,9"/>
          </svg>
        </div>

        {showProfile && (
          <div style={{ ...popoverStyle, width: '160px', top: '100%', right: 0, marginTop: '8px' }}>
            {['Profile', 'Account Settings', 'Sign Out'].map((item, i) => (
              <button
                key={item}
                onClick={() => {
                  setShowProfile(false);
                  if (item === 'Sign Out') alert('Signing out...');
                  else alert(`Navigating to ${item}...`);
                }}
                style={{
                  width: '100%', padding: '10px 16px', textAlign: 'left',
                  fontSize: '12px', color: i === 2 ? 'var(--pink)' : 'var(--text-2)',
                  fontWeight: i === 2 ? 600 : 500,
                  background: 'none', border: 'none', cursor: 'pointer',
                  borderBottom: i < 2 ? '1px solid var(--border-faint)' : 'none',
                  transition: 'background 0.2s'
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                {item}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Compact History Details Modal ── */}
      {detailItem && (
        <>
          <div onClick={() => setDetailItem(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.75)', backdropFilter: 'blur(4px)', zIndex: 1000 }} />
          <div style={{
            position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
            width: '380px', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--r-xl)', zIndex: 1001, padding: '24px', boxShadow: 'var(--shadow-drop)'
          }}>
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-1)', marginBottom: 16 }}>Activity Details</h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
              <div style={detailRowStyle}>
                <span style={detailLabelStyle}>Type:</span>
                <span style={{ ...detailValueStyle, textTransform: 'capitalize', fontWeight: 700, color: 'var(--pink)' }}>{detailItem.type}</span>
              </div>
              <div style={detailRowStyle}>
                <span style={detailLabelStyle}>Date & Time:</span>
                <span style={detailValueStyle}>{formatHistoryDate(detailItem.createdAt)}</span>
              </div>
              
              {detailItem.type === 'scrape' && (
                <>
                  <div style={detailRowStyle}>
                    <span style={detailLabelStyle}>Niche:</span>
                    <span style={detailValueStyle}>{detailItem.niche}</span>
                  </div>
                  <div style={detailRowStyle}>
                    <span style={detailLabelStyle}>Location:</span>
                    <span style={detailValueStyle}>{detailItem.location}</span>
                  </div>
                  <div style={detailRowStyle}>
                    <span style={detailLabelStyle}>Result Count:</span>
                    <span style={detailValueStyle}>{detailItem.scraped} / {detailItem.requested} leads</span>
                  </div>
                </>
              )}

              {detailItem.type === 'segregation' && (
                <>
                  <div style={detailRowStyle}>
                    <span style={detailLabelStyle}>Sheet Name:</span>
                    <span style={detailValueStyle}>{detailItem.sheetName}</span>
                  </div>
                  <div style={detailRowStyle}>
                    <span style={detailLabelStyle}>Service:</span>
                    <span style={detailValueStyle}>{SERVICE_LABELS[detailItem.service as ServiceType] || detailItem.service}</span>
                  </div>
                  <div style={detailRowStyle}>
                    <span style={detailLabelStyle}>Processed:</span>
                    <span style={detailValueStyle}>{detailItem.processedCount} leads</span>
                  </div>
                </>
              )}

              {detailItem.type === 'export' && (
                <>
                  <div style={detailRowStyle}>
                    <span style={detailLabelStyle}>Lead Sheet:</span>
                    <span style={detailValueStyle}>{detailItem.leadName}</span>
                  </div>
                  <div style={detailRowStyle}>
                    <span style={detailLabelStyle}>Service:</span>
                    <span style={detailValueStyle}>{SERVICE_LABELS[detailItem.service as ServiceType] || detailItem.service}</span>
                  </div>
                  <div style={detailRowStyle}>
                    <span style={detailLabelStyle}>Leads Count:</span>
                    <span style={detailValueStyle}>{detailItem.processedCount} leads</span>
                  </div>
                  <div style={detailRowStyle}>
                    <span style={detailLabelStyle}>Format:</span>
                    <span style={detailValueStyle}>{detailItem.format}</span>
                  </div>
                </>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setDetailItem(null)} className="btn btn-pink" style={{ padding: '8px 20px', fontSize: '12px' }}>
                Close
              </button>
            </div>
          </div>
        </>
      )}

    </header>
  );
}

function ThreeDot({ historyId, activeId, setActiveId, actions }: { historyId: string; activeId: string | null; setActiveId: (id: string | null) => void; actions: { label: string; onClick: () => void }[] }) {
  const isOpen = activeId === historyId;
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const click = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setActiveId(null);
      }
    };
    document.addEventListener('mousedown', click);
    return () => document.removeEventListener('mousedown', click);
  }, [isOpen]);

  return (
    <div ref={menuRef} style={{ position: 'relative' }}>
      <button
        onClick={e => { e.stopPropagation(); setActiveId(isOpen ? null : historyId); }}
        style={{
          background: 'none', border: 'none', color: 'var(--text-3)', fontSize: '16px',
          fontWeight: 'bold', cursor: 'pointer', padding: '0 6px', display: 'flex',
          alignItems: 'center', justifyContent: 'center', height: '24px', width: '24px',
          borderRadius: '4px'
        }}
        onMouseEnter={e => e.currentTarget.style.color = 'var(--text-1)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--text-3)'}
      >
        ⋮
      </button>

      {isOpen && (
        <div style={{
          position: 'absolute', right: 0, top: '24px', width: '130px',
          background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-md)', overflow: 'hidden', boxShadow: 'var(--shadow-drop)',
          zIndex: 100
        }}>
          {actions.map(act => (
            <button
              key={act.label}
              onClick={() => { act.onClick(); setActiveId(null); }}
              style={{
                width: '100%', padding: '8px 12px', textAlign: 'left', fontSize: '11px',
                color: 'var(--text-2)', background: 'none', border: 'none', cursor: 'pointer',
                transition: 'background 0.2s', display: 'block'
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              {act.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function IconBtn({ label, children, onClick }: { label: string; children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      style={{
        width: '32px', height: '32px', display: 'flex', alignItems: 'center',
        justifyContent: 'center', borderRadius: 'var(--r-md)', color: 'var(--text-3)',
        transition: 'background var(--ease), color var(--ease)',
        background: 'none', border: 'none', cursor: 'pointer'
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-hover)';
        (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-1)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
        (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-3)';
      }}
    >
      {children}
    </button>
  );
}

const popoverStyle: React.CSSProperties = {
  position: 'absolute', top: '100%', right: 0, width: '320px',
  background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--r-xl)', boxShadow: 'var(--shadow-drop)',
  marginTop: '8px', overflow: 'hidden', display: 'flex', flexDirection: 'column',
  zIndex: 100
};

const searchInputStyle = {
  width: '100%', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--r-md)', padding: '6px 10px', fontSize: '12px', color: 'var(--text-1)',
  outline: 'none'
};

const emptyStyle = {
  padding: '24px', textAlign: 'center' as const, fontSize: '12px', color: 'var(--text-3)',
  lineHeight: '1.6'
};

const historyItemStyle = {
  padding: '12px 16px', borderBottom: '1px solid var(--border-faint)',
  display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10
};

const detailRowStyle = {
  display: 'flex', justifyContent: 'space-between', fontSize: '12px', borderBottom: '1px solid var(--border-faint)', paddingBottom: '8px'
};

const detailLabelStyle = {
  color: 'var(--text-3)'
};

const detailValueStyle = {
  color: 'var(--text-1)'
};
