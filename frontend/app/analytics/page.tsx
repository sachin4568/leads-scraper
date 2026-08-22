'use client';
import React, { useEffect, useState } from 'react';
import { LeadSheet } from '../lib/data';
import { api } from '../lib/api';

export default function AnalyticsPage() {
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

  const totalLeads = sheets.reduce((a, s) => a + s.leads.length, 0);
  const warmLeads = sheets.reduce((a, s) => a + s.leads.filter(l => l.status === 'warm' || l.status === 'converted').length, 0);
  const avgScore = totalLeads > 0 ? Math.round(sheets.flatMap(s => s.leads).reduce((a, l) => a + (l.priorityScore || 0), 0) / totalLeads) : 0;

  const niches = ['Restaurant', 'Salon', 'Fitness', 'Plumbing', 'Finance', 'Healthcare'];
  const niche_counts = niches.map(n => ({
    name: n,
    count: sheets.filter(s => s.niches.includes(n)).reduce((acc, s) => acc + s.leads.length, 0),
  })).filter(n => n.count > 0);

  if (loading) {
    return (
      <div>
        <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>Intelligence</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>Loading insights...</p>
      </div>
    );
  }

  if (sheets.length === 0) {
    return (
      <div>
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>Intelligence</h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
            AI-powered insights and analytics across your lead pipeline
          </p>
        </div>
        <div style={{background:'var(--bg-surface)',border:'1px solid var(--border-faint)',borderRadius:'var(--r-xl)',padding:'32px',textAlign:'center',color:'var(--text-3)'}}>
          No verified leads found.
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>Intelligence</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
          AI-powered insights and analytics across your lead pipeline
        </p>
      </div>

      {/* KPI cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px', marginBottom: '24px' }}>
        {[
          { label: 'Total Leads', value: totalLeads, sub: 'Across all sheets', color: 'var(--pink-primary)' },
          { label: 'Warm / Converted', value: warmLeads, sub: totalLeads > 0 ? `${Math.round((warmLeads/totalLeads)*100)}% conversion` : '0% conversion', color: 'var(--green)' },
          { label: 'Avg Priority Score', value: `${avgScore}`, sub: 'Out of 100', color: 'var(--amber)' },
          { label: 'Active Sheets', value: sheets.length, sub: 'Lead collections', color: '#60a5fa' },
        ].map(kpi => (
          <div key={kpi.label} style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '20px',
          }}>
            <div style={{ fontSize: '28px', fontWeight: 700, color: kpi.color, marginBottom: '4px' }}>{kpi.value}</div>
            <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '3px' }}>{kpi.label}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{kpi.sub}</div>
          </div>
        ))}
      </div>

      {/* Niche breakdown */}
      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-xl)',
        padding: '24px',
      }}>
        <div style={{
          fontSize: '12px', fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '18px',
        }}>
          Lead Distribution by Niche
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {niche_counts.map(n => (
            <div key={n.name}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{n.name}</span>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{n.count} leads</span>
              </div>
              <div style={{ height: '5px', borderRadius: '5px', background: 'var(--bg-glass)', overflow: 'hidden' }}>
                <div style={{
                  width: totalLeads > 0 ? `${(n.count / totalLeads) * 100}%` : '0%',
                  height: '100%',
                  background: 'var(--pink-primary)',
                  borderRadius: '5px',
                }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
