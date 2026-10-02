'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { api, OperationsLeadDetailAPI, OperationsLeadItemAPI } from '../../lib/api';

export default function OperationsLeadsPage() {
  const [leads, setLeads] = useState<OperationsLeadItemAPI[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(20);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [detailLead, setDetailLead] = useState<OperationsLeadDetailAPI | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [drawerTab, setDrawerTab] = useState<'ACTIONS' | 'TIMELINE' | 'DEALS' | 'INTELLIGENCE' | 'AUDIT'>('ACTIONS');

  // Deal Form State inside Drawer
  const [showDealForm, setShowDealForm] = useState<boolean>(false);
  const [dealTitle, setDealTitle] = useState<string>('');
  const [dealService, setDealService] = useState<string>('WEBSITE_DEVELOPMENT');
  const [dealValue, setDealValue] = useState<number>(35000);
  const [dealStage, setDealStage] = useState<string>('QUALIFIED');
  const [dealNotes, setDealNotes] = useState<string>('');
  const [submittingDeal, setSubmittingDeal] = useState<boolean>(false);

  // Filters State
  const [search, setSearch] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [oppCategory, setOppCategory] = useState<string>('');
  const [webStatus, setWebStatus] = useState<string>('');
  const [serviceFilter, setServiceFilter] = useState<string>('');
  const [workflowStatus, setWorkflowStatus] = useState<string>('');
  const [priorityQueue, setPriorityQueue] = useState<string>('');
  const [hasPhone, setHasPhone] = useState<boolean | undefined>(undefined);
  const [hasEmail, setHasEmail] = useState<boolean | undefined>(undefined);
  const [hasWhatsApp, setHasWhatsApp] = useState<boolean | undefined>(undefined);
  const [hasSocial, setHasSocial] = useState<boolean | undefined>(undefined);
  const [sortBy, setSortBy] = useState<string>('opportunity_score_desc');

  // Log Action Modal / Form State inside Drawer
  const [showActionForm, setShowActionForm] = useState<boolean>(false);
  const [actionChannel, setActionChannel] = useState<'PHONE' | 'EMAIL' | 'WHATSAPP' | 'SOCIAL_DM' | 'CONTACT_PAGE' | 'OTHER'>('PHONE');
  const [actionOutcome, setActionOutcome] = useState<'CONTACTED' | 'RESPONDED' | 'INTERESTED' | 'NOT_INTERESTED' | 'MEETING_BOOKED' | 'QUALIFIED' | 'CONVERTED' | 'LOST' | 'NO_RESPONSE' | 'WRONG_NUMBER' | 'BOUNCED' | 'FOLLOW_UP_SCHEDULED'>('NO_RESPONSE');
  const [actionNotes, setActionNotes] = useState<string>('');
  const [actionFollowUpDate, setActionFollowUpDate] = useState<string>('');
  const [submittingAction, setSubmittingAction] = useState<boolean>(false);

  // Debounce search input by 300ms to eliminate UI lag while typing
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(handler);
  }, [search]);

  // Load Leads
  const loadLeads = useCallback(() => {
    setLoading(true);
    api.getOperationsLeads({
      opportunity_category: oppCategory || undefined,
      website_status: webStatus || undefined,
      service: serviceFilter || undefined,
      workflow_status: workflowStatus || undefined,
      priority_queue: priorityQueue || undefined,
      has_phone: hasPhone,
      has_email: hasEmail,
      has_whatsapp: hasWhatsApp,
      has_social: hasSocial,
      search: debouncedSearch.trim() || undefined,
      sort_by: sortBy,
      page,
      page_size: pageSize,
    })
      .then((res) => {
        setLeads(res.results || []);
        setTotal(res.total || 0);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load leads:', err);
        setLeads([]);
        setTotal(0);
        setLoading(false);
      });
  }, [debouncedSearch, oppCategory, webStatus, serviceFilter, workflowStatus, priorityQueue, hasPhone, hasEmail, hasWhatsApp, hasSocial, sortBy, page, pageSize]);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  // Open Lead Detail
  const openLeadDetail = (leadId: string) => {
    setSelectedLeadId(leadId);
    setDetailLoading(true);
    setShowActionForm(false);
    api.getOperationsLeadDetail(leadId)
      .then((data) => {
        setDetailLead(data);
        setDetailLoading(false);
        if (data.recommended_channel?.channel && data.recommended_channel.channel !== 'NONE') {
          setActionChannel(data.recommended_channel.channel as any);
        }
      })
      .catch((err) => {
        console.error('Failed to load lead detail:', err);
        setDetailLoading(false);
      });
  };

  // Update Workflow Status
  const handleWorkflowChange = (leadId: string, newStatus: string) => {
    api.updateLeadWorkflow(leadId, newStatus)
      .then((updated) => {
        setLeads((prev) => prev.map((l) => (l.id === leadId ? { ...l, workflow_status: updated.workflow_status as any } : l)));
        if (detailLead && detailLead.id === leadId) {
          setDetailLead({ ...detailLead, workflow_status: updated.workflow_status as any });
        }
      })
      .catch((err) => console.error('Failed to update status:', err));
  };

  // Record Outreach Action
  const handleRecordActionSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLeadId) return;
    setSubmittingAction(true);

    api.recordLeadAction(selectedLeadId, {
      channel: actionChannel,
      outcome: actionOutcome,
      notes: actionNotes.trim() || undefined,
      follow_up_date: actionFollowUpDate ? new Date(actionFollowUpDate).toISOString() : undefined,
    })
      .then(() => {
        setSubmittingAction(false);
        setShowActionForm(false);
        setActionNotes('');
        setActionFollowUpDate('');
        openLeadDetail(selectedLeadId);
        loadLeads();
      })
      .catch((err) => {
        console.error('Failed to record action:', err);
        setSubmittingAction(false);
      });
  };

  // Create CRM Deal Submit
  const handleCreateDealSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLeadId || !detailLead) return;
    setSubmittingDeal(true);

    api.createDeal({
      lead_id: selectedLeadId,
      title: dealTitle.trim() || `${detailLead.business_name} - ${dealService.replace(/_/g, ' ')}`,
      service_type: dealService,
      deal_value: dealValue,
      stage: dealStage,
      notes: dealNotes.trim() || undefined,
    })
      .then(() => {
        setSubmittingDeal(false);
        setShowDealForm(false);
        setDealTitle('');
        setDealNotes('');
        openLeadDetail(selectedLeadId);
        loadLeads();
      })
      .catch((err) => {
        console.error('Failed to create deal:', err);
        setSubmittingDeal(false);
      });
  };

  // Bulk Workflow Update
  const handleBulkWorkflowChange = (newStatus: string) => {
    if (selectedIds.length === 0) return;
    api.bulkUpdateLeadWorkflow(selectedIds, newStatus)
      .then(() => {
        setLeads((prev) =>
          prev.map((l) => (selectedIds.includes(l.id) ? { ...l, workflow_status: newStatus as any } : l))
        );
        setSelectedIds([]);
      })
      .catch((err) => console.error('Bulk update failed:', err));
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === leads.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(leads.map((l) => l.id));
    }
  };

  const getCategoryBadge = (cat: string) => {
    switch (cat) {
      case 'VERY_HIGH':
        return { bg: 'var(--red-dim)', text: 'var(--red)', border: 'rgba(239,68,68,0.3)' };
      case 'HIGH':
        return { bg: 'var(--amber-dim)', text: 'var(--amber)', border: 'rgba(245,158,11,0.3)' };
      case 'MEDIUM':
        return { bg: 'var(--blue-dim)', text: 'var(--blue)', border: 'rgba(96,165,250,0.3)' };
      case 'LOW':
        return { bg: 'var(--green-dim)', text: 'var(--green)', border: 'rgba(34,197,94,0.3)' };
      default:
        return { bg: 'var(--bg-input)', text: 'var(--text-3)', border: 'var(--border-subtle)' };
    }
  };

  const getQueueBadge = (q: string) => {
    switch (q) {
      case 'CONTACT_NOW':
        return { bg: 'var(--red-dim)', text: 'var(--red)' };
      case 'FOLLOW_UP_OVERDUE':
        return { bg: 'rgba(234,88,12,0.14)', text: '#ea580c' };
      case 'FOLLOW_UP_SCHEDULED':
        return { bg: 'var(--amber-dim)', text: 'var(--amber)' };
      case 'REVIEW':
        return { bg: 'var(--pink-dim)', text: 'var(--pink)' };
      default:
        return { bg: 'var(--bg-input)', text: 'var(--text-2)' };
    }
  };

  const queueTabs = [
    { id: '', label: 'All Leads' },
    { id: 'CONTACT_NOW', label: '🔴 Contact Now' },
    { id: 'FOLLOW_UP_OVERDUE', label: '🚨 Overdue Follow-ups' },
    { id: 'FOLLOW_UP_SCHEDULED', label: '🟠 Follow Up Pending' },
    { id: 'REVIEW', label: '🟡 Review Required' },
    { id: 'NO_CONTACT_CHANNEL', label: '⚪ No Direct Channel' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', width: '100%', minHeight: '100%' }}>
      {/* ── Top Bar Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.02em', margin: 0 }}>
            Lead Intelligence & Operations
          </h1>
          <p style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '3px' }}>
            Click-to-execute outreach, response tracking, chronological activity timelines, and sales queues ({total} leads)
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <a
            href="/crm"
            className="btn btn-ghost"
            style={{ fontSize: '12px', height: '34px', padding: '0 12px' }}
          >
            💼 CRM Pipeline ↗
          </a>
          <a
            href="/outreach"
            className="btn btn-pink"
            style={{ fontSize: '12px', height: '34px', padding: '0 14px' }}
          >
            📊 Outreach Analytics ↗
          </a>
        </div>
      </div>

      {/* ── Priority Queue Filter Tabs ── */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {queueTabs.map((tab) => {
          const active = priorityQueue === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => { setPriorityQueue(tab.id); setPage(1); }}
              style={{
                padding: '6px 14px',
                borderRadius: 'var(--r-pill)',
                fontSize: '12px',
                fontWeight: active ? 600 : 500,
                border: `1px solid ${active ? 'var(--pink)' : 'var(--border-subtle)'}`,
                background: active ? 'var(--pink)' : 'var(--bg-card)',
                color: active ? '#fff' : 'var(--text-2)',
                cursor: 'pointer',
                transition: 'all var(--ease)',
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ── Filter Card ── */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-xl)',
          padding: '16px 18px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.02)',
        }}
      >
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Search Input */}
          <div style={{
            flex: '1 1 240px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'var(--bg-input)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--r-md)',
            padding: '0 12px',
            height: '36px',
          }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <input
              type="text"
              placeholder="Search business, phone, email, website..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                flex: 1,
                background: 'none',
                border: 'none',
                outline: 'none',
                color: 'var(--text-1)',
                fontSize: '12px',
              }}
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                style={{ fontSize: '11px', color: 'var(--text-3)', cursor: 'pointer' }}
              >
                ✕
              </button>
            )}
          </div>

          <select
            value={oppCategory}
            onChange={(e) => { setOppCategory(e.target.value); setPage(1); }}
            style={{
              padding: '0 12px',
              height: '36px',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-md)',
              fontSize: '12px',
              background: 'var(--bg-card)',
              color: 'var(--text-1)',
            }}
          >
            <option value="">Opportunity: All</option>
            <option value="VERY_HIGH">VERY HIGH (≥ 80)</option>
            <option value="HIGH">HIGH (65-79)</option>
            <option value="MEDIUM">MEDIUM (45-64)</option>
            <option value="LOW">LOW (25-44)</option>
            <option value="MINIMAL">MINIMAL (&lt; 25)</option>
          </select>

          <select
            value={webStatus}
            onChange={(e) => { setWebStatus(e.target.value); setPage(1); }}
            style={{
              padding: '0 12px',
              height: '36px',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-md)',
              fontSize: '12px',
              background: 'var(--bg-card)',
              color: 'var(--text-1)',
            }}
          >
            <option value="">Website: All</option>
            <option value="has_website">Has Website</option>
            <option value="no_website">No Website</option>
            <option value="verified_website">Verified Domain</option>
            <option value="unverified_website">Unverified Domain</option>
          </select>

          <select
            value={serviceFilter}
            onChange={(e) => { setServiceFilter(e.target.value); setPage(1); }}
            style={{
              padding: '0 12px',
              height: '36px',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-md)',
              fontSize: '12px',
              background: 'var(--bg-card)',
              color: 'var(--text-1)',
            }}
          >
            <option value="">Service: All</option>
            <option value="WEBSITE_DEVELOPMENT">Website Development</option>
            <option value="SEO">SEO Optimization</option>
            <option value="SMMA">Social Media Marketing</option>
          </select>

          <select
            value={workflowStatus}
            onChange={(e) => { setWorkflowStatus(e.target.value); setPage(1); }}
            style={{
              padding: '0 12px',
              height: '36px',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-md)',
              fontSize: '12px',
              background: 'var(--bg-card)',
              color: 'var(--text-1)',
            }}
          >
            <option value="">Workflow: All</option>
            <option value="NEW">NEW</option>
            <option value="REVIEWED">REVIEWED</option>
            <option value="CONTACTED">CONTACTED</option>
            <option value="QUALIFIED">QUALIFIED</option>
            <option value="CONVERTED">CONVERTED</option>
            <option value="LOST">LOST</option>
            <option value="DISMISSED">DISMISSED</option>
          </select>

          <select
            value={sortBy}
            onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
            style={{
              padding: '0 12px',
              height: '36px',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-md)',
              fontSize: '12px',
              background: 'var(--bg-card)',
              color: 'var(--text-1)',
            }}
          >
            <option value="opportunity_score_desc">Opportunity: High → Low</option>
            <option value="opportunity_score_asc">Opportunity: Low → High</option>
            <option value="genuineness_score_desc">Genuineness: High → Low</option>
            <option value="contactability_desc">Contactability: High → Low</option>
            <option value="created_at_desc">Recently Discovered</option>
            <option value="updated_at_desc">Recently Enriched</option>
          </select>
        </div>

        {/* Channel Pills */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Reachability:
          </span>
          
          <button
            type="button"
            onClick={() => setHasPhone(hasPhone === true ? undefined : true)}
            style={{
              padding: '4px 10px',
              borderRadius: 'var(--r-pill)',
              fontSize: '11px',
              fontWeight: 500,
              border: `1px solid ${hasPhone === true ? 'var(--pink)' : 'var(--border-subtle)'}`,
              background: hasPhone === true ? 'var(--pink-dim)' : 'transparent',
              color: hasPhone === true ? 'var(--pink)' : 'var(--text-2)',
              cursor: 'pointer',
            }}
          >
            📞 Phone
          </button>

          <button
            type="button"
            onClick={() => setHasEmail(hasEmail === true ? undefined : true)}
            style={{
              padding: '4px 10px',
              borderRadius: 'var(--r-pill)',
              fontSize: '11px',
              fontWeight: 500,
              border: `1px solid ${hasEmail === true ? 'var(--pink)' : 'var(--border-subtle)'}`,
              background: hasEmail === true ? 'var(--pink-dim)' : 'transparent',
              color: hasEmail === true ? 'var(--pink)' : 'var(--text-2)',
              cursor: 'pointer',
            }}
          >
            ✉️ Email
          </button>

          <button
            type="button"
            onClick={() => setHasWhatsApp(hasWhatsApp === true ? undefined : true)}
            style={{
              padding: '4px 10px',
              borderRadius: 'var(--r-pill)',
              fontSize: '11px',
              fontWeight: 500,
              border: `1px solid ${hasWhatsApp === true ? 'var(--green)' : 'var(--border-subtle)'}`,
              background: hasWhatsApp === true ? 'var(--green-dim)' : 'transparent',
              color: hasWhatsApp === true ? 'var(--green)' : 'var(--text-2)',
              cursor: 'pointer',
            }}
          >
            💬 WhatsApp
          </button>

          <button
            type="button"
            onClick={() => setHasSocial(hasSocial === true ? undefined : true)}
            style={{
              padding: '4px 10px',
              borderRadius: 'var(--r-pill)',
              fontSize: '11px',
              fontWeight: 500,
              border: `1px solid ${hasSocial === true ? 'var(--blue)' : 'var(--border-subtle)'}`,
              background: hasSocial === true ? 'var(--blue-dim)' : 'transparent',
              color: hasSocial === true ? 'var(--blue)' : 'var(--text-2)',
              cursor: 'pointer',
            }}
          >
            🌐 Social Profile
          </button>

          {(oppCategory || webStatus || serviceFilter || workflowStatus || priorityQueue || hasPhone !== undefined || hasEmail !== undefined || hasWhatsApp !== undefined || hasSocial !== undefined || search) && (
            <button
              type="button"
              onClick={() => {
                setSearch('');
                setOppCategory('');
                setWebStatus('');
                setServiceFilter('');
                setWorkflowStatus('');
                setPriorityQueue('');
                setHasPhone(undefined);
                setHasEmail(undefined);
                setHasWhatsApp(undefined);
                setHasSocial(undefined);
                setPage(1);
              }}
              style={{
                marginLeft: 'auto',
                fontSize: '11px',
                color: 'var(--pink)',
                fontWeight: 600,
                cursor: 'pointer',
                background: 'none',
                border: 'none',
              }}
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* ── Bulk Actions Floating Bar ── */}
      {selectedIds.length > 0 && (
        <div style={{
          background: 'var(--text-1)',
          color: '#fff',
          padding: '10px 18px',
          borderRadius: 'var(--r-lg)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: 'var(--shadow-drop)',
        }}>
          <div style={{ fontSize: '12px', fontWeight: 600 }}>
            {selectedIds.length} lead{selectedIds.length > 1 ? 's' : ''} selected
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => handleBulkWorkflowChange('REVIEWED')}
              style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', padding: '5px 12px', borderRadius: 'var(--r-sm)', fontSize: '11px', fontWeight: 600, cursor: 'pointer' }}
            >
              Mark Reviewed
            </button>
            <button
              onClick={() => handleBulkWorkflowChange('CONTACTED')}
              style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', padding: '5px 12px', borderRadius: 'var(--r-sm)', fontSize: '11px', fontWeight: 600, cursor: 'pointer' }}
            >
              Mark Contacted
            </button>
            <button
              onClick={() => handleBulkWorkflowChange('QUALIFIED')}
              style={{ background: 'var(--green)', color: '#fff', padding: '5px 12px', borderRadius: 'var(--r-sm)', fontSize: '11px', fontWeight: 600, cursor: 'pointer' }}
            >
              Mark Qualified
            </button>
            <button
              onClick={() => handleBulkWorkflowChange('DISMISSED')}
              style={{ background: 'var(--red)', color: '#fff', padding: '5px 12px', borderRadius: 'var(--r-sm)', fontSize: '11px', fontWeight: 600, cursor: 'pointer' }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* ── Leads Operations Table Card ── */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-xl)',
          overflow: 'hidden',
          boxShadow: '0 2px 8px rgba(0,0,0,0.02)',
        }}
      >
        <div style={{ overflowX: 'auto', width: '100%' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-2)', fontWeight: 600 }}>
                <th style={{ padding: '12px 14px', width: '36px' }}>
                  <input
                    type="checkbox"
                    checked={leads.length > 0 && selectedIds.length === leads.length}
                    onChange={toggleSelectAll}
                    style={{ accentColor: 'var(--pink)', cursor: 'pointer' }}
                  />
                </th>
                <th style={{ padding: '12px 14px' }}>Business & Direct Action Links</th>
                <th style={{ padding: '12px 14px' }}>Opportunity Score</th>
                <th style={{ padding: '12px 14px' }}>Priority Queue</th>
                <th style={{ padding: '12px 14px' }}>Recommended Channel</th>
                <th style={{ padding: '12px 14px' }}>Workflow</th>
                <th style={{ padding: '12px 14px' }}>Latest Action</th>
                <th style={{ padding: '12px 14px', textAlign: 'right' }}>Dossier</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ padding: '48px 16px', textAlign: 'center', color: 'var(--text-3)' }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ animation: 'spin 1s linear infinite' }}>⏳</span> Loading lead operations...
                    </div>
                  </td>
                </tr>
              ) : leads.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: '48px 16px', textAlign: 'center', color: 'var(--text-2)' }}>
                    No leads matching the selected filter criteria.
                  </td>
                </tr>
              ) : (
                leads.map((lead) => {
                  const catBadge = getCategoryBadge(lead.opportunity_category);
                  const qBadge = getQueueBadge(lead.priority_queue?.queue || 'STANDARD');
                  const isSelected = selectedLeadId === lead.id;

                  return (
                    <tr
                      key={lead.id}
                      style={{
                        borderBottom: '1px solid var(--border-faint)',
                        transition: 'background var(--ease)',
                        cursor: 'pointer',
                        background: isSelected ? 'var(--bg-active)' : 'transparent',
                      }}
                      onClick={() => openLeadDetail(lead.id)}
                    >
                      <td style={{ padding: '12px 14px' }} onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(lead.id)}
                          onChange={() => toggleSelect(lead.id)}
                          style={{ accentColor: 'var(--pink)', cursor: 'pointer' }}
                        />
                      </td>

                      {/* Business & Direct Execution Links */}
                      <td style={{ padding: '12px 14px' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-1)', fontSize: '13px' }}>
                          {lead.business_name}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-2)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          {lead.email ? (
                            <a href={`mailto:${lead.email}`} onClick={e => e.stopPropagation()} style={{ color: 'var(--pink)', fontWeight: 600, textDecoration: 'none' }}>
                              ✉ {lead.email}
                            </a>
                          ) : (
                            <span style={{ color: 'var(--text-3)' }}>No direct email</span>
                          )}
                          {lead.phone ? <span style={{ color: 'var(--text-3)' }}>• 📞 {lead.phone}</span> : ''}
                        </div>

                        {/* Click-to-Execute Quick Links */}
                        <div style={{ display: 'flex', gap: '5px', marginTop: '6px', flexWrap: 'wrap' }} onClick={(e) => e.stopPropagation()}>
                          {lead.execution_links?.slice(0, 3).map((link, idx) => (
                            <a
                              key={idx}
                              href={link.url}
                              target={link.channel === 'PHONE' || link.channel === 'EMAIL' ? '_self' : '_blank'}
                              rel="noreferrer"
                              style={{
                                padding: '2px 7px',
                                borderRadius: 'var(--r-sm)',
                                fontSize: '10px',
                                fontWeight: 600,
                                textDecoration: 'none',
                                background: link.channel === 'WHATSAPP' ? 'var(--green-dim)' : link.channel === 'PHONE' ? 'var(--blue-dim)' : link.channel === 'EMAIL' ? 'var(--pink-dim)' : 'var(--bg-input)',
                                color: link.channel === 'WHATSAPP' ? 'var(--green)' : link.channel === 'PHONE' ? 'var(--blue)' : link.channel === 'EMAIL' ? 'var(--pink)' : 'var(--text-2)',
                                border: '1px solid transparent',
                              }}
                            >
                              {link.channel === 'WHATSAPP' ? '💬 WhatsApp' : link.channel === 'PHONE' ? '📞 Call' : link.channel === 'EMAIL' ? '✉️ Email' : '🌐 Visit'}
                            </a>
                          ))}
                        </div>

                        {lead.has_conflict && (
                          <span style={{ display: 'inline-block', fontSize: '10px', fontWeight: 600, color: 'var(--amber)', background: 'var(--amber-dim)', padding: '1px 5px', borderRadius: '4px', marginTop: '4px' }}>
                            ⚠️ Contact Conflict
                          </span>
                        )}
                      </td>

                      {/* Opportunity Score */}
                      <td style={{ padding: '12px 14px' }}>
                        <span
                          className="pill"
                          style={{
                            background: catBadge.bg,
                            color: catBadge.text,
                            border: `1px solid ${catBadge.border}`,
                          }}
                        >
                          {lead.opportunity_score} • {lead.opportunity_category}
                        </span>
                      </td>

                      {/* Priority Queue */}
                      <td style={{ padding: '12px 14px' }}>
                        <span
                          className="pill"
                          style={{
                            background: qBadge.bg,
                            color: qBadge.text,
                          }}
                        >
                          {lead.priority_queue?.badge || 'Standard Priority'}
                        </span>
                      </td>

                      {/* Recommended Channel */}
                      <td style={{ padding: '12px 14px' }}>
                        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-1)' }}>
                          {lead.recommended_channel?.label || 'No Direct Channel'}
                        </span>
                      </td>

                      {/* Workflow Dropdown */}
                      <td style={{ padding: '12px 14px' }} onClick={(e) => e.stopPropagation()}>
                        <select
                          value={lead.workflow_status || 'NEW'}
                          onChange={(e) => handleWorkflowChange(lead.id, e.target.value)}
                          style={{
                            padding: '3px 7px',
                            borderRadius: 'var(--r-sm)',
                            fontSize: '11px',
                            fontWeight: 600,
                            border: '1px solid var(--border-subtle)',
                            background: 'var(--bg-input)',
                            color: 'var(--text-1)',
                          }}
                        >
                          <option value="NEW">NEW</option>
                          <option value="REVIEWED">REVIEWED</option>
                          <option value="CONTACTED">CONTACTED</option>
                          <option value="QUALIFIED">QUALIFIED</option>
                          <option value="CONVERTED">CONVERTED</option>
                          <option value="LOST">LOST</option>
                          <option value="DISMISSED">DISMISSED</option>
                        </select>
                      </td>

                      {/* Latest Action */}
                      <td style={{ padding: '12px 14px' }}>
                        {lead.latest_action ? (
                          <div>
                            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-1)' }}>
                              {lead.latest_action.channel} • {lead.latest_action.outcome.replace(/_/g, ' ')}
                            </div>
                            <div style={{ fontSize: '10px', color: 'var(--text-3)' }}>
                              {new Date(lead.latest_action.created_at).toLocaleDateString()}
                            </div>
                          </div>
                        ) : (
                          <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>No attempts yet</span>
                        )}
                      </td>

                      {/* Dossier Button */}
                      <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                        <button
                          onClick={() => openLeadDetail(lead.id)}
                          style={{
                            background: 'var(--pink-dim)',
                            color: 'var(--pink)',
                            border: '1px solid var(--border-pink)',
                            padding: '4px 9px',
                            borderRadius: 'var(--r-sm)',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Dossier →
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 18px',
          background: 'var(--bg-surface)',
          borderTop: '1px solid var(--border-subtle)',
          fontSize: '12px',
        }}>
          <div style={{ color: 'var(--text-2)' }}>
            Showing {leads.length > 0 ? (page - 1) * pageSize + 1 : 0} to {Math.min(page * pageSize, total)} of {total} leads
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="btn btn-ghost"
              style={{ padding: '0 10px', height: '28px', fontSize: '11px', opacity: page <= 1 ? 0.4 : 1 }}
            >
              Previous
            </button>
            <span style={{ color: 'var(--text-1)', fontWeight: 600, padding: '0 4px' }}>
              Page {page} of {Math.max(1, Math.ceil(total / pageSize))}
            </span>
            <button
              disabled={page >= Math.ceil(total / pageSize)}
              onClick={() => setPage((p) => p + 1)}
              className="btn btn-ghost"
              style={{ padding: '0 10px', height: '28px', fontSize: '11px', opacity: page >= Math.ceil(total / pageSize) ? 0.4 : 1 }}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* ── Slide-over Lead Action & Intelligence Drawer ── */}
      {selectedLeadId && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.4)',
            zIndex: 999,
            display: 'flex',
            justifyContent: 'flex-end',
          }}
          onClick={() => setSelectedLeadId(null)}
        >
          <div
            style={{
              width: '680px',
              maxWidth: '100vw',
              height: '100%',
              background: 'var(--bg-card)',
              boxShadow: 'var(--shadow-drop)',
              display: 'flex',
              flexDirection: 'column',
              overflowY: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header */}
            <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <h2 style={{ margin: 0, fontSize: '17px', fontWeight: 700, color: 'var(--text-1)' }}>
                  {detailLead?.business_name || 'Lead Dossier'}
                </h2>
                <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '3px' }}>
                  Recommended: <strong style={{ color: 'var(--pink)' }}>{detailLead?.recommended_channel?.label}</strong> • Queue: <strong>{detailLead?.priority_queue?.badge}</strong>
                </div>
              </div>

              <button
                onClick={() => setSelectedLeadId(null)}
                style={{
                  background: 'var(--bg-input)',
                  border: 'none',
                  borderRadius: 'var(--r-pill)',
                  width: '28px',
                  height: '28px',
                  fontSize: '14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  color: 'var(--text-2)',
                }}
              >
                ✕
              </button>
            </div>

            {detailLoading ? (
              <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-3)' }}>
                Loading lead dossier and intelligence...
              </div>
            ) : detailLead && (
              <>
                {/* Tabs */}
                <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-surface)' }}>
                  {[
                    { id: 'ACTIONS', label: 'Outreach & Actions' },
                    { id: 'TIMELINE', label: 'Activity Timeline' },
                    { id: 'DEALS', label: `Deals (${detailLead.deals?.length || 0})` },
                    { id: 'INTELLIGENCE', label: 'Tech & Signals' },
                  ].map((tab) => {
                    const active = drawerTab === tab.id;
                    return (
                      <button
                        key={tab.id}
                        type="button"
                        onClick={() => setDrawerTab(tab.id as any)}
                        style={{
                          flex: 1,
                          padding: '10px 12px',
                          border: 'none',
                          borderBottom: `2px solid ${active ? 'var(--pink)' : 'transparent'}`,
                          background: 'transparent',
                          fontSize: '12px',
                          fontWeight: active ? 600 : 500,
                          color: active ? 'var(--pink)' : 'var(--text-2)',
                          cursor: 'pointer',
                        }}
                      >
                        {tab.label}
                      </button>
                    );
                  })}
                </div>

                {/* Tab Content */}
                <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {drawerTab === 'ACTIONS' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      {/* Direct Channels */}
                      <div style={{ background: 'var(--bg-surface)', padding: '14px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
                        <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: '8px' }}>
                          Direct Outreach Channels
                        </div>
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                          {detailLead.execution_links?.map((link, idx) => (
                            <a
                              key={idx}
                              href={link.url}
                              target={link.channel === 'PHONE' || link.channel === 'EMAIL' ? '_self' : '_blank'}
                              rel="noreferrer"
                              className="btn btn-pink"
                              style={{ height: '32px', fontSize: '12px', padding: '0 12px' }}
                            >
                              {link.label}
                            </a>
                          ))}
                        </div>
                      </div>

                      {/* Log Action Button / Form */}
                      {!showActionForm ? (
                        <button
                          type="button"
                          onClick={() => setShowActionForm(true)}
                          className="btn btn-ghost"
                          style={{ width: '100%', justifyContent: 'center', height: '38px', fontWeight: 600 }}
                        >
                          + Record Outreach Action / Follow-up
                        </button>
                      ) : (
                        <form onSubmit={handleRecordActionSubmit} style={{ background: 'var(--bg-surface)', padding: '16px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-1)' }}>Record Outreach Action</div>
                          <div style={{ display: 'flex', gap: '10px' }}>
                            <div style={{ flex: 1 }}>
                              <label style={{ fontSize: '11px', color: 'var(--text-2)', display: 'block', marginBottom: '4px' }}>Channel</label>
                              <select
                                value={actionChannel}
                                onChange={(e) => setActionChannel(e.target.value as any)}
                                style={{ width: '100%', height: '34px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', fontSize: '12px', background: 'var(--bg-card)', color: 'var(--text-1)', padding: '0 8px' }}
                              >
                                <option value="PHONE">Phone Call</option>
                                <option value="WHATSAPP">WhatsApp Direct</option>
                                <option value="EMAIL">Email</option>
                                <option value="SOCIAL_DM">Social DM</option>
                                <option value="CONTACT_PAGE">Contact Form</option>
                                <option value="OTHER">Other</option>
                              </select>
                            </div>
                            <div style={{ flex: 1 }}>
                              <label style={{ fontSize: '11px', color: 'var(--text-2)', display: 'block', marginBottom: '4px' }}>Outcome</label>
                              <select
                                value={actionOutcome}
                                onChange={(e) => setActionOutcome(e.target.value as any)}
                                style={{ width: '100%', height: '34px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', fontSize: '12px', background: 'var(--bg-card)', color: 'var(--text-1)', padding: '0 8px' }}
                              >
                                <option value="NO_RESPONSE">No Response</option>
                                <option value="CONTACTED">Contacted</option>
                                <option value="RESPONDED">Responded</option>
                                <option value="INTERESTED">Interested</option>
                                <option value="NOT_INTERESTED">Not Interested</option>
                                <option value="MEETING_BOOKED">Meeting Booked</option>
                                <option value="QUALIFIED">Qualified</option>
                                <option value="CONVERTED">Converted / Closed</option>
                                <option value="LOST">Lost</option>
                              </select>
                            </div>
                          </div>

                          <div>
                            <label style={{ fontSize: '11px', color: 'var(--text-2)', display: 'block', marginBottom: '4px' }}>Notes</label>
                            <input
                              type="text"
                              placeholder="Key conversation notes, requirements..."
                              value={actionNotes}
                              onChange={(e) => setActionNotes(e.target.value)}
                              style={{ width: '100%', height: '34px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', fontSize: '12px', background: 'var(--bg-card)', color: 'var(--text-1)', padding: '0 10px', boxSizing: 'border-box' }}
                            />
                          </div>

                          <div>
                            <label style={{ fontSize: '11px', color: 'var(--text-2)', display: 'block', marginBottom: '4px' }}>Follow-up Date (Optional)</label>
                            <input
                              type="date"
                              value={actionFollowUpDate}
                              onChange={(e) => setActionFollowUpDate(e.target.value)}
                              style={{ width: '100%', height: '34px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', fontSize: '12px', background: 'var(--bg-card)', color: 'var(--text-1)', padding: '0 10px', boxSizing: 'border-box' }}
                            />
                          </div>

                          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '6px' }}>
                            <button
                              type="button"
                              onClick={() => setShowActionForm(false)}
                              className="btn btn-ghost"
                              style={{ height: '32px', fontSize: '11px' }}
                            >
                              Cancel
                            </button>
                            <button
                              type="submit"
                              disabled={submittingAction}
                              className="btn btn-pink"
                              style={{ height: '32px', fontSize: '11px' }}
                            >
                              {submittingAction ? 'Saving...' : 'Save Action'}
                            </button>
                          </div>
                        </form>
                      )}

                      {/* Action History List */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-1)' }}>Action History</div>
                        {detailLead.action_history && detailLead.action_history.length > 0 ? (
                          detailLead.action_history.map((act) => (
                            <div key={act.id} style={{ background: 'var(--bg-surface)', padding: '10px 14px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-subtle)', fontSize: '12px' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600, color: 'var(--text-1)' }}>
                                <span>{act.channel} • {act.outcome.replace(/_/g, ' ')}</span>
                                <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>{new Date(act.created_at).toLocaleString()}</span>
                              </div>
                              {act.notes && <div style={{ fontSize: '11px', color: 'var(--text-2)', marginTop: '4px' }}>{act.notes}</div>}
                            </div>
                          ))
                        ) : (
                          <div style={{ fontSize: '12px', color: 'var(--text-3)', fontStyle: 'italic' }}>No outreach recorded yet.</div>
                        )}
                      </div>
                    </div>
                  )}

                  {drawerTab === 'TIMELINE' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {detailLead.timeline?.map((ev) => (
                        <div key={ev.id} style={{ display: 'flex', gap: '12px', padding: '10px 0', borderBottom: '1px solid var(--border-faint)' }}>
                          <div style={{ fontSize: '16px' }}>📌</div>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-1)' }}>{ev.title}</span>
                              <span style={{ fontSize: '10px', color: 'var(--text-3)' }}>{new Date(ev.timestamp).toLocaleDateString()}</span>
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--text-2)', marginTop: '2px' }}>{ev.description}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {drawerTab === 'DEALS' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {!showDealForm ? (
                        <button
                          type="button"
                          onClick={() => setShowDealForm(true)}
                          className="btn btn-pink"
                          style={{ width: '100%', justifyContent: 'center', height: '36px', fontSize: '12px' }}
                        >
                          + Create CRM Opportunity Deal
                        </button>
                      ) : (
                        <form onSubmit={handleCreateDealSubmit} style={{ background: 'var(--bg-surface)', padding: '14px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-1)' }}>Create Deal</div>
                          <input
                            type="text"
                            placeholder="Deal title..."
                            value={dealTitle}
                            onChange={(e) => setDealTitle(e.target.value)}
                            style={{ width: '100%', height: '34px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', fontSize: '12px', background: 'var(--bg-card)', color: 'var(--text-1)', padding: '0 10px', boxSizing: 'border-box' }}
                          />
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <input
                              type="number"
                              placeholder="Deal value (INR)"
                              value={dealValue}
                              onChange={(e) => setDealValue(Number(e.target.value))}
                              style={{ flex: 1, height: '34px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', fontSize: '12px', background: 'var(--bg-card)', color: 'var(--text-1)', padding: '0 10px', boxSizing: 'border-box' }}
                            />
                            <select
                              value={dealService}
                              onChange={(e) => setDealService(e.target.value)}
                              style={{ flex: 1, height: '34px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', fontSize: '12px', background: 'var(--bg-card)', color: 'var(--text-1)', padding: '0 8px' }}
                            >
                              <option value="WEBSITE_DEVELOPMENT">Website Dev</option>
                              <option value="SEO">SEO</option>
                              <option value="SMMA">SMMA</option>
                            </select>
                          </div>
                          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                            <button type="button" onClick={() => setShowDealForm(false)} className="btn btn-ghost" style={{ height: '30px', fontSize: '11px' }}>Cancel</button>
                            <button type="submit" disabled={submittingDeal} className="btn btn-pink" style={{ height: '30px', fontSize: '11px' }}>{submittingDeal ? 'Creating...' : 'Create Deal'}</button>
                          </div>
                        </form>
                      )}

                      {detailLead.deals && detailLead.deals.length > 0 ? (
                        detailLead.deals.map((d) => (
                          <div key={d.id} style={{ background: 'var(--bg-surface)', padding: '12px 14px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontWeight: 600, color: 'var(--text-1)', fontSize: '13px' }}>{d.title}</span>
                              <span style={{ fontWeight: 700, color: 'var(--green)', fontSize: '13px' }}>₹{d.deal_value?.toLocaleString()}</span>
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--text-2)', marginTop: '4px' }}>
                              Stage: <strong style={{ color: 'var(--pink)' }}>{d.stage}</strong> • Win Probability: {(d.probability * 100).toFixed(0)}%
                            </div>
                          </div>
                        ))
                      ) : (
                        <div style={{ fontSize: '12px', color: 'var(--text-3)', fontStyle: 'italic' }}>No CRM deals created yet.</div>
                      )}
                    </div>
                  )}

                  {drawerTab === 'INTELLIGENCE' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      <div style={{ background: 'var(--bg-surface)', padding: '14px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
                        <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: '8px' }}>Intelligence Assessment</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-1)' }}>
                          <strong>Recommended Pitch:</strong> {detailLead.recommended_service?.replace(/_/g, ' ')}
                        </div>
                        <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          {detailLead.top_reasons?.map((r, i) => (
                            <div key={i} style={{ fontSize: '11px', color: 'var(--text-2)' }}>• {r}</div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
