'use client';
import { useState, useMemo } from 'react';
import { Lead, LeadSheet, ServiceType, SERVICE_LABELS } from '../lib/data';
import { LeadDetailDrawer } from './LeadDetailDrawer';

const SC: Record<string,{bg:string;text:string}> = {
  new:       {bg:'rgba(148,163,184,.12)',text:'#94a3b8'},
  assigned:  {bg:'rgba(96,165,250,.12)', text:'#60a5fa'},
  called:    {bg:'rgba(245,158,11,.12)', text:'#fbbf24'},
  warm:      {bg:'rgba(236,72,153,.15)', text:'#f472b6'},
  converted: {bg:'rgba(34,197,94,.12)',  text:'#4ade80'},
};

/* columns vary by service */
function getColumns(svc: ServiceType) {
  if (svc === 'website_dev') {
    return ['Lead ID', 'Business Name', 'Niche', 'Email', 'Phone', 'Social Media', 'Business Maturity', 'Genuineness Probability', 'Contactability Score', 'Priority Rank'];
  }
  if (svc === 'seo') {
    return ['Lead ID', 'Business Name', 'Niche', 'Website Link', 'SEO Score', 'Email', 'Phone', 'Social Media', 'Genuineness', 'Contactability Score', 'Priority Score'];
  }
  if (svc === 'smma') {
    return ['Lead ID', 'Business Name', 'Country & Region', 'Instagram', 'Facebook', 'Follower Count', 'Email', 'Business Maturity', 'Genuineness', 'Social Media Management Score'];
  }
  if (svc === 'social_media') {
    return ['Lead ID', 'Business Name', 'Country & Region', 'Instagram', 'Facebook', 'Follower Count', 'Total Followers Count', 'Ads Library Signal', 'Facebook Page Transparency', 'Email', 'Business Maturity', 'Genuineness', 'Social Media Marketing Score'];
  }
  return ['Lead ID', 'Business Name', 'Location', 'Niche', 'Priority Score', 'Status'];
}

const tdStyle = { padding: '12px 16px', color: 'var(--text-2)', fontSize: '12px', whiteSpace: 'nowrap' as const };
const boldTdStyle = { padding: '12px 16px', fontWeight: 600, color: 'var(--text-1)', fontSize: '13px', whiteSpace: 'nowrap' as const };
const linkStyle = { color: 'var(--blue)', fontSize: '12px', textDecoration: 'none' };

const renderLeadCells = (lead: Lead, svc: ServiceType, idx: number) => {
  const niche = (lead as any).niche || 'Not available';
  const email = lead.contactEmail || (lead as any).email || 'Not available';
  const phone = lead.contactPhone || (lead as any).phone || 'Not available';
  const social = lead.instagramHandle || lead.facebookHandle || 'Not available';
  const maturity = (lead as any).businessMaturity || 'Not available';
  const genuinenessProb = lead.genuineness !== undefined && lead.genuineness !== null ? `${lead.genuineness}%` : 'Not available';
  const contactability = (lead as any).contactabilityScore ?? 'Not available';
  const priorityRank = `#${idx + 1}`;
  const seoScore = lead.seoScore !== undefined && lead.seoScore !== null ? `${lead.seoScore}/100` : 'Not available';
  const regionCountry = lead.location || 'Not available';
  const ig = lead.instagramHandle || 'Not available';
  const fb = lead.facebookHandle || 'Not available';
  const followers = lead.followersCount !== undefined && lead.followersCount !== null ? lead.followersCount.toLocaleString() : 'Not available';
  const totalFollowers = (lead as any).totalFollowersCount ?? 'Not available';
  const adsSignal = (lead as any).adsLibrarySignal || 'Not available';
  const fbTransparency = (lead as any).facebookPageTransparency || 'Not available';
  const sMMScore = (lead as any).socialMediaManagementScore ?? 'Not available';
  const sMktScore = (lead as any).socialMediaMarketingScore ?? 'Not available';

  if (svc === 'website_dev') {
    return (
      <>
        <td style={tdStyle}>{lead.leadId}</td>
        <td style={boldTdStyle}>{lead.businessName}</td>
        <td style={tdStyle}>{niche}</td>
        <td style={tdStyle}>{email}</td>
        <td style={tdStyle}>{phone}</td>
        <td style={tdStyle}>{social}</td>
        <td style={tdStyle}>{maturity}</td>
        <td style={tdStyle}>{genuinenessProb}</td>
        <td style={tdStyle}>{contactability}</td>
        <td style={tdStyle}>{priorityRank}</td>
      </>
    );
  }
  if (svc === 'seo') {
    return (
      <>
        <td style={tdStyle}>{lead.leadId}</td>
        <td style={boldTdStyle}>{lead.businessName}</td>
        <td style={tdStyle}>{niche}</td>
        <td style={tdStyle}>
          {lead.websiteUrl ? (
            <a href={`https://${lead.websiteUrl}`} target="_blank" rel="noreferrer" onClick={e=>e.stopPropagation()} style={linkStyle}>
              {lead.websiteUrl}
            </a>
          ) : '—'}
        </td>
        <td style={tdStyle}>{seoScore}/100</td>
        <td style={tdStyle}>{email}</td>
        <td style={tdStyle}>{phone}</td>
        <td style={tdStyle}>{social}</td>
        <td style={tdStyle}>{lead.genuineness}%</td>
        <td style={tdStyle}>{contactability}</td>
        <td style={tdStyle}>{lead.priorityScore}</td>
      </>
    );
  }
  if (svc === 'smma') {
    return (
      <>
        <td style={tdStyle}>{lead.leadId}</td>
        <td style={boldTdStyle}>{lead.businessName}</td>
        <td style={tdStyle}>{regionCountry}</td>
        <td style={tdStyle}>{ig}</td>
        <td style={tdStyle}>{fb}</td>
        <td style={tdStyle}>{followers.toLocaleString()}</td>
        <td style={tdStyle}>{email}</td>
        <td style={tdStyle}>{maturity}</td>
        <td style={tdStyle}>{lead.genuineness}%</td>
        <td style={tdStyle}>{sMMScore}</td>
      </>
    );
  }
  if (svc === 'social_media') {
    return (
      <>
        <td style={tdStyle}>{lead.leadId}</td>
        <td style={boldTdStyle}>{lead.businessName}</td>
        <td style={tdStyle}>{regionCountry}</td>
        <td style={tdStyle}>{ig}</td>
        <td style={tdStyle}>{fb}</td>
        <td style={tdStyle}>{followers.toLocaleString()}</td>
        <td style={tdStyle}>{totalFollowers.toLocaleString()}</td>
        <td style={tdStyle}>{adsSignal}</td>
        <td style={tdStyle}>{fbTransparency}</td>
        <td style={tdStyle}>{email}</td>
        <td style={tdStyle}>{maturity}</td>
        <td style={tdStyle}>{lead.genuineness}%</td>
        <td style={tdStyle}>{sMktScore}</td>
      </>
    );
  }

  return (
    <>
      <td style={tdStyle}>{lead.leadId}</td>
      <td style={boldTdStyle}>{lead.businessName}</td>
      <td style={tdStyle}>{lead.location}</td>
      <td style={tdStyle}>{niche}</td>
      <td style={tdStyle}>{lead.priorityScore}</td>
      <td style={tdStyle}>{lead.status}</td>
    </>
  );
}

export function LeadSheetModal({ sheet, onClose, initialFullScreen = false }: { sheet: LeadSheet; onClose: () => void; initialFullScreen?: boolean }) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selected, setSelected] = useState<Lead|null>(null);
  const [isFullScreen, setIsFullScreen] = useState<boolean>(initialFullScreen);

  const filtered = useMemo(() => sheet.leads.filter(l => {
    const q = search.toLowerCase();
    const matchText = l.businessName.toLowerCase().includes(q) || l.location.toLowerCase().includes(q) || l.leadId.toLowerCase().includes(q);
    const matchStatus = statusFilter === 'all' || l.status === statusFilter;
    return matchText && matchStatus;
  }), [sheet.leads, search, statusFilter]);

  const cols = getColumns(sheet.service);
  const total = sheet.leads.length;
  const warm = sheet.leads.filter(l=>l.status==='warm').length;
  const conv = sheet.leads.filter(l=>l.status==='converted').length;

  const exportCSV = () => {
    const headers = ['Lead ID','Business','Location','Website','Email','Phone','Priority Score','Status'];
    const rows = sheet.leads.map(l => [l.leadId, l.businessName, l.location, l.websiteUrl||'', l.contactEmail||(l as any).email||'', l.contactPhone||'', l.priorityScore, l.status]);
    const csv = [headers, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csv], {type:'text/csv'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${sheet.name}.csv`; a.click();

    // Log to Export History
    if (typeof window !== 'undefined') {
      const exportRecord = {
        id: `exp-${Date.now()}`,
        type: "export",
        createdAt: new Date().toISOString(),
        leadId: sheet.sheetId,
        leadName: sheet.name,
        service: sheet.service,
        processedCount: sheet.leads.length,
        format: "CSV",
        status: "completed"
      };
      const saved = localStorage.getItem('lead_system_export_history');
      const current = saved ? JSON.parse(saved) : [];
      localStorage.setItem('lead_system_export_history', JSON.stringify([exportRecord, ...current]));
      window.dispatchEvent(new Event('history-updated'));
    }
  };

  return (
    <>
      <div onClick={onClose} style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.72)',backdropFilter:'blur(5px)',zIndex:100 }} />
      <div style={{
        position:'fixed',
        top: isFullScreen ? 0 : '50%',
        left: isFullScreen ? 0 : '50%',
        transform: isFullScreen ? 'none' : 'translate(-50%,-50%)',
        width: isFullScreen ? '100vw' : 'min(94vw,1100px)',
        height: isFullScreen ? '100vh' : 'auto',
        maxHeight: isFullScreen ? '100vh' : '88vh',
        background:'var(--bg-elevated)',
        border: isFullScreen ? 'none' : '1px solid var(--border-subtle)',
        borderRadius: isFullScreen ? 0 : 'var(--r-2xl)',
        zIndex:101,
        display:'flex',
        flexDirection:'column',
        overflow:'hidden',
        boxShadow: isFullScreen ? 'none' : '0 40px 100px rgba(0,0,0,.65)',
        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
      }}>

        {/* ── Header ── */}
        <div
          onDoubleClick={() => setIsFullScreen(f => !f)}
          title="Double click to toggle fullscreen"
          style={{ padding:'20px 24px',borderBottom:'1px solid var(--border-faint)',display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:16,flexShrink:0,cursor:'pointer' }}
        >
          <div style={{ flex:1,minWidth:0 }}>
            <div style={{ display:'flex',alignItems:'center',gap:10,flexWrap:'wrap',marginBottom:4 }}>
              <span style={{ fontSize:'15px',fontWeight:700,color:'var(--text-1)' }}>{sheet.name}</span>
              <span className="pill" style={{ background:'var(--pink-dim)',color:'var(--pink-light)',fontSize:'10px' }}>{SERVICE_LABELS[sheet.service]}</span>
              <span style={{ fontSize:'11px',color:'var(--text-3)',fontFamily:'monospace' }}>{sheet.sheetId}</span>
            </div>
            <div style={{ fontSize:'12px',color:'var(--text-3)',lineHeight:1.6 }}>
              {sheet.sources.map(s=>s.replace('_',' ')).join(' · ')} · {sheet.niches.join(', ')} · {total} leads · Assigned to <strong style={{color:'var(--text-2)'}}>{sheet.callerName}</strong>
            </div>
          </div>
          {/* Stats */}
          <div style={{ display:'flex',alignItems:'center',gap:10,flexShrink:0 }} onClick={e => e.stopPropagation()}>
            {[{l:'Total',v:total,c:'var(--text-1)'},{l:'Warm',v:warm,c:'var(--pink-light)'},{l:'Converted',v:conv,c:'var(--green)'}].map(s=>(
              <div key={s.l} style={{ background:'var(--bg-card)',border:'1px solid var(--border-subtle)',borderRadius:'var(--r-lg)',padding:'8px 16px',textAlign:'center',minWidth:64 }}>
                <div style={{ fontSize:'18px',fontWeight:700,color:s.c }}>{s.v}</div>
                <div style={{ fontSize:'9px',textTransform:'uppercase',letterSpacing:'.07em',color:'var(--text-3)',marginTop:1 }}>{s.l}</div>
              </div>
            ))}
            {/* Export */}
            <div style={{ display:'flex',gap:6,marginLeft:4 }}>
              <button onClick={exportCSV} className="btn btn-ghost btn-sm" style={{ gap:5 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                CSV
              </button>
              {sheet.googleSheetsUrl && (
                <a href={sheet.googleSheetsUrl} target="_blank" rel="noreferrer">
                  <button className="btn btn-ghost btn-sm" style={{ gap:5 }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
                    Sheets
                  </button>
                </a>
              )}
            </div>
            {/* Fullscreen Toggle Button */}
            <button
              onClick={() => setIsFullScreen(f => !f)}
              title={isFullScreen ? "Exit Fullscreen" : "Fullscreen"}
              style={{ width:30,height:30,display:'flex',alignItems:'center',justifyContent:'center',borderRadius:'var(--r-md)',color:'var(--text-3)',marginLeft:4,cursor:'pointer' }}
              onMouseEnter={e=>(e.currentTarget.style.background='var(--bg-hover)')}
              onMouseLeave={e=>(e.currentTarget.style.background='transparent')}
            >
              {isFullScreen ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/>
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
                </svg>
              )}
            </button>
            {/* Close */}
            <button onClick={onClose} style={{ width:30,height:30,display:'flex',alignItems:'center',justifyContent:'center',borderRadius:'var(--r-md)',color:'var(--text-3)',marginLeft:4,cursor:'pointer' }}
              onMouseEnter={e=>(e.currentTarget.style.background='var(--bg-hover)')}
              onMouseLeave={e=>(e.currentTarget.style.background='transparent')}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>

        {/* ── Filters ── */}
        <div style={{ padding:'12px 24px',borderBottom:'1px solid var(--border-faint)',display:'flex',gap:10,alignItems:'center',flexShrink:0,flexWrap:'wrap' }}>
          {/* Search */}
          <div style={{ flex:1,minWidth:180,display:'flex',alignItems:'center',gap:8,background:'var(--bg-input)',border:'1px solid var(--border-subtle)',borderRadius:'var(--r-md)',padding:'0 12px',height:34 }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
            <input type="text" placeholder={`Search ${total} leads…`} value={search} onChange={e=>setSearch(e.target.value)} style={{ flex:1,background:'none',border:'none',outline:'none',color:'var(--text-1)',fontSize:'13px' }} />
          </div>
          {/* Status filter */}
          {['all','new','assigned','called','warm','converted'].map(s=>(
            <button key={s} onClick={()=>setStatusFilter(s)} style={{ padding:'4px 12px',borderRadius:'var(--r-pill)',fontSize:'11px',fontWeight:statusFilter===s?600:400,background:statusFilter===s?'var(--pink)':'var(--bg-input)',color:statusFilter===s?'#fff':'var(--text-3)',border:statusFilter===s?'1px solid transparent':'1px solid var(--border-subtle)',cursor:'pointer',textTransform:'capitalize',transition:'all var(--ease)' }}>
              {s}
            </button>
          ))}
        </div>

        {/* ── Table ── */}
        <div style={{ flex:1,overflow:'auto' }}>
          <table>
            <thead>
              <tr style={{ borderBottom:'1px solid var(--border-faint)',position:'sticky',top:0,background:'var(--bg-elevated)',zIndex:1 }}>
                {cols.map(c=>(
                  <th key={c} style={{ padding:'9px 16px',fontSize:'10px',fontWeight:600,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:'.07em',whiteSpace:'nowrap',textAlign:'left' }}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length===0 ? (
                <tr><td colSpan={cols.length} style={{ padding:'48px',textAlign:'center',color:'var(--text-3)' }}>No leads match your filters</td></tr>
              ) : filtered.map((lead,i)=>(
                <tr key={lead.leadId}
                  onClick={()=>setSelected(lead)}
                  style={{ borderBottom: i<filtered.length-1?'1px solid var(--border-faint)':'none', cursor:'pointer',transition:'background var(--ease)' }}
                  onMouseEnter={e=>(e.currentTarget.style.background='var(--bg-hover)')}
                  onMouseLeave={e=>(e.currentTarget.style.background='transparent')}
                >
                  {renderLeadCells(lead, sheet.service, i)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div style={{ padding:'12px 24px',borderTop:'1px solid var(--border-faint)',display:'flex',alignItems:'center',justifyContent:'space-between',flexShrink:0 }}>
          <span style={{ fontSize:'12px',color:'var(--text-3)' }}>{filtered.length} of {total} leads</span>
          <span style={{ fontSize:'12px',color:'var(--text-3)' }}>Click a row to view full details</span>
        </div>
      </div>

      {selected && <LeadDetailDrawer lead={selected} service={sheet.service} onClose={()=>setSelected(null)} />}
    </>
  );
}
