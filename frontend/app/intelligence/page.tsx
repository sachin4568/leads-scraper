'use client';
import React, { useEffect, useState } from 'react';
import { LeadSheet, SERVICE_LABELS } from '../lib/data';
import { api } from '../lib/api';

export default function IntelligencePage() {
  const [sheets, setSheets] = useState<LeadSheet[]>([]);
  const [loading, setLoading] = useState(true);

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

  const all = sheets.flatMap(s => s.leads);
  const total = all.length;
  const warm = all.filter(l => l.status === 'warm' || l.status === 'converted').length;
  const avg = total > 0 ? Math.round(all.reduce((a, l) => a + (l.priorityScore || 0), 0) / total) : 0;

  if (loading) {
    return (
      <div>
        <h1 style={{fontSize:'22px',fontWeight:700,color:'var(--text-1)',marginBottom:6}}>Intelligence</h1>
        <p style={{fontSize:'13px',color:'var(--text-3)',marginBottom:24}}>Loading insights...</p>
      </div>
    );
  }

  if (sheets.length === 0) {
    return (
      <div>
        <h1 style={{fontSize:'22px',fontWeight:700,color:'var(--text-1)',marginBottom:6}}>Intelligence</h1>
        <p style={{fontSize:'13px',color:'var(--text-3)',marginBottom:24}}>AI-powered insights across your lead pipeline</p>
        <div style={{background:'var(--bg-surface)',border:'1px solid var(--border-faint)',borderRadius:'var(--r-xl)',padding:'32px',textAlign:'center',color:'var(--text-3)'}}>
          No verified leads found.
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{fontSize:'22px',fontWeight:700,color:'var(--text-1)',marginBottom:6}}>Intelligence</h1>
      <p style={{fontSize:'13px',color:'var(--text-3)',marginBottom:24}}>AI-powered insights across your lead pipeline</p>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))',gap:12,marginBottom:24}}>
        {[{l:'Total Leads',v:total,c:'var(--pink-light)'},{l:'Warm / Converted',v:warm,c:'var(--green)'},{l:'Avg Priority',v:`${avg}`,c:'var(--amber)'},{l:'Active Sheets',v:sheets.length,c:'var(--blue)'}].map(k=>(
          <div key={k.l} style={{background:'var(--bg-surface)',border:'1px solid var(--border-faint)',borderRadius:'var(--r-lg)',padding:'20px'}}>
            <div style={{fontSize:'28px',fontWeight:800,color:k.c,marginBottom:5}}>{k.v}</div>
            <div style={{fontSize:'10px',textTransform:'uppercase',letterSpacing:'.08em',color:'var(--text-4)'}}>{k.l}</div>
          </div>
        ))}
      </div>
      <div style={{background:'var(--bg-surface)',border:'1px solid var(--border-faint)',borderRadius:'var(--r-xl)',padding:'32px',textAlign:'center',color:'var(--text-3)'}}>
        Advanced analytics — coming soon
      </div>
    </div>
  );
}
