'use client';
import { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';
import { LeadSheet, SERVICE_LABELS, ServiceType } from '../lib/data';

const COUNTRIES = [
  { code: 'US', name: 'United States' },
  { code: 'UK', name: 'United Kingdom' },
  { code: 'CA', name: 'Canada' },
  { code: 'AU', name: 'Australia' },
  { code: 'IN', name: 'India' }
];

const REGIONS: Record<string, string[]> = {
  US: [
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut', 'Delaware', 'Florida', 'Georgia', 
    'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana', 'Maine', 'Maryland', 
    'Massachusetts', 'Michigan', 'Minnesota', 'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada', 'New Hampshire', 'New Jersey', 
    'New Mexico', 'New York', 'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 'South Carolina', 
    'South Dakota', 'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington', 'West Virginia', 'Wisconsin', 'Wyoming'
  ],
  UK: [
    'England', 'Scotland', 'Wales', 'Northern Ireland'
  ],
  CA: [
    'Ontario', 'Quebec', 'Nova Scotia', 'New Brunswick', 'Manitoba', 'British Columbia', 'Prince Edward Island', 'Saskatchewan', 'Alberta', 'Newfoundland and Labrador', 'Northwest Territories', 'Yukon', 'Nunavut'
  ],
  AU: [
    'New South Wales', 'Queensland', 'South Australia', 'Tasmania', 'Victoria', 'Western Australia', 'Australian Capital Territory', 'Northern Territory'
  ],
  IN: [
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 
    'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab', 
    'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal', 'Delhi'
  ]
};

const NICHES = [
  'HVAC', 'Lawn Care', 'Garbage Removal', 'Dentists', 'Medspas', 
  'CPA Firms', 'Lawyers', 'Plumbers', 'Electricians', 'Car Mechanics'
];

const NICHE_SUGGESTIONS: Record<string, string[]> = {
  'Electricians': ['Residential electricians', 'Emergency electricians', 'Commercial electricians', 'Electrical contractors', 'Licensed electricians'],
  'Dentists': ['Cosmetic dentists', 'Family dentists', 'Emergency dentists', 'Pediatric dentists'],
  'HVAC': ['HVAC contractors', 'AC repair', 'Heating contractors', 'HVAC installation'],
  'Plumbers': ['Plumbing Contractor', 'Drain Service', 'Emergency Plumbing', 'Pipe Repair'],
  'Lawn Care': ['Lawn mowing', 'Landscaping services', 'Lawn aeration', 'Weed control'],
  'Garbage Removal': ['Junk removal', 'Waste disposal', 'Debris cleanup', 'Dumpster rental'],
  'Medspas': ['Botox clinic', 'Laser hair removal', 'Skin rejuvenation', 'Facial spa'],
  'CPA Firms': ['Tax preparation', 'Accounting services', 'Bookkeeping', 'Financial audit'],
  'Lawyers': ['Family law', 'Personal injury lawyer', 'Criminal defense', 'Corporate attorney'],
  'Car Mechanics': ['Auto repair shop', 'Brake service', 'Engine diagnostic', 'Oil change']
};

const REGION_CITIES: Record<string, string[]> = {
  'Alabama': ['Birmingham', 'Montgomery', 'Mobile', 'Huntsville'],
  'California': ['Los Angeles', 'San Francisco', 'San Diego', 'San Jose', 'Sacramento'],
  'Texas': ['Austin', 'Houston', 'Dallas', 'San Antonio', 'Fort Worth'],
  'New York': ['New York City', 'Buffalo', 'Rochester', 'Syracuse', 'Albany'],
  'Florida': ['Miami', 'Orlando', 'Tampa', 'Jacksonville', 'Tallahassee'],
  'England': ['London', 'Birmingham', 'Manchester', 'Leeds', 'Liverpool'],
  'Scotland': ['Edinburgh', 'Glasgow', 'Aberdeen', 'Dundee'],
  'Wales': ['Cardiff', 'Swansea', 'Newport'],
  'Ontario': ['Toronto', 'Ottawa', 'Mississauga', 'Hamilton'],
  'Quebec': ['Montreal', 'Quebec City', 'Laval', 'Gatineau'],
  'British Columbia': ['Vancouver', 'Victoria', 'Burnaby', 'Surrey'],
  'New South Wales': ['Sydney', 'Newcastle', 'Wollongong'],
  'Victoria': ['Melbourne', 'Geelong', 'Ballarat'],
  'Maharashtra': ['Mumbai', 'Pune', 'Nagpur', 'Thane'],
  'Delhi': ['New Delhi', 'Dwarka', 'Rohini'],
  'Karnataka': ['Bangalore', 'Mysore', 'Hubli'],
  'Tamil Nadu': ['Chennai', 'Coimbatore', 'Madurai']
};

const SERVICES = [
  { key: 'website_dev', label: 'Website Development' },
  { key: 'seo', label: 'SEO' },
  { key: 'smma', label: 'Social Media Management' },
  { key: 'social_media', label: 'Social Media Marketing' }
];

const formatDate = (dateStr: string) => {
  const d = new Date(dateStr);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = String(d.getFullYear()).slice(-2);
  return `${day}/${month}/${day === 'NaN' || month === 'NaN' ? '26' : year}`;
};


class ScraperParticle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  color: string;
  alpha: number;
  decay: number;

  constructor(x: number, y: number) {
    this.x = x;
    this.y = y;
    this.vx = (Math.random() - 0.5) * 5;
    this.vy = -(Math.random() * 4 + 2);
    this.size = Math.random() * 3 + 1;
    this.alpha = 1.0;
    this.decay = Math.random() * 0.02 + 0.015;
    this.color = Math.random() > 0.5 ? '#ec4899' : '#a855f7'; // pink and purple
  }

  update() {
    this.x += this.vx;
    this.y += this.vy;
    this.alpha -= this.decay;
  }

  draw(ctx: CanvasRenderingContext2D) {
    ctx.save();
    ctx.globalAlpha = Math.max(0, this.alpha);
    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

export default function OperationsPage() {
  const [niche, setNiche] = useState(NICHES[0]);
  const [country, setCountry] = useState('US');
  const [region, setRegion] = useState('');
  const [city, setCity] = useState('');
  const [service, setService] = useState('website_dev');
  const [count, setCount] = useState('100');
  const [selectedSources, setSelectedSources] = useState<string[]>(['google_maps']);
  
  // Advanced Scraper Options
  const [customCount, setCustomCount] = useState('');
  const [allAvailable, setAllAvailable] = useState(false);
  const [plainQuery, setPlainQuery] = useState(false);
  const [plainQueryValue, setPlainQueryValue] = useState('');
  const [exactMatch, setExactMatch] = useState(false);
  const [relatedCategories, setRelatedCategories] = useState(true);
  const [searchMode, setSearchMode] = useState<'exact' | 'balanced' | 'broad'>('balanced');
  const [searchDepth, setSearchDepth] = useState<'standard' | 'deep' | 'maximum'>('standard');
  const [customLocation, setCustomLocation] = useState(false);
  const [customLocationValue, setCustomLocationValue] = useState('');
  const [locations, setLocations] = useState<string[]>([]);
  const [duplicateHandling, setDuplicateHandling] = useState<'remove' | 'quality' | 'keep'>('remove');
  const [qualityFilter, setQualityFilter] = useState<'any' | 'good' | 'high' | 'very_high'>('any');
  const [presets, setPresets] = useState<{ name: string; config: any }[]>([]);
  const [presetNameInput, setPresetNameInput] = useState('');
  const [showPresetDropdown, setShowPresetDropdown] = useState(false);
  const [recentSearches, setRecentSearches] = useState<any[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [nicheSearchQuery, setNicheSearchQuery] = useState('');
  const [showNicheDropdown, setShowNicheDropdown] = useState(false);
  const [categories, setCategories] = useState<string[]>([]);
  const [citySearchQuery, setCitySearchQuery] = useState('');
  const [showCityDropdown, setShowCityDropdown] = useState(false);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  
  const [scrapeStats, setScrapeStats] = useState({
    discovered: 0,
    valid: 0,
    duplicates: 0,
    saved: 0,
    failed: 0
  });

  const [microStatus, setMicroStatus] = useState('Initializing scraper...');
  const [paused, setPaused] = useState(false);
  const [savedCountWhenStopped, setSavedCountWhenStopped] = useState<number | null>(null);
  const [creatingJob, setCreatingJob] = useState(false);
  
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const formContainerRef = useRef<HTMLDivElement | null>(null);
  const [isDisintegrating, setIsDisintegrating] = useState(false);

  // Load presets/recents from localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedPresets = localStorage.getItem('lead_scraper_presets');
      if (savedPresets) setPresets(JSON.parse(savedPresets));
      const savedRecents = localStorage.getItem('lead_scraper_recent_searches');
      if (savedRecents) setRecentSearches(JSON.parse(savedRecents));
    }
  }, []);

  // Scraper State
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [remainingTime, setRemainingTime] = useState(0);
  const [scrapedCount, setScrapedCount] = useState(0);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [scrapeError, setScrapeError] = useState<string | null>(null);
  const [scrapeStatus, setScrapeStatus] = useState<'idle' | 'running' | 'completed' | 'partial' | 'cancelled' | 'failed' | 'cancelling' | 'stopped_saved'>('idle');
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Workflow Sheets
  const [rawSheets, setRawSheets] = useState<LeadSheet[]>([]);
  const [selectedRawId, setSelectedRawId] = useState<string | null>(null);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [segregating, setSegregating] = useState(false);

  // Rename modal state
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [renameInput, setRenameInput] = useState('');
  const [pendingRawSheet, setPendingRawSheet] = useState<any>(null);

  // Guard: track which job IDs have already shown the rename modal (prevents multi-popup)
  const shownRenameForRef = useRef<Set<string>>(new Set());

  // Polling interval ref
  const pollingIntervalRef = useRef<any>(null);

  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  // Preview raw sheet modal state
  const [openRawSheet, setOpenRawSheet] = useState<any>(null);
  const [previewLeads, setPreviewLeads] = useState<any[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Segregation progress state
  const [segregationProgress, setSegregationProgress] = useState(0);
  const [segregationTotal, setSegregationTotal] = useState(0);

  // Scroll target ref for View Leads
  const tableRef = useRef<HTMLDivElement>(null);

  // Load raw sheets from database
  const loadRawSheets = () => {
    api.getRawLeads()
      .then(data => {
        // Raw sheets are those jobs that are COMPLETED, PARTIAL or RUNNING
        const raw = (data as any || []).filter((job: any) => job.status === 'COMPLETED' || job.status === 'PARTIAL' || job.status === 'RUNNING');
        setRawSheets(raw as any);
      })
      .catch(err => {
        console.error("Failed to load raw sheets", err);
        setRawSheets([]);
      });
  };

  useEffect(() => {
    loadRawSheets();
  }, []);

  // Fetch preview leads when modal is opened
  useEffect(() => {
    if (openRawSheet) {
      setLoadingPreview(true);
      api.getJobLeads(openRawSheet.id)
        .then(data => {
          setPreviewLeads(data || []);
          setLoadingPreview(false);
        })
        .catch(err => {
          console.error("Failed to load raw sheet leads", err);
          setPreviewLeads([]);
          setLoadingPreview(false);
        });
    } else {
      setPreviewLeads([]);
    }
  }, [openRawSheet]);

  // Update regions based on Country
  useEffect(() => {
    const list = REGIONS[country] || [];
    if (list.length > 0) {
      setRegion(list[0]);
    } else {
      setRegion('');
    }
  }, [country]);

  const logScrapeHistory = (jobId: string, nicheVal: string, locationVal: string, requestedVal: number, scrapedVal: number, statusVal: string) => {
    if (typeof window !== 'undefined') {
      const scrapeRecord = {
        id: `scr-${Date.now()}`,
        type: "scrape",
        createdAt: new Date().toISOString(),
        jobId: jobId,
        niche: nicheVal,
        location: locationVal || 'London',
        requested: requestedVal,
        scraped: scrapedVal,
        status: statusVal
      };
      const saved = localStorage.getItem('lead_system_scrape_history');
      const current = saved ? JSON.parse(saved) : [];
      localStorage.setItem('lead_system_scrape_history', JSON.stringify([scrapeRecord, ...current]));
      window.dispatchEvent(new Event('history-updated'));
    }
  };

  const addNotification = (message: string, sheetId: string) => {
    if (typeof window !== 'undefined') {
      const notification = {
        id: `notif-${Date.now()}`,
        message,
        sheetId,
        timestamp: new Date().toISOString(),
        read: false
      };
      const savedNotifs = localStorage.getItem('lead_system_notifications');
      const currentNotifs = savedNotifs ? JSON.parse(savedNotifs) : [];
      localStorage.setItem('lead_system_notifications', JSON.stringify([notification, ...currentNotifs]));
      window.dispatchEvent(new Event('notifications-updated'));
    }
  };

  // Reusable polling logic
  const startPollingProgress = (jobId: string) => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    setActiveJobId(jobId);
    setRunning(true);
    setScrapeStatus('running');
    setScrapeError(null);
    setPaused(false);
    localStorage.setItem('lead_system_active_scrape_run', JSON.stringify({ runId: jobId }));

    const startTime = Date.now();

    const intervalId = setInterval(async () => {
      try {
        const prog = await api.getScrapeProgress(jobId);

        // Update real stats
        setScrapeStats({
          discovered: prog.discovered || prog.discovered_count || 0,
          valid: prog.valid || prog.valid_count || 0,
          duplicates: prog.duplicates || prog.duplicate_count || 0,
          saved: prog.leads_scraped || 0,
          failed: prog.failed || prog.failed_count || 0
        });

        // Set micro-status dynamically based on backend source & query
        if (prog.status === 'RUNNING' || prog.status === 'PENDING') {
          if (prog.current_source || prog.current_query) {
            setMicroStatus(`Retrieving from ${prog.current_source || 'Google Maps'} - "${prog.current_query || prog.niche}"`);
          } else {
            const steps = [
              "Connecting to Google Places API...",
              "Querying local directory coordinates...",
              "Extracting business contact records...",
              "Verifying website & email structures...",
              "Calculating ML qualification scores...",
              "Persisting leads in canonical store..."
            ];
            const idx = Math.floor((Date.now() - startTime) / 3000) % steps.length;
            setMicroStatus(steps[idx]);
          }
        }

        if (prog.status === 'CANCELLED') {
          stopPolling();
          localStorage.removeItem('lead_system_active_scrape_run');
          setActiveJobId(null);
          setScrapeStatus('idle');
          setRunning(false);
          setPaused(false);
          loadRawSheets();
          
          logScrapeHistory(jobId, prog.niche, prog.region, prog.requested, prog.leads_scraped, 'cancelled');
          addNotification(`Scrape cancelled. ${prog.leads_scraped} leads were saved.`, jobId);
          return;
        }

        if (prog.status === 'FAILED') {
          stopPolling();
          localStorage.removeItem('lead_system_active_scrape_run');
          setActiveJobId(null);
          setScrapeStatus('failed');
          setScrapeError(prog.error_message || 'Connection failed');
          setRunning(false);
          setPaused(false);
          loadRawSheets();

          logScrapeHistory(jobId, prog.niche, prog.region, prog.requested, prog.leads_scraped, 'failed');
          addNotification(`Scrape failed: ${prog.error_message || 'Unknown error'}`, jobId);
          return;
        }

        if (prog.status === 'STOPPED_SAVED') {
          stopPolling();
          setScrapeStatus('stopped_saved' as any);
          setRunning(false);
          setPaused(true);
          setSavedCountWhenStopped(prog.leads_scraped || 0);
          loadRawSheets();
          addNotification(`Scrape paused/stopped. ${prog.leads_scraped} leads saved. Ready to resume.`, jobId);
          return;
        }

        // Update counts
        setScrapedCount(prog.leads_scraped || 0);
        setProgress(prog.progress_percent || 0);

        // Update estimated time
        const elapsed = (Date.now() - startTime) / 1000;
        const target = prog.requested || parseInt(count, 10) || 100;
        if (prog.leads_scraped && prog.leads_scraped > 0) {
          const speed = prog.leads_scraped / (elapsed || 1); // leads per second
          setRemainingTime(Math.max(0, Math.ceil((target - prog.leads_scraped) / speed)));
        } else {
          setRemainingTime(-1); // will show "Estimating..."
        }

        if (prog.status === 'COMPLETED' || prog.status === 'PARTIAL') {
          stopPolling();
          localStorage.removeItem('lead_system_active_scrape_run');
          setActiveJobId(null);
          setScrapeStatus(prog.status.toLowerCase() as any);
          setRunning(false);
          setPaused(false);
          loadRawSheets();

          logScrapeHistory(jobId, prog.niche, prog.region, prog.requested, prog.leads_scraped, prog.status.toLowerCase());

          const msg = prog.status === 'COMPLETED' 
            ? `${prog.leads_scraped} leads scraped successfully.` 
            : `${prog.leads_scraped} leads scraped. Source returned no additional valid leads.`;
          addNotification(msg, jobId);

          // Only show the rename modal ONCE per job (prevents duplicate popups from recovery
          // or multiple concurrent polling intervals)
          if (!shownRenameForRef.current.has(jobId)) {
            shownRenameForRef.current.add(jobId);
            const defaultName = `${prog.niche} - ${city || 'Capital'}, ${prog.region} (${COUNTRIES.find(c => c.code === country)?.name || country})`;
            setPendingRawSheet({
              id: jobId,
              sheetId: prog.sheetId || `RLD-001`,
              name: defaultName,
              service: prog.service,
              country: country,
              region: prog.region,
              niche: prog.niche,
              leads_scraped: prog.leads_scraped,
              leads: []
            });
            setRenameInput(defaultName);
            setShowRenameModal(true);
          }
          // Reset remaining time now that scraping is done
          setRemainingTime(0);
        }
      } catch (err) {
        console.error("Error polling progress", err);
      }
    }, 1500);

    pollingIntervalRef.current = intervalId;
  };

  // Mount recovery
  useEffect(() => {
    const activeRun = localStorage.getItem('lead_system_active_scrape_run');
    if (activeRun) {
      try {
        const { runId } = JSON.parse(activeRun);
        if (runId) {
          api.getScrapeProgress(runId)
            .then(prog => {
              if (prog.status === 'PENDING' || prog.status === 'RUNNING') {
                // Restore parameters
                const recoveredNiche = prog.niche && prog.niche.includes(' - ') ? prog.niche.split(' - ')[0].trim() : prog.niche;
                setNiche(recoveredNiche || NICHES[0]);
                setCountry(prog.country || 'US');
                setRegion(prog.region || '');
                setService(prog.service || 'website_dev');
                setCount(String(prog.requested || 100));
                
                // Start polling
                startPollingProgress(runId);
              } else {
                localStorage.removeItem('lead_system_active_scrape_run');
                setScrapeStatus(prog.status.toLowerCase() as any);
                setScrapedCount(prog.leads_scraped || 0);
                setProgress(prog.progress_percent || 0);
                if (prog.status === 'FAILED') {
                  setScrapeError(prog.error_message || 'Connection failed');
                }
              }
            })
            .catch(err => {
              console.error("Failed to recover active run", err);
              localStorage.removeItem('lead_system_active_scrape_run');
            });
        }
      } catch (e) {
        console.error("Failed to parse active run JSON", e);
        localStorage.removeItem('lead_system_active_scrape_run');
      }
    }
  }, []);

  // Polling unmount cleanup
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, []);

  // Backend recovery
  useEffect(() => {
    const runningJob = rawSheets.find(s => (s as any).status === 'RUNNING' || (s as any).status === 'PENDING') as any;
    if (runningJob && !running && !activeJobId) {
      const recoveredNiche = runningJob.niche && runningJob.niche.includes(' - ') ? runningJob.niche.split(' - ')[0].trim() : runningJob.niche;
      setNiche(recoveredNiche);
      setCountry(runningJob.country);
      setRegion(runningJob.region);
      setService(runningJob.service);
      setCount(String(runningJob.target_lead_count));
      startPollingProgress(runningJob.id);
    }
  }, [rawSheets]);

  const [enrichmentOptions, setEnrichmentOptions] = useState<Record<string, boolean>>({
    email: true,
    phone: true,
    website: true,
    social: false,
    details: false
  });

  const [showResetConfirm, setShowResetConfirm] = useState(false);

  // Styles
  const sectionLabelStyle: React.CSSProperties = {
    fontSize: '11px',
    fontWeight: 600,
    color: 'var(--text-3)',
    textTransform: 'uppercase',
    letterSpacing: '.06em',
    marginBottom: '6px'
  };

  const checkboxLabelStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '13px',
    color: 'var(--text-2)',
    cursor: 'pointer',
    userSelect: 'none'
  };

  // Presets Handlers
  const handleSavePreset = () => {
    const name = presetNameInput.trim();
    if (!name) return;
    const currentConfig = {
      niche,
      country,
      region,
      city,
      locations,
      customLocation,
      customLocationValue,
      service,
      count,
      customCount,
      allAvailable,
      plainQuery,
      plainQueryValue,
      exactMatch,
      relatedCategories,
      searchMode,
      searchDepth,
      duplicateHandling,
      qualityFilter,
      enrichmentOptions
    };
    const updatedPresets = [...presets.filter(p => p.name !== name), { name, config: currentConfig }];
    setPresets(updatedPresets);
    localStorage.setItem('lead_scraper_presets', JSON.stringify(updatedPresets));
    setPresetNameInput('');
  };

  const handleLoadPreset = (name: string) => {
    const preset = presets.find(p => p.name === name);
    if (!preset) return;
    const c = preset.config;
    if (c.niche !== undefined) setNiche(c.niche);
    if (c.country !== undefined) setCountry(c.country);
    if (c.region !== undefined) setRegion(c.region);
    if (c.city !== undefined) setCity(c.city);
    if (c.locations !== undefined) setLocations(c.locations);
    if (c.customLocation !== undefined) setCustomLocation(c.customLocation);
    if (c.customLocationValue !== undefined) setCustomLocationValue(c.customLocationValue);
    if (c.service !== undefined) setService(c.service);
    if (c.count !== undefined) setCount(c.count);
    if (c.customCount !== undefined) setCustomCount(c.customCount);
    if (c.allAvailable !== undefined) setAllAvailable(c.allAvailable);
    if (c.plainQuery !== undefined) setPlainQuery(c.plainQuery);
    if (c.plainQueryValue !== undefined) setPlainQueryValue(c.plainQueryValue);
    if (c.exactMatch !== undefined) setExactMatch(c.exactMatch);
    if (c.relatedCategories !== undefined) setRelatedCategories(c.relatedCategories);
    if (c.searchMode !== undefined) setSearchMode(c.searchMode);
    if (c.searchDepth !== undefined) setSearchDepth(c.searchDepth);
    if (c.duplicateHandling !== undefined) setDuplicateHandling(c.duplicateHandling);
    if (c.qualityFilter !== undefined) setQualityFilter(c.qualityFilter);
    if (c.enrichmentOptions !== undefined) setEnrichmentOptions(c.enrichmentOptions);
  };

  const handleDeletePreset = (name: string) => {
    const updatedPresets = presets.filter(p => p.name !== name);
    setPresets(updatedPresets);
    localStorage.setItem('lead_scraper_presets', JSON.stringify(updatedPresets));
  };

  // Reset Handlers
  const handleResetClick = () => {
    const hasChanges = plainQuery || niche !== NICHES[0] || country !== 'US' || city !== '' || locations.length > 0 || count !== '100' || customLocation || !relatedCategories || exactMatch || searchMode !== 'balanced' || searchDepth !== 'standard';
    if (hasChanges) {
      setShowResetConfirm(true);
    } else {
      performReset();
    }
  };

  const performReset = () => {
    setNiche(NICHES[0]);
    setCategories([]);
    setCountry('US');
    setRegion('');
    setCity('');
    setLocations([]);
    setCustomLocation(false);
    setCustomLocationValue('');
    setService('website_dev');
    setCount('100');
    setCustomCount('');
    setAllAvailable(false);
    setPlainQuery(false);
    setPlainQueryValue('');
    setExactMatch(false);
    setRelatedCategories(true);
    setSearchMode('balanced');
    setSearchDepth('standard');
    setDuplicateHandling('remove');
    setQualityFilter('any');
    setEnrichmentOptions({ email: true, phone: true, website: true, social: false, details: false });
    setShowResetConfirm(false);
  };

  const triggerDisintegrationEffect = () => {
    if (!canvasRef.current || !formContainerRef.current) return;
    const canvas = canvasRef.current;
    const container = formContainerRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Find all controls to originate particles from their specific locations
    const controls = container.querySelectorAll('input, select, button, div[style*="border"]');
    const newParticles: ScraperParticle[] = [];
    
    controls.forEach(ctrl => {
      const elRect = ctrl.getBoundingClientRect();
      const xOffset = elRect.left - rect.left;
      const yOffset = elRect.top - rect.top;
      
      // Spawn particles within each control's bounding box
      const step = 12;
      for (let x = 0; x < elRect.width; x += step) {
        for (let y = 0; y < elRect.height; y += step) {
          if (Math.random() > 0.3) {
            newParticles.push(new ScraperParticle(xOffset + x, yOffset + y));
          }
        }
      }
    });

    // Fallback if no controls found
    if (newParticles.length === 0) {
      const step = 20;
      for (let x = 0; x < rect.width; x += step) {
        for (let y = 0; y < rect.height; y += step) {
          newParticles.push(new ScraperParticle(x, y));
        }
      }
    }

    let animationFrameId: number;
    const startTime = Date.now();

    const render = () => {
      const elapsed = Date.now() - startTime;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      newParticles.forEach(p => {
        p.update();
        p.draw(ctx);
      });

      if (elapsed < 600) {
        animationFrameId = requestAnimationFrame(render);
      } else {
        cancelAnimationFrame(animationFrameId);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    };

    render();
  };

  const handleStartScrape = async () => {
    // Prevent starting concurrent scrapes
    const active = rawSheets.find(s => (s as any).status === 'RUNNING' || (s as any).status === 'PENDING');
    if (active) {
      addNotification("A scrape is already running. You can recover it or wait for it to complete.", active.id);
      return;
    }

    // Validation
    const errors: Record<string, string> = {};
    const finalCategories = categories.length > 0 ? categories.join(', ') : niche;
    const rawNVal = plainQuery ? plainQueryValue.trim() : finalCategories.trim();
    // Clean niche: if it contains ' - ', take the first part to prevent propagation of default names
    const nVal = rawNVal.includes(' - ') ? rawNVal.split(' - ')[0].trim() : rawNVal;
    if (!nVal) {
      errors.niche = plainQuery ? "Search query is required" : "Category selection is required";
    }
    
    const locVal = customLocation 
      ? customLocationValue.trim() 
      : (locations.length > 0 ? locations[0] : city.trim());
    if (!locVal) {
      errors.location = "Location/City is required";
    }

    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }
    setValidationErrors({});

    setCreatingJob(true);

    const totalCount = allAvailable 
      ? 10000 
      : (parseInt(count === 'custom' ? customCount : count, 10) || 100);
    setRemainingTime(-1); // Estimating...

    try {
      const res = await api.startScrape({
        niche: nVal,
        city: locVal,
        region: region,
        count: totalCount,
        service: service,
        sources: selectedSources,
        plain_query: plainQuery ? plainQueryValue : null,
        exact_match: exactMatch,
        related_categories: relatedCategories,
        locations: locations.length > 0 ? locations : [locVal],
        search_mode: searchMode,
        search_depth: searchDepth,
        enrichments: Object.keys(enrichmentOptions).filter(k => enrichmentOptions[k]),
        deduplication_mode: duplicateHandling,
        quality_threshold: qualityFilter
      });
      
      const jobId = res.id || res.jobId;
      if (!jobId) {
        setCreatingJob(false);
        setScrapeStatus('idle');
        return;
      }

      setRunning(true);
      setProgress(0);
      setScrapedCount(0);
      setScrapeStatus('running');
      setScrapeError(null);
      setPaused(false);

      // Store configuration to recent searches
      const newSearch = {
        id: `rc-${Date.now()}`,
        timestamp: new Date().toISOString(),
        config: {
          niche: plainQuery ? plainQueryValue : finalCategories,
          categories,
          plainQuery,
          plainQueryValue,
          country,
          region,
          city: customLocation ? customLocationValue : city,
          locations,
          customLocation,
          customLocationValue,
          service,
          count,
          customCount,
          allAvailable,
          exactMatch,
          relatedCategories,
          searchMode,
          searchDepth,
          duplicateHandling,
          qualityFilter
        }
      };
      
      const updatedRecents = [newSearch, ...recentSearches.filter(r => r.config.niche !== newSearch.config.niche).slice(0, 4)];
      setRecentSearches(updatedRecents);
      localStorage.setItem('lead_scraper_recent_searches', JSON.stringify(updatedRecents));

      // Trigger disintegration visual effect
      setIsDisintegrating(true);
      triggerDisintegrationEffect();

      // Wait for disintegration animation to finish (600ms) before swapping UI
      setTimeout(() => {
        setIsDisintegrating(false);
        startPollingProgress(jobId);
      }, 600);

    } catch (err) {
      console.error("Failed to start scrape", err);
      setCreatingJob(false);
      setRunning(false);
      setScrapeStatus('failed');
      setScrapeError("Failed to initiate scraper. Connection refused.");
    }
  };

  const handleStopScrape = async () => {
    if (!activeJobId) return;
    setScrapeStatus('cancelling');
    try {
      await api.stopScrape(activeJobId);
      setScrapeStatus('stopped_saved' as any);
      setRunning(false);
      setPaused(true);
    } catch (e) {
      console.error("Failed to stop scrape", e);
    }
  };

  const handleResumeScrape = async () => {
    if (!activeJobId) return;
    setScrapeStatus('running');
    setRunning(true);
    setPaused(false);
    try {
      await api.resumeScrape(activeJobId);
      startPollingProgress(activeJobId);
    } catch (e) {
      console.error("Failed to resume scrape", e);
    }
  };

  const handleCancelScrape = async () => {
    if (!activeJobId) {
      setScrapeStatus('idle');
      return;
    }
    setScrapeStatus('cancelling');
    try {
      await api.cancelScrape(activeJobId);
    } catch (e) {
      console.error("Failed to cancel scrape", e);
    } finally {
      setScrapeStatus('idle');
      setRunning(false);
      setPaused(false);
      setActiveJobId(null);
      localStorage.removeItem('lead_system_active_scrape_run');
      loadRawSheets();
    }
  };

  const handleSaveRename = async (useCustom: boolean) => {
    if (!pendingRawSheet) return;
    const finalName = useCustom ? renameInput.trim() || pendingRawSheet.name : pendingRawSheet.name;
    
    try {
      await api.updateSheet(pendingRawSheet.id, { name: finalName });
      loadRawSheets();
    } catch (e) {
      console.error("Failed to rename sheet", e);
    }

    setHighlightedId(pendingRawSheet.id);
    setShowRenameModal(false);
    setPendingRawSheet(null);
  };

  const handleSegregate = async () => {
    if (!selectedRawId) return;
    const selectedSheet = rawSheets.find(s => s.id === selectedRawId);
    if (!selectedSheet) return;

    const totalLeads = (selectedSheet as any).leads_scraped || 0;

    // Guard: don't proceed with fake animation when there are no leads
    if (totalLeads === 0) {
      alert('This raw lead sheet has 0 scraped leads. Run a scrape first to get leads, then segregate.');
      return;
    }

    setSegregating(true);
    setSegregationProgress(0);
    setSegregationTotal(totalLeads);

    let current = 0;
    const interval = setInterval(async () => {
      current += Math.ceil(Math.random() * 3) + 1;
      if (current >= totalLeads) {
        current = totalLeads;
        clearInterval(interval);
        
        try {
          const res = await api.segregate(selectedRawId);
          
          if (typeof window !== 'undefined') {
            const segregationRecord = {
              id: `seg-${Date.now()}`,
              type: "segregation",
              createdAt: new Date().toISOString(),
              jobId: selectedRawId,
              sheetName: selectedSheet.name,
              service: selectedSheet.service,
              processedCount: totalLeads,
              status: "completed"
            };
            const saved = localStorage.getItem('lead_system_segregation_history');
            const currentHistory = saved ? JSON.parse(saved) : [];
            localStorage.setItem('lead_system_segregation_history', JSON.stringify([segregationRecord, ...currentHistory]));
            
            const notification = {
              id: `notif-${Date.now()}`,
              message: `${res.segregated_leads || totalLeads} leads have been segregated and are now available in Lead Collections.`,
              sheetId: selectedRawId,
              timestamp: new Date().toISOString(),
              read: false
            };
            const savedNotifs = localStorage.getItem('lead_system_notifications');
            const currentNotifs = savedNotifs ? JSON.parse(savedNotifs) : [];
            localStorage.setItem('lead_system_notifications', JSON.stringify([notification, ...currentNotifs]));
            
            window.dispatchEvent(new Event('history-updated'));
            window.dispatchEvent(new Event('notifications-updated'));
          }

          setSelectedRawId(null);
          setSegregating(false);
          loadRawSheets();
        } catch (err) {
          console.error("Segregation failed", err);
          setSegregating(false);
        }
      }
      setSegregationProgress(current);
    }, 80);
  };

  const handleViewLeads = () => {
    if (highlightedId && tableRef.current) {
      tableRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div>

      {/* ── Scrape Controls Card ── */}
      <div 
        ref={formContainerRef}
        style={{ 
          background: 'var(--bg-surface)', 
          border: '1px solid var(--border-faint)', 
          borderRadius: 'var(--r-xl)', 
          padding: '24px', 
          marginBottom: 24, 
          position: 'relative',
          overflow: 'hidden',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
        }}
      >
        {/* Particle Canvas Overlay for disintegration effect */}
        <canvas 
          ref={canvasRef} 
          style={{ 
            position: 'absolute', 
            top: 0, 
            left: 0, 
            width: '100%', 
            height: '100%', 
            pointerEvents: 'none', 
            zIndex: 10 
          }} 
        />

        <div style={{ opacity: isDisintegrating ? 0 : 1, transition: 'opacity 0.3s ease' }}>
          
          {/* Header & Presets row */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 18, borderBottom: '1px solid var(--border-faint)', paddingBottom: 12 }}>
            <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.09em', color: 'var(--text-4)' }}>Scrape Controls</div>
            
            {scrapeStatus === 'idle' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                {/* ⋯ Presets Menu */}
                <div style={{ position: 'relative' }}>
                  <button
                    onClick={() => setShowPresetDropdown(!showPresetDropdown)}
                    title="Presets"
                    style={{
                      width: 32, height: 32, borderRadius: 'var(--r-md)',
                      background: showPresetDropdown ? 'var(--bg-active)' : 'var(--bg-input)',
                      border: '1px solid var(--border-subtle)',
                      color: 'var(--text-2)', fontSize: '18px', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      letterSpacing: '1px', transition: 'background var(--ease)',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                    onMouseLeave={e => (e.currentTarget.style.background = showPresetDropdown ? 'var(--bg-active)' : 'var(--bg-input)')}
                  >
                    ⋯
                  </button>

                  {showPresetDropdown && (
                    <div style={{
                      position: 'absolute', top: '100%', right: 0, marginTop: 6,
                      background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--r-md)', zIndex: 200, minWidth: 220,
                      boxShadow: 'var(--shadow-drop)', overflow: 'hidden'
                    }}>
                      {/* Save preset section */}
                      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border-faint)' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.07em', marginBottom: 6 }}>Save Preset</div>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <input
                            type="text"
                            placeholder="Preset name..."
                            value={presetNameInput}
                            onChange={e => setPresetNameInput(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter' && presetNameInput.trim()) { handleSavePreset(); setShowPresetDropdown(false); } }}
                            style={{ ...inputStyle, flex: 1, height: 28, fontSize: '12px', padding: '0 8px' }}
                          />
                          <button
                            onClick={() => { handleSavePreset(); setShowPresetDropdown(false); }}
                            disabled={!presetNameInput.trim()}
                            style={{
                              background: presetNameInput.trim() ? 'var(--pink)' : 'var(--bg-input)',
                              border: 'none', borderRadius: 'var(--r-sm)', color: presetNameInput.trim() ? '#fff' : 'var(--text-4)',
                              padding: '0 10px', height: 28, fontSize: '11px', cursor: presetNameInput.trim() ? 'pointer' : 'default',
                              transition: 'background var(--ease)'
                            }}
                          >
                            Save
                          </button>
                        </div>
                      </div>

                      {/* Load preset section */}
                      {presets.length > 0 && (
                        <div>
                          <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.07em', padding: '8px 12px 4px' }}>Load Preset</div>
                          {presets.map(p => (
                            <div
                              key={p.name}
                              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 12px', cursor: 'pointer', fontSize: '12px', color: 'var(--text-2)' }}
                              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                            >
                              <span style={{ flex: 1 }} onClick={() => { handleLoadPreset(p.name); setShowPresetDropdown(false); }}>
                                {p.name}
                              </span>
                              <button
                                onClick={e => { e.stopPropagation(); handleDeletePreset(p.name); if (presets.length === 1) setShowPresetDropdown(false); }}
                                style={{ background: 'none', border: 'none', color: 'var(--pink)', cursor: 'pointer', padding: '0 4px', fontSize: '14px', lineHeight: 1 }}
                                title="Delete"
                              >
                                ×
                              </button>
                            </div>
                          ))}
                        </div>
                      )}

                      {presets.length === 0 && (
                        <div style={{ padding: '10px 12px', fontSize: '12px', color: 'var(--text-4)', fontStyle: 'italic' }}>No saved presets yet.</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {scrapeStatus === 'idle' ? (
            /* ==========================================
               1. CONFIGURATION VIEW (IDLE STATE)
               ========================================== */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              
              {/* Core Selector Controls - ROW 1: Categories / Country / Region */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px 20px' }}>
                
                  {/* Categories Input */}
                  <div style={{ position: 'relative', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={sectionLabelStyle}>* Categories/brands</span>
                      <div onClick={() => setPlainQuery(!plainQuery)} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '11px', color: 'var(--text-3)', cursor: 'pointer' }}>
                        <div style={{ width: 28, height: 16, background: plainQuery ? 'var(--pink)' : 'var(--bg-elevated)', borderRadius: 10, position: 'relative', transition: '0.2s', border: '1px solid var(--border-subtle)' }}>
                          <div style={{ position: 'absolute', top: 1, left: plainQuery ? 13 : 1, width: 12, height: 12, background: '#fff', borderRadius: '50%', transition: '0.2s' }} />
                        </div>
                        Plain Queries
                      </div>
                    </div>

                    {plainQuery ? (
                      <input 
                        type="text"
                        value={plainQueryValue}
                        onChange={e => setPlainQueryValue(e.target.value)}
                        style={{ ...inputStyle, width: '100%', borderColor: validationErrors.niche ? 'var(--pink)' : 'var(--border-subtle)' }}
                      />
                    ) : (
                      <div style={{ position: 'relative' }}>
                        <div style={{ display: 'flex', flexWrap: 'nowrap', overflow: 'hidden', gap: 6, background: 'var(--bg-input)', border: `1px solid ${validationErrors.niche ? 'var(--pink)' : 'var(--border-subtle)'}`, borderRadius: 'var(--r-md)', padding: '6px 8px', minHeight: 38, alignItems: 'center' }}>
                          {categories.slice(0, 2).map(cat => (
                            <span key={cat} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(192, 132, 252, 0.2)', backdropFilter: 'blur(4px)', border: '1px solid rgba(192, 132, 252, 0.4)', borderRadius: 4, padding: '2px 6px', fontSize: '12px', color: 'var(--text-1)', whiteSpace: 'nowrap' }}>
                              {cat}
                              <button onClick={() => setCategories(categories.filter(c => c !== cat))} style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', padding: 0, fontSize: '14px', lineHeight: 1 }}>×</button>
                            </span>
                          ))}
                          {categories.length > 2 && (
                            <span onClick={() => setShowNicheDropdown(true)} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(192, 132, 252, 0.2)', backdropFilter: 'blur(4px)', border: '1px solid rgba(192, 132, 252, 0.4)', borderRadius: 4, padding: '2px 6px', fontSize: '12px', color: 'var(--text-1)', cursor: 'pointer', whiteSpace: 'nowrap' }}>
                              +{categories.length - 2}
                            </span>
                          )}
                          <input 
                            type="text" 
                            value={nicheSearchQuery}
                            onChange={e => {
                              setNicheSearchQuery(e.target.value);
                              setShowNicheDropdown(true);
                            }}
                            onFocus={() => setShowNicheDropdown(true)}
                            style={{ background: 'transparent', border: 'none', color: 'var(--text-1)', fontSize: '13px', outline: 'none', flex: 1, minWidth: 60 }}
                          />
                        </div>
                        
                        {showNicheDropdown && (
                          <div style={{
                            position: 'absolute', top: '100%', left: 0, right: 0,
                            background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
                            borderRadius: 'var(--r-md)', zIndex: 100, maxHeight: 180, overflowY: 'auto',
                            marginTop: 4, boxShadow: 'var(--shadow-drop)'
                          }}
                          onMouseLeave={() => setShowNicheDropdown(false)}
                          >
                            {categories.map(cat => (
                              <div
                                key={`sel-${cat}`}
                                onClick={() => setCategories(categories.filter(c => c !== cat))}
                                style={{ padding: '8px 12px', cursor: 'pointer', fontSize: '13px', color: 'var(--text-1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(192, 132, 252, 0.05)' }}
                                onMouseEnter={e => e.currentTarget.style.background = 'rgba(192, 132, 252, 0.1)'}
                                onMouseLeave={e => e.currentTarget.style.background = 'rgba(192, 132, 252, 0.05)'}
                              >
                                {cat}
                                <span style={{ color: 'var(--text-3)', fontSize: '14px' }}>×</span>
                              </div>
                            ))}
                            {(NICHES || []).filter(c => c.toLowerCase().includes(nicheSearchQuery.toLowerCase()) && !categories.includes(c)).map(c => (
                              <div
                                key={c}
                                onClick={() => {
                                  setCategories([...categories, c]);
                                  setNicheSearchQuery('');
                                  setShowNicheDropdown(false);
                                }}
                                style={{ padding: '8px 12px', cursor: 'pointer', fontSize: '13px', color: 'var(--text-2)' }}
                                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                              >
                                {c}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Country Dropdown */}
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={sectionLabelStyle}>Country</span>
                    <select value={country} onChange={e => setCountry(e.target.value)} style={selectStyle}>
                      {COUNTRIES.map(c => <option key={c.code} value={c.code}>{c.name}</option>)}
                    </select>
                  </div>

                  {/* Region Dropdown */}
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={sectionLabelStyle}>Region / State</span>
                    <select value={region} onChange={e => setRegion(e.target.value)} style={selectStyle}>
                      {(REGIONS[country] || []).map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </div>
              </div>

              {/* Core Selector Controls - ROW 2: Locations / Target Service / Lead Target */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px 20px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', position: 'relative' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={sectionLabelStyle}>* Locations</span>
                      <div onClick={() => setCustomLocation(!customLocation)} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '11px', color: 'var(--text-3)', cursor: 'pointer' }}>
                        <div style={{ width: 28, height: 16, background: customLocation ? 'var(--pink)' : 'var(--bg-elevated)', borderRadius: 10, position: 'relative', transition: '0.2s', border: '1px solid var(--border-subtle)' }}>
                          <div style={{ position: 'absolute', top: 1, left: customLocation ? 13 : 1, width: 12, height: 12, background: '#fff', borderRadius: '50%', transition: '0.2s' }} />
                        </div>
                        Custom Locations
                      </div>
                    </div>

                    {customLocation ? (
                      <input 
                        type="text"
                        value={customLocationValue}
                        onChange={e => setCustomLocationValue(e.target.value)}
                        style={{ ...inputStyle, width: '100%', borderColor: validationErrors.location ? 'var(--pink)' : 'var(--border-subtle)' }}
                      />
                    ) : (
                      <div style={{ position: 'relative' }}>
                        <div style={{ display: 'flex', flexWrap: 'nowrap', overflow: 'hidden', gap: 6, background: 'var(--bg-input)', border: `1px solid ${validationErrors.location ? 'var(--pink)' : 'var(--border-subtle)'}`, borderRadius: 'var(--r-md)', padding: '6px 8px', minHeight: 38, alignItems: 'center' }}>
                          {locations.slice(0, 2).map(loc => (
                            <span key={loc} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(192, 132, 252, 0.2)', backdropFilter: 'blur(4px)', border: '1px solid rgba(192, 132, 252, 0.4)', borderRadius: 4, padding: '2px 6px', fontSize: '12px', color: 'var(--text-1)', whiteSpace: 'nowrap' }}>
                              {loc}
                              <button onClick={() => setLocations(locations.filter(l => l !== loc))} style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', padding: 0, fontSize: '14px', lineHeight: 1 }}>×</button>
                            </span>
                          ))}
                          {locations.length > 2 && (
                            <span onClick={() => setShowCityDropdown(true)} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(192, 132, 252, 0.2)', backdropFilter: 'blur(4px)', border: '1px solid rgba(192, 132, 252, 0.4)', borderRadius: 4, padding: '2px 6px', fontSize: '12px', color: 'var(--text-1)', cursor: 'pointer', whiteSpace: 'nowrap' }}>
                              +{locations.length - 2}
                            </span>
                          )}
                          <input 
                            type="text" 
                            value={citySearchQuery}
                            onChange={e => {
                              setCitySearchQuery(e.target.value);
                              setShowCityDropdown(true);
                            }}
                            onFocus={() => setShowCityDropdown(true)}
                            style={{ background: 'transparent', border: 'none', color: 'var(--text-1)', fontSize: '13px', outline: 'none', flex: 1, minWidth: 60 }}
                          />
                        </div>
                        
                        {showCityDropdown && (
                          <div style={{
                            position: 'absolute', top: '100%', left: 0, right: 0,
                            background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
                            borderRadius: 'var(--r-md)', zIndex: 100, maxHeight: 180, overflowY: 'auto',
                            marginTop: 4, boxShadow: 'var(--shadow-drop)'
                          }}
                          onMouseLeave={() => setShowCityDropdown(false)}
                          >
                            {locations.map(loc => (
                              <div
                                key={`sel-${loc}`}
                                onClick={() => setLocations(locations.filter(l => l !== loc))}
                                style={{ padding: '8px 12px', cursor: 'pointer', fontSize: '13px', color: 'var(--text-1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(192, 132, 252, 0.05)' }}
                                onMouseEnter={e => e.currentTarget.style.background = 'rgba(192, 132, 252, 0.1)'}
                                onMouseLeave={e => e.currentTarget.style.background = 'rgba(192, 132, 252, 0.05)'}
                              >
                                {loc}
                                <span style={{ color: 'var(--text-3)', fontSize: '14px' }}>×</span>
                              </div>
                            ))}
                            {(REGION_CITIES[region] || []).filter(c => c.toLowerCase().includes(citySearchQuery.toLowerCase()) && !locations.includes(c)).map(c => (
                              <div
                                key={c}
                                onClick={() => {
                                  setLocations([...locations, c]);
                                  setCitySearchQuery('');
                                  setShowCityDropdown(false);
                                }}
                                style={{ padding: '8px 12px', cursor: 'pointer', fontSize: '13px', color: 'var(--text-2)' }}
                                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                              >
                                {c}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                    
                    {!customLocation && (
                      <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: 4 }}>
                        Try: {({ US: ['New York City', 'Los Angeles', 'Chicago'], UK: ['London', 'Manchester', 'Birmingham'], CA: ['Toronto', 'Vancouver', 'Montreal'], AU: ['Sydney', 'Melbourne', 'Brisbane'], IN: ['Mumbai', 'Delhi', 'Bangalore'] }[country] || ['London', 'Manchester', 'Birmingham']).map((cVal, idx, arr) => (
                          <span key={cVal}>
                            <button 
                              onClick={() => {
                                if (!locations.includes(cVal)) {
                                  setLocations([...locations, cVal]);
                                }
                              }} 
                              style={{ background: 'none', border: 'none', color: 'var(--text-3)', textDecoration: 'underline', cursor: 'pointer', padding: 0 }}
                            >
                              {cVal}
                            </button>
                            {idx < arr.length - 1 && ' · '}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Service Dropdown */}
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={sectionLabelStyle}>Target Service</span>
                    <select value={service} onChange={e => setService(e.target.value)} style={selectStyle}>
                      {SERVICES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
                    </select>
                  </div>

                  {/* Lead Count */}
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={sectionLabelStyle}>Lead Target</span>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '11px', color: 'var(--text-3)', cursor: 'pointer' }}>
                        <input 
                          type="checkbox" 
                          checked={allAvailable} 
                          onChange={e => setAllAvailable(e.target.checked)} 
                          style={{ accentColor: 'var(--pink)' }}
                        />
                        All Available
                      </label>
                    </div>

                    {!allAvailable && count === 'custom' ? (
                      <div style={{ display: 'flex', gap: 6 }}>
                        <input 
                          type="number"
                          placeholder="Limit (1-10000)"
                          value={customCount}
                          onChange={e => setCustomCount(e.target.value)}
                          style={{ ...inputStyle, width: '100%' }}
                        />
                        <button 
                          onClick={() => setCount('100')} 
                          style={{ background: 'none', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-md)', color: 'var(--text-3)', padding: '0 10px', fontSize: '11px', cursor: 'pointer' }}
                        >
                          Reset
                        </button>
                      </div>
                    ) : (
                      <select 
                        value={count} 
                        onChange={e => setCount(e.target.value)} 
                        disabled={allAvailable}
                        style={{ ...selectStyle, opacity: allAvailable ? 0.5 : 1 }}
                      >
                        <option value="10">10 leads</option>
                        <option value="25">25 leads</option>
                        <option value="50">50 leads</option>
                        <option value="100">100 leads</option>
                        <option value="200">200 leads</option>
                        <option value="500">500 leads</option>
                        <option value="custom">Custom target...</option>
                      </select>
                    )}
                  </div>
              </div>

              {/* Collapsible Advanced Tuning Panel */}
              <div>
                <button
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8, background: 'none', border: 'none',
                    color: 'var(--text-2)', fontSize: '13px', fontWeight: 600, cursor: 'pointer', padding: '6px 0', outline: 'none'
                  }}
                >
                  <span style={{ color: 'var(--pink)', transition: 'transform 0.2s', transform: showAdvanced ? 'rotate(90deg)' : 'rotate(0deg)', display: 'inline-block' }}>▶</span>
                  Advanced Tuning & Enrichment Options
                </button>

                {showAdvanced && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20, marginTop: 14, padding: '16px', background: 'var(--bg-nav)', borderRadius: 'var(--r-md)', border: '1px solid var(--border-faint)' }}>
                    
                    {/* Tuning parameters */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.05em' }}>Scraper tuning</div>
                      
                      {/* Duplicate handling */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>Deduplication Rules</span>
                        <select value={duplicateHandling} onChange={e => setDuplicateHandling(e.target.value as any)} style={{ ...selectStyle, height: 32 }}>
                          <option value="remove">Remove duplicates (Default)</option>
                          <option value="quality">Prefer highest quality record</option>
                          <option value="keep">Keep all duplicates</option>
                        </select>
                      </div>

                      {/* Minimum Lead Quality */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <span style={{ fontSize: '11px', color: 'var(--text-3)' }}>Minimum Quality Score</span>
                        <select value={qualityFilter} onChange={e => setQualityFilter(e.target.value as any)} style={{ ...selectStyle, height: 32 }}>
                          <option value="any">Any lead quality</option>
                          <option value="good">Good conversion probability</option>
                          <option value="high">High conversion probability</option>
                          <option value="very_high">Verify high quality score</option>
                        </select>
                      </div>

                      {/* Exact match checkbox & related expansion */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
                        <label style={checkboxLabelStyle}>
                          <input 
                            type="checkbox" 
                            checked={exactMatch} 
                            onChange={e => setExactMatch(e.target.checked)}
                            style={{ accentColor: 'var(--pink)' }}
                          />
                          Exact category matching
                        </label>
                        <label style={checkboxLabelStyle}>
                          <input 
                            type="checkbox" 
                            checked={relatedCategories} 
                            onChange={e => setRelatedCategories(e.target.checked)}
                            style={{ accentColor: 'var(--pink)' }}
                          />
                          Category expansion (related)
                        </label>
                      </div>
                    </div>

                    {/* Advanced Enrichment checkboxes */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.05em' }}>Advanced Enrichment</div>
                      
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <label style={checkboxLabelStyle}>
                          <input 
                            type="checkbox" 
                            checked={enrichmentOptions.email} 
                            onChange={e => setEnrichmentOptions({ ...enrichmentOptions, email: e.target.checked })}
                            style={{ accentColor: 'var(--pink)' }}
                          />
                          Verify Business Emails
                          {(service === 'website_dev' || service === 'seo') && <span style={{ fontSize: '9px', color: 'var(--pink-light)', background: 'rgba(236,72,153,0.1)', padding: '1px 5px', borderRadius: 4 }}>Rec.</span>}
                        </label>
                        <label style={checkboxLabelStyle}>
                          <input 
                            type="checkbox" 
                            checked={enrichmentOptions.phone} 
                            onChange={e => setEnrichmentOptions({ ...enrichmentOptions, phone: e.target.checked })}
                            style={{ accentColor: 'var(--pink)' }}
                          />
                          Validate Contacts Phone
                          {service === 'website_dev' && <span style={{ fontSize: '9px', color: 'var(--pink-light)', background: 'rgba(236,72,153,0.1)', padding: '1px 5px', borderRadius: 4 }}>Rec.</span>}
                        </label>
                        <label style={checkboxLabelStyle}>
                          <input 
                            type="checkbox" 
                            checked={enrichmentOptions.website} 
                            onChange={e => setEnrichmentOptions({ ...enrichmentOptions, website: e.target.checked })}
                            style={{ accentColor: 'var(--pink)' }}
                          />
                          Analyze Domain Presence
                          {service === 'seo' && <span style={{ fontSize: '9px', color: 'var(--pink-light)', background: 'rgba(236,72,153,0.1)', padding: '1px 5px', borderRadius: 4 }}>Rec.</span>}
                        </label>
                        <label style={checkboxLabelStyle}>
                          <input 
                            type="checkbox" 
                            checked={enrichmentOptions.social} 
                            onChange={e => setEnrichmentOptions({ ...enrichmentOptions, social: e.target.checked })}
                            style={{ accentColor: 'var(--pink)' }}
                          />
                          Extract Social Links
                          {(service === 'smma' || service === 'social_media') && <span style={{ fontSize: '9px', color: 'var(--pink-light)', background: 'rgba(236,72,153,0.1)', padding: '1px 5px', borderRadius: 4 }}>Rec.</span>}
                        </label>
                        <label style={checkboxLabelStyle}>
                          <input 
                            type="checkbox" 
                            checked={enrichmentOptions.details} 
                            onChange={e => setEnrichmentOptions({ ...enrichmentOptions, details: e.target.checked })}
                            style={{ accentColor: 'var(--pink)' }}
                          />
                          Audit Marketing signals
                          {service === 'social_media' && <span style={{ fontSize: '9px', color: 'var(--pink-light)', background: 'rgba(236,72,153,0.1)', padding: '1px 5px', borderRadius: 4 }}>Rec.</span>}
                        </label>
                      </div>
                    </div>

                    {/* Sources Selection */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.05em' }}>Connected Sources</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <label style={checkboxLabelStyle}>
                          <input 
                            type="checkbox" 
                            checked={selectedSources.includes('google_maps')} 
                            onChange={e => {
                              if (e.target.checked) {
                                setSelectedSources([...selectedSources, 'google_maps']);
                              } else {
                                setSelectedSources(selectedSources.filter(s => s !== 'google_maps'));
                              }
                            }}
                            style={{ accentColor: 'var(--pink)' }} 
                          />
                          Google Maps API
                        </label>
                        <label style={checkboxLabelStyle}>
                          <input 
                            type="checkbox" 
                            checked={selectedSources.includes('osm_overpass')} 
                            onChange={e => {
                              if (e.target.checked) {
                                setSelectedSources([...selectedSources, 'osm_overpass']);
                              } else {
                                setSelectedSources(selectedSources.filter(s => s !== 'osm_overpass'));
                              }
                            }}
                            style={{ accentColor: 'var(--pink)' }} 
                          />
                          OpenStreetMap Overpass
                        </label>
                        <label style={checkboxLabelStyle}>
                          <input 
                            type="checkbox" 
                            checked={selectedSources.includes('yelp')} 
                            onChange={e => {
                              if (e.target.checked) {
                                setSelectedSources([...selectedSources, 'yelp']);
                              } else {
                                setSelectedSources(selectedSources.filter(s => s !== 'yelp'));
                              }
                            }}
                            style={{ accentColor: 'var(--pink)' }} 
                          />
                          Yelp Connector
                        </label>
                      </div>
                    </div>

                  </div>
                )}
              </div>

              {/* Validation errors */}
              {Object.keys(validationErrors).length > 0 && (
                <div style={{ padding: '8px 12px', background: 'rgba(236,72,153,0.1)', border: '1px solid var(--pink)', borderRadius: 'var(--r-md)', color: 'var(--pink-light)', fontSize: '12px' }}>
                  {Object.values(validationErrors).map((errMsg, i) => <div key={i}>• {errMsg}</div>)}
                </div>
              )}

              {/* Search preview card */}
              <div style={{ background: 'rgba(200,9,171,0.03)', border: '1px dashed var(--border-pink)', borderRadius: 'var(--r-md)', padding: '12px 16px', fontSize: '12px', color: 'var(--text-2)' }}>
                <strong>Configuration Summary:</strong> Target{' '}
                <span style={{ color: 'var(--pink-light)', fontWeight: 600 }}>{allAvailable ? 'all available' : (count === 'custom' ? customCount : count)} leads</span> from{' '}
                <span style={{ color: 'var(--pink-light)', fontWeight: 600 }}>
                  {selectedSources.length === 0
                    ? 'no source'
                    : selectedSources.map(s =>
                        s === 'google_maps' ? 'Google Maps'
                        : s === 'osm_overpass' ? 'OpenStreetMap'
                        : s === 'yelp' ? 'Yelp'
                        : s
                      ).join(' + ')}
                </span> for{' '}
                <span style={{ color: 'var(--pink-light)', fontWeight: 600 }}>{plainQuery ? `"${plainQueryValue || 'empty'}"` : categories.join(', ') || niche}</span> in{' '}
                <span style={{ color: 'var(--pink-light)', fontWeight: 600 }}>
                  {customLocation ? customLocationValue : (locations.length > 0 ? locations.join(', ') : (city || 'London'))}
                </span>{' '}
                ({COUNTRIES.find(c => c.code === country)?.name || country}).
              </div>

              {/* Buttons row */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, alignItems: 'center' }}>
                {showResetConfirm ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(236,72,153,0.1)', padding: '6px 12px', borderRadius: 'var(--r-md)' }}>
                    <span style={{ fontSize: '12px', color: 'var(--pink-light)' }}>Reset configuration?</span>
                    <button onClick={performReset} className="btn btn-pink btn-sm" style={{ padding: '4px 10px', fontSize: '11px' }}>Yes, Reset</button>
                    <button onClick={() => setShowResetConfirm(false)} className="btn btn-ghost btn-sm" style={{ padding: '4px 10px', fontSize: '11px', color: 'var(--text-3)' }}>Cancel</button>
                  </div>
                ) : (
                  <button onClick={handleResetClick} className="btn btn-ghost btn-sm" style={{ height: 38, padding: '0 16px', fontSize: '12px', color: 'var(--text-3)', display: 'flex', alignItems: 'center' }}>
                    Reset Options
                  </button>
                )}
                
                <button onClick={handleStartScrape} disabled={creatingJob} className="btn btn-pink" style={{ height: 38, padding: '0 24px', fontWeight: 600, display: 'flex', alignItems: 'center' }}>
                  {creatingJob ? 'Starting...' : 'Start Scrape'}
                </button>
              </div>

            </div>
          ) : (
            /* ==========================================
               2. ACTIVE SCRAPING PROGRESS VIEW
               ========================================== */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-1)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {scrapeStatus === 'running' && <span style={{color: 'var(--pink)'}}>●</span>}
                    {scrapeStatus === 'stopped_saved' && <span style={{color: 'var(--text-3)'}}>Ⅱ</span>}
                    {scrapeStatus === 'cancelled' && <span style={{color: 'var(--text-3)'}}>■</span>}
                    {scrapeStatus === 'cancelling' && <span style={{color: 'var(--text-3)'}}>■</span>}
                    {(scrapeStatus === 'completed' || scrapeStatus === 'partial') && <span style={{color: 'var(--pink)'}}>✓</span>}
                    {scrapeStatus === 'failed' && <span style={{color: 'var(--pink)'}}>!</span>}
                    
                    {scrapeStatus === 'running' && `Scraping "${plainQuery ? plainQueryValue : categories.join(', ') || niche}" leads...`}
                    {scrapeStatus === 'stopped_saved' && 'Scrape Paused'}
                    {scrapeStatus === 'cancelling' && 'Safely halting operations...'}
                    {scrapeStatus === 'cancelled' && 'Scrape Stopped'}
                    {scrapeStatus === 'completed' && 'Scrape Complete'}
                    {scrapeStatus === 'partial' && 'Partial Scrape Complete'}
                    {scrapeStatus === 'failed' && 'Scraper Connection Failed'}
                  </span>
                </div>
              </div>

              {/* ETA */}
              <div style={{ fontSize: '13px', color: 'var(--text-3)' }}>
                Target: <strong style={{ color: 'var(--text-1)' }}>{allAvailable ? 'All Available' : count} leads</strong>
                {scrapeStatus === 'running' && (remainingTime > 0 ? ` · ~${remainingTime > 60 ? `${Math.floor(remainingTime / 60)}m ${remainingTime % 60}s` : `${remainingTime}s`} remaining` : ' · Estimating...')}
              </div>
              
              {/* Progress text */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-2)', marginTop: 8 }}>
                <span>Progress:</span>
                <span>{scrapedCount} / {allAvailable ? 'All Available' : count} raw leads {allAvailable ? '' : `(${Math.floor(progress)}% complete)`}</span>
              </div>

              {/* Progress bar */}
              <div style={{ height: 6, borderRadius: 3, background: 'var(--bg-input)', overflow: 'hidden' }}>
                <div style={{ 
                  width: `${scrapeStatus === 'failed' ? 100 : progress}%`, 
                  height: '100%', 
                  background: 'var(--pink)', 
                  transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)' 
                }} />
              </div>

              {/* Status Box */}
              {scrapeStatus === 'running' && (
                <div style={{ padding: '10px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-md)', fontSize: '12px', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'monospace' }}>
                  <span style={{color: 'var(--text-3)'}}>●</span> {microStatus}
                </div>
              )}
              {scrapeStatus === 'stopped_saved' && (
                <div style={{ padding: '10px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-md)', fontSize: '12px', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'monospace' }}>
                  {scrapedCount} leads saved so far
                </div>
              )}
              {scrapeStatus === 'cancelled' && (
                <div style={{ padding: '10px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-md)', fontSize: '12px', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'monospace' }}>
                  {scrapedCount} raw leads saved
                </div>
              )}

              {/* Real statistics indicators */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 16 }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 4 }}>Fetched</div>
                  <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-1)' }}>{scrapeStats.discovered || 0}</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 4 }}>Saved</div>
                  <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-1)' }}>{scrapeStats.saved || 0}</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 4 }}>Failed</div>
                  <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-1)' }}>{scrapeStats.failed || 0}</div>
                </div>
              </div>

              {/* Error messages */}
              {scrapeStatus === 'failed' && scrapeError && (
                <div style={{ fontSize: '12px', color: 'var(--pink)', marginTop: 4, background: 'rgba(236,72,153,0.05)', padding: '8px 12px', borderRadius: 'var(--r-md)', border: '1px solid var(--pink)' }}>
                  Error: {scrapeError}
                </div>
              )}

              {/* Controls buttons row */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginTop: 16, padding: '12px 16px', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-md)' }}>
                
                {/* Left side actions */}
                <div style={{ display: 'flex', gap: 8 }}>
                  {scrapeStatus === 'running' && (
                    <>
                      <button 
                        onClick={handleStopScrape} 
                        className="btn btn-outline btn-sm" 
                        style={{ padding: '6px 14px', fontSize: '12px', color: 'var(--text-1)', borderColor: 'var(--border-subtle)' }}
                      >
                        ⏸ Pause
                      </button>
                      <button 
                        onClick={handleCancelScrape}
                        className="btn btn-outline btn-sm" 
                        style={{ padding: '6px 14px', fontSize: '12px', color: 'var(--text-1)', borderColor: 'var(--border-subtle)' }}
                      >
                        ■ Stop
                      </button>
                      <button 
                        disabled
                        className="btn btn-outline btn-sm" 
                        style={{ padding: '6px 14px', fontSize: '12px', color: 'var(--text-1)', borderColor: 'var(--border-subtle)', opacity: 0.5, cursor: 'not-allowed' }}
                      >
                        Save
                      </button>
                    </>
                  )}

                  {(scrapeStatus === 'stopped_saved' || scrapeStatus === 'cancelled') && (
                    <>
                      <button 
                        onClick={handleResumeScrape} 
                        className="btn btn-outline btn-sm" 
                        style={{ padding: '6px 14px', fontSize: '12px', color: 'var(--text-1)', borderColor: 'var(--border-subtle)' }}
                      >
                        ▶ Resume
                      </button>
                      <button 
                        onClick={() => {
                          setSaveSuccess(true);
                          setTimeout(() => setSaveSuccess(false), 2000);
                        }} 
                        className="btn btn-outline btn-sm" 
                        style={{ padding: '6px 14px', fontSize: '12px', color: 'var(--text-1)', borderColor: 'var(--border-subtle)' }}
                      >
                        {saveSuccess ? 'Saved successfully' : 'Save'}
                      </button>
                    </>
                  )}

                  {(scrapeStatus === 'completed' || scrapeStatus === 'partial') && (
                    <button onClick={handleViewLeads} className="btn btn-outline btn-sm" style={{ padding: '6px 14px', fontSize: '12px', color: 'var(--text-1)', borderColor: 'var(--border-subtle)' }}>
                      View Raw Leads
                    </button>
                  )}

                  {scrapeStatus === 'failed' && (
                    <button 
                      onClick={() => { 
                        setRunning(false); 
                        setProgress(0); 
                        setScrapedCount(0); 
                        setScrapeStatus('idle'); 
                        setScrapeError(null); 
                        handleStartScrape(); 
                      }} 
                      className="btn btn-outline btn-sm" 
                      style={{ padding: '6px 14px', fontSize: '12px', color: 'var(--text-1)', borderColor: 'var(--border-subtle)' }}
                    >
                      Retry Scrape
                    </button>
                  )}
                </div>

                {/* Right side actions */}
                <div style={{ display: 'flex', gap: 8 }}>
                  {(scrapeStatus === 'running' || scrapeStatus === 'stopped_saved' || scrapeStatus === 'cancelled') && (
                    <button 
                      onClick={handleCancelScrape} 
                      className="btn btn-ghost btn-sm" 
                      style={{ padding: '6px 14px', fontSize: '12px', color: 'var(--text-2)' }}
                      onMouseEnter={e => e.currentTarget.style.color = 'var(--pink)'}
                      onMouseLeave={e => e.currentTarget.style.color = 'var(--text-2)'}
                    >
                      ✕ Cancel
                    </button>
                  )}

                  {['completed', 'partial', 'failed'].includes(scrapeStatus) && (
                    <button 
                      onClick={() => { 
                        setRunning(false); 
                        setProgress(0); 
                        setScrapedCount(0); 
                        setScrapeStatus('idle'); 
                        setScrapeError(null); 
                      }} 
                      className="btn btn-ghost btn-sm" 
                      style={{ padding: '6px 14px', fontSize: '12px', color: 'var(--text-1)' }}
                    >
                      Run Another Scrape
                    </button>
                  )}
                </div>

              </div>

            </div>
          )}

        </div>
      </div>

      {/* ── Raw Lead Sheets section ── */}
      <div ref={tableRef} style={{ background:'var(--bg-surface)',border:'1px solid var(--border-faint)',borderRadius:'var(--r-2xl)',overflow:'hidden',marginBottom:14 }}>
        <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',padding:'16px 24px',borderBottom:'1px solid var(--border-faint)' }}>
          <span style={{ fontSize:'14px',fontWeight:700,color:'var(--text-1)' }}>Raw Lead Sheets</span>
          
          {segregating ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: '12px', color: 'var(--text-3)' }}>
                Segregating leads... {segregationProgress}/{segregationTotal}
              </span>
              <div style={{ width: 80, height: 6, borderRadius: 3, background: 'var(--bg-input)', overflow: 'hidden' }}>
                <div style={{ width: `${(segregationProgress / segregationTotal) * 100}%`, height: '100%', background: 'var(--pink)' }} />
              </div>
            </div>
          ) : (
            <button 
              onClick={handleSegregate} 
              disabled={!selectedRawId} 
              className="btn btn-pink" 
              style={{ height:34, padding:'0 16px', opacity:!selectedRawId ? 0.5 : 1 }}
            >
              Segregate
            </button>
          )}
        </div>

        <div style={{ overflowX:'auto' }}>
          <table>
            <thead>
              <tr style={{ borderBottom:'1px solid var(--border-faint)' }}>
                {['Lead ID', 'Lead Name', 'Country & Region', 'Niche', 'Service', 'Total Leads', 'Date'].map(c => (
                  <th key={c} style={{ padding:'10px 18px',fontSize:'10px',fontWeight:600,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:'.07em',textAlign:'left',whiteSpace:'nowrap' }}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rawSheets.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding:'56px',textAlign:'center',color:'var(--text-3)',fontSize:'14px' }}>
                    No raw lead sheets available. Run a scrape above to create one.
                  </td>
                </tr>
              ) : rawSheets.map((sheet) => {
                const isSelected = selectedRawId === sheet.id;
                const isHighlighted = highlightedId === sheet.id;
                
                let rowBg = 'transparent';
                if (isSelected) rowBg = 'rgba(236,72,153,0.12)';
                else if (isHighlighted) rowBg = 'var(--pink-dim)';

                const countryName = COUNTRIES.find(c => c.code === sheet.country)?.name || sheet.country || 'United Kingdom';
                const regionName = sheet.region || 'London';
                const countryRegionStr = `${regionName}, ${countryName}`;

                return (
                  <tr key={sheet.id}
                    onClick={() => {
                      setSelectedRawId(isSelected ? null : sheet.id);
                      setHighlightedId(null); // clear View Leads highlight
                    }}
                    onDoubleClick={() => setOpenRawSheet(sheet)}
                    title="Double click to preview raw leads"
                    style={{ 
                      borderBottom:'1px solid var(--border-faint)',
                      cursor:'pointer',
                      background: rowBg,
                      transition:'background var(--ease)' 
                    }}
                    onMouseEnter={e => { if(!isSelected && !isHighlighted) e.currentTarget.style.background='var(--bg-hover)'; }}
                    onMouseLeave={e => { if(!isSelected && !isHighlighted) e.currentTarget.style.background='transparent'; }}
                  >
                    {/* Lead ID */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',fontFamily:'monospace',fontSize:'11px',color:'var(--text-3)' }}>
                      {sheet.sheetId}
                    </td>
                    {/* Business Name */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',fontWeight:600,color:'var(--text-1)' }}>
                      {sheet.name}
                    </td>
                    {/* Country & Region */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',color:'var(--text-2)' }}>
                      {countryRegionStr}
                    </td>
                    {/* Niche */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',color:'var(--text-2)' }}>
                      {(sheet.niches || [(sheet as any).niche || 'General']).join(', ')}
                    </td>
                    {/* Service */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',color:'var(--text-2)' }}>
                      {SERVICE_LABELS[sheet.service] || sheet.service}
                    </td>
                    {/* Total Leads */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',color:'var(--text-2)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span>{(sheet as any).leads_scraped || 0} leads</span>
                        {/* Show "Segregated" pill when the job is COMPLETED and status implies segregation done */}
                        {(sheet as any).status === 'COMPLETED' && (sheet as any).leads_scraped > 0 && (
                          <span style={{
                            fontSize: '9px', fontWeight: 700, padding: '2px 6px',
                            borderRadius: 4, background: 'rgba(34,197,94,0.15)',
                            color: '#4ade80', border: '1px solid rgba(34,197,94,0.3)',
                            textTransform: 'uppercase', letterSpacing: '.05em'
                          }}>
                            Segregated
                          </span>
                        )}
                      </div>
                    </td>
                    {/* Date */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',color:'var(--text-3)',fontSize:'11px',whiteSpace:'nowrap' }}>
                      {formatDate(sheet.createdAt)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── One-Time Rename Modal ── */}
      {showRenameModal && (
        <>
          <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.75)',backdropFilter:'blur(4px)',zIndex:200 }} />
          <div style={{
            position:'fixed', top:'50%', left:'50%', transform:'translate(-50%,-50%)',
            width:'400px', background:'var(--bg-elevated)', border:'1px solid var(--border-subtle)',
            borderRadius:'var(--r-xl)', zIndex:201, padding:'24px', boxShadow:'0 24px 60px rgba(0,0,0,.5)'
          }}>
            <h3 style={{ fontSize:'16px', fontWeight:700, color:'var(--text-1)', marginBottom:12 }}>Rename lead sheet</h3>
            <p style={{ fontSize:'12px', color:'var(--text-3)', marginBottom:16 }}>Choose a custom name or keep the default name for this collection.</p>
            
            <input 
              type="text" 
              value={renameInput}
              onChange={e => setRenameInput(e.target.value)}
              style={{
                width:'100%', background:'var(--bg-input)', border:'1px solid var(--border-subtle)',
                borderRadius:'var(--r-md)', padding:'10px 14px', color:'var(--text-1)',
                fontSize:'13px', outline:'none', marginBottom:20
              }}
              onFocus={e => e.currentTarget.style.borderColor = 'var(--border-pink)'}
              onBlur={e => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
            />

            <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
              <button onClick={() => handleSaveRename(false)} className="btn btn-ghost" style={{ padding:'8px 16px', fontSize:'12px' }}>
                Keep name
              </button>
              <button onClick={() => handleSaveRename(true)} className="btn btn-pink" style={{ padding:'8px 16px', fontSize:'12px', fontWeight:600 }}>
                Save name
              </button>
            </div>
          </div>
        </>
      )}

      {/* ── Raw Sheet Preview Modal ── */}
      {openRawSheet && (
        <>
          <div onClick={() => setOpenRawSheet(null)} style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.75)',backdropFilter:'blur(4px)',zIndex:100 }} />
          <div style={{ position:'fixed',top:'50%',left:'50%',transform:'translate(-50%,-50%)',width:'min(94vw,900px)',maxHeight:'80vh',background:'var(--bg-elevated)',border:'1px solid var(--border-subtle)',borderRadius:'var(--r-2xl)',zIndex:101,display:'flex',flexDirection:'column',overflow:'hidden',boxShadow:'0 40px 100px rgba(0,0,0,.65)' }}>
            {/* Header */}
            <div style={{ padding:'20px 24px',borderBottom:'1px solid var(--border-faint)',display:'flex',alignItems:'center',justifyContent:'space-between',flexShrink:0 }}>
              <div>
                <div style={{ display:'flex',alignItems:'center',gap:10,marginBottom:4 }}>
                  <span style={{ fontSize:'15px',fontWeight:700,color:'var(--text-1)' }}>{openRawSheet.name}</span>
                  <span className="pill" style={{ background:'var(--pink-dim)',color:'var(--pink-light)',fontSize:'10px' }}>RAW LEAD SHEET</span>
                  <span style={{ fontSize:'11px',color:'var(--text-3)',fontFamily:'monospace' }}>{openRawSheet.sheetId}</span>
                </div>
                <div style={{ fontSize:'12px',color:'var(--text-3)' }}>Service: {SERVICE_LABELS[openRawSheet.service as ServiceType]}</div>
              </div>
              <button onClick={() => setOpenRawSheet(null)} className="btn btn-ghost btn-sm" style={{ padding: 6 }}>
                ✕
              </button>
            </div>
            {/* Body */}
            <div style={{ flex:1,overflowY:'auto',padding:'24px' }}>
              {loadingPreview ? (
                <div style={{ padding:'40px',textAlign:'center',color:'var(--text-3)' }}>Loading leads...</div>
              ) : previewLeads.length === 0 ? (
                <div style={{ padding:'40px',textAlign:'center',color:'var(--text-3)' }}>No leads found in this raw sheet</div>
              ) : (
                <div style={{ overflowX:'auto' }}>
                  <table style={{ width:'100%',borderCollapse:'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom:'1px solid var(--border-faint)' }}>
                        {['Lead ID', 'Business Name', 'Location', 'Website', 'Phone'].map(col => (
                          <th key={col} style={{ padding:'8px 12px',fontSize:'10px',fontWeight:600,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:'.07em',textAlign:'left' }}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {previewLeads.map((l, idx) => (
                        <tr key={l.leadId} style={{ borderBottom:'1px solid var(--border-faint)' }}>
                          <td style={{ padding:'10px 12px',fontSize:'11px',fontFamily:'monospace',color:'var(--text-3)' }}>{`RAW-${idx + 1}`}</td>
                          <td style={{ padding:'10px 12px',fontWeight:600,color:'var(--text-1)' }}>{l.businessName}</td>
                          <td style={{ padding:'10px 12px',color:'var(--text-2)' }}>{l.location}</td>
                          <td style={{ padding:'10px 12px',color:'var(--text-2)',fontSize:'12px' }}>{l.websiteUrl || '—'}</td>
                          <td style={{ padding:'10px 12px',color:'var(--text-2)',fontSize:'12px' }}>{l.contactPhone || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}

    </div>
  );
}

const selectStyle = {
  background: 'var(--bg-input)',
  border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--r-md)',
  padding: '0 12px',
  height: 38,
  color: 'var(--text-2)',
  fontSize: '13px',
  outline: 'none',
  cursor: 'pointer'
};

const inputStyle = {
  background: 'var(--bg-input)',
  border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--r-md)',
  padding: '0 12px',
  height: 38,
  color: 'var(--text-1)',
  fontSize: '13px',
  outline: 'none',
  flex: 1,
  minWidth: '130px'
};

