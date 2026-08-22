'use client';
import { LeadSheet, SERVICE_LABELS } from '../lib/data';

export function SheetDetailsModal({ sheet, onClose }: { sheet: LeadSheet; onClose: () => void }) {
  return (
    <>
      <div onClick={onClose} style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.65)',backdropFilter:'blur(4px)',zIndex:300 }} />
      <div style={{ position:'fixed',top:'50%',left:'50%',transform:'translate(-50%,-50%)',width:'min(92vw,480px)',background:'var(--bg-elevated)',border:'1px solid var(--border-subtle)',borderRadius:'var(--r-xl)',zIndex:301,overflow:'hidden',boxShadow:'0 32px 80px rgba(0,0,0,.6)' }}>
        <div style={{ padding:'18px 22px',borderBottom:'1px solid var(--border-faint)',display:'flex',alignItems:'center',justifyContent:'space-between' }}>
          <span style={{ fontSize:'14px',fontWeight:600,color:'var(--text-1)' }}>Sheet Details</span>
          <button onClick={onClose} style={{ width:28,height:28,display:'flex',alignItems:'center',justifyContent:'center',borderRadius:'var(--r-md)',color:'var(--text-3)' }}
            onMouseEnter={e=>(e.currentTarget.style.background='var(--bg-hover)')} onMouseLeave={e=>(e.currentTarget.style.background='transparent')}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div style={{ padding:'18px 22px' }}>
          {[
            ['Sheet ID', sheet.sheetId],
            ['Name', sheet.name],
            ['Service', SERVICE_LABELS[sheet.service]],
            ['Sources', sheet.sources.map(s=>s.replace('_',' ')).join(', ')],
            ['Niches', sheet.niches.join(', ')],
            ['Time to Fetch', `${sheet.timeTakenMin} minutes`],
            ['Total Leads', String(sheet.leads.length)],
            ['Assigned To', sheet.callerName||'—'],
            ['Created', new Date(sheet.createdAt).toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})],
            ['Google Sheets', sheet.googleSheetsUrl||'Not linked'],
          ].map(([k,v])=>(
            <div key={k} style={{ display:'flex',justifyContent:'space-between',padding:'9px 0',borderBottom:'1px solid var(--border-faint)',gap:16 }}>
              <span style={{ fontSize:'12px',color:'var(--text-3)',flexShrink:0 }}>{k}</span>
              {k==='Google Sheets'&&sheet.googleSheetsUrl
                ? <a href={sheet.googleSheetsUrl} target="_blank" rel="noreferrer" style={{ fontSize:'12px',color:'var(--blue)',textAlign:'right',wordBreak:'break-all' }}>{v}</a>
                : <span style={{ fontSize:'12px',color:'var(--text-1)',textAlign:'right',wordBreak:'break-all' }}>{v}</span>
              }
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
