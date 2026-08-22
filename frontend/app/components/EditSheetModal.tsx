'use client';
import { useState } from 'react';
import { LeadSheet } from '../lib/data';

export function EditSheetModal({ sheet, onClose, onSave }: { sheet: LeadSheet; onClose: () => void; onSave: (name: string, url: string) => void }) {
  const [name, setName] = useState(sheet.name);
  const [url, setUrl]   = useState(sheet.googleSheetsUrl||'');
  return (
    <>
      <div onClick={onClose} style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.65)',backdropFilter:'blur(4px)',zIndex:300 }} />
      <div style={{ position:'fixed',top:'50%',left:'50%',transform:'translate(-50%,-50%)',width:'min(92vw,440px)',background:'var(--bg-elevated)',border:'1px solid var(--border-subtle)',borderRadius:'var(--r-xl)',zIndex:301,overflow:'hidden',boxShadow:'0 32px 80px rgba(0,0,0,.6)' }}>
        <div style={{ padding:'18px 22px',borderBottom:'1px solid var(--border-faint)',display:'flex',alignItems:'center',justifyContent:'space-between' }}>
          <span style={{ fontSize:'14px',fontWeight:600,color:'var(--text-1)' }}>Edit Lead Sheet</span>
          <button onClick={onClose} style={{ width:28,height:28,display:'flex',alignItems:'center',justifyContent:'center',borderRadius:'var(--r-md)',color:'var(--text-3)' }}
            onMouseEnter={e=>(e.currentTarget.style.background='var(--bg-hover)')} onMouseLeave={e=>(e.currentTarget.style.background='transparent')}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div style={{ padding:'18px 22px',display:'flex',flexDirection:'column',gap:14 }}>
          <Field label="Sheet Name">
            <input value={name} onChange={e=>setName(e.target.value)} style={{ width:'100%',background:'var(--bg-input)',border:'1px solid var(--border-subtle)',borderRadius:'var(--r-md)',padding:'9px 12px',color:'var(--text-1)',outline:'none' }}
              onFocus={e=>(e.currentTarget.style.borderColor='var(--border-pink)')} onBlur={e=>(e.currentTarget.style.borderColor='var(--border-subtle)')} />
          </Field>
          <Field label="Google Sheets URL">
            <input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://docs.google.com/spreadsheets/d/..." style={{ width:'100%',background:'var(--bg-input)',border:'1px solid var(--border-subtle)',borderRadius:'var(--r-md)',padding:'9px 12px',color:'var(--text-1)',outline:'none' }}
              onFocus={e=>(e.currentTarget.style.borderColor='var(--border-pink)')} onBlur={e=>(e.currentTarget.style.borderColor='var(--border-subtle)')} />
          </Field>
        </div>
        <div style={{ padding:'14px 22px',borderTop:'1px solid var(--border-faint)',display:'flex',gap:8,justifyContent:'flex-end' }}>
          <button onClick={onClose} className="btn btn-ghost">Cancel</button>
          <button onClick={()=>{ onSave(name,url); onClose(); }} className="btn btn-pink">Save Changes</button>
        </div>
      </div>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize:'11px',fontWeight:600,color:'var(--text-3)',marginBottom:6,textTransform:'uppercase',letterSpacing:'.06em' }}>{label}</div>
      {children}
    </div>
  );
}
