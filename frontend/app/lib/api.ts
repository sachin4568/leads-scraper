/**
 * API CLIENT — connects every frontend feature to the backend.
 * Base URL is read from NEXT_PUBLIC_API_URL env variable.
 * All functions are typed and ready to swap in for mock data.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

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
  return res.json() as Promise<T>;
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

  // ─── Intelligence ────────────────────────────────────────────────────────
  /** GET /api/v1/intelligence/stats */
  getStats: () => request<StatsAPI>('/api/v1/intelligence/stats'),
};

// ─── API Response Types (match your backend response shapes) ─────────────────

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
  seoScore?: number;
  socialScore?: number;
  genuineness: number;
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

export interface StatsAPI {
  totalLeads: number;
  warmLeads: number;
  convertedLeads: number;
  avgPriorityScore: number;
  totalSheets: number;
  conversionRate: number;
}
