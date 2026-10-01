'use client';
import { useState, useMemo, useEffect, useRef } from 'react';
import { LeadSheet, SERVICE_LABELS } from '../lib/data';
import { api } from '../lib/api';
import { LeadSheetModal } from '../components/LeadSheetModal';
import { SheetDetailsModal } from '../components/SheetDetailsModal';
import { EditSheetModal } from '../components/EditSheetModal';
import { ThreeDotMenu } from '../components/ThreeDotMenu';

const I = {
  info:   <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>,
  edit:   <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>,
  trash:  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3,6 5,6 21,6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>,
  filter: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="22,3 2,3 10,12.46 10,19 14,21 14,12.46 22,3"/></svg>,
  plus:   <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
};

const formatDate = (dateStr: string) => {
  const d = new Date(dateStr);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = String(d.getFullYear()).slice(-2);
  return `${day}/${month}/${day === 'NaN' || month === 'NaN' ? '26' : year}`;
};

const getCountryRegion = (sheet: any) => {
  if (sheet.country_region) return sheet.country_region;
  if (sheet.region && sheet.country) return `${sheet.region}, ${sheet.country}`;
  if (sheet.country) return sheet.country;
  if (sheet.region) return sheet.region;
  return '—';
};

export default function LeadsPage() {
  const [sheets, setSheets] = useState<LeadSheet[]>([]);
  const [search, setSearch] = useState('');
  const [openSheet, setOpenSheet]         = useState<LeadSheet|null>(null);
  const [openFullScreen, setOpenFullScreen] = useState<boolean>(false);
  const [detailSheet, setDetailSheet]     = useState<LeadSheet|null>(null);
  const [editSheet, setEditSheet]         = useState<LeadSheet|null>(null);

  // Filter & Sort state
  const [sortField, setSortField] = useState<'none' | 'name' | 'sheetId' | 'leadCount'>('none');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [filterServices, setFilterServices] = useState<string[]>(['website_dev', 'seo', 'smma', 'social_media']);
  const [filterOpen, setFilterOpen] = useState(false);
  const filterRef = useRef<HTMLDivElement>(null);

  // Keep old sortOrder alias for backwards-compat with existing memo
  const sortOrder = sortField === 'name' ? (sortDir === 'asc' ? 'asc' : 'desc') : 'none';

  const [highlightId, setHighlightId] = useState<string | null>(null);

  // Load from backend
  const loadSheets = () => {
    api.getSheets()
      .then(data => {
        setSheets((data as any) || []);
      })
      .catch(err => {
        console.error(err);
        setSheets([]);
      });
  };

  useEffect(() => {
    loadSheets();
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const hl = new URLSearchParams(window.location.search).get('highlight');
      if (hl) {
        setHighlightId(hl);
        const newUrl = window.location.pathname;
        window.history.replaceState({}, '', newUrl);
        setTimeout(() => setHighlightId(null), 3500);
      }
    }
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(e.target as Node)) {
        setFilterOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const deleteSheet = async (id: string) => {
    try {
      await api.deleteSheet(id);
      loadSheets();
    } catch (e) {
      console.error(e);
    }
  };

  const saveSheet = async (id: string, name: string, url: string) => {
    try {
      await api.updateSheet(id, { name, googleSheetsUrl: url });
      loadSheets();
    } catch (e) {
      console.error(e);
    }
  };

  const cycleSort = (field: typeof sortField) => {
    if (sortField !== field) {
      setSortField(field);
      setSortDir('asc');
    } else if (sortDir === 'asc') {
      setSortDir('desc');
    } else {
      setSortField('none');
      setSortDir('asc');
    }
  };

  const displayed = useMemo(() => {
    let list = [...sheets];
    list = list.filter(s => filterServices.includes(s.service));

    if (sortField === 'name') {
      list.sort((a, b) => sortDir === 'asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
    } else if (sortField === 'sheetId') {
      list.sort((a, b) => sortDir === 'asc' ? a.sheetId.localeCompare(b.sheetId) : b.sheetId.localeCompare(a.sheetId));
    } else if (sortField === 'leadCount') {
      list.sort((a, b) => sortDir === 'asc' ? a.leads.length - b.leads.length : b.leads.length - a.leads.length);
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(s =>
        s.name.toLowerCase().includes(q) ||
        s.sheetId.toLowerCase().includes(q) ||
        s.niches.some(n => n.toLowerCase().includes(q))
      );
    }
    return list;
  }, [sheets, filterServices, sortField, sortDir, search]);

  const toggleService = (srv: string) => {
    setFilterServices(prev =>
      prev.includes(srv) ? prev.filter(x => x !== srv) : [...prev, srv]
    );
  };

  const activeFilterCount = (sortField !== 'none' ? 1 : 0) + (filterServices.length < 4 ? 1 : 0);


  return (
    <div style={{ height: 'calc(100vh - var(--topbar) - 56px)', display: 'flex', flexDirection: 'column' }}>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background:'var(--bg-surface)',border:'1px solid var(--border-faint)',borderRadius:'var(--r-2xl)',overflow:'hidden' }}>

        {/* ── Tab bar ── */}
        <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',padding:'14px 24px',borderBottom:'1px solid var(--border-faint)',flexShrink:0 }}>
          <span style={{ fontSize:'14px',fontWeight:700,color:'var(--text-1)' }}>Lead Collections</span>

          {/* Filter Button + Dropdown */}
          <div ref={filterRef} style={{ position:'relative' }}>
            <button
              onClick={() => setFilterOpen(o => !o)}
              style={{
                display:'flex', alignItems:'center', gap:6,
                height:32, padding:'0 12px', borderRadius:'var(--r-md)',
                background: filterOpen || activeFilterCount > 0 ? 'var(--bg-active)' : 'var(--bg-input)',
                border:`1px solid ${activeFilterCount > 0 ? 'var(--border-pink)' : 'var(--border-subtle)'}`,
                color: activeFilterCount > 0 ? 'var(--pink)' : 'var(--text-2)',
                fontSize:'12px', fontWeight:500, cursor:'pointer',
                transition:'all var(--ease)',
              }}
            >
              {I.filter}
              Filter &amp; Sort
              {activeFilterCount > 0 && (
                <span style={{
                  background:'var(--pink)', color:'#fff',
                  borderRadius:'var(--r-pill)', fontSize:'10px',
                  fontWeight:700, padding:'1px 5px', lineHeight:'14px'
                }}>
                  {activeFilterCount}
                </span>
              )}
            </button>

            {filterOpen && (
              <div
                onClick={e => e.stopPropagation()}
                style={{
                  position:'absolute', right:0, top:'calc(100% + 8px)',
                  width:'240px',
                  background:'var(--bg-card)',
                  border:'1px solid var(--border-subtle)',
                  borderRadius:'var(--r-lg)',
                  boxShadow:'var(--shadow-drop)',
                  zIndex:200, overflow:'hidden',
                }}
              >
                {/* Sort section */}
                <div style={{ padding:'12px 14px', borderBottom:'1px solid var(--border-faint)' }}>
                  <div style={{ fontSize:'10px',fontWeight:700,color:'var(--text-4)',textTransform:'uppercase',letterSpacing:'.07em',marginBottom:8 }}>Sort By</div>
                  <div style={{ display:'flex', flexDirection:'column', gap:2 }}>
                    {([
                      { key:'name',      label:'Lead Name' },
                      { key:'sheetId',   label:'Lead ID' },
                      { key:'leadCount', label:'Leads Count' },
                    ] as const).map(opt => {
                      const active = sortField === opt.key;
                      return (
                        <button
                          key={opt.key}
                          onClick={() => cycleSort(opt.key)}
                          style={{
                            display:'flex', alignItems:'center', justifyContent:'space-between',
                            width:'100%', padding:'7px 10px', borderRadius:'var(--r-sm)',
                            fontSize:'12px', cursor:'pointer', border:'none',
                            background: active ? 'var(--bg-active)' : 'transparent',
                            color: active ? 'var(--pink)' : 'var(--text-2)',
                            fontWeight: active ? 600 : 400,
                            transition:'background var(--ease)',
                          }}
                          onMouseEnter={e => { if (!active) e.currentTarget.style.background='var(--bg-hover)'; }}
                          onMouseLeave={e => { if (!active) e.currentTarget.style.background='transparent'; }}
                        >
                          <span>{opt.label}</span>
                          {active && (
                            <span style={{ fontSize:'11px', opacity:0.8 }}>
                              {sortDir === 'asc' ? '↑ A–Z' : '↓ Z–A'}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Filter by Service */}
                <div style={{ padding:'12px 14px' }}>
                  <div style={{ fontSize:'10px',fontWeight:700,color:'var(--text-4)',textTransform:'uppercase',letterSpacing:'.07em',marginBottom:8 }}>Filter by Service</div>
                  <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
                    {([
                      { key:'website_dev',  label:'Website Development' },
                      { key:'seo',          label:'SEO' },
                      { key:'smma',         label:'Social Media Mgmt.' },
                      { key:'social_media', label:'Social Media Mktg.' },
                    ] as const).map(svc => {
                      const active = filterServices.includes(svc.key);
                      return (
                        <label
                          key={svc.key}
                          style={{ display:'flex', alignItems:'center', gap:8, padding:'5px 4px', cursor:'pointer', borderRadius:'var(--r-sm)', fontSize:'12px', color:'var(--text-2)' }}
                        >
                          <input
                            type="checkbox"
                            checked={active}
                            onChange={() => toggleService(svc.key)}
                            style={{ accentColor:'var(--pink)', width:13, height:13 }}
                          />
                          {svc.label}
                        </label>
                      );
                    })}
                  </div>
                </div>

                {/* Reset footer */}
                {activeFilterCount > 0 && (
                  <div style={{ padding:'8px 14px', borderTop:'1px solid var(--border-faint)', display:'flex', justifyContent:'flex-end' }}>
                    <button
                      onClick={() => { setSortField('none'); setSortDir('asc'); setFilterServices(['website_dev','seo','smma','social_media']); }}
                      style={{ background:'none', border:'none', fontSize:'11px', color:'var(--pink)', fontWeight:600, cursor:'pointer', padding:0 }}
                    >
                      Reset filters
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── Search ── */}
        <div style={{ padding:'14px 24px',borderBottom:'1px solid var(--border-faint)',flexShrink:0 }}>
          <div style={{ display:'flex',alignItems:'center',gap:9,background:'var(--bg-input)',border:'1px solid var(--border-subtle)',borderRadius:'var(--r-md)',padding:'0 14px',height:38 }}
            onFocusCapture={e=>(e.currentTarget.style.borderColor='var(--border-pink)')}
            onBlurCapture={e=>(e.currentTarget.style.borderColor='var(--border-subtle)')}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
            <input type="text" placeholder="Search lead collections…" value={search} onChange={e=>setSearch(e.target.value)} style={{ flex:1,background:'none',border:'none',outline:'none',color:'var(--text-1)',fontSize:'13px' }} />
          </div>
        </div>

        {/* ── Table ── */}
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'auto' }}>
          <table>
            <thead>
              <tr style={{ borderBottom:'1px solid var(--border-faint)' }}>
                {['Lead ID', 'Lead Name', 'Country & Region', 'Niche', 'Service', 'Total Leads', 'Date', ''].map(c=>(
                  <th key={c} style={{ padding:'10px 18px',fontSize:'10px',fontWeight:600,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:'.07em',textAlign:'left',whiteSpace:'nowrap' }}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayed.length===0 ? (
                <tr><td colSpan={8} style={{ padding:'56px',textAlign:'center',color:'var(--text-3)',fontSize:'14px' }}>No verified leads found.</td></tr>
              ) : displayed.map((sheet,i)=>{
                return (
                  <tr key={sheet.id}
                    onClick={() => { setOpenSheet(sheet); setOpenFullScreen(false); }}
                    onDoubleClick={() => { setOpenSheet(sheet); setOpenFullScreen(true); }}
                    title="Click to open · Double-click for full screen"
                    style={{
                      borderBottom: i < displayed.length - 1 ? '1px solid var(--border-faint)' : 'none',
                      cursor: 'pointer',
                      transition: 'background var(--ease), border-left var(--ease)',
                      background: sheet.id === highlightId ? 'var(--pink-dim)' : 'transparent',
                      borderLeft: sheet.id === highlightId ? '3px solid var(--pink)' : '3px solid transparent'
                    }}
                    onMouseEnter={e=>(e.currentTarget.style.background='var(--bg-hover)')}
                    onMouseLeave={e=>(e.currentTarget.style.background=sheet.id === highlightId ? 'var(--pink-dim)' : 'transparent')}
                  >
                    {/* Lead ID */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',fontFamily:'monospace',fontSize:'11px',color:'var(--text-3)' }}>
                      {sheet.sheetId}
                    </td>
                    {/* Business Name */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',fontWeight:600,color:'var(--text-1)' }}>
                      {sheet.name}
                    </td>
                    {/* Country & Region */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',color:'var(--text-2)' }}>
                      {getCountryRegion(sheet)}
                    </td>
                    {/* Niche */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',color:'var(--text-2)' }}>
                      {(sheet.niches || [(sheet as any).niche || 'General']).join(', ')}
                    </td>
                    {/* Service */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',color:'var(--text-2)' }}>
                      {SERVICE_LABELS[sheet.service] || sheet.service}
                    </td>
                    {/* Total Leads */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',color:'var(--text-2)' }}>
                      {sheet.leads.length} leads
                    </td>
                    {/* Date */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',color:'var(--text-3)',fontSize:'11px',whiteSpace:'nowrap' }}>
                      {formatDate(sheet.createdAt)}
                    </td>
                    {/* Options */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle' }} onClick={e=>e.stopPropagation()}>
                      <ThreeDotMenu items={[
                        { label:'Details', icon:I.info, onClick:()=>setDetailSheet(sheet) },
                        { label:'Edit Sheet', icon:I.edit, onClick:()=>setEditSheet(sheet) },
                        { label:'Delete Sheet', icon:I.trash, danger:true, onClick:()=>deleteSheet(sheet.id) },
                      ]} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div style={{ padding:'12px 24px',borderTop:'1px solid var(--border-faint)',display:'flex',alignItems:'center',justifyContent:'space-between',flexShrink:0 }}>
          <span style={{ fontSize:'12px',color:'var(--text-3)' }}>{displayed.length} sheet{displayed.length!==1?'s':''} · {displayed.reduce((a,s)=>a+s.leads.length,0)} leads</span>
        </div>
      </div>

      {openSheet  && <LeadSheetModal sheet={openSheet} initialFullScreen={openFullScreen} onClose={()=>setOpenSheet(null)} />}
      {detailSheet && <SheetDetailsModal sheet={detailSheet} onClose={()=>setDetailSheet(null)} />}
      {editSheet  && <EditSheetModal sheet={editSheet} onClose={()=>setEditSheet(null)} onSave={(n,u)=>saveSheet(editSheet.id,n,u)} />}
    </div>
  );
}
