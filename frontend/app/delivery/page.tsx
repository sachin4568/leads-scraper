'use client';

import React, { useEffect, useState } from 'react';
import { api, CustomerAPI, DeliverableAPI, DeliveryMetricsAPI, DeliveryProjectAPI } from '../lib/api';

export default function DeliveryPage() {
  const [activeTab, setActiveTab] = useState<'projects' | 'customers'>('projects');
  const [projects, setProjects] = useState<DeliveryProjectAPI[]>([]);
  const [customers, setCustomers] = useState<CustomerAPI[]>([]);
  const [metrics, setMetrics] = useState<DeliveryMetricsAPI | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters
  const [stageFilter, setStageFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Selected project for deliverable management
  const [selectedProjectDetail, setSelectedProjectDetail] = useState<DeliveryProjectAPI | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);

  // Add Deliverable Modal
  const [addDelivProject, setAddDelivProject] = useState<DeliveryProjectAPI | null>(null);
  const [newDelivTitle, setNewDelivTitle] = useState<string>('');
  const [newDelivNotes, setNewDelivNotes] = useState<string>('');
  const [addingDeliv, setAddingDeliv] = useState<boolean>(false);

  // Stage Transition Modal
  const [stageModalProject, setStageModalProject] = useState<DeliveryProjectAPI | null>(null);
  const [targetStage, setTargetStage] = useState<string>('IN_PROGRESS');
  const [updatingStage, setUpdatingStage] = useState<boolean>(false);

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api.getDeliveryProjects({ status: stageFilter || undefined, search: searchQuery || undefined }).catch(() => ({ total: 0, page: 1, page_size: 50, projects: [] })),
      api.getCustomers({ search: searchQuery || undefined }).catch(() => ({ total: 0, page: 1, page_size: 50, customers: [] })),
      api.getDeliveryMetrics().catch(() => null),
    ]).then(([projRes, custRes, metricsRes]) => {
      setProjects(projRes.projects);
      setCustomers(custRes.customers);
      setMetrics(metricsRes);
      setLoading(false);
    });
  };

  useEffect(() => {
    loadData();
  }, [stageFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadData();
  };

  const handleOpenProjectDetail = (projectId: string) => {
    setLoadingDetail(true);
    api.getProjectDetail(projectId)
      .then((detail) => {
        setSelectedProjectDetail(detail);
        setLoadingDetail(false);
      })
      .catch((err) => {
        console.error('Failed to load project detail:', err);
        setLoadingDetail(false);
      });
  };

  const handleToggleDeliverable = (deliverable: DeliverableAPI) => {
    const nextStatus = deliverable.status === 'COMPLETED' ? 'PENDING' : 'COMPLETED';
    api.updateDeliverableStatus(deliverable.id, nextStatus)
      .then(() => {
        if (selectedProjectDetail) {
          handleOpenProjectDetail(selectedProjectDetail.id);
        }
        loadData();
      })
      .catch((err) => console.error('Failed to toggle deliverable:', err));
  };

  const handleAddDeliverableSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!addDelivProject || !newDelivTitle.trim()) return;
    setAddingDeliv(true);
    api.addProjectDeliverable(addDelivProject.id, {
      title: newDelivTitle.trim(),
      notes: newDelivNotes.trim() || undefined,
    })
      .then(() => {
        setAddingDeliv(false);
        setAddDelivProject(null);
        setNewDelivTitle('');
        setNewDelivNotes('');
        loadData();
      })
      .catch((err) => {
        console.error('Failed to add deliverable:', err);
        setAddingDeliv(false);
      });
  };

  const handleStageTransitionSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!stageModalProject) return;
    setUpdatingStage(true);
    api.updateProjectStatus(stageModalProject.id, targetStage)
      .then(() => {
        setUpdatingStage(false);
        setStageModalProject(null);
        loadData();
      })
      .catch((err) => {
        console.error('Failed to update project stage:', err);
        setUpdatingStage(false);
      });
  };

  const getStageBadgeStyle = (status: string) => {
    switch (status) {
      case 'ONBOARDING':
        return { bg: '#EEF2FF', color: '#4338CA', label: 'Onboarding' };
      case 'REQUIREMENTS':
        return { bg: '#EFF6FF', color: '#1D4ED8', label: 'Requirements' };
      case 'IN_PROGRESS':
        return { bg: '#FEF3C7', color: '#B45309', label: 'In Progress' };
      case 'REVIEW':
        return { bg: '#FDF4FF', color: '#A21CAF', label: 'Internal Review' };
      case 'CLIENT_APPROVAL':
        return { bg: '#F3E8FF', color: '#7E22CE', label: 'Client Approval' };
      case 'COMPLETED':
        return { bg: '#DCFCE7', color: '#15803D', label: 'Completed (Realized)' };
      case 'ON_HOLD':
        return { bg: '#F1F5F9', color: '#64748B', label: 'On Hold' };
      case 'CANCELLED':
        return { bg: '#FEE2E2', color: '#B91C1C', label: 'Cancelled' };
      default:
        return { bg: '#F1F5F9', color: '#475569', label: status };
    }
  };

  return (
    <div style={{ padding: '24px 32px', backgroundColor: '#F8FAFC', minHeight: '100vh', fontFamily: 'Inter, system-ui, sans-serif' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: '700', color: '#0F172A', margin: 0 }}>Customer Onboarding & Delivery Management</h1>
          <p style={{ fontSize: '14px', color: '#64748B', margin: '4px 0 0 0' }}>
            Transform won CRM deals into active delivery projects, track deliverables, and realize project revenue
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
          ↻ Refresh Delivery
        </button>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            In-Delivery Revenue
          </div>
          <div style={{ fontSize: '24px', fontWeight: '700', color: '#2563EB' }}>
            ₹{metrics ? (metrics.in_delivery_revenue / 100000).toFixed(2) : '0.00'}L
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            Across {metrics?.active_projects ?? 0} active delivery projects
          </div>
        </div>

        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            Realized Won Revenue
          </div>
          <div style={{ fontSize: '24px', fontWeight: '700', color: '#10B981' }}>
            ₹{metrics ? (metrics.realized_completed_revenue / 100000).toFixed(2) : '0.00'}L
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            {metrics?.completed_projects ?? 0} projects delivered & approved
          </div>
        </div>

        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            Active Customers
          </div>
          <div style={{ fontSize: '24px', fontWeight: '700', color: '#0F172A' }}>
            {metrics?.active_customers ?? 0}
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            {metrics?.total_customers ?? 0} total converted accounts
          </div>
        </div>

        <div style={{ backgroundColor: '#FFFFFF', padding: '20px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
            Avg Delivery Progress
          </div>
          <div style={{ fontSize: '24px', fontWeight: '700', color: '#F59E0B' }}>
            {metrics?.avg_project_progress ?? 0}%
          </div>
          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
            On-Time Delivery Rate: {metrics?.on_time_delivery_rate ?? 100}%
          </div>
        </div>
      </div>

      {/* Tabs & Filters */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setActiveTab('projects')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: 'none',
              fontSize: '13px',
              fontWeight: '600',
              backgroundColor: activeTab === 'projects' ? '#2563EB' : '#E2E8F0',
              color: activeTab === 'projects' ? '#FFFFFF' : '#475569',
              cursor: 'pointer',
            }}
          >
            Delivery Projects ({projects.length})
          </button>
          <button
            onClick={() => setActiveTab('customers')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: 'none',
              fontSize: '13px',
              fontWeight: '600',
              backgroundColor: activeTab === 'customers' ? '#2563EB' : '#E2E8F0',
              color: activeTab === 'customers' ? '#FFFFFF' : '#475569',
              cursor: 'pointer',
            }}
          >
            Customer Directory ({customers.length})
          </button>
        </div>

        {activeTab === 'projects' && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', fontWeight: '600', color: '#475569' }}>Stage:</span>
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '13px' }}
            >
              <option value="">All Stages</option>
              <option value="ONBOARDING">Onboarding</option>
              <option value="REQUIREMENTS">Requirements</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="REVIEW">Internal Review</option>
              <option value="CLIENT_APPROVAL">Client Approval</option>
              <option value="COMPLETED">Completed</option>
              <option value="ON_HOLD">On Hold</option>
            </select>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      {activeTab === 'projects' ? (
        <div style={{ backgroundColor: '#FFFFFF', borderRadius: '12px', border: '1px solid #E2E8F0', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0', textAlign: 'left', color: '#64748B' }}>
                <th style={{ padding: '12px 16px' }}>Project Name & Customer</th>
                <th style={{ padding: '12px 16px' }}>Service</th>
                <th style={{ padding: '12px 16px' }}>Contract Value</th>
                <th style={{ padding: '12px 16px' }}>Stage</th>
                <th style={{ padding: '12px 16px', width: '180px' }}>Delivery Progress</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} style={{ padding: '32px', textAlign: 'center', color: '#94A3B8' }}>
                    Loading projects...
                  </td>
                </tr>
              ) : projects.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding: '32px', textAlign: 'center', color: '#94A3B8' }}>
                    No delivery projects found. Accept proposals or convert WON deals to create projects.
                  </td>
                </tr>
              ) : (
                projects.map((proj) => {
                  const badge = getStageBadgeStyle(proj.status);
                  return (
                    <tr key={proj.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ fontWeight: '600', color: '#0F172A' }}>{proj.project_name}</div>
                        <div style={{ fontSize: '12px', color: '#64748B' }}>Customer: {proj.customer_name}</div>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{ fontSize: '11px', fontWeight: '700', padding: '2px 8px', borderRadius: '4px', backgroundColor: '#F1F5F9', color: '#475569' }}>
                          {proj.service_type}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', fontWeight: '700', color: '#0F172A' }}>
                        ₹{proj.contract_value.toLocaleString('en-IN')}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{ backgroundColor: badge.bg, color: badge.color, padding: '4px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: '700' }}>
                          {badge.label}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <div style={{ flex: 1, height: '8px', backgroundColor: '#E2E8F0', borderRadius: '4px', overflow: 'hidden' }}>
                            <div
                              style={{
                                width: `${proj.progress_percent}%`,
                                height: '100%',
                                backgroundColor: proj.progress_percent === 100 ? '#10B981' : '#2563EB',
                                borderRadius: '4px',
                              }}
                            />
                          </div>
                          <span style={{ fontSize: '12px', fontWeight: '600', color: '#475569', minWidth: '36px' }}>
                            {proj.progress_percent}%
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        <button
                          onClick={() => { setStageModalProject(proj); setTargetStage(proj.status); }}
                          style={{ padding: '4px 10px', backgroundColor: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: '6px', fontSize: '12px', fontWeight: '600', color: '#334155', cursor: 'pointer', marginRight: '6px' }}
                        >
                          Stage
                        </button>
                        <button
                          onClick={() => { setAddDelivProject(proj); setNewDelivTitle(''); setNewDelivNotes(''); }}
                          style={{ padding: '4px 10px', backgroundColor: '#EEF2FF', border: '1px solid #C7D2FE', borderRadius: '6px', fontSize: '12px', fontWeight: '600', color: '#4338CA', cursor: 'pointer', marginRight: '6px' }}
                        >
                          + Task
                        </button>
                        <button
                          onClick={() => handleOpenProjectDetail(proj.id)}
                          style={{ padding: '4px 10px', backgroundColor: '#2563EB', color: '#FFFFFF', border: 'none', borderRadius: '6px', fontSize: '12px', fontWeight: '600', cursor: 'pointer' }}
                        >
                          Deliverables
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      ) : (
        /* Customer Directory View */
        <div style={{ backgroundColor: '#FFFFFF', borderRadius: '12px', border: '1px solid #E2E8F0', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0', textAlign: 'left', color: '#64748B' }}>
                <th style={{ padding: '12px 16px' }}>Company Name</th>
                <th style={{ padding: '12px 16px' }}>Contact Details</th>
                <th style={{ padding: '12px 16px' }}>Lifetime Value</th>
                <th style={{ padding: '12px 16px' }}>Projects</th>
                <th style={{ padding: '12px 16px' }}>Status</th>
                <th style={{ padding: '12px 16px' }}>Onboarded Date</th>
              </tr>
            </thead>
            <tbody>
              {customers.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding: '32px', textAlign: 'center', color: '#94A3B8' }}>
                    No customers found.
                  </td>
                </tr>
              ) : (
                customers.map((c) => (
                  <tr key={c.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                    <td style={{ padding: '12px 16px', fontWeight: '600', color: '#0F172A' }}>
                      {c.company_name}
                      {c.website && (
                        <div style={{ fontSize: '11px', color: '#2563EB' }}>
                          <a href={c.website} target="_blank" rel="noreferrer">{c.website}</a>
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ color: '#334155' }}>{c.contact_email || '—'}</div>
                      <div style={{ fontSize: '11px', color: '#64748B' }}>{c.contact_phone || '—'}</div>
                    </td>
                    <td style={{ padding: '12px 16px', fontWeight: '700', color: '#10B981' }}>
                      ₹{c.lifetime_value.toLocaleString('en-IN')}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#334155' }}>
                      {c.projects_count} projects
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ backgroundColor: c.status === 'ACTIVE' ? '#DCFCE7' : '#EEF2FF', color: c.status === 'ACTIVE' ? '#15803D' : '#4338CA', padding: '2px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: '700' }}>
                        {c.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', color: '#64748B' }}>
                      {new Date(c.onboarded_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 1. Deliverables Detail Modal */}
      {selectedProjectDetail && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: '#FFFFFF', padding: '24px', borderRadius: '12px', maxWidth: '600px', width: '100%', maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '18px', fontWeight: '700', margin: 0, color: '#0F172A' }}>
                  {selectedProjectDetail.project_name}
                </h3>
                <p style={{ fontSize: '13px', color: '#64748B', margin: '4px 0 0 0' }}>
                  Contract Value: <strong>₹{selectedProjectDetail.contract_value.toLocaleString('en-IN')}</strong> | Progress: <strong>{selectedProjectDetail.progress_percent}%</strong>
                </p>
              </div>
              <button onClick={() => setSelectedProjectDetail(null)} style={{ border: 'none', background: 'none', fontSize: '18px', cursor: 'pointer' }}>✕</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '16px' }}>
              {selectedProjectDetail.deliverables.map((deliv) => (
                <div
                  key={deliv.id}
                  onClick={() => handleToggleDeliverable(deliv)}
                  style={{
                    padding: '12px 16px',
                    borderRadius: '8px',
                    border: '1px solid #E2E8F0',
                    backgroundColor: deliv.status === 'COMPLETED' ? '#F0FDF4' : '#FFFFFF',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <input
                      type="checkbox"
                      checked={deliv.status === 'COMPLETED'}
                      readOnly
                      style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                    />
                    <div>
                      <div style={{ fontSize: '13px', fontWeight: '600', color: deliv.status === 'COMPLETED' ? '#15803D' : '#0F172A', textDecoration: deliv.status === 'COMPLETED' ? 'line-through' : 'none' }}>
                        {deliv.title}
                      </div>
                      {deliv.notes && <div style={{ fontSize: '11px', color: '#64748B' }}>{deliv.notes}</div>}
                    </div>
                  </div>
                  <span style={{ fontSize: '11px', fontWeight: '700', color: deliv.status === 'COMPLETED' ? '#15803D' : '#64748B' }}>
                    {deliv.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 2. Add Deliverable Modal */}
      {addDelivProject && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: '#FFFFFF', padding: '24px', borderRadius: '12px', maxWidth: '450px', width: '100%' }}>
            <h3 style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 16px 0', color: '#0F172A' }}>
              Add Milestone / Deliverable
            </h3>
            <form onSubmit={handleAddDeliverableSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: '600', color: '#475569' }}>Deliverable Title</label>
                <input
                  type="text"
                  placeholder="e.g. WhatsApp Bot Webhook Setup"
                  value={newDelivTitle}
                  onChange={(e) => setNewDelivTitle(e.target.value)}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', marginTop: '4px' }}
                  required
                />
              </div>
              <div>
                <label style={{ fontSize: '12px', fontWeight: '600', color: '#475569' }}>Notes (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Needs Twilio sandbox credentials"
                  value={newDelivNotes}
                  onChange={(e) => setNewDelivNotes(e.target.value)}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', marginTop: '4px' }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                <button
                  type="button"
                  onClick={() => setAddDelivProject(null)}
                  style={{ padding: '8px 16px', backgroundColor: '#F1F5F9', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addingDeliv}
                  style={{ padding: '8px 16px', backgroundColor: '#2563EB', color: '#FFFFFF', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}
                >
                  {addingDeliv ? 'Adding...' : 'Add Deliverable'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 3. Stage Transition Modal */}
      {stageModalProject && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: '#FFFFFF', padding: '24px', borderRadius: '12px', maxWidth: '450px', width: '100%' }}>
            <h3 style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 16px 0', color: '#0F172A' }}>
              Update Delivery Stage
            </h3>
            <form onSubmit={handleStageTransitionSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: '600', color: '#475569' }}>Project Stage</label>
                <select
                  value={targetStage}
                  onChange={(e) => setTargetStage(e.target.value)}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', marginTop: '4px', fontSize: '13px' }}
                >
                  <option value="ONBOARDING">Onboarding</option>
                  <option value="REQUIREMENTS">Requirements Specification</option>
                  <option value="IN_PROGRESS">In Progress / Development</option>
                  <option value="REVIEW">Internal QA / Review</option>
                  <option value="CLIENT_APPROVAL">Client Review & Signoff</option>
                  <option value="COMPLETED">Completed (Realized Revenue)</option>
                  <option value="ON_HOLD">On Hold</option>
                  <option value="CANCELLED">Cancelled</option>
                </select>
              </div>
              {targetStage === 'COMPLETED' && (
                <div style={{ padding: '10px', backgroundColor: '#DCFCE7', borderRadius: '6px', fontSize: '12px', color: '#15803D', fontWeight: '500' }}>
                  ✓ Marking as Completed realizes <strong>₹{stageModalProject.contract_value.toLocaleString('en-IN')}</strong> in delivered revenue and completes project delivery.
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                <button
                  type="button"
                  onClick={() => setStageModalProject(null)}
                  style={{ padding: '8px 16px', backgroundColor: '#F1F5F9', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updatingStage}
                  style={{ padding: '8px 16px', backgroundColor: targetStage === 'COMPLETED' ? '#10B981' : '#2563EB', color: '#FFFFFF', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}
                >
                  {updatingStage ? 'Updating...' : 'Confirm Stage Update'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
