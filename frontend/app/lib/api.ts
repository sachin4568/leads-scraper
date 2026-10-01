/**
 * API CLIENT — connects every frontend feature to the backend.
 * Base URL is read from NEXT_PUBLIC_API_URL env variable.
 * All functions are typed and ready to swap in for mock data.
 */

const BASE = typeof window !== 'undefined' ? '' : (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000');

export async function fetchWithAuth<T>(path: string, options?: RequestInit, token?: string): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(options?.headers as Record<string, string>) };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API ${res.status}: ${err}`);
  }
  if (res.status === 204) {
    return {} as T;
  }
  const text = await res.text();
  if (!text || !text.trim()) {
    return {} as T;
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  return fetchWithAuth<T>(path, options);
}

// ─── Lead Sheets ─────────────────────────────────────────────────────────────
export const api = {

  /** GET /api/v1/sheets — fetch all lead sheets (master view) */
  getSheets: () => request<LeadSheetAPI[]>('/api/v1/sheets'),

  /** GET /api/v1/sheets/:id — single sheet with all leads */
  getSheet: (id: string) => request<LeadSheetAPI>(`/api/v1/sheets/${id}`),

  /** PATCH /api/v1/sheets/:id — rename or update google sheets URL */
  updateSheet: (id: string, body: { name?: string; googleSheetsUrl?: string }) =>
    request<LeadSheetAPI>(`/api/v1/sheets/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  /** DELETE /api/v1/sheets/:id */
  deleteSheet: (id: string) => request<void>(`/api/v1/sheets/${id}`, { method: 'DELETE' }),

  /** POST /api/v1/sheets/:id/export?format=csv|xlsx|gsheets */
  exportSheet: (id: string, format: 'csv' | 'xlsx' | 'gsheets') =>
    request<{ url: string }>(`/api/v1/sheets/${id}/export?format=${format}`, { method: 'POST' }),

  // ─── Leads ───────────────────────────────────────────────────────────────
  /** PATCH /api/leads/:leadId — update status or notes */
  updateLead: (leadId: string, body: { status?: string; notes?: string }) =>
    request<LeadAPI>(`/api/leads/${leadId}`, { method: 'PATCH', body: JSON.stringify(body) }),

  // ─── Scraping ────────────────────────────────────────────────────────────
  /** POST /api/v1/scrape-jobs — kick off a new scrape job */
  startScrape: (body: {
    niche: string;
    city: string;
    region: string;
    country?: string;
    count: number;
    service: string;
    sources?: string[];
    plain_query?: string | null;
    exact_match?: boolean | null;
    related_categories?: boolean | null;
    locations?: string[] | null;
    search_mode?: string | null;
    search_depth?: string | null;
    enrichments?: string[] | null;
    deduplication_mode?: string | null;
    quality_threshold?: string | null;
  }) =>
    request<{ id: string; jobId?: string }>('/api/v1/scrape-jobs', {
      method: 'POST',
      body: JSON.stringify({
        niche: body.niche,
        city: body.city,
        region: body.region,
        country: body.country,
        service: body.service,
        target_lead_count: body.count,
        sources: body.sources,
        plain_query: body.plain_query,
        exact_match: body.exact_match,
        related_categories: body.related_categories,
        locations: body.locations,
        search_mode: body.search_mode,
        search_depth: body.search_depth,
        enrichments: body.enrichments,
        deduplication_mode: body.deduplication_mode,
        quality_threshold: body.quality_threshold,
      }),
    }),

  /** POST /api/v1/validate-location — validate geographic configuration */
  validateLocation: (body: {
    country: string;
    region?: string;
    city?: string;
    locations?: string[];
  }) =>
    request<{ is_valid: boolean; error_message?: string; canonical_location?: any }>('/api/v1/validate-location', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** GET /api/v1/scraping/jobs/:jobId */
  getScrapeProgress: (jobId: string) =>
    request<any>(`/api/v1/scraping/jobs/${jobId}`),

  /** POST /api/v1/scrape-jobs/:jobId/cancel — cancel an active scrape job */
  cancelScrape: (jobId: string) =>
    request<{ status: string; message: string }>(`/api/v1/scrape-jobs/${jobId}/cancel`, { method: 'POST' }),

  /** POST /api/v1/scrape-jobs/:jobId/stop-save — stop and save an active scrape job */
  stopScrape: (jobId: string) =>
    request<{ status: string; message: string }>(`/api/v1/scrape-jobs/${jobId}/stop-save`, { method: 'POST' }),

  /** POST /api/v1/scrape-jobs/:jobId/resume — resume a stopped scrape job */
  resumeScrape: (jobId: string) =>
    request<{ status: string; message: string }>(`/api/v1/scrape-jobs/${jobId}/resume`, { method: 'POST' }),

  /** POST /api/v1/scrape-jobs/:jobId/segregate — run AI qualification + sheet assignment */
  segregate: (jobId: string) =>
    request<{ raw_leads: number; segregated_leads: number }>(`/api/v1/scrape-jobs/${jobId}/segregate`, { method: 'POST' }),

  // ─── Raw Leads ───────────────────────────────────────────────────────────
  /** GET /api/v1/scrape-jobs */
  getRawLeads: () => request<RawLeadAPI[]>('/api/v1/scrape-jobs'),

  /** GET /api/v1/scrape-jobs/:jobId/leads */
  getJobLeads: (jobId: string) => request<LeadAPI[]>(`/api/v1/scrape-jobs/${jobId}/leads`),

  /** DELETE /api/v1/scrape-jobs/:jobId */
  deleteRawSheet: (jobId: string) => request<void>(`/api/v1/scrape-jobs/${jobId}`, { method: 'DELETE' }),

  // ─── Intelligence ────────────────────────────────────────────────────────
  /** GET /api/v1/intelligence/stats */
  getStats: () => request<StatsAPI>('/api/v1/intelligence/stats'),

  // ─── Operations & Lead Intelligence ──────────────────────────────────────
  getOperationsLeads: (params: {
    opportunity_category?: string;
    website_status?: string;
    has_phone?: boolean;
    has_email?: boolean;
    has_whatsapp?: boolean;
    has_social?: boolean;
    service?: string;
    workflow_status?: string;
    priority_queue?: string;
    search?: string;
    sort_by?: string;
    page?: number;
    page_size?: number;
  }) => {
    const query = new URLSearchParams();
    if (params.opportunity_category) query.set('opportunity_category', params.opportunity_category);
    if (params.website_status) query.set('website_status', params.website_status);
    if (params.has_phone !== undefined) query.set('has_phone', String(params.has_phone));
    if (params.has_email !== undefined) query.set('has_email', String(params.has_email));
    if (params.has_whatsapp !== undefined) query.set('has_whatsapp', String(params.has_whatsapp));
    if (params.has_social !== undefined) query.set('has_social', String(params.has_social));
    if (params.service) query.set('service', params.service);
    if (params.workflow_status) query.set('workflow_status', params.workflow_status);
    if (params.priority_queue) query.set('priority_queue', params.priority_queue);
    if (params.search) query.set('search', params.search);
    if (params.sort_by) query.set('sort_by', params.sort_by);
    if (params.page) query.set('page', String(params.page));
    if (params.page_size) query.set('page_size', String(params.page_size));

    return request<OperationsLeadListAPI>(`/api/operations/leads?${query.toString()}`);
  },

  getOperationsLeadDetail: (leadId: string) =>
    request<OperationsLeadDetailAPI>(`/api/operations/leads/${leadId}`),

  updateLeadWorkflow: (leadId: string, workflow_status: string) =>
    request<OperationsLeadItemAPI>(`/api/operations/leads/${leadId}/workflow`, {
      method: 'PATCH',
      body: JSON.stringify({ workflow_status }),
    }),

  bulkUpdateLeadWorkflow: (lead_ids: string[], workflow_status: string) =>
    request<{ updated_count: number; workflow_status: string; status: string }>(
      `/api/operations/leads/bulk-workflow`,
      {
        method: 'PATCH',
        body: JSON.stringify({ lead_ids, workflow_status }),
      }
    ),

  recordLeadAction: (
    leadId: string,
    body: {
      channel: 'PHONE' | 'EMAIL' | 'WHATSAPP' | 'SOCIAL_DM' | 'CONTACT_PAGE' | 'OTHER';
      outcome: 'CONTACTED' | 'RESPONDED' | 'INTERESTED' | 'NOT_INTERESTED' | 'MEETING_BOOKED' | 'QUALIFIED' | 'CONVERTED' | 'LOST' | 'NO_RESPONSE' | 'WRONG_NUMBER' | 'BOUNCED' | 'FOLLOW_UP_SCHEDULED';
      notes?: string;
      follow_up_date?: string;
      next_workflow_status?: string;
    }
  ) =>
    request<LeadActionAPI>(`/api/operations/leads/${leadId}/actions`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getLeadActions: (leadId: string) =>
    request<LeadActionAPI[]>(`/api/operations/leads/${leadId}/actions`),

  getLeadTimeline: (leadId: string) =>
    request<LeadTimelineAPI>(`/api/operations/leads/${leadId}/timeline`),

  getOutreachDashboard: () =>
    request<OutreachDashboardAPI>(`/api/operations/outreach/dashboard`),

  getOutreachAnalytics: () =>
    request<OutreachAnalyticsAPI>(`/api/operations/outreach/analytics`),

  // ─── CRM Pipeline & Deals ────────────────────────────────────────────────
  createDeal: (body: {
    lead_id: string;
    title: string;
    service_type?: string;
    deal_value: number;
    currency?: string;
    stage?: string;
    probability?: number;
    expected_close_date?: string;
    owner?: string;
    notes?: string;
  }) =>
    request<DealAPI>(`/api/operations/deals`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getDeals: (params?: { stage?: string; service_type?: string; lead_id?: string }) => {
    const query = new URLSearchParams();
    if (params?.stage) query.set('stage', params.stage);
    if (params?.service_type) query.set('service_type', params.service_type);
    if (params?.lead_id) query.set('lead_id', params.lead_id);
    return request<DealAPI[]>(`/api/operations/deals?${query.toString()}`);
  },

  getDealDetail: (dealId: string) =>
    request<DealAPI>(`/api/operations/deals/${dealId}`),

  updateDeal: (
    dealId: string,
    body: {
      title?: string;
      service_type?: string;
      deal_value?: number;
      currency?: string;
      stage?: string;
      probability?: number;
      expected_close_date?: string;
      owner?: string;
      win_loss_reason?: string;
      notes?: string;
    }
  ) =>
    request<DealAPI>(`/api/operations/deals/${dealId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  getCrmPipeline: () =>
    request<CrmPipelineDashboardAPI>(`/api/operations/crm/pipeline`),

  // ─── Phase 15: Executive Business Analytics ──────────────────────────────
  getAnalyticsOverview: (params?: { timeframe?: string; start_date?: string; end_date?: string }) => {
    const query = new URLSearchParams();
    if (params?.timeframe) query.set('timeframe', params.timeframe);
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    return request<AnalyticsOverviewAPI>(`/api/analytics/overview?${query.toString()}`);
  },

  getAnalyticsFunnel: (params?: { timeframe?: string }) => {
    const query = new URLSearchParams();
    if (params?.timeframe) query.set('timeframe', params.timeframe);
    return request<PipelineFunnelStageAPI[]>(`/api/analytics/funnel?${query.toString()}`);
  },

  getAnalyticsRevenue: (params?: { timeframe?: string }) => {
    const query = new URLSearchParams();
    if (params?.timeframe) query.set('timeframe', params.timeframe);
    return request<ExecutiveKpiSummaryAPI>(`/api/analytics/revenue?${query.toString()}`);
  },

  getAnalyticsQuality: (params?: { timeframe?: string }) => {
    const query = new URLSearchParams();
    if (params?.timeframe) query.set('timeframe', params.timeframe);
    return request<QualityTierPerformanceAPI[]>(`/api/analytics/quality?${query.toString()}`);
  },

  getAnalyticsSources: (params?: { timeframe?: string }) => {
    const query = new URLSearchParams();
    if (params?.timeframe) query.set('timeframe', params.timeframe);
    return request<SourcePerformanceAPI[]>(`/api/analytics/sources?${query.toString()}`);
  },

  getAnalyticsServices: (params?: { timeframe?: string }) => {
    const query = new URLSearchParams();
    if (params?.timeframe) query.set('timeframe', params.timeframe);
    return request<ServicePerformanceAnalyticsAPI[]>(`/api/analytics/services?${query.toString()}`);
  },

  getAnalyticsChannels: (params?: { timeframe?: string }) => {
    const query = new URLSearchParams();
    if (params?.timeframe) query.set('timeframe', params.timeframe);
    return request<ChannelMetricsAPI[]>(`/api/analytics/channels?${query.toString()}`);
  },

  // ─── Observability & Monitoring ───────────────────────────────────────────
  getHealth: () => request<HealthAPI>('/api/health'),
  getObservabilityDashboard: () => request<ObservabilityDashboardAPI>('/api/operations/observability/dashboard'),
  getJobDiagnostics: (jobId: string) => request<JobDiagnosticsAPI>(`/api/operations/observability/jobs/${jobId}/diagnostics`),
  recoverJob: (jobId: string) => request<{ status: string; message: string; job_id: string }>(`/api/operations/observability/jobs/${jobId}/recover`, { method: 'POST' }),

  // ─── Proposals & Quotations ───────────────────────────────────────────────
  createDealProposal: (dealId: string, body: {
    title: string;
    service_type?: string;
    base_price: number;
    addons_total?: number;
    discount_amount?: number;
    scope_of_work?: string;
    deliverables?: string[];
    timeline?: string;
    terms_and_conditions?: string;
    expected_start_date?: string;
    expiry_date?: string;
    notes?: string;
  }) => request<ProposalAPI>(`/api/operations/deals/${dealId}/proposals`, {
    method: 'POST',
    body: JSON.stringify(body),
  }),

  getProposals: (params?: {
    status?: string;
    service_type?: string;
    deal_id?: string;
    lead_id?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.service_type) query.set('service_type', params.service_type);
    if (params?.deal_id) query.set('deal_id', params.deal_id);
    if (params?.lead_id) query.set('lead_id', params.lead_id);
    if (params?.search) query.set('search', params.search);
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    return request<ProposalListAPI>(`/api/operations/proposals?${query.toString()}`);
  },

  getProposalDetail: (proposalId: string) =>
    request<ProposalAPI>(`/api/operations/proposals/${proposalId}`),

  createProposalVersion: (proposalId: string, body: {
    base_price: number;
    addons_total?: number;
    discount_amount?: number;
    scope_of_work?: string;
    deliverables?: string[];
    timeline?: string;
    change_summary?: string;
  }) => request<ProposalAPI>(`/api/operations/proposals/${proposalId}/versions`, {
    method: 'POST',
    body: JSON.stringify(body),
  }),

  updateProposalStatus: (proposalId: string, body: {
    status: string;
    rejection_reason?: string;
  }) => request<ProposalAPI>(`/api/operations/proposals/${proposalId}/status`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  }),

  getProposalMetrics: () =>
    request<ProposalMetricsAPI>('/api/operations/proposals/metrics'),

  // ─── Customer Onboarding & Delivery Management ────────────────────────────
  getDeliveryMetrics: () =>
    request<DeliveryMetricsAPI>('/api/operations/delivery/metrics'),

  convertDealToCustomer: (dealId: string) =>
    request<DeliveryProjectAPI>(`/api/operations/deals/${dealId}/convert-to-customer`, {
      method: 'POST',
    }),

  getCustomers: (params?: {
    status?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.search) query.set('search', params.search);
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    return request<CustomerListAPI>(`/api/operations/customers?${query.toString()}`);
  },

  getDeliveryProjects: (params?: {
    status?: string;
    service_type?: string;
    customer_id?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.service_type) query.set('service_type', params.service_type);
    if (params?.customer_id) query.set('customer_id', params.customer_id);
    if (params?.search) query.set('search', params.search);
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    return request<DeliveryProjectListAPI>(`/api/operations/delivery/projects?${query.toString()}`);
  },

  getProjectDetail: (projectId: string) =>
    request<DeliveryProjectAPI>(`/api/operations/delivery/projects/${projectId}`),

  updateProjectStatus: (projectId: string, status: string) =>
    request<DeliveryProjectAPI>(`/api/operations/delivery/projects/${projectId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  addProjectDeliverable: (projectId: string, body: { title: string; due_date?: string; notes?: string }) =>
    request<DeliverableAPI>(`/api/operations/delivery/projects/${projectId}/deliverables`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateDeliverableStatus: (deliverableId: string, status: string) =>
    request<DeliverableAPI>(`/api/operations/delivery/deliverables/${deliverableId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  // ─── Customer Success & Recurring Revenue ─────────────────────────────────
  getSuccessMetrics: () =>
    request<SuccessMetricsAPI>('/api/operations/success/metrics'),

  createCustomerRetainer: (customerId: string, body: {
    service_type: string;
    billing_frequency: string;
    billing_amount: number;
    currency?: string;
    start_date?: string;
    duration_months?: number;
    auto_renew?: boolean;
    notes?: string;
  }) => request<RetainerAPI>(`/api/operations/customers/${customerId}/retainers`, {
    method: 'POST',
    body: JSON.stringify(body),
  }),

  getRetainers: (params?: {
    status?: string;
    customer_id?: string;
  }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.customer_id) query.set('customer_id', params.customer_id);
    return request<RetainerAPI[]>(`/api/operations/retainers?${query.toString()}`);
  },

  renewRetainer: (retainerId: string) =>
    request<RetainerAPI>(`/api/operations/retainers/${retainerId}/renew`, {
      method: 'PATCH',
    }),

  updateRetainerStatus: (retainerId: string, body: {
    status: string;
    notes?: string;
  }) => request<RetainerAPI>(`/api/operations/retainers/${retainerId}/status`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  }),

  getUpsellOpportunities: (params?: {
    status?: string;
  }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    return request<UpsellOpportunityAPI[]>(`/api/operations/success/upsells?${query.toString()}`);
  },

  updateUpsellStatus: (upsellId: string, status: string) =>
    request<UpsellOpportunityAPI>(`/api/operations/success/upsells/${upsellId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  getCustomerHealthMatrix: (params?: {
    health_score?: string;
  }) => {
    const query = new URLSearchParams();
    if (params?.health_score) query.set('health_score', params.health_score);
    return request<CustomerHealthAPI[]>(`/api/operations/success/health?${query.toString()}`);
  },
};

// ─── API Response Types ──────────────────────────────────────────────────────

export interface LeadSheetAPI {
  id: string;
  sheetId: string;
  name: string;
  googleSheetsUrl?: string;
  service: 'website_dev' | 'seo' | 'smma' | 'social_media';
  sources: string[];
  niches: string[];
  timeTakenMin: number;
  createdAt: string;
  callerName?: string;
  callerEmail?: string;
  leads: LeadAPI[];
}

export interface LeadAPI {
  leadId: string;
  businessName: string;
  location: string;
  websiteUrl?: string;
  contactPhone?: string;
  contactEmail?: string;
  instagramHandle?: string;
  facebookHandle?: string;
  followersCount?: number;
  priorityScore: number;
  contactabilityScore?: number;
  seoScore?: number;
  socialScore?: number;
  genuineness: number;
  whatsappLink?: string;
  niche?: string;
  businessMaturity?: string;
  status: 'new' | 'assigned' | 'called' | 'warm' | 'converted';
  source: 'google_maps' | 'yelp' | 'linkedin';
  addedAt: string;
  notes?: string;
}

export interface ScrapeProgressAPI {
  jobId: string;
  total: number;
  scraped: number;
  filtered: number;
  enriched: number;
  scored: number;
  qualified: number;
  status: 'idle' | 'running' | 'done' | 'error';
  estimatedMinutes: number;
  percentComplete: number;
}

export interface RawLeadAPI {
  id: string;
  businessName: string;
  location: string;
  niche: string;
  phone?: string;
  website?: string;
  source: string;
  scrapedAt: string;
  status: 'pending' | 'processing' | 'qualified' | 'rejected';
}

export interface ExecutiveKpiSummaryAPI {
  total_leads: number;
  contactable_leads: number;
  contacted_leads: number;
  responded_leads: number;
  qualified_leads: number;
  won_leads: number;
  lost_leads: number;
  total_pipeline_value: number;
  weighted_pipeline_value: number;
  won_revenue: number;
  lost_value: number;
  overall_conversion_rate: number;
  overall_response_rate: number;
  win_rate: number;
  avg_deal_size: number;
}

export interface QualityTierPerformanceAPI {
  tier: string;
  leads_count: number;
  contactable_count: number;
  contactable_pct: number;
  contacted_count: number;
  contacted_pct: number;
  qualified_count: number;
  qualified_pct: number;
  won_count: number;
  won_pct: number;
  won_revenue: number;
  avg_deal_size: number;
}

export interface SourcePerformanceAPI {
  source: string;
  leads_count: number;
  contactable_pct: number;
  response_pct: number;
  qualified_pct: number;
  won_pct: number;
  won_revenue: number;
  pipeline_value: number;
  avg_deal_size: number;
}

export interface ServicePerformanceAnalyticsAPI {
  service: string;
  leads_pitched: number;
  opportunities_count: number;
  pipeline_value: number;
  won_revenue: number;
  win_rate: number;
  avg_deal_size: number;
}

export interface AnalyticsOverviewAPI {
  timeframe: string;
  start_date?: string;
  end_date?: string;
  kpis: ExecutiveKpiSummaryAPI;
  funnel: PipelineFunnelStageAPI[];
  quality_performance: QualityTierPerformanceAPI[];
  source_performance: SourcePerformanceAPI[];
  service_performance: ServicePerformanceAnalyticsAPI[];
  channel_effectiveness: ChannelMetricsAPI[];
}

export interface DealAPI {
  id: string;
  workspace_id: string;
  lead_id: string;
  business_name?: string;
  title: string;
  service_type: string;
  deal_value: number;
  currency: string;
  stage: 'NEW' | 'CONTACTED' | 'INTERESTED' | 'QUALIFIED' | 'PROPOSAL' | 'NEGOTIATION' | 'WON' | 'LOST';
  probability: number;
  weighted_value: number;
  expected_close_date?: string;
  owner?: string;
  win_loss_reason?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  closed_at?: string;
}

export interface CrmStageMetricsAPI {
  stage: string;
  count: number;
  total_value: number;
  weighted_value: number;
}

export interface RevenueBreakdownItemAPI {
  category: string;
  deals_count: number;
  won_revenue: number;
  pipeline_value: number;
}

export interface CrmPipelineDashboardAPI {
  total_pipeline_value: number;
  weighted_pipeline_value: number;
  won_revenue: number;
  lost_value: number;
  total_deals: number;
  active_deals_count: number;
  won_deals_count: number;
  lost_deals_count: number;
  avg_deal_size: number;
  win_rate: number;
  stages: CrmStageMetricsAPI[];
  revenue_by_service: RevenueBreakdownItemAPI[];
  revenue_by_source: RevenueBreakdownItemAPI[];
  recent_deals: DealAPI[];
}

export interface ExecutionLinkAPI {
  channel: 'PHONE' | 'EMAIL' | 'WHATSAPP' | 'SOCIAL_DM' | 'CONTACT_PAGE';
  label: string;
  url: string;
  is_direct: boolean;
}

export interface TimelineEventAPI {
  id: string;
  event_type: 'DISCOVERY' | 'WEBSITE_VERIFICATION' | 'ENRICHMENT' | 'OPPORTUNITY_SCORING' | 'OUTREACH_ATTEMPT' | 'RESPONSE_RECEIVED' | 'FOLLOW_UP' | 'MEETING' | 'QUALIFICATION' | 'CONVERSION' | 'LOST';
  title: string;
  description: string;
  channel?: string;
  outcome?: string;
  timestamp: string;
  source: string;
  metadata?: Record<string, any>;
}

export interface LeadTimelineAPI {
  lead_id: string;
  business_name: string;
  current_workflow_status: string;
  events: TimelineEventAPI[];
}

export interface LeadActionAPI {
  id: string;
  workspace_id: string;
  lead_id: string;
  channel: string;
  outcome: string;
  notes?: string;
  follow_up_date?: string;
  created_at: string;
}

export interface RecommendedChannelAPI {
  channel: 'WHATSAPP' | 'EMAIL' | 'PHONE' | 'SOCIAL_DM' | 'NONE';
  value?: string;
  label: string;
}

export interface PriorityQueueAPI {
  queue: 'CONTACT_NOW' | 'FOLLOW_UP_OVERDUE' | 'FOLLOW_UP_SCHEDULED' | 'REVIEW' | 'NO_CONTACT_CHANNEL' | 'ARCHIVED' | 'STANDARD';
  badge: string;
  urgency: number;
}

export interface OperationsLeadItemAPI {
  id: string;
  business_name: string;
  category?: string;
  location?: string;
  phone?: string;
  email?: string;
  website?: string;
  website_status: string;
  opportunity_score: number;
  opportunity_category: 'VERY_HIGH' | 'HIGH' | 'MEDIUM' | 'LOW' | 'MINIMAL';
  genuineness_score: number;
  recommended_service?: string;
  recommended_service_score?: number;
  workflow_status: 'NEW' | 'REVIEWED' | 'CONTACTED' | 'QUALIFIED' | 'CONVERTED' | 'DISMISSED' | 'LOST';
  top_reasons: string[];
  has_conflict: boolean;
  has_whatsapp: boolean;
  has_social: boolean;
  recommended_channel: RecommendedChannelAPI;
  priority_queue: PriorityQueueAPI;
  execution_links: ExecutionLinkAPI[];
  follow_up_date?: string;
  actions_count: number;
  latest_action?: LeadActionAPI;
  last_enriched_at?: string;
  created_at: string;
}

export interface OperationsLeadDetailAPI extends OperationsLeadItemAPI {
  contactability: {
    phone?: string;
    email?: string;
    whatsapp_links?: string[];
    website_phones?: string[];
    website_emails?: string[];
    addresses?: Array<{ address: string; source: string }>;
    contactability_score?: number;
  };
  website_health: {
    is_reachable?: boolean;
    is_https?: boolean;
    verified_url?: string;
  };
  seo: {
    seo_score?: number;
    title?: string;
    meta_description?: string;
    canonical_url?: string;
    h1_tags?: string[];
    h2_tags?: string[];
    og_title?: string;
    og_image?: string;
    twitter_card?: string;
    seo_issues?: string[];
  };
  social: {
    profiles?: Record<string, string>;
  };
  technologies: string[];
  service_opportunities: Record<string, { eligible: boolean; score: number }>;
  evidence_records: Array<{
    id: string;
    field_name: string;
    status: string;
    confidence_score: number;
    source: string;
    details: Record<string, any>;
    created_at?: string;
  }>;
  conflicts: Record<string, any>;
  action_history: LeadActionAPI[];
  timeline: TimelineEventAPI[];
  deals: DealAPI[];
}

export interface OperationsLeadListAPI {
  total: number;
  page: number;
  page_size: number;
  results: OperationsLeadItemAPI[];
}

export interface ChannelMetricsAPI {
  channel: string;
  attempts: number;
  responses: number;
  interested: number;
  meetings_booked: number;
  conversions: number;
  response_rate: number;
  interest_rate: number;
  conversion_rate: number;
}

export interface ServiceMetricsAPI {
  service: string;
  leads_count: number;
  attempts: number;
  responses: number;
  interested: number;
  meetings_booked: number;
  conversions: number;
}

export interface PipelineFunnelStageAPI {
  stage: string;
  count: number;
  conversion_rate_from_previous: number;
  conversion_rate_from_total: number;
}

export interface OutreachAnalyticsAPI {
  total_leads: number;
  contactable_leads: number;
  contacted_leads: number;
  responded_leads: number;
  interested_leads: number;
  meeting_booked_leads: number;
  qualified_leads: number;
  converted_leads: number;
  lost_leads: number;
  overall_response_rate: number;
  overall_interest_rate: number;
  overall_conversion_rate: number;
  funnel: PipelineFunnelStageAPI[];
  channel_effectiveness: ChannelMetricsAPI[];
  service_effectiveness: ServiceMetricsAPI[];
}

export interface OutreachDashboardAPI {
  total_leads: number;
  new_leads: number;
  ready_to_contact: number;
  contacted: number;
  follow_up_required: number;
  overdue_follow_ups_count: number;
  qualified: number;
  converted: number;
  dismissed: number;
  channels_breakdown: Record<string, number>;
  recent_actions: LeadActionAPI[];
}

export interface StatsAPI {
  totalLeads: number;
  warmLeads: number;
  convertedLeads: number;
  avgPriorityScore: number;
  totalSheets: number;
  conversionRate: number;
}

export interface HealthAPI {
  status: string;
  app_env: string;
  version: string;
  uptime_seconds: number;
  timestamp: string;
  database: {
    connected: boolean;
    latency_ms: number;
  };
  workers: {
    active_count: number;
    stale_count: number;
    status: string;
  };
}

export interface WorkerInfoAPI {
  worker_id: string;
  status: string;
  current_job_id: string | null;
  jobs_processed: number;
  jobs_failed: number;
  last_heartbeat: string;
  started_at: string;
  last_completed_at: string | null;
  last_error_at: string | null;
  last_error_message: string | null;
}

export interface RecentFailureAPI {
  id: string;
  job_id: string;
  stage: string;
  error_category: string;
  error_detail: string | null;
  retry_count: number;
  started_at: string;
}

export interface ObservabilityDashboardAPI {
  workspace_id: string;
  timestamp: string;
  job_health: {
    total_jobs: number;
    running: number;
    completed: number;
    failed: number;
    partial: number;
    stuck_count: number;
    stuck_jobs: Array<{
      job_id: string;
      niche: string;
      state: string;
      status: string;
      progress_percent: number;
      reason: string;
      updated_at: string | null;
    }>;
  };
  workers: {
    total_count: number;
    workers: WorkerInfoAPI[];
  };
  recent_failures: RecentFailureAPI[];
  provider_telemetry: {
    osm_overpass: {
      requests_total: number;
      success_total: number;
      timeouts: number;
      rate_limits_429: number;
      errors: number;
      avg_latency_ms: number;
    };
    website_enrichment: {
      domains_attempted: number;
      success_total: number;
      http_errors: number;
      dns_errors: number;
      ssl_errors: number;
      pages_fetched: number;
      bytes_downloaded: number;
      avg_latency_ms: number;
    };
  };
}

export interface JobDiagnosticsAPI {
  job_id: string;
  workspace_id: string;
  niche: string;
  state: string;
  status: string;
  progress_percent: number;
  leads_scraped: number;
  discovered_count: number;
  valid_count: number;
  persisted_leads_in_db: number;
  is_stuck: boolean;
  stuck_reason: string | null;
  error_message: string | null;
  completion_reason: string | null;
  created_at: string;
  updated_at: string | null;
  stages: Array<{
    id: string;
    stage: string;
    status: string;
    duration_ms: number;
    error_category: string | null;
    error_detail: string | null;
    retry_count: number;
    metrics: any;
    started_at: string;
    ended_at: string | null;
  }>;
}

export interface ProposalVersionAPI {
  id: string;
  version_number: number;
  base_price: number;
  addons_total: number;
  discount_amount: number;
  quoted_amount: number;
  scope_of_work?: string | null;
  deliverables?: string[] | null;
  timeline?: string | null;
  change_summary?: string | null;
  created_at: string;
}

export interface ProposalAPI {
  id: string;
  workspace_id: string;
  deal_id: string;
  lead_id: string;
  client_name: string;
  deal_title: string;
  proposal_number: string;
  title: string;
  service_type: string;
  status: string; // PROPOSAL_DRAFT, PROPOSAL_SENT, VIEWED, NEGOTIATION, ACCEPTED, REJECTED, EXPIRED
  current_version: number;
  base_price: number;
  addons_total: number;
  discount_amount: number;
  quoted_amount: number;
  currency: string;
  scope_of_work?: string | null;
  deliverables?: string[] | null;
  timeline?: string | null;
  terms_and_conditions?: string | null;
  expected_start_date?: string | null;
  expiry_date?: string | null;
  sent_at?: string | null;
  viewed_at?: string | null;
  accepted_at?: string | null;
  rejected_at?: string | null;
  rejection_reason?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  versions: ProposalVersionAPI[];
}

export interface ProposalListAPI {
  total: number;
  page: number;
  page_size: number;
  proposals: ProposalAPI[];
}

export interface ProposalMetricsAPI {
  total_proposals: number;
  draft_count: number;
  sent_count: number;
  viewed_count: number;
  negotiation_count: number;
  accepted_count: number;
  rejected_count: number;
  expired_count: number;
  total_quoted_pipeline: number;
  total_won_revenue: number;
  proposal_to_win_rate: number;
  avg_proposal_value: number;
  avg_discount_amount: number;
  avg_negotiation_reduction: number;
}

export interface DeliverableAPI {
  id: string;
  project_id: string;
  title: string;
  status: string; // PENDING, IN_PROGRESS, COMPLETED, BLOCKED
  due_date?: string | null;
  completed_at?: string | null;
  sort_order: number;
  notes?: string | null;
  created_at: string;
}

export interface DeliveryProjectAPI {
  id: string;
  workspace_id: string;
  customer_id: string;
  deal_id?: string | null;
  proposal_id?: string | null;
  customer_name: string;
  project_name: string;
  service_type: string;
  contract_value: number;
  currency: string;
  status: string; // ONBOARDING, REQUIREMENTS, IN_PROGRESS, REVIEW, CLIENT_APPROVAL, COMPLETED, ON_HOLD, CANCELLED
  progress_percent: number;
  start_date?: string | null;
  target_completion_date?: string | null;
  actual_completion_date?: string | null;
  owner?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  deliverables: DeliverableAPI[];
}

export interface DeliveryProjectListAPI {
  total: number;
  page: number;
  page_size: number;
  projects: DeliveryProjectAPI[];
}

export interface CustomerAPI {
  id: string;
  workspace_id: string;
  lead_id?: string | null;
  company_name: string;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  website?: string | null;
  status: string; // ONBOARDING, ACTIVE, CHURNED, COMPLETED
  lifetime_value: number;
  currency: string;
  notes?: string | null;
  onboarded_at: string;
  created_at: string;
  updated_at: string;
  projects_count: number;
}

export interface CustomerListAPI {
  total: number;
  page: number;
  page_size: number;
  customers: CustomerAPI[];
}

export interface DeliveryMetricsAPI {
  total_customers: number;
  active_customers: number;
  total_projects: number;
  active_projects: number;
  completed_projects: number;
  in_delivery_revenue: number;
  realized_completed_revenue: number;
  avg_project_progress: number;
  on_time_delivery_rate: number;
}

export interface RetainerAPI {
  id: string;
  workspace_id: string;
  customer_id: string;
  customer_name: string;
  service_type: string;
  billing_frequency: string; // MONTHLY, QUARTERLY, ANNUAL
  billing_amount: number;
  monthly_mrr: number;
  currency: string;
  status: string; // ACTIVE, EXPIRING_SOON, RENEWED, EXPIRED, CANCELLED
  start_date: string;
  renewal_date: string;
  auto_renew: boolean;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface UpsellOpportunityAPI {
  id: string;
  workspace_id: string;
  customer_id: string;
  customer_name: string;
  service_type: string;
  estimated_mrr: number;
  estimated_value: number;
  reason: string;
  status: string; // IDENTIFIED, PITCHED, ACCEPTED, DECLINED
  created_at: string;
  updated_at: string;
}

export interface CustomerHealthAPI {
  id: string;
  company_name: string;
  status: string;
  health_score: string; // HEALTHY, AT_RISK, CRITICAL, DORMANT
  health_reason?: string | null;
  mrr: number;
  arr: number;
  lifetime_value: number;
  next_renewal_date?: string | null;
  active_retainers_count: number;
  last_activity_at?: string | null;
}

export interface SuccessMetricsAPI {
  total_customers: number;
  active_customers: number;
  healthy_customers: number;
  at_risk_customers: number;
  critical_customers: number;
  dormant_customers: number;
  total_mrr: number;
  total_arr: number;
  active_retainers_count: number;
  renewals_due_30d_count: number;
  expansion_pipeline_value: number;
  avg_customer_ltv: number;
}
