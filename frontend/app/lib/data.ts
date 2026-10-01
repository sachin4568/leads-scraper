// ─── Service Types ──────────────────────────────────────────────────────────
export type ServiceType = 'website_dev' | 'seo' | 'smma' | 'social_media';

export const SERVICE_LABELS: Record<ServiceType, string> = {
  website_dev:  'Website Development',
  seo:          'SEO',
  smma:         'SMMA',
  social_media: 'Social Media Marketing',
};

// ─── Lead ────────────────────────────────────────────────────────────────────
export interface Lead {
  leadId: string;          // e.g. LD-101-01
  businessName: string;
  location: string;
  websiteUrl?: string;
  contactPhone?: string;
  contactEmail?: string;
  instagramHandle?: string;
  facebookHandle?: string;
  followersCount?: number;
  priorityScore: number;   // 0–100
  contactabilityScore?: number;
  seoScore?: number;       // SEO service only
  socialScore?: number;    // SMMA / social
  genuineness: number;     // 0–100
  whatsappLink?: string;
  niche?: string;
  businessMaturity?: string;
  status: 'new' | 'assigned' | 'called' | 'warm' | 'converted';
  source: 'google_maps' | 'yelp' | 'linkedin';
  addedAt: string;
  notes?: string;
}

// ─── Lead Sheet ──────────────────────────────────────────────────────────────
export interface LeadSheet {
  id: string;              // sheet-001
  sheetId: string;         // LD-101
  name: string;
  googleSheetsUrl?: string;
  service: ServiceType;
  sources: string[];
  niches: string[];
  timeTakenMin: number;    // minutes to scrape
  createdAt: string;
  callerName?: string;
  callerEmail?: string;
  country?: string;
  region?: string;
  leads: Lead[];
}

// ─── Real Production Lead Collections Data Model ────────────────────────────
export const MOCK_SHEETS: LeadSheet[] = [];

export const ALL_LEADS: Lead[] = [];

// ─── Raw Leads ───────────────────────────────────────────────────────────────
export interface RawLead {
  id: string; businessName: string; location: string; niche: string;
  phone?: string; website?: string; source: string; scrapedAt: string;
  status: 'pending' | 'processing' | 'qualified' | 'rejected';
}

export const RAW_LEADS: RawLead[] = [];

// ─── Scrape progress (live state shape for backend) ──────────────────────────
export interface ScrapeProgress {
  total: number; scraped: number; filtered: number;
  enriched: number; scored: number; qualified: number;
  status: 'idle' | 'running' | 'done';
  estimatedMinutes: number;
}

