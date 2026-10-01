'use client';

import React, { useEffect, useState } from 'react';
import { api, AnalyticsOverviewAPI } from '../lib/api';

export default function BusinessAnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsOverviewAPI | null>(null);
  const [timeframe, setTimeframe] = useState<string>('30d');
  const [loading, setLoading] = useState<boolean>(true);

  const loadAnalytics = (tf: string) => {
    setLoading(true);
    api.getAnalyticsOverview({ timeframe: tf })
      .then((data) => {
        setAnalytics(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load business analytics:', err);
        setAnalytics(null);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadAnalytics(timeframe);
  }, [timeframe]);

  const getTierBadge = (tier: string) => {
    switch (tier) {
      case 'VERY_HIGH':
        return { bg: '#FEF2F2', text: '#DC2626', border: '#FCA5A5' };
      case 'HIGH':
        return { bg: '#FFFBEB', text: '#D97706', border: '#FCD34D' };
      case 'MEDIUM':
        return { bg: '#EFF6FF', text: '#2563EB', border: '#93C5FD' };
      case 'LOW':
        return { bg: '#F0FDF4', text: '#16A34A', border: '#86EFAC' };
      default:
        return { bg: '#F3F4F6', text: '#4B5563', border: '#D1D5DB' };
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1440px', margin: '0 auto', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      {/* Header & Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, margin: 0, color: '#111827' }}>
            Executive Business Analytics & Commercial Dashboard
          </h1>
          <p style={{ fontSize: '13px', color: '#6B7280', margin: '4px 0 0 0' }}>
            End-to-end commercial performance: Discovery → Contactability → Outreach → Intelligence → Revenue
          </p>
        </div>

        {/* Global Timeframe Selector */}
        <div style={{ display: 'flex', gap: '6px', background: '#F1F5F9', padding: '4px', borderRadius: '8px' }}>
          {[
            { id: 'today', label: 'Today' },
            { id: '7d', label: '7D' },
            { id: '30d', label: '30D' },
            { id: '90d', label: '90D' },
            { id: 'this_year', label: 'This Year' },
            { id: 'all_time', label: 'All Time' },
          ].map((tf) => (
            <button
              key={tf.id}
              type="button"
              onClick={() => setTimeframe(tf.id)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 600,
                border: 'none',
                background: timeframe === tf.id ? '#FFFFFF' : 'transparent',
                color: timeframe === tf.id ? '#0F172A' : '#64748B',
                boxShadow: timeframe === tf.id ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
                cursor: 'pointer',
              }}
            >
              {tf.label}
            </button>
          ))}
        </div>
      </div>

      {/* Core Executive KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px', marginBottom: '24px' }}>
        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Total Ingested Leads</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#0F172A', marginTop: '4px' }}>
            {analytics?.kpis.total_leads ?? 0}
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            {analytics?.kpis.contactable_leads ?? 0} contactable ({analytics?.kpis.total_leads ? Math.round((analytics.kpis.contactable_leads / analytics.kpis.total_leads) * 100) : 0}%)
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Contacted Leads</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#2563EB', marginTop: '4px' }}>
            {analytics?.kpis.contacted_leads ?? 0}
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            {analytics?.kpis.overall_response_rate ?? 0}% response rate
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Qualified Opportunities</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#7C3AED', marginTop: '4px' }}>
            {analytics?.kpis.qualified_leads ?? 0}
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            Consultation / demo booked
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Won Closed Revenue</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#059669', marginTop: '4px' }}>
            ₹{analytics?.kpis.won_revenue.toLocaleString('en-IN') ?? '0'}
          </div>
          <div style={{ fontSize: '11px', color: '#16A34A', fontWeight: 600, marginTop: '2px' }}>
            {analytics?.kpis.won_leads ?? 0} closed clients
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Active Pipeline Value</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#1E293B', marginTop: '4px' }}>
            ₹{analytics?.kpis.total_pipeline_value.toLocaleString('en-IN') ?? '0'}
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            ₹{analytics?.kpis.weighted_pipeline_value.toLocaleString('en-IN') ?? '0'} weighted
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Average Deal Size</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#D97706', marginTop: '4px' }}>
            ₹{analytics?.kpis.avg_deal_size.toLocaleString('en-IN') ?? '0'}
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            Win rate: {analytics?.kpis.win_rate ?? 0}%
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Funnel Conversion Rate</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#047857', marginTop: '4px' }}>
            {analytics?.kpis.overall_conversion_rate ?? 0}%
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            Discovered → Won
          </div>
        </div>
      </div>

      {/* End-to-End Sales Conversion Funnel */}
      <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', marginBottom: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: '#111827' }}>
              Full Business Conversion Funnel
            </h2>
            <div style={{ fontSize: '12px', color: '#6B7280', marginTop: '2px' }}>
              Step-by-step conversion drop-offs exposing where deals are won or lost
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
          {analytics?.funnel.map((stage, idx) => {
            const isLast = idx === analytics.funnel.length - 1;
            return (
              <div
                key={stage.stage}
                style={{
                  background: isLast ? '#ECFDF5' : '#F8FAFC',
                  border: `1px solid ${isLast ? '#6EE7B7' : '#E2E8F0'}`,
                  borderRadius: '8px',
                  padding: '12px',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748B' }}>{stage.stage}</div>
                <div style={{ fontSize: '22px', fontWeight: 800, color: isLast ? '#059669' : '#0F172A', marginTop: '4px' }}>
                  {stage.count}
                </div>
                <div style={{ fontSize: '10px', color: '#94A3B8', marginTop: '4px' }}>
                  {idx === 0 ? '100% total' : `${stage.conversion_rate_from_previous}% step drop`}
                </div>
                <div style={{ fontSize: '10px', color: '#64748B', fontWeight: 600 }}>
                  {stage.conversion_rate_from_total}% overall
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Opportunity Quality Tier Performance Matrix */}
      <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', marginBottom: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 4px 0', color: '#111827' }}>
          Opportunity Scoring vs Real-World Sales Outcomes
        </h2>
        <p style={{ fontSize: '12px', color: '#6B7280', margin: '0 0 16px 0' }}>
          Validating whether Phase 9 intelligence tiers (VERY_HIGH → MINIMAL) accurately predict qualification, conversions, and closed revenue
        </p>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#475569', fontWeight: 700 }}>
                <th style={{ padding: '10px 12px' }}>Quality Tier</th>
                <th style={{ padding: '10px 12px' }}>Leads</th>
                <th style={{ padding: '10px 12px' }}>Contactable %</th>
                <th style={{ padding: '10px 12px' }}>Contacted %</th>
                <th style={{ padding: '10px 12px' }}>Qualified %</th>
                <th style={{ padding: '10px 12px' }}>Won %</th>
                <th style={{ padding: '10px 12px' }}>Won Revenue</th>
                <th style={{ padding: '10px 12px' }}>Avg Deal Value</th>
              </tr>
            </thead>
            <tbody>
              {analytics?.quality_performance.map((tier) => {
                const badge = getTierBadge(tier.tier);
                return (
                  <tr key={tier.tier} style={{ borderBottom: '1px solid #F1F5F9' }}>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ fontSize: '11px', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: badge.bg, color: badge.text, border: `1px solid ${badge.border}` }}>
                        {tier.tier}
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 700, color: '#1E293B' }}>{tier.leads_count}</td>
                    <td style={{ padding: '10px 12px', color: '#475569' }}>{tier.contactable_pct}%</td>
                    <td style={{ padding: '10px 12px', color: '#475569' }}>{tier.contacted_pct}%</td>
                    <td style={{ padding: '10px 12px', fontWeight: 600, color: tier.qualified_pct >= 20 ? '#2563EB' : '#475569' }}>
                      {tier.qualified_pct}%
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 700, color: tier.won_pct > 0 ? '#059669' : '#94A3B8' }}>
                      {tier.won_pct}%
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 700, color: tier.won_revenue > 0 ? '#059669' : '#64748B' }}>
                      ₹{tier.won_revenue.toLocaleString('en-IN')}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#64748B' }}>
                      ₹{tier.avg_deal_size.toLocaleString('en-IN')}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Acquisition Source & Service Performance Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
        {/* Source Commercial Performance */}
        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 4px 0', color: '#111827' }}>
            Acquisition Source Performance
          </h2>
          <p style={{ fontSize: '12px', color: '#6B7280', margin: '0 0 12px 0' }}>
            Comparing OSM Discovery vs Zero-Budget Verified Websites
          </p>

          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#475569', fontWeight: 700 }}>
                <th style={{ padding: '8px 10px' }}>Source</th>
                <th style={{ padding: '8px 10px' }}>Leads</th>
                <th style={{ padding: '8px 10px' }}>Contactable</th>
                <th style={{ padding: '8px 10px' }}>Won %</th>
                <th style={{ padding: '8px 10px' }}>Revenue</th>
              </tr>
            </thead>
            <tbody>
              {analytics?.source_performance.map((src) => (
                <tr key={src.source} style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 700, color: '#0F172A' }}>{src.source}</td>
                  <td style={{ padding: '8px 10px', color: '#475569' }}>{src.leads_count}</td>
                  <td style={{ padding: '8px 10px', color: '#475569' }}>{src.contactable_pct}%</td>
                  <td style={{ padding: '8px 10px', fontWeight: 700, color: src.won_pct > 0 ? '#059669' : '#64748B' }}>
                    {src.won_pct}%
                  </td>
                  <td style={{ padding: '8px 10px', fontWeight: 700, color: '#059669' }}>
                    ₹{src.won_revenue.toLocaleString('en-IN')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Service Performance Matrix */}
        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 4px 0', color: '#111827' }}>
            Service Pitch Revenue Matrix
          </h2>
          <p style={{ fontSize: '12px', color: '#6B7280', margin: '0 0 12px 0' }}>
            Revenue, pipeline, and win rate across pitched offerings
          </p>

          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#475569', fontWeight: 700 }}>
                <th style={{ padding: '8px 10px' }}>Service</th>
                <th style={{ padding: '8px 10px' }}>Deals</th>
                <th style={{ padding: '8px 10px' }}>Pipeline</th>
                <th style={{ padding: '8px 10px' }}>Won Revenue</th>
                <th style={{ padding: '8px 10px' }}>Win Rate</th>
              </tr>
            </thead>
            <tbody>
              {analytics?.service_performance.map((svc) => (
                <tr key={svc.service} style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 700, color: '#0F172A' }}>{svc.service}</td>
                  <td style={{ padding: '8px 10px', color: '#475569' }}>{svc.opportunities_count}</td>
                  <td style={{ padding: '8px 10px', color: '#2563EB', fontWeight: 600 }}>
                    ₹{svc.pipeline_value.toLocaleString('en-IN')}
                  </td>
                  <td style={{ padding: '8px 10px', fontWeight: 700, color: '#059669' }}>
                    ₹{svc.won_revenue.toLocaleString('en-IN')}
                  </td>
                  <td style={{ padding: '8px 10px', fontWeight: 600, color: '#475569' }}>
                    {svc.win_rate}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Channel Effectiveness Breakdown */}
      <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 12px 0', color: '#111827' }}>
          Outreach Channel Performance Breakdown
        </h2>

        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
          <thead>
            <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#475569', fontWeight: 700 }}>
              <th style={{ padding: '10px 12px' }}>Channel</th>
              <th style={{ padding: '10px 12px' }}>Attempts</th>
              <th style={{ padding: '10px 12px' }}>Responses</th>
              <th style={{ padding: '10px 12px' }}>Response Rate</th>
              <th style={{ padding: '10px 12px' }}>Interested</th>
              <th style={{ padding: '10px 12px' }}>Meetings</th>
              <th style={{ padding: '10px 12px' }}>Conversions</th>
            </tr>
          </thead>
          <tbody>
            {analytics?.channel_effectiveness.map((ch) => (
              <tr key={ch.channel} style={{ borderBottom: '1px solid #F1F5F9' }}>
                <td style={{ padding: '10px 12px', fontWeight: 700, color: '#0F172A' }}>{ch.channel}</td>
                <td style={{ padding: '10px 12px', color: '#475569' }}>{ch.attempts}</td>
                <td style={{ padding: '10px 12px', color: '#475569' }}>{ch.responses}</td>
                <td style={{ padding: '10px 12px', fontWeight: 600, color: ch.response_rate >= 20 ? '#16A34A' : '#475569' }}>
                  {ch.response_rate}%
                </td>
                <td style={{ padding: '10px 12px', color: '#D97706', fontWeight: 600 }}>{ch.interested}</td>
                <td style={{ padding: '10px 12px', color: '#7C3AED', fontWeight: 600 }}>{ch.meetings_booked}</td>
                <td style={{ padding: '10px 12px', fontWeight: 700, color: '#059669' }}>{ch.conversions}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
