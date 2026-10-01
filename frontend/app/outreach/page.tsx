'use client';

import React, { useEffect, useState } from 'react';
import { api, OperationsLeadItemAPI, OutreachAnalyticsAPI } from '../lib/api';

export default function OutreachPage() {
  const [analytics, setAnalytics] = useState<OutreachAnalyticsAPI | null>(null);
  const [queueLeads, setQueueLeads] = useState<OperationsLeadItemAPI[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getOutreachAnalytics().catch(() => null),
      api.getOperationsLeads({ priority_queue: 'CONTACT_NOW', page_size: 15 }).catch(() => ({ total: 0, page: 1, page_size: 15, results: [] })),
    ]).then(([analyticsData, leadsData]) => {
      setAnalytics(analyticsData);
      setQueueLeads(leadsData.results || []);
      setLoading(false);
    });
  }, []);

  return (
    <div style={{ padding: '24px', maxWidth: '1440px', margin: '0 auto', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, margin: 0, color: '#111827' }}>Outreach Performance & Sales Funnel Analytics</h1>
          <p style={{ fontSize: '13px', color: '#6B7280', margin: '4px 0 0 0' }}>
            Pipeline conversion stages, response tracking, and channel effectiveness
          </p>
        </div>
        <a
          href="/operations/leads"
          style={{
            padding: '8px 16px',
            background: '#2563EB',
            color: '#FFF',
            borderRadius: '6px',
            textDecoration: 'none',
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          Open Operations Lead Queue ↗
        </a>
      </div>

      {/* KPI Overview Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Total Contacted Leads</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#1E293B', marginTop: '4px' }}>
            {analytics?.contacted_leads ?? 0}
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            Out of {analytics?.contactable_leads ?? 0} contactable ({analytics ? Math.round((analytics.contacted_leads / Math.max(1, analytics.contactable_leads)) * 100) : 0}%)
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Overall Response Rate</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#2563EB', marginTop: '4px' }}>
            {analytics?.overall_response_rate ?? 0}%
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            {analytics?.responded_leads ?? 0} leads engaged back
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Interest Rate</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#D97706', marginTop: '4px' }}>
            {analytics?.overall_interest_rate ?? 0}%
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            {analytics?.interested_leads ?? 0} positive responses
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Meetings Booked</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#7C3AED', marginTop: '4px' }}>
            {analytics?.meeting_booked_leads ?? 0}
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            {analytics?.qualified_leads ?? 0} qualified for closing
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Client Conversions</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#059669', marginTop: '4px' }}>
            {analytics?.converted_leads ?? 0}
          </div>
          <div style={{ fontSize: '11px', color: '#16A34A', fontWeight: 600, marginTop: '2px' }}>
            {analytics?.overall_conversion_rate ?? 0}% conversion rate
          </div>
        </div>
      </div>

      {/* Pipeline Funnel Visualizer */}
      <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', marginBottom: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 16px 0', color: '#111827' }}>
          Sales Conversion Pipeline Funnel
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
          {analytics?.funnel.map((f, idx) => (
            <div
              key={idx}
              style={{
                background: idx === analytics.funnel.length - 1 ? '#ECFDF5' : '#F8FAFC',
                border: `1px solid ${idx === analytics.funnel.length - 1 ? '#6EE7B7' : '#E2E8F0'}`,
                borderRadius: '8px',
                padding: '12px',
                textAlign: 'center',
                position: 'relative',
              }}
            >
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748B' }}>{f.stage}</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: idx === analytics.funnel.length - 1 ? '#059669' : '#0F172A', marginTop: '4px' }}>
                {f.count}
              </div>
              <div style={{ fontSize: '10px', color: '#94A3B8', marginTop: '4px' }}>
                {idx === 0 ? '100%' : `${f.conversion_rate_from_previous}% step`}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Channel Effectiveness & Service Performance Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px', marginBottom: '24px' }}>
        {/* Channel Effectiveness Table */}
        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 12px 0', color: '#111827' }}>
            Outreach Channel Effectiveness
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#475569', fontWeight: 700 }}>
                <th style={{ padding: '8px 10px' }}>Channel</th>
                <th style={{ padding: '8px 10px' }}>Attempts</th>
                <th style={{ padding: '8px 10px' }}>Responses</th>
                <th style={{ padding: '8px 10px' }}>Response Rate</th>
                <th style={{ padding: '8px 10px' }}>Meetings</th>
                <th style={{ padding: '8px 10px' }}>Conversions</th>
              </tr>
            </thead>
            <tbody>
              {analytics?.channel_effectiveness.map((ch, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: '10px', fontWeight: 700, color: '#1E293B' }}>{ch.channel}</td>
                  <td style={{ padding: '10px', color: '#475569' }}>{ch.attempts}</td>
                  <td style={{ padding: '10px', color: '#475569' }}>{ch.responses}</td>
                  <td style={{ padding: '10px', fontWeight: 600, color: ch.response_rate >= 20 ? '#16A34A' : '#475569' }}>
                    {ch.response_rate}%
                  </td>
                  <td style={{ padding: '10px', color: '#7C3AED', fontWeight: 600 }}>{ch.meetings_booked}</td>
                  <td style={{ padding: '10px', color: '#059669', fontWeight: 700 }}>{ch.conversions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Service Performance Breakdown */}
        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 12px 0', color: '#111827' }}>
            Service Performance Breakdown
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {analytics?.service_effectiveness.map((svc, idx) => (
              <div key={idx} style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', padding: '12px', borderRadius: '8px', fontSize: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, color: '#0F172A' }}>{svc.service.replace(/_/g, ' ')}</span>
                  <span style={{ fontSize: '11px', color: '#64748B' }}>{svc.leads_count} Leads in Niche</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '8px', marginTop: '8px', color: '#475569', fontSize: '11px' }}>
                  <div>Attempts: <strong>{svc.attempts}</strong></div>
                  <div>Responses: <strong>{svc.responses}</strong></div>
                  <div>Meetings: <strong style={{ color: '#7C3AED' }}>{svc.meetings_booked}</strong></div>
                  <div>Converted: <strong style={{ color: '#059669' }}>{svc.conversions}</strong></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Immediate Cohort Action Queue */}
      <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: '#111827' }}>
              🔴 Immediate Outreach Cohort (Contact Now Queue)
            </h2>
            <div style={{ fontSize: '12px', color: '#6B7280', marginTop: '2px' }}>
              High-opportunity leads ready for execution
            </div>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: '#F9FAFB', borderBottom: '1px solid #E5E7EB', color: '#4B5563', fontWeight: 600 }}>
                <th style={{ padding: '12px 16px' }}>Business Name</th>
                <th style={{ padding: '12px 16px' }}>Opportunity</th>
                <th style={{ padding: '12px 16px' }}>Recommended Channel</th>
                <th style={{ padding: '12px 16px' }}>Direct Actions</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>Dossier</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} style={{ padding: '40px', textAlign: 'center', color: '#6B7280' }}>
                    Loading active cohort queue...
                  </td>
                </tr>
              ) : queueLeads.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: '40px', textAlign: 'center', color: '#6B7280' }}>
                    No leads in the immediate Contact Now queue.
                  </td>
                </tr>
              ) : (
                queueLeads.map((lead) => (
                  <tr key={lead.id} style={{ borderBottom: '1px solid #F3F4F6' }}>
                    <td style={{ padding: '12px 16px', fontWeight: 600, color: '#111827' }}>
                      {lead.business_name}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ fontSize: '11px', fontWeight: 700, padding: '3px 8px', borderRadius: '12px', background: '#FEF2F2', color: '#DC2626', border: '1px solid #FCA5A5' }}>
                        {lead.opportunity_score} • {lead.opportunity_category}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ fontWeight: 600, color: '#2563EB' }}>
                        {lead.recommended_channel?.label || 'Direct'}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        {lead.execution_links?.slice(0, 2).map((link, idx) => (
                          <a
                            key={idx}
                            href={link.url}
                            target={link.channel === 'PHONE' || link.channel === 'EMAIL' ? '_self' : '_blank'}
                            rel="noreferrer"
                            style={{
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              fontWeight: 600,
                              textDecoration: 'none',
                              background: link.channel === 'WHATSAPP' ? '#DCFCE7' : link.channel === 'PHONE' ? '#DBEAFE' : '#F1F5F9',
                              color: link.channel === 'WHATSAPP' ? '#166534' : link.channel === 'PHONE' ? '#1E40AF' : '#334155',
                              border: '1px solid #E2E8F0',
                            }}
                          >
                            {link.channel === 'WHATSAPP' ? '💬 WhatsApp' : link.channel === 'PHONE' ? '📞 Call' : '✉️ Email'}
                          </a>
                        ))}
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <a
                        href={`/operations/leads?search=${encodeURIComponent(lead.business_name)}`}
                        style={{
                          padding: '5px 12px',
                          background: '#EFF6FF',
                          color: '#2563EB',
                          border: '1px solid #BFDBFE',
                          borderRadius: '4px',
                          textDecoration: 'none',
                          fontSize: '12px',
                          fontWeight: 600,
                        }}
                      >
                        Action Dossier →
                      </a>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
