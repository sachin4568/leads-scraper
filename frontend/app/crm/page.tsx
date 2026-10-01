'use client';

import React, { useEffect, useState } from 'react';
import { api, CrmPipelineDashboardAPI, DealAPI } from '../lib/api';

export default function CrmPipelinePage() {
  const [pipeline, setPipeline] = useState<CrmPipelineDashboardAPI | null>(null);
  const [deals, setDeals] = useState<DealAPI[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [stageFilter, setStageFilter] = useState<string>('');
  const [serviceFilter, setServiceFilter] = useState<string>('');

  // Move stage modal state
  const [selectedDeal, setSelectedDeal] = useState<DealAPI | null>(null);
  const [targetStage, setTargetStage] = useState<string>('PROPOSAL');
  const [winLossReason, setWinLossReason] = useState<string>('');
  const [updatingStage, setUpdatingStage] = useState<boolean>(false);

  const loadPipelineData = () => {
    setLoading(true);
    Promise.all([
      api.getCrmPipeline().catch(() => null),
      api.getDeals({ stage: stageFilter || undefined, service_type: serviceFilter || undefined }).catch(() => []),
    ]).then(([pipeData, dealsData]) => {
      setPipeline(pipeData);
      setDeals(dealsData);
      setLoading(false);
    });
  };

  useEffect(() => {
    loadPipelineData();
  }, [stageFilter, serviceFilter]);

  const handleStageChangeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDeal) return;
    setUpdatingStage(true);

    api.updateDeal(selectedDeal.id, {
      stage: targetStage,
      win_loss_reason: winLossReason.trim() || undefined,
    })
      .then(() => {
        setUpdatingStage(false);
        setSelectedDeal(null);
        setWinLossReason('');
        loadPipelineData();
      })
      .catch((err) => {
        console.error('Failed to update deal stage:', err);
        setUpdatingStage(false);
      });
  };

  const getStageColor = (stage: string) => {
    switch (stage) {
      case 'QUALIFIED':
        return { bg: '#EFF6FF', text: '#2563EB', border: '#93C5FD' };
      case 'PROPOSAL':
        return { bg: '#FAF5FF', text: '#9333EA', border: '#D8B4FE' };
      case 'NEGOTIATION':
        return { bg: '#FFFBEB', text: '#D97706', border: '#FCD34D' };
      case 'WON':
        return { bg: '#ECFDF5', text: '#059669', border: '#6EE7B7' };
      case 'LOST':
        return { bg: '#FEF2F2', text: '#DC2626', border: '#FCA5A5' };
      default:
        return { bg: '#F1F5F9', text: '#475569', border: '#CBD5E1' };
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1440px', margin: '0 auto', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, margin: 0, color: '#111827' }}>
            CRM Pipeline & Revenue Tracking
          </h1>
          <p style={{ fontSize: '13px', color: '#6B7280', margin: '4px 0 0 0' }}>
            Live revenue forecasting, deal progression, and sales opportunity management
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
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
            ← Back to Operations Leads
          </a>
        </div>
      </div>

      {/* Revenue & Pipeline KPI Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Active Pipeline Value</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#1E293B', marginTop: '4px' }}>
            ₹{pipeline?.total_pipeline_value.toLocaleString('en-IN') ?? '0'}
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            Across {pipeline?.active_deals_count ?? 0} active opportunities
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Weighted Forecast</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#2563EB', marginTop: '4px' }}>
            ₹{pipeline?.weighted_pipeline_value.toLocaleString('en-IN') ?? '0'}
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            Probability-adjusted expected revenue
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Won Revenue</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#059669', marginTop: '4px' }}>
            ₹{pipeline?.won_revenue.toLocaleString('en-IN') ?? '0'}
          </div>
          <div style={{ fontSize: '11px', color: '#16A34A', fontWeight: 600, marginTop: '2px' }}>
            {pipeline?.won_deals_count ?? 0} closed deals
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Average Deal Size</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#7C3AED', marginTop: '4px' }}>
            ₹{pipeline?.avg_deal_size.toLocaleString('en-IN') ?? '0'}
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            Per sales opportunity
          </div>
        </div>

        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>Sales Win Rate</div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#D97706', marginTop: '4px' }}>
            {pipeline?.win_rate ?? 0}%
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
            {pipeline?.won_deals_count ?? 0} won vs {pipeline?.lost_deals_count ?? 0} lost
          </div>
        </div>
      </div>

      {/* Stage Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px', marginBottom: '24px' }}>
        {pipeline?.stages.map((st) => {
          const color = getStageColor(st.stage);
          return (
            <div
              key={st.stage}
              style={{
                background: color.bg,
                border: `1px solid ${color.border}`,
                borderRadius: '8px',
                padding: '12px',
              }}
            >
              <div style={{ fontSize: '11px', fontWeight: 700, color: color.text }}>{st.stage}</div>
              <div style={{ fontSize: '18px', fontWeight: 800, color: '#1E293B', marginTop: '2px' }}>
                {st.count} <span style={{ fontSize: '11px', fontWeight: 500, color: '#64748B' }}>deals</span>
              </div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: color.text, marginTop: '2px' }}>
                ₹{st.total_value.toLocaleString('en-IN')}
              </div>
            </div>
          );
        })}
      </div>

      {/* Deals Pipeline Table / List */}
      <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', marginBottom: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: '#111827' }}>
              Sales Opportunities & Deals Pipeline
            </h2>
            <div style={{ fontSize: '12px', color: '#6B7280', marginTop: '2px' }}>
              Track deal values, stage advancement, and expected revenue closing dates
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              style={{ padding: '6px 10px', border: '1px solid #D1D5DB', borderRadius: '6px', fontSize: '12px', background: '#FFF' }}
            >
              <option value="">Stage: All</option>
              <option value="QUALIFIED">QUALIFIED (40%)</option>
              <option value="PROPOSAL">PROPOSAL (60%)</option>
              <option value="NEGOTIATION">NEGOTIATION (80%)</option>
              <option value="WON">WON (100%)</option>
              <option value="LOST">LOST (0%)</option>
            </select>

            <select
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value)}
              style={{ padding: '6px 10px', border: '1px solid #D1D5DB', borderRadius: '6px', fontSize: '12px', background: '#FFF' }}
            >
              <option value="">Service: All</option>
              <option value="WEBSITE_DEVELOPMENT">Website Development</option>
              <option value="SEO">SEO Optimization</option>
              <option value="SMMA">Social Media Management</option>
              <option value="PAID_ADS">Paid Ads</option>
            </select>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: '#F9FAFB', borderBottom: '1px solid #E5E7EB', color: '#4B5563', fontWeight: 600 }}>
                <th style={{ padding: '12px 16px' }}>Opportunity Title & Business</th>
                <th style={{ padding: '12px 16px' }}>Service Type</th>
                <th style={{ padding: '12px 16px' }}>Deal Value</th>
                <th style={{ padding: '12px 16px' }}>Stage & Prob</th>
                <th style={{ padding: '12px 16px' }}>Weighted Value</th>
                <th style={{ padding: '12px 16px' }}>Owner</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>Stage Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#6B7280' }}>
                    Loading CRM deals pipeline...
                  </td>
                </tr>
              ) : deals.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#6B7280' }}>
                    No deals found matching the selected stage/service filter.
                  </td>
                </tr>
              ) : (
                deals.map((deal) => {
                  const color = getStageColor(deal.stage);
                  return (
                    <tr key={deal.id} style={{ borderBottom: '1px solid #F3F4F6' }}>
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ fontWeight: 700, color: '#111827' }}>{deal.title}</div>
                        <div style={{ fontSize: '11px', color: '#6B7280' }}>{deal.business_name || 'Lead Opportunity'}</div>
                      </td>
                      <td style={{ padding: '12px 16px', color: '#374151' }}>
                        {deal.service_type.replace(/_/g, ' ')}
                      </td>
                      <td style={{ padding: '12px 16px', fontWeight: 700, color: '#1E293B' }}>
                        ₹{deal.deal_value.toLocaleString('en-IN')}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            padding: '3px 8px',
                            borderRadius: '6px',
                            background: color.bg,
                            color: color.text,
                            border: `1px solid ${color.border}`,
                          }}
                        >
                          {deal.stage} ({Math.round(deal.probability * 100)}%)
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', color: '#64748B', fontWeight: 600 }}>
                        ₹{deal.weighted_value.toLocaleString('en-IN')}
                      </td>
                      <td style={{ padding: '12px 16px', color: '#6B7280', fontSize: '12px' }}>
                        {deal.owner || 'Sales Rep'}
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        <button
                          onClick={() => {
                            setSelectedDeal(deal);
                            setTargetStage(deal.stage);
                          }}
                          style={{
                            padding: '5px 12px',
                            background: '#EFF6FF',
                            color: '#2563EB',
                            border: '1px solid #BFDBFE',
                            borderRadius: '4px',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Move Stage →
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Revenue by Service & Source Breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Service Breakdown */}
        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 12px 0', color: '#111827' }}>
            Revenue by Service Pitch
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {pipeline?.revenue_by_service.map((svc, idx) => (
              <div key={idx} style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', padding: '12px', borderRadius: '8px', fontSize: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, color: '#0F172A' }}>{svc.category}</span>
                  <span style={{ fontSize: '11px', color: '#64748B' }}>{svc.deals_count} Deals</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '6px', fontSize: '11px' }}>
                  <div>Won Revenue: <strong style={{ color: '#059669' }}>₹{svc.won_revenue.toLocaleString('en-IN')}</strong></div>
                  <div>In Pipeline: <strong style={{ color: '#2563EB' }}>₹{svc.pipeline_value.toLocaleString('en-IN')}</strong></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Source Breakdown */}
        <div style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 12px 0', color: '#111827' }}>
            Revenue by Acquisition Source
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {pipeline?.revenue_by_source.map((src, idx) => (
              <div key={idx} style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', padding: '12px', borderRadius: '8px', fontSize: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, color: '#0F172A' }}>{src.category}</span>
                  <span style={{ fontSize: '11px', color: '#64748B' }}>{src.deals_count} Deals</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '6px', fontSize: '11px' }}>
                  <div>Won Revenue: <strong style={{ color: '#059669' }}>₹{src.won_revenue.toLocaleString('en-IN')}</strong></div>
                  <div>In Pipeline: <strong style={{ color: '#2563EB' }}>₹{src.pipeline_value.toLocaleString('en-IN')}</strong></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Move Stage Modal */}
      {selectedDeal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div style={{ background: '#FFF', borderRadius: '12px', width: '480px', padding: '24px', boxShadow: '0 10px 25px rgba(0,0,0,0.2)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 4px 0', color: '#111827' }}>
              Advance Deal Pipeline Stage
            </h2>
            <p style={{ fontSize: '12px', color: '#6B7280', margin: '0 0 16px 0' }}>
              {selectedDeal.title} • Current: <strong>{selectedDeal.stage}</strong>
            </p>

            <form onSubmit={handleStageChangeSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#374151', display: 'block', marginBottom: '4px' }}>
                  Select Target Pipeline Stage
                </label>
                <select
                  value={targetStage}
                  onChange={(e) => setTargetStage(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid #D1D5DB', borderRadius: '6px', fontSize: '13px' }}
                >
                  <option value="QUALIFIED">QUALIFIED (40% Probability)</option>
                  <option value="PROPOSAL">PROPOSAL (60% Probability)</option>
                  <option value="NEGOTIATION">NEGOTIATION (80% Probability)</option>
                  <option value="WON">WON (100% Closed Revenue 🎉)</option>
                  <option value="LOST">LOST (0% Lost Opportunity)</option>
                </select>
              </div>

              {(targetStage === 'WON' || targetStage === 'LOST') && (
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: '#374151', display: 'block', marginBottom: '4px' }}>
                    {targetStage === 'WON' ? 'Win Reason / Notes' : 'Loss Reason / Feedback'}
                  </label>
                  <input
                    type="text"
                    placeholder={targetStage === 'WON' ? 'e.g. Retainer approved' : 'e.g. Budget constraints'}
                    value={winLossReason}
                    onChange={(e) => setWinLossReason(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', border: '1px solid #D1D5DB', borderRadius: '6px', fontSize: '13px' }}
                  />
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '12px' }}>
                <button
                  type="button"
                  onClick={() => setSelectedDeal(null)}
                  style={{ padding: '8px 16px', background: '#F3F4F6', color: '#374151', border: 'none', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updatingStage}
                  style={{ padding: '8px 16px', background: targetStage === 'WON' ? '#059669' : '#2563EB', color: '#FFF', border: 'none', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                >
                  {updatingStage ? 'Updating...' : 'Save Stage Progression'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
