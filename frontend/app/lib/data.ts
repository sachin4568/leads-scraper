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
  seoScore?: number;       // SEO service only
  socialScore?: number;    // SMMA / social
  genuineness: number;     // 0–100
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

// ─── Mock data ───────────────────────────────────────────────────────────────
export const MOCK_SHEETS: LeadSheet[] = [
  {
    id: 'sheet-001', sheetId: 'LD-101',
    name: 'NYC Restaurants – Aug 2026',
    service: 'website_dev',
    sources: ['google_maps', 'yelp'],
    niches: ['Restaurant', 'Food & Beverage'],
    timeTakenMin: 14,
    createdAt: '2026-08-14T02:00:00Z',
    callerName: 'Caller 1', callerEmail: 'caller1@company.com',
    googleSheetsUrl: 'https://docs.google.com/spreadsheets/d/example1',
    leads: [
      { leadId: 'LD-101-01', businessName: 'The Rustic Table', location: 'Brooklyn, NY', websiteUrl: 'rustic-table.com', contactPhone: '(212) 445-7890', priorityScore: 87, genuineness: 98, status: 'new',  source: 'google_maps', addedAt: '2026-08-14' },
      { leadId: 'LD-101-02', businessName: 'Bella Cucina',     location: 'Manhattan, NY', websiteUrl: 'bellacucina.com', contactPhone: '(917) 332-1055', priorityScore: 79, genuineness: 96, status: 'new',  source: 'google_maps', addedAt: '2026-08-14' },
      { leadId: 'LD-101-03', businessName: 'Golden Wok',       location: 'Flushing, NY',  contactEmail: 'chen@goldenwok.com', contactPhone: undefined, priorityScore: 65, genuineness: 91, status: 'called', source: 'yelp',        addedAt: '2026-08-14', instagramHandle: '@goldenwok_ny', facebookHandle: 'goldenwokny', followersCount: 1200 },
      { leadId: 'LD-101-04', businessName: 'Spice Route',      location: 'Jackson Heights, NY', websiteUrl: 'spiceroute.com', contactPhone: '(718) 780-4422', priorityScore: 72, genuineness: 95, status: 'warm',   source: 'google_maps', addedAt: '2026-08-14' },
      { leadId: 'LD-101-05', businessName: 'The Burger Lab',   location: 'Astoria, NY',   websiteUrl: 'burgerlab.co',   contactPhone: '(718) 555-9900', priorityScore: 68, genuineness: 97, status: 'new',  source: 'google_maps', addedAt: '2026-08-14' },
    ],
  },
  {
    id: 'sheet-002', sheetId: 'LD-102',
    name: 'SF Salons – Aug 2026',
    service: 'social_media',
    sources: ['google_maps', 'yelp'],
    niches: ['Beauty', 'Hair Salon'],
    timeTakenMin: 9,
    createdAt: '2026-08-13T02:00:00Z',
    callerName: 'Caller 2', callerEmail: 'caller2@company.com',
    googleSheetsUrl: 'https://docs.google.com/spreadsheets/d/example2',
    leads: [
      { leadId: 'LD-102-01', businessName: 'Luxe Cuts',      location: 'San Francisco, CA', websiteUrl: 'luxecuts.com', contactPhone: '(415) 220-3344', instagramHandle: '@luxecuts_sf', followersCount: 8400, socialScore: 72, priorityScore: 91, genuineness: 99, status: 'new',      source: 'google_maps', addedAt: '2026-08-13' },
      { leadId: 'LD-102-02', businessName: 'The Hair Studio', location: 'San Francisco, CA', contactEmail: 'renee@hairstudio.com', instagramHandle: '@thehairstudio', followersCount: 3200, socialScore: 58, priorityScore: 74, genuineness: 94, status: 'assigned', source: 'yelp',        addedAt: '2026-08-13' },
      { leadId: 'LD-102-03', businessName: 'Glow Up Salon',  location: 'Oakland, CA',       websiteUrl: 'glowup.salon', contactPhone: '(510) 889-2200', instagramHandle: '@glowupsalon', facebookHandle: 'GlowUpSalon', followersCount: 5600, socialScore: 81, priorityScore: 83, genuineness: 96, status: 'new', source: 'google_maps', addedAt: '2026-08-13' },
    ],
  },
  {
    id: 'sheet-003', sheetId: 'LD-103',
    name: 'Chicago Plumbers – Aug 2026',
    service: 'seo',
    sources: ['yelp', 'google_maps'],
    niches: ['Home Services', 'Plumbing'],
    timeTakenMin: 11,
    createdAt: '2026-08-12T02:00:00Z',
    callerName: 'Caller 3', callerEmail: 'caller3@company.com',
    leads: [
      { leadId: 'LD-103-01', businessName: 'Windy City Plumbing', location: 'Chicago, IL',    websiteUrl: 'windycityplumbing.com', contactPhone: '(312) 400-7755', seoScore: 34, priorityScore: 88, genuineness: 98, status: 'new',  source: 'yelp',        addedAt: '2026-08-12' },
      { leadId: 'LD-103-02', businessName: 'Reliable Pipes Co.',  location: 'Naperville, IL', contactEmail: 'carl@reliablepipes.com', seoScore: 21, priorityScore: 61, genuineness: 92, status: 'new',  source: 'yelp',        addedAt: '2026-08-12' },
      { leadId: 'LD-103-03', businessName: 'HydroFix Services',   location: 'Evanston, IL',   websiteUrl: 'hydrofix.com', contactPhone: '(847) 511-3300', seoScore: 47, priorityScore: 77, genuineness: 97, status: 'warm', source: 'google_maps', addedAt: '2026-08-12' },
    ],
  },
  {
    id: 'sheet-004', sheetId: 'LD-104',
    name: 'Austin Gyms – Aug 2026',
    service: 'smma',
    sources: ['google_maps', 'linkedin'],
    niches: ['Fitness', 'Gym'],
    timeTakenMin: 7,
    createdAt: '2026-08-11T02:00:00Z',
    callerName: 'Caller 1', callerEmail: 'caller1@company.com',
    googleSheetsUrl: 'https://docs.google.com/spreadsheets/d/example4',
    leads: [
      { leadId: 'LD-104-01', businessName: 'Iron Temple Gym', location: 'Austin, TX',     websiteUrl: 'irontemple.gym', contactPhone: '(512) 773-0022', instagramHandle: '@irontemple', facebookHandle: 'IronTempleGym', followersCount: 12800, socialScore: 88, priorityScore: 94, genuineness: 98, status: 'new',    source: 'linkedin',    addedAt: '2026-08-11' },
      { leadId: 'LD-104-02', businessName: 'Flex Zone',       location: 'Round Rock, TX', websiteUrl: 'flexzone.fit',   contactPhone: '(512) 444-8811', instagramHandle: '@flexzone_fit', followersCount: 4300, socialScore: 63, priorityScore: 80, genuineness: 95, status: 'called', source: 'google_maps', addedAt: '2026-08-11' },
    ],
  },
];

export const ALL_LEADS: Lead[] = MOCK_SHEETS.flatMap(s => s.leads);

// ─── Raw Leads ───────────────────────────────────────────────────────────────
export interface RawLead {
  id: string; businessName: string; location: string; niche: string;
  phone?: string; website?: string; source: string; scrapedAt: string;
  status: 'pending' | 'processing' | 'qualified' | 'rejected';
}

export const RAW_LEADS: RawLead[] = [
  { id: 'r-001', businessName: 'Pizza Palace',         location: 'Brooklyn, NY',  niche: 'Restaurant',   phone: '(718) 222-1111', website: 'yes', source: 'Google Maps', scrapedAt: '2026-08-15 02:14', status: 'pending' },
  { id: 'r-002', businessName: "McDonald's #2241",     location: 'Manhattan, NY', niche: 'Restaurant',   phone: '(212) 888-0000',              source: 'Google Maps', scrapedAt: '2026-08-15 02:14', status: 'rejected' },
  { id: 'r-003', businessName: 'Sunrise Yoga Studio',  location: 'Portland, OR',  niche: 'Fitness',      phone: '(503) 445-6677', website: 'yes', source: 'Yelp',        scrapedAt: '2026-08-15 02:15', status: 'processing' },
  { id: 'r-004', businessName: 'Blue Ridge Accounting',location: 'Asheville, NC', niche: 'Finance',      phone: '(828) 334-9900', website: 'yes', source: 'Google Maps', scrapedAt: '2026-08-15 02:15', status: 'qualified' },
  { id: 'r-005', businessName: 'The Dog Groomer',      location: 'Denver, CO',    niche: 'Pet Services',                                        source: 'Yelp',        scrapedAt: '2026-08-15 02:16', status: 'pending' },
  { id: 'r-006', businessName: 'Starbucks #8842',      location: 'Seattle, WA',   niche: 'Cafe',         phone: '(206) 000-1234',              source: 'Google Maps', scrapedAt: '2026-08-15 02:16', status: 'rejected' },
  { id: 'r-007', businessName: 'Harbor View Dental',   location: 'San Diego, CA', niche: 'Healthcare',   phone: '(619) 778-3344', website: 'yes', source: 'Google Maps', scrapedAt: '2026-08-15 02:17', status: 'processing' },
  { id: 'r-008', businessName: 'Neon Tattoo Parlor',   location: 'Las Vegas, NV', niche: 'Beauty',       phone: '(702) 443-2211', website: 'yes', source: 'Yelp',        scrapedAt: '2026-08-15 02:18', status: 'pending' },
];

// ─── Scrape progress (live state shape for backend) ──────────────────────────
export interface ScrapeProgress {
  total: number; scraped: number; filtered: number;
  enriched: number; scored: number; qualified: number;
  status: 'idle' | 'running' | 'done';
  estimatedMinutes: number;
}
