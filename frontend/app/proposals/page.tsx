'use client';

import React, { useEffect, useState } from 'react';
import { api, ProposalAPI, ProposalMetricsAPI } from '../lib/api';

export default function ProposalsPage() {
  const [proposals, setProposals] = useState<ProposalAPI[]>([]);
  const [metrics, setMetrics] = useState<ProposalMetricsAPI | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Selected proposal for Version Revision Modal
  const [selectedProposalForVersion, setSelectedProposalForVersion] = useState<ProposalAPI | null>(null);
  const [newVersionBase, setNewVersionBase] = useState<number>(0);
  const [newVersionAddons, setNewVersionAddons] = useState<number>(0);
  const [newVersionDiscount, setNewVersionDiscount] = useState<number>(0);
  const [newVersionSummary, setNewVersionSummary] = useState<string>('');
  const [savingVersion, setSavingVersion] = useState<boolean>(false);

  // Selected proposal for History Modal
  const [selectedProposalDetail, setSelectedProposalDetail] = useState<ProposalAPI | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);

  // Status transition modal
  const [statusModalProposal, setStatusModalProposal] = useState<ProposalAPI | null>(null);
  const [targetStatus, setTargetStatus] = useState<string>('PROPOSAL_SENT');
  const [rejectionReason, setRejectionReason] = useState<string>('');
  const [updatingStatus, setUpdatingStatus] = useState<boolean>(false);

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api.getProposals({ status: statusFilter || undefined, search: searchQuery || undefined }).catch(() => ({ total: 0, page: 1, page_size: 50, proposals: [] })),
      api.getProposalMetrics().catch(() => null),
    ]).then(([listRes, metricsRes]) => {
      setProposals(listRes.proposals);
      setMetrics(metricsRes);
      setLoading(false);
    });
  };

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadData();
  };

  const handleOpenVersionModal = (prop: ProposalAPI) => {
    setSelectedProposalForVersion(prop);
    setNewVersionBase(prop.base_price);
    setNewVersionAddons(prop.addons_total);
    setNewVersionDiscount(prop.discount_amount);
    setNewVersionSummary('');
  };

  const handleSaveNewVersion = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProposalForVersion) return;
    setSavingVersion(true);
    api.createProposalVersion(selectedProposalForVersion.id, {
      base_price: Number(newVersionBase),
      addons_total: Number(newVersionAddons),
      discount_amount: Number(newVersionDiscount),
      change_summary: newVersionSummary.trim() || undefined,
    })
      .then(() => {
        setSavingVersion(false);
        setSelectedProposalForVersion(null);
        loadData();
      })
      .catch((err) => {
        console.error('Failed to create proposal version:', err);
        setSavingVersion(false);
      });
  };

  const handleOpenHistoryModal = (proposalId: string) => {
    setLoadingDetail(true);
    api.getProposalDetail(proposalId)
      .then((detail) => {
        setSelectedProposalDetail(detail);
        setLoadingDetail(false);
      })
      .catch((err) => {
        console.error('Failed to fetch proposal history:', err);
        setLoadingDetail(false);
      });
  };

  const handleStatusTransitionSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!statusModalProposal) return;
    setUpdatingStatus(true);
    api.updateProposalStatus(statusModalProposal.id, {
      status: targetStatus,
      rejection_reason: targetStatus === 'REJECTED' ? rejectionReason.trim() : undefined,
    })
      .then(() => {
        setUpdatingStatus(false);
        setStatusModalProposal(null);
        setRejectionReason('');
        loadData();
      })
      .catch((err) => {
        console.error('Failed to update proposal status:', err);
        setUpdatingStatus(false);
      });
  };

  const getStatusBadgeStyle = (status: string) => {
    switch (status) {
      case 'PROPOSAL_DRAFT':
        return { bg: '#F1F5F9', color: '#475569', label: 'Draft' };
      case 'PROPOSAL_SENT':
        return { bg: '#EFF6FF', color: '#1D4ED8', label: 'Sent' };
      case 'VIEWED':
        return { bg: '#FDF4FF', color: '#A21CAF', label: 'Viewed' };
      case 'NEGOTIATION':
        return { bg: '#FEF3C7', color: '#B45309', label: 'Negotiation' };
      case 'ACCEPTED':
        return { bg: '#DCFCE7', color: '#15803D', label: 'Accepted (Won)' };
      case 'REJECTED':
        return { bg: '#FEE2E2', color: '#B91C1C', label: 'Rejected' };
      case 'EXPIRED':
        return { bg: '#F3F4F6', color: '#9CA3AF', label: 'Expired' };
      default:
        return { bg: '#F1F5F9', color: '#475569', label: status };
    }
  };

  return (
    <div style={{ padding: '24px 32px', backgroundColor: '#F8FAFC', minHeight: '100vh', fontFamily: 'Inter, system-ui, sans-serif' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: '700', color: '#0F172A', margin: 0 }}>Proposals & Commercial Quotations</h1>
          <p style={{ fontSize: '14px', color: '#64748B', margin: '4px 0 0 0' }}>
            Structured proposals, multi-tier pricing, versioned negotiation history, and CRM closing integration
          </p>
        </div>
        <button
          onClick={loadData}
          style={{
            padding: '8px 16px',
            backgroundColor: '#FFFFFF',
            border: '1px solid #CBD5E1',
            borderRadius: '8px',
            fontSize: '13px',
            fontWeight: '600',
            color: '#334155',
            cursor: 'pointer',
          }}
        >
          ↻ Refresh Proposals
        </button>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            Total Quoted Pipeline
          </div>
          <div style={{ fontSize: '24px', fontWeight: '700', color: '#0F172A' }}>
            ₹{metrics ? (metrics.total_quoted_pipeline / 100000).toFixed(2) : '0.00'}L
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            Across {metrics?.total_proposals ?? 0} proposal records
          </div>
        </div>

        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            Won Proposal Revenue
          </div>
          <div style={{ fontSize: '24px', fontWeight: '700', color: '#10B981' }}>
            ₹{metrics ? (metrics.total_won_revenue / 100000).toFixed(2) : '0.00'}L
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            {metrics?.accepted_count ?? 0} deals accepted & closed
          </div>
        </div>

        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            Proposal Win Rate
          </div>
          <div style={{ fontSize: '24px', fontWeight: '700', color: '#2563EB' }}>
            {metrics?.proposal_to_win_rate ?? 0}%
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            Avg Deal Value: ₹{metrics ? metrics.avg_proposal_value.toLocaleString('en-IN') : 0}
          </div>
        </div>

        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            Active Negotiations
          </div>
          <div style={{ fontSize: '24px', fontWeight: '700', color: '#F59E0B' }}>
            {metrics?.negotiation_count ?? 0} In Play
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            Avg Discount: ₹{metrics ? metrics.avg_discount_amount.toLocaleString('en-IN') : 0}
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div style={{ backgroundColor: '#FFFFFF', padding: '16px 20px', borderRadius: '12px', border: '1px solid #E2E8F0', marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span style={{ fontSize: '13px', fontWeight: '600', color: '#475569' }}>Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '13px', color: '#0F172A' }}
          >
            <option value="">All Statuses</option>
            <option value="PROPOSAL_DRAFT">Draft</option>
            <option value="PROPOSAL_SENT">Sent</option>
            <option value="VIEWED">Viewed</option>
            <option value="NEGOTIATION">Negotiation</option>
            <option value="ACCEPTED">Accepted (Won)</option>
            <option value="REJECTED">Rejected</option>
            <option value="EXPIRED">Expired</option>
          </select>
        </div>

        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            placeholder="Search proposal #, client, title..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '13px', minWidth: '260px' }}
          />
          <button
            type="submit"
            style={{ padding: '6px 16px', backgroundColor: '#2563EB', color: '#FFFFFF', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}
          >
            Search
          </button>
        </form>
      </div>

      {/* Proposals Table */}
      <div style={{ backgroundColor: '#FFFFFF', borderRadius: '12px', border: '1px solid #E2E8F0', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0', textAlign: 'left', color: '#64748B' }}>
              <th style={{ padding: '12px 16px' }}>Proposal #</th>
              <th style={{ padding: '12px 16px' }}>Client & Deal</th>
              <th style={{ padding: '12px 16px' }}>Service</th>
              <th style={{ padding: '12px 16px' }}>Commercial Quote</th>
              <th style={{ padding: '12px 16px' }}>Version</th>
              <th style={{ padding: '12px 16px' }}>Status</th>
              <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} style={{ padding: '32px', textAlign: 'center', color: '#94A3B8' }}>
                  Loading proposals...
                </td>
              </tr>
            ) : proposals.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: '32px', textAlign: 'center', color: '#94A3B8' }}>
                  No proposals found matching criteria. Create proposals from qualified CRM deals.
                </td>
              </tr>
            ) : (
              proposals.map((p) => {
                const badge = getStatusBadgeStyle(p.status);
                return (
                  <tr key={p.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                    <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontWeight: '700', color: '#1E293B' }}>
                      {p.proposal_number}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: '600', color: '#0F172A' }}>{p.client_name}</div>
                      <div style={{ fontSize: '12px', color: '#64748B' }}>{p.title}</div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ fontSize: '11px', fontWeight: '700', padding: '2px 8px', borderRadius: '4px', backgroundColor: '#F1F5F9', color: '#475569' }}>
                        {p.service_type}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: '700', color: '#0F172A', fontSize: '14px' }}>
                        ₹{p.quoted_amount.toLocaleString('en-IN')}
                      </div>
                      <div style={{ fontSize: '11px', color: '#94A3B8' }}>
                        Base: ₹{p.base_price.toLocaleString('en-IN')} {p.addons_total > 0 && `+ ₹${p.addons_total.toLocaleString('en-IN')}`} {p.discount_amount > 0 && `- ₹${p.discount_amount.toLocaleString('en-IN')}`}
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ backgroundColor: '#EEF2FF', color: '#4338CA', padding: '2px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: '700' }}>
                        v{p.current_version}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ backgroundColor: badge.bg, color: badge.color, padding: '4px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: '700' }}>
                        {badge.label}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <button
                        onClick={() => { setStatusModalProposal(p); setTargetStatus(p.status); }}
                        style={{ padding: '4px 10px', backgroundColor: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: '6px', fontSize: '12px', fontWeight: '600', color: '#334155', cursor: 'pointer', marginRight: '6px' }}
                      >
                        Status
                      </button>
                      <button
                        onClick={() => handleOpenVersionModal(p)}
                        style={{ padding: '4px 10px', backgroundColor: '#EEF2FF', border: '1px solid #C7D2FE', borderRadius: '6px', fontSize: '12px', fontWeight: '600', color: '#4338CA', cursor: 'pointer', marginRight: '6px' }}
                      >
                        + Version
                      </button>
                      <button
                        onClick={() => handleOpenHistoryModal(p.id)}
                        style={{ padding: '4px 10px', backgroundColor: '#F8FAFC', border: '1px solid #CBD5E1', borderRadius: '6px', fontSize: '12px', fontWeight: '600', color: '#475569', cursor: 'pointer' }}
                      >
                        History
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 1. Revision / New Version Modal */}
      {selectedProposalForVersion && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: '#FFFFFF', padding: '24px', borderRadius: '12px', maxWidth: '500px', width: '100%' }}>
            <h3 style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 16px 0', color: '#0F172A' }}>
              Create Revised Version (v{selectedProposalForVersion.current_version + 1})
            </h3>
            <p style={{ fontSize: '13px', color: '#64748B', marginBottom: '16px' }}>
              Previous versions are preserved immutably in the commercial audit history.
            </p>
            <form onSubmit={handleSaveNewVersion} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: '600', color: '#475569' }}>Base Price (₹)</label>
                <input
                  type="number"
                  value={newVersionBase}
                  onChange={(e) => setNewVersionBase(Number(e.target.value))}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', marginTop: '4px' }}
                  required
                />
              </div>
              <div>
                <label style={{ fontSize: '12px', fontWeight: '600', color: '#475569' }}>Add-ons Total (₹)</label>
                <input
                  type="number"
                  value={newVersionAddons}
                  onChange={(e) => setNewVersionAddons(Number(e.target.value))}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', marginTop: '4px' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '12px', fontWeight: '600', color: '#475569' }}>Negotiated Discount (₹)</label>
                <input
                  type="number"
                  value={newVersionDiscount}
                  onChange={(e) => setNewVersionDiscount(Number(e.target.value))}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', marginTop: '4px' }}
                />
              </div>
              <div style={{ padding: '10px', backgroundColor: '#F8FAFC', borderRadius: '6px', fontSize: '14px', fontWeight: '700', color: '#0F172A' }}>
                New Quoted Total: ₹{(newVersionBase + newVersionAddons - newVersionDiscount).toLocaleString('en-IN')}
              </div>
              <div>
                <label style={{ fontSize: '12px', fontWeight: '600', color: '#475569' }}>Revision Reason / Change Summary</label>
                <input
                  type="text"
                  placeholder="e.g. 10% discount offered during negotiation call"
                  value={newVersionSummary}
                  onChange={(e) => setNewVersionSummary(e.target.value)}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', marginTop: '4px' }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                <button
                  type="button"
                  onClick={() => setSelectedProposalForVersion(null)}
                  style={{ padding: '8px 16px', backgroundColor: '#F1F5F9', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingVersion}
                  style={{ padding: '8px 16px', backgroundColor: '#2563EB', color: '#FFFFFF', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}
                >
                  {savingVersion ? 'Saving...' : 'Save New Version'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 2. Status Transition Modal */}
      {statusModalProposal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: '#FFFFFF', padding: '24px', borderRadius: '12px', maxWidth: '450px', width: '100%' }}>
            <h3 style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 16px 0', color: '#0F172A' }}>
              Update Proposal Lifecycle Status
            </h3>
            <form onSubmit={handleStatusTransitionSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: '600', color: '#475569' }}>Target Status</label>
                <select
                  value={targetStatus}
                  onChange={(e) => setTargetStatus(e.target.value)}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', marginTop: '4px', fontSize: '13px' }}
                >
                  <option value="PROPOSAL_DRAFT">Draft</option>
                  <option value="PROPOSAL_SENT">Proposal Sent</option>
                  <option value="VIEWED">Viewed by Client</option>
                  <option value="NEGOTIATION">Under Negotiation</option>
                  <option value="ACCEPTED">ACCEPTED (Close Deal as WON)</option>
                  <option value="REJECTED">REJECTED (Mark Deal as LOST)</option>
                  <option value="EXPIRED">Expired</option>
                </select>
              </div>
              {targetStatus === 'ACCEPTED' && (
                <div style={{ padding: '10px', backgroundColor: '#DCFCE7', borderRadius: '6px', fontSize: '12px', color: '#15803D', fontWeight: '500' }}>
                  ✓ Accepting this proposal will automatically mark the CRM Deal as <strong>WON</strong> and record <strong>₹{statusModalProposal.quoted_amount.toLocaleString('en-IN')}</strong> in closed revenue.
                </div>
              )}
              {targetStatus === 'REJECTED' && (
                <div>
                  <label style={{ fontSize: '12px', fontWeight: '600', color: '#475569' }}>Rejection Reason</label>
                  <input
                    type="text"
                    placeholder="e.g. Budget constraints, chose competitor"
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                    style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', marginTop: '4px' }}
                    required
                  />
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                <button
                  type="button"
                  onClick={() => setStatusModalProposal(null)}
                  style={{ padding: '8px 16px', backgroundColor: '#F1F5F9', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updatingStatus}
                  style={{ padding: '8px 16px', backgroundColor: targetStatus === 'ACCEPTED' ? '#10B981' : '#2563EB', color: '#FFFFFF', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}
                >
                  {updatingStatus ? 'Updating...' : 'Confirm Update'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 3. Version History Audit Modal */}
      {selectedProposalDetail && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: '#FFFFFF', padding: '24px', borderRadius: '12px', maxWidth: '600px', width: '100%', maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '18px', fontWeight: '700', margin: 0, color: '#0F172A' }}>
                Commercial History: {selectedProposalDetail.proposal_number}
              </h3>
              <button onClick={() => setSelectedProposalDetail(null)} style={{ border: 'none', background: 'none', fontSize: '18px', cursor: 'pointer' }}>✕</button>
            </div>
            <p style={{ fontSize: '13px', color: '#64748B', marginBottom: '16px' }}>
              Client: <strong>{selectedProposalDetail.client_name}</strong> | Service: <strong>{selectedProposalDetail.service_type}</strong>
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {selectedProposalDetail.versions.map((ver) => (
                <div key={ver.id} style={{ padding: '12px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontWeight: '700', color: '#1E293B', fontSize: '14px' }}>Version {ver.version_number}</span>
                    <span style={{ fontSize: '14px', fontWeight: '700', color: '#2563EB' }}>₹{ver.quoted_amount.toLocaleString('en-IN')}</span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#64748B', display: 'flex', gap: '12px' }}>
                    <span>Base: ₹{ver.base_price.toLocaleString('en-IN')}</span>
                    {ver.addons_total > 0 && <span>Addons: +₹{ver.addons_total.toLocaleString('en-IN')}</span>}
                    {ver.discount_amount > 0 && <span style={{ color: '#DC2626' }}>Discount: -₹{ver.discount_amount.toLocaleString('en-IN')}</span>}
                  </div>
                  {ver.change_summary && (
                    <div style={{ fontSize: '12px', color: '#475569', marginTop: '6px', fontStyle: 'italic' }}>
                      "{ver.change_summary}"
                    </div>
                  )}
                  <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '4px' }}>
                    Created: {new Date(ver.created_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
