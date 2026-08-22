'use client';
import { useState } from 'react';
import { RAW_LEADS } from '../lib/data';

const PIPE = [
  {label:'Scraped',   count:8, total:8,  color:'#60a5fa'},
  {label:'Filtered',  count:6, total:8,  color:'#a78bfa'},
  {label:'Enriched',  count:5, total:6,  color:'#f472b6'},
  {label:'Scored',    count:4, total:5,  color:'#fb923c'},
  {label:'Qualified', count:3, total:4,  color:'#4ade80'},
];

export default function ReadingsPage() {
  const totalRaw  = RAW_LEADS.length;
  const qualified = RAW_LEADS.filter(l=>l.status==='qualified').length;
  const pending   = RAW_LEADS.filter(l=>l.status==='pending').length;
  const rejected  = RAW_LEADS.filter(l=>l.status==='rejected').length;

  return (
    <div>
      <h1 style={{ fontSize:'22px',fontWeight:700,color:'var(--text-1)',marginBottom:4 }}>Readings</h1>
      <p style={{ fontSize:'13px',color:'var(--text-3)',marginBottom:24 }}>System readings, scraping metrics, and pipeline metrics</p>

      {/* ── KPI row ── */}
      <div style={{ display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:12,marginBottom:18 }}>
        {[{l:'Total Raw',v:totalRaw,c:'var(--text-1)'},{l:'Qualified',v:qualified,c:'var(--green)'},{l:'Pending',v:pending,c:'var(--amber)'},{l:'Rejected',v:rejected,c:'var(--red)'}].map(k=>(
          <div key={k.l} style={{ background:'var(--bg-surface)',border:'1px solid var(--border-faint)',borderRadius:'var(--r-lg)',padding:'18px 20px' }}>
            <div style={{ fontSize:'26px',fontWeight:800,color:k.c,marginBottom:4 }}>{k.v}</div>
            <div style={{ fontSize:'10px',textTransform:'uppercase',letterSpacing:'.08em',color:'var(--text-4)' }}>{k.l}</div>
          </div>
        ))}
      </div>

      {/* ── Pipeline progress ── */}
      <div style={{ background:'var(--bg-surface)',border:'1px solid var(--border-faint)',borderRadius:'var(--r-xl)',padding:'20px 24px',maxWidth:'600px' }}>
        <div style={{ fontSize:'10px',fontWeight:700,textTransform:'uppercase',letterSpacing:'.09em',color:'var(--text-4)',marginBottom:18 }}>Pipeline Progress</div>
        {PIPE.map(s=>(
          <div key={s.label} style={{ marginBottom:14 }}>
            <div style={{ display:'flex',justifyContent:'space-between',marginBottom:6 }}>
              <span style={{ fontSize:'12px',color:'var(--text-2)' }}>{s.label}</span>
              <span style={{ fontSize:'12px' }}><span style={{ color:s.color,fontWeight:700 }}>{s.count}</span><span style={{ color:'var(--text-3)' }}>/{s.total}</span></span>
            </div>
            <div style={{ height:4,borderRadius:4,background:'var(--bg-input)',overflow:'hidden' }}>
              <div style={{ width:`${(s.count/s.total)*100}%`,height:'100%',background:s.color,borderRadius:4 }} />
            </div>
          </div>
        ))}
        <div style={{ marginTop:18,background:'var(--bg-card)',border:'1px solid var(--border-subtle)',borderRadius:'var(--r-md)',padding:'11px 14px',display:'flex',justifyContent:'space-between' }}>
          <span style={{ fontSize:'12px',color:'var(--text-3)' }}>Qualification rate</span>
          <span style={{ fontSize:'14px',fontWeight:700,color:'var(--green)' }}>37.5%</span>
        </div>
      </div>
    </div>
  );
}
