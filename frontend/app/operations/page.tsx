'use client';
import { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';
import { LeadSheet, SERVICE_LABELS, ServiceType } from '../lib/data';
import { ThreeDotMenu } from '../components/ThreeDotMenu';

const I = {
  edit: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>,
  download: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
  trash: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3,6 5,6 21,6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>,
  preview: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>,
};

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
  'Alabama': ['Birmingham', 'Montgomery', 'Mobile', 'Huntsville', 'Tuscaloosa'],
  'Alaska': ['Anchorage', 'Fairbanks', 'Juneau', 'Sitka', 'Ketchikan'],
  'Arizona': ['Phoenix', 'Tucson', 'Mesa', 'Chandler', 'Scottsdale', 'Glendale', 'Gilbert', 'Tempe'],
  'Arkansas': ['Little Rock', 'Fort Smith', 'Fayetteville', 'Springdale', 'Jonesboro'],
  'California': ['Los Angeles', 'San Francisco', 'San Diego', 'San Jose', 'Sacramento', 'Fresno', 'Long Beach', 'Oakland', 'Bakersfield', 'Anaheim', 'Irvine'],
  'Colorado': ['Denver', 'Colorado Springs', 'Aurora', 'Fort Collins', 'Lakewood', 'Thornton', 'Arvada', 'Westminster', 'Pueblo', 'Boulder'],
  'Connecticut': ['Bridgeport', 'New Haven', 'Stamford', 'Hartford', 'Waterbury', 'Norwalk', 'Danbury'],
  'Delaware': ['Wilmington', 'Dover', 'Newark', 'Middletown', 'Smyrna'],
  'Florida': ['Miami', 'Orlando', 'Tampa', 'Jacksonville', 'Tallahassee', 'St. Petersburg', 'Hialeah', 'Fort Lauderdale', 'Cape Coral', 'Gainesville'],
  'Georgia': ['Atlanta', 'Augusta', 'Columbus', 'Macon', 'Savannah', 'Athens', 'Sandy Springs', 'Roswell'],
  'Hawaii': ['Honolulu', 'Hilo', 'Kailua', 'Kapolei', 'Kaneohe'],
  'Idaho': ['Boise', 'Meridian', 'Nampa', 'Idaho Falls', 'Caldwell', 'Pocatello'],
  'Illinois': ['Chicago', 'Aurora', 'Naperville', 'Joliet', 'Rockford', 'Springfield', 'Elgin', 'Peoria', 'Champaign'],
  'Indiana': ['Indianapolis', 'Fort Wayne', 'Evansville', 'South Bend', 'Carmel', 'Fishers', 'Bloomington'],
  'Iowa': ['Des Moines', 'Cedar Rapids', 'Davenport', 'Sioux City', 'Iowa City', 'Waterloo', 'Ames'],
  'Kansas': ['Wichita', 'Overland Park', 'Kansas City', 'Olathe', 'Topeka', 'Lawrence'],
  'Kentucky': ['Louisville', 'Lexington', 'Bowling Green', 'Owensboro', 'Covington'],
  'Louisiana': ['New Orleans', 'Baton Rouge', 'Shreveport', 'Lafayette', 'Lake Charles'],
  'Maine': ['Portland', 'Lewiston', 'Bangor', 'South Portland', 'Auburn'],
  'Maryland': ['Baltimore', 'Frederick', 'Rockville', 'Gaithersburg', 'Bowie', 'Annapolis'],
  'Massachusetts': ['Boston', 'Worcester', 'Springfield', 'Cambridge', 'Lowell', 'Brockton', 'Quincy', 'Lynn'],
  'Michigan': ['Detroit', 'Grand Rapids', 'Warren', 'Sterling Heights', 'Ann Arbor', 'Lansing', 'Flint'],
  'Minnesota': ['Minneapolis', 'St. Paul', 'Rochester', 'Bloomington', 'Duluth', 'Brooklyn Park'],
  'Mississippi': ['Jackson', 'Gulfport', 'Southaven', 'Biloxi', 'Hattiesburg'],
  'Missouri': ['Kansas City', 'St. Louis', 'Springfield', 'Columbia', 'Independence'],
  'Montana': ['Billings', 'Missoula', 'Great Falls', 'Bozeman', 'Helena'],
  'Nebraska': ['Omaha', 'Lincoln', 'Bellevue', 'Grand Island', 'Kearney'],
  'Nevada': ['Las Vegas', 'Henderson', 'Reno', 'North Las Vegas', 'Sparks', 'Carson City'],
  'New Hampshire': ['Manchester', 'Nashua', 'Concord', 'Dover', 'Rochester'],
  'New Jersey': ['Newark', 'Jersey City', 'Paterson', 'Elizabeth', 'Edison', 'Woodbridge', 'Lakewood', 'Trenton'],
  'New Mexico': ['Albuquerque', 'Las Cruces', 'Rio Rancho', 'Santa Fe', 'Roswell'],
  'New York': ['New York City', 'Buffalo', 'Rochester', 'Syracuse', 'Albany', 'Yonkers', 'White Plains'],
  'North Carolina': ['Charlotte', 'Raleigh', 'Greensboro', 'Durham', 'Winston-Salem', 'Fayetteville', 'Cary', 'Wilmington'],
  'North Dakota': ['Fargo', 'Bismarck', 'Grand Forks', 'Minot', 'West Fargo'],
  'Ohio': ['Columbus', 'Cleveland', 'Cincinnati', 'Toledo', 'Akron', 'Dayton', 'Canton'],
  'Oklahoma': ['Oklahoma City', 'Tulsa', 'Norman', 'Broken Arrow', 'Edmond', 'Lawton'],
  'Oregon': ['Portland', 'Salem', 'Eugene', 'Gresham', 'Hillsboro', 'Beaverton', 'Bend'],
  'Pennsylvania': ['Philadelphia', 'Pittsburgh', 'Allentown', 'Erie', 'Reading', 'Scranton', 'Lancaster', 'Harrisburg'],
  'Rhode Island': ['Providence', 'Warwick', 'Cranston', 'Pawtucket', 'East Providence'],
  'South Carolina': ['Charleston', 'Columbia', 'North Charleston', 'Mount Pleasant', 'Rock Hill', 'Greenville'],
  'South Dakota': ['Sioux Falls', 'Rapid City', 'Aberdeen', 'Brookings', 'Watertown'],
  'Tennessee': ['Nashville', 'Memphis', 'Knoxville', 'Chattanooga', 'Clarksville', 'Murfreesboro'],
  'Texas': ['Houston', 'San Antonio', 'Dallas', 'Austin', 'Fort Worth', 'El Paso', 'Arlington', 'Corpus Christi', 'Plano', 'Lubbock', 'Irving', 'Frisco'],
  'Utah': ['Salt Lake City', 'West Valley City', 'Provo', 'West Jordan', 'Orem', 'Sandy', 'Ogden'],
  'Vermont': ['Burlington', 'South Burlington', 'Rutland', 'Barre', 'Montpelier'],
  'Virginia': ['Virginia Beach', 'Norfolk', 'Chesapeake', 'Richmond', 'Newport News', 'Alexandria', 'Hampton', 'Roanoke'],
  'Washington': ['Seattle', 'Spokane', 'Tacoma', 'Vancouver', 'Bellevue', 'Kent', 'Everett', 'Renton'],
  'West Virginia': ['Charleston', 'Huntington', 'Morgantown', 'Parkersburg', 'Wheeling'],
  'Wisconsin': ['Milwaukee', 'Madison', 'Green Bay', 'Kenosha', 'Racine', 'Appleton'],
  'Wyoming': ['Cheyenne', 'Casper', 'Laramie', 'Gillette', 'Rock Springs'],
  // UK
  'England': ['London', 'Birmingham', 'Manchester', 'Leeds', 'Liverpool', 'Newcastle', 'Sheffield', 'Bristol', 'Leicester', 'Brighton', 'Coventry', 'Nottingham', 'Southampton', 'Oxford', 'Cambridge'],
  'Scotland': ['Edinburgh', 'Glasgow', 'Aberdeen', 'Dundee', 'Inverness', 'Perth', 'Stirling'],
  'Wales': ['Cardiff', 'Swansea', 'Newport', 'Wrexham', 'Barry'],
  'Northern Ireland': ['Belfast', 'Derry', 'Lisburn', 'Newry', 'Bangor'],
  // CA
  'Ontario': ['Toronto', 'Ottawa', 'Mississauga', 'Hamilton', 'Brampton', 'London', 'Markham', 'Vaughan', 'Kitchener', 'Windsor'],
  'Quebec': ['Montreal', 'Quebec City', 'Laval', 'Gatineau', 'Longueuil', 'Sherbrooke'],
  'British Columbia': ['Vancouver', 'Victoria', 'Burnaby', 'Surrey', 'Richmond', 'Kelowna', 'Abbotsford'],
  'Alberta': ['Calgary', 'Edmonton', 'Red Deer', 'Lethbridge', 'St. Albert'],
  'Nova Scotia': ['Halifax', 'Sydney', 'Dartmouth', 'Truro'],
  'Manitoba': ['Winnipeg', 'Brandon', 'Steinbach'],
  'Saskatchewan': ['Saskatoon', 'Regina', 'Prince Albert'],
  // AU
  'New South Wales': ['Sydney', 'Newcastle', 'Wollongong', 'Central Coast', 'Maitland'],
  'Victoria': ['Melbourne', 'Geelong', 'Ballarat', 'Bendigo', 'Shepparton'],
  'Queensland': ['Brisbane', 'Gold Coast', 'Sunshine Coast', 'Townsville', 'Cairns', 'Toowoomba'],
  'Western Australia': ['Perth', 'Mandurah', 'Bunbury', 'Geraldton'],
  'South Australia': ['Adelaide', 'Mount Gambier', 'Gawler'],
  'Tasmania': ['Hobart', 'Launceston', 'Devonport'],
  'Australian Capital Territory': ['Canberra'],
  'Northern Territory': ['Darwin', 'Alice Springs'],
  // IN
  'Maharashtra': ['Mumbai', 'Pune', 'Nagpur', 'Thane', 'Nashik', 'Aurangabad', 'Navi Mumbai', 'Solapur'],
  'Delhi': ['New Delhi', 'Dwarka', 'Rohini', 'South Delhi', 'East Delhi', 'North Delhi', 'Noida', 'Gurgaon'],
  'Karnataka': ['Bangalore', 'Mysore', 'Hubli', 'Mangalore', 'Belgaum', 'Davanagere'],
  'Tamil Nadu': ['Chennai', 'Coimbatore', 'Madurai', 'Tiruchirappalli', 'Salem', 'Tirunelveli'],
  'Telangana': ['Hyderabad', 'Warangal', 'Nizamabad', 'Karimnagar', 'Khammam'],
  'Gujarat': ['Ahmedabad', 'Surat', 'Vadodara', 'Rajkot', 'Bhavnagar', 'Jamnagar'],
  'Uttar Pradesh': ['Lucknow', 'Kanpur', 'Ghaziabad', 'Agra', 'Varanasi', 'Meerut', 'Noida', 'Prayagraj'],
  'West Bengal': ['Kolkata', 'Howrah', 'Durgapur', 'Asansol', 'Siliguri'],
  'Rajasthan': ['Jaipur', 'Jodhpur', 'Kota', 'Bikaner', 'Ajmer', 'Udaipur'],
  'Punjab': ['Ludhiana', 'Amritsar', 'Jalandhar', 'Patiala', 'Bathinda'],
  'Haryana': ['Gurgaon', 'Faridabad', 'Panipat', 'Ambala', 'Karnal'],
  'Kerala': ['Thiruvananthapuram', 'Kochi', 'Kozhikode', 'Thrissur', 'Kollam'],
  'Madhya Pradesh': ['Indore', 'Bhopal', 'Jabalpur', 'Gwalior', 'Ujjain'],
  'Bihar': ['Patna', 'Gaya', 'Bhagalpur', 'Muzaffarpur'],
  'Andhra Pradesh': ['Visakhapatnam', 'Vijayawada', 'Guntur', 'Nellore', 'Kurnool']
};

const COUNTRY_CITIES: Record<string, string[]> = {
  US: [
    'New York City', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia', 'San Antonio', 'San Diego',
    'Dallas', 'San Jose', 'Austin', 'Jacksonville', 'Fort Worth', 'Columbus', 'Charlotte', 'San Francisco',
    'Indianapolis', 'Seattle', 'Denver', 'Washington', 'Boston', 'El Paso', 'Nashville', 'Detroit', 'Oklahoma City',
    'Portland', 'Las Vegas', 'Memphis', 'Louisville', 'Baltimore', 'Milwaukee', 'Albuquerque', 'Tucson', 'Fresno',
    'Sacramento', 'Mesa', 'Kansas City', 'Atlanta', 'Omaha', 'Colorado Springs', 'Raleigh', 'Miami', 'Virginia Beach',
    'Oakland', 'Minneapolis', 'Tulsa', 'Arlington', 'Tampa', 'New Orleans', 'Wichita', 'Cleveland', 'Bakersfield'
  ],
  UK: [
    'London', 'Birmingham', 'Manchester', 'Leeds', 'Glasgow', 'Liverpool', 'Newcastle', 'Sheffield', 'Bristol',
    'Belfast', 'Edinburgh', 'Leicester', 'Brighton', 'Cardiff', 'Coventry', 'Nottingham', 'Hull', 'Plymouth',
    'Stoke-on-Trent', 'Derby', 'Southampton', 'Reading', 'Swansea', 'Aberdeen', 'Dundee', 'Oxford', 'Cambridge'
  ],
  CA: [
    'Toronto', 'Montreal', 'Vancouver', 'Calgary', 'Edmonton', 'Ottawa', 'Winnipeg', 'Quebec City', 'Hamilton',
    'Kitchener', 'London', 'Victoria', 'Halifax', 'Oshawa', 'Windsor', 'Saskatoon', 'Regina', 'St. John\'s', 'Kelowna', 'Barrie'
  ],
  AU: [
    'Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Adelaide', 'Gold Coast', 'Newcastle', 'Canberra', 'Sunshine Coast',
    'Wollongong', 'Geelong', 'Hobart', 'Townsville', 'Cairns', 'Darwin', 'Toowoomba', 'Ballarat', 'Bendigo'
  ],
  IN: [
    'Mumbai', 'Delhi', 'New Delhi', 'Bangalore', 'Hyderabad', 'Ahmedabad', 'Chennai', 'Kolkata', 'Surat', 'Pune',
    'Jaipur', 'Lucknow', 'Kanpur', 'Nagpur', 'Indore', 'Thane', 'Bhopal', 'Visakhapatnam', 'Patna', 'Vadodara',
    'Ghaziabad', 'Ludhiana', 'Agra', 'Nashik', 'Ranchi', 'Faridabad', 'Meerut', 'Rajkot', 'Varanasi', 'Noida', 'Gurgaon'
  ]
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


export default function OperationsPage() {
  const [niche, setNiche] = useState(NICHES[0]);
  const [country, setCountry] = useState('US');
  const [region, setRegion] = useState('');
  const [city, setCity] = useState('');
  const [service, setService] = useState('website_dev');
  const [count, setCount] = useState('100');
  const [selectedSources, setSelectedSources] = useState<string[]>(['google_maps', 'osm_overpass']);
  
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


  // Load presets/recents and URL query parameters on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedPresets = localStorage.getItem('lead_scraper_presets');
      if (savedPresets) setPresets(JSON.parse(savedPresets));
      const savedRecents = localStorage.getItem('lead_scraper_recent_searches');
      if (savedRecents) setRecentSearches(JSON.parse(savedRecents));

      const params = new URLSearchParams(window.location.search);
      const urlNiche = params.get('niche');
      const urlCity = params.get('city');
      if (urlNiche) {
        setNiche(urlNiche);
        setCategories([urlNiche]);
      }
      if (urlCity) {
        setCity(urlCity);
      }
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
  const [completionReason, setCompletionReason] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Workflow Sheets
  const [rawSheets, setRawSheets] = useState<LeadSheet[]>([]);
  const [selectedRawId, setSelectedRawId] = useState<string | null>(null);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [segregating, setSegregating] = useState(false);

  // In-Screen Delete Confirmation Modal State
  const [sheetToDelete, setSheetToDelete] = useState<any | null>(null);
  const [isDeletingSheet, setIsDeletingSheet] = useState(false);
  const [deleteSheetError, setDeleteSheetError] = useState<string | null>(null);

  // Dropdown click-outside refs & state
  const presetRef = useRef<HTMLDivElement>(null);
  const nicheRef = useRef<HTMLDivElement>(null);
  const cityRef = useRef<HTMLDivElement>(null);
  const countryRef = useRef<HTMLDivElement>(null);
  const regionRef = useRef<HTMLDivElement>(null);
  const serviceRef = useRef<HTMLDivElement>(null);

  const [showCountryDropdown, setShowCountryDropdown] = useState(false);
  const [showRegionDropdown, setShowRegionDropdown] = useState(false);
  const [regionSearchQuery, setRegionSearchQuery] = useState('');
  const [showServiceDropdown, setShowServiceDropdown] = useState(false);

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
  const [isRawFullScreen, setIsRawFullScreen] = useState<boolean>(false);
  const [previewLeads, setPreviewLeads] = useState<any[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Segregation progress state
  const [segregationProgress, setSegregationProgress] = useState(0);
  const [segregationTotal, setSegregationTotal] = useState(0);

  // Scroll target ref for View Leads
  const tableRef = useRef<HTMLDivElement>(null);

  // Click outside handler for custom dropdowns
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (presetRef.current && !presetRef.current.contains(target)) {
        setShowPresetDropdown(false);
      }
      if (nicheRef.current && !nicheRef.current.contains(target)) {
        setShowNicheDropdown(false);
      }
      if (cityRef.current && !cityRef.current.contains(target)) {
        setShowCityDropdown(false);
      }
      if (countryRef.current && !countryRef.current.contains(target)) {
        setShowCountryDropdown(false);
      }
      if (regionRef.current && !regionRef.current.contains(target)) {
        setShowRegionDropdown(false);
      }
      if (serviceRef.current && !serviceRef.current.contains(target)) {
        setShowServiceDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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

        // Set micro-status dynamically based on true backend stage & query
        if (prog.status === 'RUNNING' || prog.status === 'PENDING') {
          if (prog.current_source) {
            setMicroStatus(prog.current_source);
          } else if (prog.current_query) {
            setMicroStatus(`Querying directory for "${prog.current_query}"...`);
          } else {
            setMicroStatus(`Connecting to discovery providers for "${prog.niche || 'leads'}"...`);
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
        const currentCount = prog.leads_scraped || prog.discovered || 0;
        if (currentCount > 0 && elapsed > 1) {
          const speed = currentCount / elapsed; // items per second
          const remainingItems = Math.max(0, target - currentCount);
          setRemainingTime(Math.max(1, Math.ceil(remainingItems / speed)));
        } else if (prog.progress_percent && prog.progress_percent > 3 && elapsed > 1) {
          const totalEstimated = elapsed / (prog.progress_percent / 100);
          const remainingSecs = Math.max(1, Math.ceil(totalEstimated - elapsed));
          setRemainingTime(remainingSecs);
        } else {
          setRemainingTime(-1); // will show "Estimating..."
        }

        if (prog.status === 'COMPLETED' || prog.status === 'PARTIAL') {
          stopPolling();
          localStorage.removeItem('lead_system_active_scrape_run');
          setActiveJobId(null);
          setScrapeStatus(prog.status.toLowerCase() as any);
          setCompletionReason(prog.completion_reason || null);
          setRunning(false);
          setPaused(false);
          loadRawSheets();

          logScrapeHistory(jobId, prog.niche, prog.region, prog.requested, prog.leads_scraped, prog.status.toLowerCase());

          const msg = prog.status === 'COMPLETED' 
            ? (prog.completion_reason === 'REGION_EXHAUSTED'
                ? `${prog.leads_scraped} leads found. Region exhausted (no additional matching businesses).`
                : `${prog.leads_scraped} leads scraped successfully (Target Reached).`)
            : `${prog.leads_scraped} leads scraped. Some discovery provider requests failed.`;
          addNotification(msg, jobId);

          // Only show the rename modal ONCE per job (prevents duplicate popups from recovery
          // or multiple concurrent polling intervals)
          if (!shownRenameForRef.current.has(jobId)) {
            shownRenameForRef.current.add(jobId);
            const defaultName = `${prog.niche} - ${city || 'Capital'}, ${prog.region} (${COUNTRIES.find(c => c.code === country)?.name || country})`;
            setPendingRawSheet({
              id: jobId,
              sheetId: prog.sheetId || '0001',
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

  // Restore active running scrape on page refresh / mount
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const restoreActiveJob = async () => {
      let targetJobId: string | null = null;

      // 1. Check localStorage first
      const activeRunStr = localStorage.getItem('lead_system_active_scrape_run');
      if (activeRunStr) {
        try {
          const parsed = JSON.parse(activeRunStr);
          if (parsed && parsed.runId) {
            targetJobId = parsed.runId;
          }
        } catch {
          // ignore
        }
      }

      // 2. If found in localStorage, verify with backend
      if (targetJobId) {
        try {
          const prog = await api.getScrapeProgress(targetJobId);
          if (prog && (prog.status === 'RUNNING' || prog.status === 'PENDING')) {
            setActiveJobId(targetJobId);
            setRunning(true);
            setScrapeStatus('running');
            setProgress(prog.progress_percent || 0);
            setScrapedCount(prog.leads_scraped || 0);
            if (prog.niche) {
              setNiche(prog.niche);
              setCategories([prog.niche]);
            }
            if (prog.city || prog.state) {
              const loc = prog.city || prog.state;
              setCity(loc);
              setLocations([loc]);
            }
            if (prog.country) {
              const cMatch = COUNTRIES.find(c => c.name === prog.country || c.code === prog.country || (prog.country === 'GB' && c.code === 'UK'));
              if (cMatch) setCountry(cMatch.code);
            }
            if (prog.requested) {
              setCount(prog.requested.toString());
              if (!['10', '25', '50', '100', '200', '500'].includes(prog.requested.toString())) {
                setCount('custom');
                setCustomCount(prog.requested.toString());
              }
            }
            startPollingProgress(targetJobId);
            return;
          } else if (prog && (prog.status === 'COMPLETED' || prog.status === 'PARTIAL' || prog.status === 'STOPPED_SAVED')) {
            setScrapedCount(prog.leads_scraped || 0);
            setProgress(100);
            setScrapeStatus(prog.status.toLowerCase() as any);
            localStorage.removeItem('lead_system_active_scrape_run');
            loadRawSheets();
            return;
          } else {
            localStorage.removeItem('lead_system_active_scrape_run');
          }
        } catch {
          localStorage.removeItem('lead_system_active_scrape_run');
        }
      }

      // 3. Fallback: Check if any recent sheet in database is currently RUNNING
      try {
        const rawList = await api.getRawLeads();
        const now = new Date().getTime();
        const activeSheet = (rawList as any || []).find((s: any) => {
          if (s.status !== 'RUNNING' && s.status !== 'PENDING') return false;
          if (!s.created_at) return true;
          const jobTime = new Date(s.created_at).getTime();
          return (now - jobTime) < 12 * 60 * 60 * 1000; // Only auto-restore jobs less than 12h old
        });
        if (activeSheet && activeSheet.id) {
          setActiveJobId(activeSheet.id);
          setRunning(true);
          setScrapeStatus('running');
          setProgress(activeSheet.progress_percent || 0);
          setScrapedCount(activeSheet.leads_scraped || 0);
          if (activeSheet.niche) {
            setNiche(activeSheet.niche);
            setCategories([activeSheet.niche]);
          }
          if (activeSheet.city || activeSheet.state) {
            const loc = activeSheet.city || activeSheet.state;
            setCity(loc);
            setLocations([loc]);
          }
          if (activeSheet.country) {
            const cMatch = COUNTRIES.find(c => c.name === activeSheet.country || c.code === activeSheet.country || (activeSheet.country === 'GB' && c.code === 'UK'));
            if (cMatch) setCountry(cMatch.code);
          }
          if (activeSheet.target_lead_count) {
            setCount(activeSheet.target_lead_count.toString());
            if (!['10', '25', '50', '100', '200', '500'].includes(activeSheet.target_lead_count.toString())) {
              setCount('custom');
              setCustomCount(activeSheet.target_lead_count.toString());
            }
          }
          startPollingProgress(activeSheet.id);
        }
      } catch {
        // ignore
      }
    };

    restoreActiveJob();
  }, []);

  // Polling unmount cleanup
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, []);

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

  const handleBackToControls = () => {
    stopPolling();
    setRunning(false);
    setProgress(0);
    setScrapedCount(0);
    setScrapeStatus('idle');
    setScrapeError(null);
    setActiveJobId(null);
    setCreatingJob(false);
    setPaused(false);
    loadRawSheets();
  };

  const handleStartScrape = async () => {
    if (running || creatingJob) {
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
      const selectedCountryName = COUNTRIES.find(c => c.code === country)?.name || country;
      const res = await api.startScrape({
        niche: nVal,
        city: locVal,
        region: region,
        country: selectedCountryName,
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

      setActiveJobId(jobId);
      setRunning(true);
      setProgress(0);
      setScrapedCount(0);
      setScrapeStatus('running');
      setScrapeError(null);
      setPaused(false);
      setCreatingJob(false);

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

      startPollingProgress(jobId);

    } catch (err: any) {
      console.error("Failed to start scrape", err);
      setCreatingJob(false);
      setRunning(false);
      setScrapeStatus('failed');
      setScrapeError(err?.message || "Failed to initiate scraper. Connection refused.");
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

  const handleOpenRenameModal = (sheet: any) => {
    setPendingRawSheet(sheet);
    setRenameInput(sheet.name);
    setShowRenameModal(true);
  };

  const handleExportSheet = async (sheet: any) => {
    try {
      const leads = await api.getJobLeads(sheet.id);
      if (!leads || leads.length === 0) {
        alert('This sheet has 0 leads to export.');
        return;
      }
      const headers = ['Lead ID', 'Business Name', 'Location', 'Website', 'Phone', 'Email', 'Opportunity Category', 'Opportunity Score'];
      const rows = leads.map((l: any, idx: number) => [
        `RAW-${idx + 1}`,
        `"${(l.businessName || l.business_name || '').replace(/"/g, '""')}"`,
        `"${(l.location || '').replace(/"/g, '""')}"`,
        `"${(l.websiteUrl || l.website || '').replace(/"/g, '""')}"`,
        `"${(l.contactPhone || l.phone || '').replace(/"/g, '""')}"`,
        `"${(l.contactEmail || l.email || '').replace(/"/g, '""')}"`,
        `"${(l.opportunity_category || '').replace(/"/g, '""')}"`,
        l.opportunity_score || ''
      ]);
      const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${(sheet.name || 'leads').replace(/[^a-zA-Z0-9_-]/g, '_')}_leads.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Failed to export sheet:', e);
      alert('Failed to export lead sheet');
    }
  };

  const handleDeleteSheet = (sheet: any) => {
    setDeleteSheetError(null);
    setSheetToDelete(sheet);
  };

  const confirmDeleteSheet = async () => {
    if (!sheetToDelete) return;
    setIsDeletingSheet(true);
    setDeleteSheetError(null);
    try {
      await api.deleteRawSheet(sheetToDelete.id);
      if (selectedRawId === sheetToDelete.id) setSelectedRawId(null);
      loadRawSheets();
      setSheetToDelete(null);
    } catch (e: any) {
      console.error('Failed to delete sheet:', e);
      setDeleteSheetError(e?.message || 'Failed to delete sheet. Please try again.');
    } finally {
      setIsDeletingSheet(false);
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
        style={{ 
          background: 'var(--bg-surface)', 
          border: '1px solid var(--border-faint)', 
          borderRadius: 'var(--r-xl)', 
          padding: scrapeStatus === 'idle' ? '24px' : '14px 20px', 
          marginBottom: scrapeStatus === 'idle' ? 24 : 16, 
          position: 'relative',
          overflow: 'hidden',
          boxShadow: '0 2px 10px rgba(0,0,0,0.02)',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
        }}
      >
        {/* Header & Presets row */}
        {scrapeStatus === 'idle' && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 18, borderBottom: '1px solid var(--border-faint)', paddingBottom: 12 }}>
            <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.09em', color: 'var(--text-4)' }}>Scrape Controls</div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              {/* ⋯ Presets Menu */}
              <div ref={presetRef} style={{ position: 'relative' }}>
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
          </div>
        )}

          {scrapeStatus === 'idle' ? (
            /* ==========================================
               1. CONFIGURATION VIEW (IDLE STATE)
               ========================================== */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              
              {/* Core Selector Controls - ROW 1: Categories / Country / Region */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '16px 20px' }}>
                
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
                      <div ref={nicheRef} style={{ position: 'relative' }}>
                        <div 
                          onClick={() => setShowNicheDropdown(true)}
                          style={{ display: 'flex', flexWrap: 'nowrap', overflow: 'hidden', gap: 6, background: 'var(--bg-input)', border: `1px solid ${validationErrors.niche ? 'var(--pink)' : 'var(--border-subtle)'}`, borderRadius: 'var(--r-md)', padding: '6px 8px', minHeight: 38, alignItems: 'center', cursor: 'text' }}
                        >
                          {categories.slice(0, 2).map(cat => (
                            <span key={cat} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(192, 132, 252, 0.2)', backdropFilter: 'blur(4px)', border: '1px solid rgba(192, 132, 252, 0.4)', borderRadius: 4, padding: '2px 6px', fontSize: '12px', color: 'var(--text-1)', whiteSpace: 'nowrap' }}>
                              {cat}
                              <button onClick={(e) => { e.stopPropagation(); setCategories(categories.filter(c => c !== cat)); }} style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', padding: 0, fontSize: '14px', lineHeight: 1 }}>×</button>
                            </span>
                          ))}
                          {categories.length > 2 && (
                            <span onClick={(e) => { e.stopPropagation(); setShowNicheDropdown(true); }} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(192, 132, 252, 0.2)', backdropFilter: 'blur(4px)', border: '1px solid rgba(192, 132, 252, 0.4)', borderRadius: 4, padding: '2px 6px', fontSize: '12px', color: 'var(--text-1)', cursor: 'pointer', whiteSpace: 'nowrap' }}>
                              +{categories.length - 2}
                            </span>
                          )}
                          <input 
                            type="text" 
                            value={nicheSearchQuery}
                            placeholder={categories.length === 0 ? "Search or add category..." : ""}
                            onChange={e => {
                              setNicheSearchQuery(e.target.value);
                              setShowNicheDropdown(true);
                            }}
                            onFocus={() => setShowNicheDropdown(true)}
                            onKeyDown={e => {
                              if (e.key === 'Enter' && nicheSearchQuery.trim()) {
                                e.preventDefault();
                                if (!categories.includes(nicheSearchQuery.trim())) {
                                  setCategories([...categories, nicheSearchQuery.trim()]);
                                }
                                setNicheSearchQuery('');
                                setShowNicheDropdown(false);
                              }
                            }}
                            style={{ background: 'transparent', border: 'none', color: 'var(--text-1)', fontSize: '13px', outline: 'none', flex: 1, minWidth: 80 }}
                          />
                        </div>
                        
                        {showNicheDropdown && (() => {
                          const availableNiches = Array.from(new Set([
                            ...NICHES,
                            ...Object.values(NICHE_SUGGESTIONS).flat()
                          ]));
                          const filteredNiches = availableNiches.filter(
                            c => c.toLowerCase().includes(nicheSearchQuery.toLowerCase()) && !categories.includes(c)
                          );

                          return (
                            <div style={{
                              position: 'absolute', top: '100%', left: 0, right: 0,
                              background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
                              borderRadius: 'var(--r-md)', zIndex: 100, maxHeight: 220, overflowY: 'auto',
                              marginTop: 4, boxShadow: 'var(--shadow-drop)'
                            }}>
                              {nicheSearchQuery.trim() && !categories.includes(nicheSearchQuery.trim()) && !filteredNiches.some(c => c.toLowerCase() === nicheSearchQuery.trim().toLowerCase()) && (
                                <div
                                  onClick={() => {
                                    setCategories([...categories, nicheSearchQuery.trim()]);
                                    setNicheSearchQuery('');
                                    setShowNicheDropdown(false);
                                  }}
                                  style={{ padding: '8px 12px', cursor: 'pointer', fontSize: '13px', color: 'var(--pink)', fontWeight: 600, borderBottom: '1px solid var(--border-faint)', background: 'rgba(236,72,153,0.06)' }}
                                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(236,72,153,0.12)'}
                                  onMouseLeave={e => e.currentTarget.style.background = 'rgba(236,72,153,0.06)'}
                                >
                                  + Add &ldquo;{nicheSearchQuery.trim()}&rdquo;
                                </div>
                              )}

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

                              {filteredNiches.map(c => (
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

                              {filteredNiches.length === 0 && (!nicheSearchQuery.trim() || categories.includes(nicheSearchQuery.trim())) && (
                                <div style={{ padding: '10px 12px', fontSize: '12px', color: 'var(--text-3)', fontStyle: 'italic' }}>
                                  Type to search or add any category...
                                </div>
                              )}
                            </div>
                          );
                        })()}
                      </div>
                    )}
                  </div>

                  {/* Country Dropdown */}
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={sectionLabelStyle}>Country</span>
                    <div ref={countryRef} style={{ position: 'relative' }}>
                      <button
                        type="button"
                        onClick={() => setShowCountryDropdown(o => !o)}
                        style={{
                          width: '100%', height: 38, padding: '0 14px',
                          background: 'var(--bg-input)', border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--r-md)', display: 'flex', alignItems: 'center',
                          justifyContent: 'space-between', color: 'var(--text-1)', fontSize: '13px',
                          cursor: 'pointer', transition: 'border-color var(--ease), background var(--ease)'
                        }}
                        onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border-strong)'}
                        onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
                      >
                        <span style={{ fontWeight: 500 }}>{COUNTRIES.find(c => c.code === country)?.name || country}</span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: 'var(--text-3)', transform: showCountryDropdown ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0 }}>
                          <path d="M6 9l6 6 6-6"/>
                        </svg>
                      </button>

                      {showCountryDropdown && (
                        <div style={{
                          position: 'absolute', top: '100%', left: 0, right: 0,
                          background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--r-md)', zIndex: 120, maxHeight: 220, overflowY: 'auto',
                          marginTop: 4, boxShadow: 'var(--shadow-drop)'
                        }}>
                          {COUNTRIES.map(c => {
                            const isSelected = country === c.code;
                            return (
                              <div
                                key={c.code}
                                onClick={() => {
                                  setCountry(c.code);
                                  setRegion('');
                                  setLocations([]);
                                  setShowCountryDropdown(false);
                                }}
                                style={{
                                  padding: '9px 14px', cursor: 'pointer', fontSize: '13px',
                                  color: isSelected ? 'var(--pink)' : 'var(--text-1)',
                                  fontWeight: isSelected ? 600 : 400,
                                  background: isSelected ? 'rgba(236,72,153,0.08)' : 'transparent',
                                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                  transition: 'background var(--ease)'
                                }}
                                onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'var(--bg-hover)'; }}
                                onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                              >
                                <span>{c.name}</span>
                                {isSelected && <span style={{ color: 'var(--pink)', fontSize: '12px', fontWeight: 700 }}>✓</span>}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Region Dropdown */}
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={sectionLabelStyle}>Region / State</span>
                    <div ref={regionRef} style={{ position: 'relative' }}>
                      <button
                        type="button"
                        onClick={() => { setShowRegionDropdown(o => !o); setRegionSearchQuery(''); }}
                        style={{
                          width: '100%', height: 38, padding: '0 14px',
                          background: 'var(--bg-input)', border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--r-md)', display: 'flex', alignItems: 'center',
                          justifyContent: 'space-between', color: 'var(--text-1)', fontSize: '13px',
                          cursor: 'pointer', transition: 'border-color var(--ease), background var(--ease)'
                        }}
                        onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border-strong)'}
                        onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
                      >
                        <span style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {region || 'All Regions / States'}
                        </span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: 'var(--text-3)', transform: showRegionDropdown ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0 }}>
                          <path d="M6 9l6 6 6-6"/>
                        </svg>
                      </button>

                      {showRegionDropdown && (
                        <div style={{
                          position: 'absolute', top: '100%', left: 0, right: 0,
                          background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--r-md)', zIndex: 120, maxHeight: 240, overflowY: 'auto',
                          marginTop: 4, boxShadow: 'var(--shadow-drop)'
                        }}>
                          {/* Search input for states/regions if > 5 */}
                          {(REGIONS[country] || []).length > 5 && (
                            <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--border-faint)', position: 'sticky', top: 0, background: 'var(--bg-elevated)', zIndex: 2 }}>
                              <input
                                type="text"
                                placeholder="Search state or region..."
                                value={regionSearchQuery}
                                onChange={e => setRegionSearchQuery(e.target.value)}
                                onClick={e => e.stopPropagation()}
                                style={{
                                  width: '100%', padding: '6px 10px', background: 'var(--bg-input)',
                                  border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)',
                                  color: 'var(--text-1)', fontSize: '12px', outline: 'none'
                                }}
                              />
                            </div>
                          )}

                          {/* "All Regions / States" Option */}
                          <div
                            onClick={() => {
                              setRegion('');
                              setLocations([]);
                              setShowRegionDropdown(false);
                            }}
                            style={{
                              padding: '9px 14px', cursor: 'pointer', fontSize: '13px',
                              color: !region ? 'var(--pink)' : 'var(--text-1)',
                              fontWeight: !region ? 600 : 400,
                              background: !region ? 'rgba(236,72,153,0.08)' : 'transparent',
                              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                              transition: 'background var(--ease)'
                            }}
                            onMouseEnter={e => { if (region) e.currentTarget.style.background = 'var(--bg-hover)'; }}
                            onMouseLeave={e => { if (region) e.currentTarget.style.background = 'transparent'; }}
                          >
                            <span>All Regions / States</span>
                            {!region && <span style={{ color: 'var(--pink)', fontSize: '12px', fontWeight: 700 }}>✓</span>}
                          </div>

                          {/* Filtered regions */}
                          {(REGIONS[country] || [])
                            .filter(r => r.toLowerCase().includes(regionSearchQuery.toLowerCase()))
                            .map(r => {
                              const isSelected = region === r;
                              return (
                                <div
                                  key={r}
                                  onClick={() => {
                                    setRegion(r);
                                    setLocations([]);
                                    setShowRegionDropdown(false);
                                  }}
                                  style={{
                                    padding: '9px 14px', cursor: 'pointer', fontSize: '13px',
                                    color: isSelected ? 'var(--pink)' : 'var(--text-1)',
                                    fontWeight: isSelected ? 600 : 400,
                                    background: isSelected ? 'rgba(236,72,153,0.08)' : 'transparent',
                                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                    transition: 'background var(--ease)'
                                  }}
                                  onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'var(--bg-hover)'; }}
                                  onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                                >
                                  <span>{r}</span>
                                  {isSelected && <span style={{ color: 'var(--pink)', fontSize: '12px', fontWeight: 700 }}>✓</span>}
                                </div>
                              );
                            })}
                        </div>
                      )}
                    </div>
                  </div>
              </div>

              {/* Core Selector Controls - ROW 2: Locations / Target Service / Lead Target */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '16px 20px' }}>
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
                      <div ref={cityRef} style={{ position: 'relative' }}>
                        <div 
                          onClick={() => setShowCityDropdown(true)}
                          style={{ display: 'flex', flexWrap: 'nowrap', overflow: 'hidden', gap: 6, background: 'var(--bg-input)', border: `1px solid ${validationErrors.location ? 'var(--pink)' : 'var(--border-subtle)'}`, borderRadius: 'var(--r-md)', padding: '6px 8px', minHeight: 38, alignItems: 'center', cursor: 'text' }}
                        >
                          {locations.slice(0, 2).map(loc => (
                            <span key={loc} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(192, 132, 252, 0.2)', backdropFilter: 'blur(4px)', border: '1px solid rgba(192, 132, 252, 0.4)', borderRadius: 4, padding: '2px 6px', fontSize: '12px', color: 'var(--text-1)', whiteSpace: 'nowrap' }}>
                              {loc}
                              <button onClick={(e) => { e.stopPropagation(); setLocations(locations.filter(l => l !== loc)); }} style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', padding: 0, fontSize: '14px', lineHeight: 1 }}>×</button>
                            </span>
                          ))}
                          {locations.length > 2 && (
                            <span onClick={(e) => { e.stopPropagation(); setShowCityDropdown(true); }} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(192, 132, 252, 0.2)', backdropFilter: 'blur(4px)', border: '1px solid rgba(192, 132, 252, 0.4)', borderRadius: 4, padding: '2px 6px', fontSize: '12px', color: 'var(--text-1)', cursor: 'pointer', whiteSpace: 'nowrap' }}>
                              +{locations.length - 2}
                            </span>
                          )}
                          <input 
                            type="text" 
                            value={citySearchQuery}
                            placeholder={locations.length === 0 ? "Search or add city/location..." : ""}
                            onChange={e => {
                              setCitySearchQuery(e.target.value);
                              setShowCityDropdown(true);
                            }}
                            onFocus={() => setShowCityDropdown(true)}
                            onKeyDown={e => {
                              if (e.key === 'Enter' && citySearchQuery.trim()) {
                                e.preventDefault();
                                if (!locations.includes(citySearchQuery.trim())) {
                                  setLocations([...locations, citySearchQuery.trim()]);
                                }
                                setCitySearchQuery('');
                                setShowCityDropdown(false);
                              }
                            }}
                            style={{ background: 'transparent', border: 'none', color: 'var(--text-1)', fontSize: '13px', outline: 'none', flex: 1, minWidth: 80 }}
                          />
                        </div>
                        
                        {showCityDropdown && (() => {
                          // Filter strictly by selected region (state), or by country if region is empty
                          const availableCities = Array.from(new Set(
                            region && REGION_CITIES[region]
                              ? REGION_CITIES[region]
                              : (COUNTRY_CITIES[country] || COUNTRY_CITIES['US'])
                          ));
                          const filteredCities = availableCities.filter(
                            c => c.toLowerCase().includes(citySearchQuery.toLowerCase()) && !locations.includes(c)
                          );

                          return (
                            <div style={{
                              position: 'absolute', top: '100%', left: 0, right: 0,
                              background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
                              borderRadius: 'var(--r-md)', zIndex: 100, maxHeight: 220, overflowY: 'auto',
                              marginTop: 4, boxShadow: 'var(--shadow-drop)'
                            }}>
                              {citySearchQuery.trim() && !locations.includes(citySearchQuery.trim()) && !filteredCities.some(c => c.toLowerCase() === citySearchQuery.trim().toLowerCase()) && (
                                <div
                                  onClick={() => {
                                    setLocations([...locations, citySearchQuery.trim()]);
                                    setCitySearchQuery('');
                                    setShowCityDropdown(false);
                                  }}
                                  style={{ padding: '8px 12px', cursor: 'pointer', fontSize: '13px', color: 'var(--pink)', fontWeight: 600, borderBottom: '1px solid var(--border-faint)', background: 'rgba(236,72,153,0.06)' }}
                                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(236,72,153,0.12)'}
                                  onMouseLeave={e => e.currentTarget.style.background = 'rgba(236,72,153,0.06)'}
                                >
                                  + Add &ldquo;{citySearchQuery.trim()}&rdquo;
                                </div>
                              )}

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

                              {filteredCities.map(c => (
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

                              {filteredCities.length === 0 && (!citySearchQuery.trim() || locations.includes(citySearchQuery.trim())) && (
                                <div style={{ padding: '10px 12px', fontSize: '12px', color: 'var(--text-3)', fontStyle: 'italic' }}>
                                  {region ? `No more suggestions for ${region}. Type to add custom city...` : 'Type to search or add any location...'}
                                </div>
                              )}
                            </div>
                          );
                        })()}
                      </div>
                    )}
                    
                    {!customLocation && (
                      <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: 4 }}>
                        Try:{' '}
                        {(() => {
                          const suggestions = region && REGION_CITIES[region]
                            ? REGION_CITIES[region].slice(0, 4)
                            : ({
                                US: ['New York City', 'Los Angeles', 'Chicago', 'Houston'],
                                UK: ['London', 'Manchester', 'Birmingham', 'Leeds'],
                                CA: ['Toronto', 'Vancouver', 'Montreal', 'Calgary'],
                                AU: ['Sydney', 'Melbourne', 'Brisbane', 'Perth'],
                                IN: ['Mumbai', 'Delhi', 'Bangalore', 'Hyderabad']
                              }[country] || ['New York City', 'Los Angeles', 'Chicago']);

                          return suggestions.map((cVal, idx, arr) => (
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
                          ));
                        })()}
                      </div>
                    )}
                  </div>

                  {/* Service Dropdown */}
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={sectionLabelStyle}>Target Service</span>
                    <div ref={serviceRef} style={{ position: 'relative' }}>
                      <button
                        type="button"
                        onClick={() => setShowServiceDropdown(o => !o)}
                        style={{
                          width: '100%', height: 38, padding: '0 14px',
                          background: 'var(--bg-input)', border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--r-md)', display: 'flex', alignItems: 'center',
                          justifyContent: 'space-between', color: 'var(--text-1)', fontSize: '13px',
                          cursor: 'pointer', transition: 'border-color var(--ease), background var(--ease)'
                        }}
                        onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border-strong)'}
                        onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
                      >
                        <span style={{ fontWeight: 500 }}>{SERVICES.find(s => s.key === service)?.label || service}</span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: 'var(--text-3)', transform: showServiceDropdown ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0 }}>
                          <path d="M6 9l6 6 6-6"/>
                        </svg>
                      </button>

                      {showServiceDropdown && (
                        <div style={{
                          position: 'absolute', top: '100%', left: 0, right: 0,
                          background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--r-md)', zIndex: 120, maxHeight: 220, overflowY: 'auto',
                          marginTop: 4, boxShadow: 'var(--shadow-drop)'
                        }}>
                          {SERVICES.map(s => {
                            const isSelected = service === s.key;
                            return (
                              <div
                                key={s.key}
                                onClick={() => {
                                  setService(s.key);
                                  setShowServiceDropdown(false);
                                }}
                                style={{
                                  padding: '9px 14px', cursor: 'pointer', fontSize: '13px',
                                  color: isSelected ? 'var(--pink)' : 'var(--text-1)',
                                  fontWeight: isSelected ? 600 : 400,
                                  background: isSelected ? 'rgba(236,72,153,0.08)' : 'transparent',
                                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                  transition: 'background var(--ease)'
                                }}
                                onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'var(--bg-hover)'; }}
                                onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                              >
                                <span>{s.label}</span>
                                {isSelected && <span style={{ color: 'var(--pink)', fontSize: '12px', fontWeight: 700 }}>✓</span>}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
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
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 20, marginTop: 14, padding: '16px', background: 'var(--bg-nav)', borderRadius: 'var(--r-md)', border: '1px solid var(--border-faint)' }}>
                    
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
               2. ACTIVE SCRAPING PROGRESS VIEW (COMPACT TOP STRIP)
               ========================================== */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                
                {/* Left: Status Dot, Title, Stage pill & ETA */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', minWidth: 0, flex: 1 }}>
                  {/* Status indicator dot */}
                  <div style={{
                    width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                    background: scrapeStatus === 'running' ? 'var(--pink)' :
                               (scrapeStatus === 'completed' || scrapeStatus === 'partial') ? 'var(--green)' :
                               scrapeStatus === 'failed' ? 'var(--red)' : 'var(--amber)',
                    boxShadow: scrapeStatus === 'running' ? '0 0 10px var(--pink)' : 'none',
                    animation: scrapeStatus === 'running' ? 'pulse 1.5s infinite' : 'none'
                  }} />

                  {/* Title */}
                  <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {scrapeStatus === 'running' && `Scraping "${plainQuery ? plainQueryValue : (categories[0] || niche)}"`}
                    {scrapeStatus === 'stopped_saved' && 'Scrape Paused'}
                    {scrapeStatus === 'cancelling' && 'Halting...'}
                    {scrapeStatus === 'cancelled' && 'Scrape Stopped'}
                    {scrapeStatus === 'completed' && (scrapedCount === 0 ? 'Complete (0 Found)' : 'Scrape Complete')}
                    {scrapeStatus === 'partial' && 'Partial Complete'}
                    {scrapeStatus === 'failed' && (scrapeError ? `Failed: ${scrapeError}` : 'Scrape Failed')}
                  </span>

                  {/* Stage micro-status */}
                  {scrapeStatus === 'running' && (
                    <span className="pill" style={{ background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', color: 'var(--text-2)', fontSize: '11px', fontWeight: 500, fontFamily: 'monospace' }}>
                      {microStatus}
                    </span>
                  )}

                  {/* ETA */}
                  {scrapeStatus === 'running' && (
                    <span style={{ fontSize: '11px', color: 'var(--text-3)', background: 'rgba(0,0,0,0.03)', padding: '2px 8px', borderRadius: 'var(--r-sm)' }}>
                      ⏱ {remainingTime > 0 ? (remainingTime > 60 ? `~${Math.floor(remainingTime / 60)}m ${remainingTime % 60}s` : `~${remainingTime}s left`) : 'Estimating...'}
                    </span>
                  )}
                </div>

                {/* Right: Progress stats & compact actions */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
                  {/* Progress count */}
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-1)' }}>
                    {scrapedCount} <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>/ {allAvailable ? '∞' : (count === 'custom' ? customCount : count)} leads</span>
                    {!allAvailable && <span style={{ color: 'var(--pink)', fontSize: '11px', marginLeft: 4 }}>({Math.floor(progress)}%)</span>}
                  </div>

                  {/* Stats chips */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--bg-input)', padding: '2px 8px', borderRadius: 'var(--r-sm)', fontSize: '11px' }}>
                    <span style={{ color: 'var(--text-3)' }}>Fetched: <strong style={{ color: 'var(--text-1)' }}>{scrapeStats.discovered || 0}</strong></span>
                    <span style={{ color: 'var(--border-subtle)' }}>|</span>
                    <span style={{ color: 'var(--green)' }}>Saved: <strong>{scrapeStats.saved || 0}</strong></span>
                    {scrapeStats.failed > 0 && (
                      <>
                        <span style={{ color: 'var(--border-subtle)' }}>|</span>
                        <span style={{ color: 'var(--red)' }}>Failed: <strong>{scrapeStats.failed}</strong></span>
                      </>
                    )}
                  </div>

                  {/* Action buttons */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {scrapeStatus === 'running' && (
                      <>
                        <button 
                          onClick={handleStopScrape} 
                          className="btn btn-ghost btn-sm" 
                          style={{ height: 28, padding: '0 10px', fontSize: '11px' }}
                        >
                          ⏸ Pause
                        </button>
                        <button 
                          onClick={handleCancelScrape} 
                          title="Stop Scrape"
                          className="btn btn-ghost btn-sm" 
                          style={{ height: 28, padding: '0 10px', fontSize: '11px' }}
                        >
                          ■ Stop
                        </button>
                        <button 
                          onClick={handleCancelScrape} 
                          title="Cancel Scrape"
                          className="btn btn-ghost btn-sm" 
                          style={{ height: 28, width: 28, padding: 0, justifyContent: 'center', fontSize: '13px' }}
                        >
                          ✕
                        </button>
                      </>
                    )}

                    {(scrapeStatus === 'stopped_saved' || scrapeStatus === 'cancelled') && (
                      <>
                        <button 
                          onClick={handleResumeScrape} 
                          className="btn btn-pink btn-sm" 
                          style={{ height: 28, padding: '0 12px', fontSize: '11px', fontWeight: 600 }}
                        >
                          ▶ Resume
                        </button>
                        <button 
                          onClick={() => {
                            setSaveSuccess(true);
                            setTimeout(() => setSaveSuccess(false), 2000);
                          }} 
                          className="btn btn-ghost btn-sm" 
                          style={{ height: 28, padding: '0 10px', fontSize: '11px' }}
                        >
                          {saveSuccess ? 'Saved ✓' : 'Save'}
                        </button>
                        <button 
                          onClick={handleBackToControls} 
                          className="btn btn-ghost btn-sm" 
                          style={{ height: 28, padding: '0 10px', fontSize: '11px' }}
                        >
                          Back
                        </button>
                      </>
                    )}

                    {(scrapeStatus === 'completed' || scrapeStatus === 'partial') && (
                      <>
                        <button 
                          onClick={handleViewLeads} 
                          className="btn btn-ghost btn-sm" 
                          style={{ height: 28, padding: '0 10px', fontSize: '11px' }}
                        >
                          View Raw Leads
                        </button>
                        <button 
                          onClick={handleBackToControls} 
                          className="btn btn-pink btn-sm" 
                          style={{ height: 28, padding: '0 12px', fontSize: '11px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 5 }}
                        >
                          Back to Controls
                        </button>
                      </>
                    )}

                    {scrapeStatus === 'failed' && (
                      <>
                        <button 
                          onClick={() => { 
                            setRunning(false); 
                            setProgress(0); 
                            setScrapedCount(0); 
                            setScrapeStatus('idle'); 
                            setScrapeError(null); 
                            handleStartScrape(); 
                          }} 
                          className="btn btn-ghost btn-sm" 
                          style={{ height: 28, padding: '0 10px', fontSize: '11px' }}
                        >
                          Retry Scrape
                        </button>
                        <button 
                          onClick={handleBackToControls} 
                          className="btn btn-pink btn-sm" 
                          style={{ height: 28, padding: '0 12px', fontSize: '11px', fontWeight: 600 }}
                        >
                          Back to Controls
                        </button>
                      </>
                    )}
                  </div>
                </div>

              </div>

              {/* Progress Bar (Slim 4px track at bottom of card) */}
              <div style={{ height: 4, borderRadius: 2, background: 'var(--bg-input)', overflow: 'hidden', width: '100%', marginTop: 2 }}>
                <div style={{ 
                  width: `${Math.min(100, Math.max(0, progress))}%`, 
                  height: '100%', 
                  background: 'linear-gradient(90deg, var(--pink), #f472b6)', 
                  transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)' 
                }} />
              </div>

              {/* Error messages if failed */}
              {scrapeStatus === 'failed' && scrapeError && (
                <div style={{ fontSize: '11px', color: 'var(--red)', marginTop: 2, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>⚠️</span> Error: {scrapeError}
                </div>
              )}
            </div>
          )}

      </div>


      {/* ── Raw Lead Sheets section ── */}
      <div ref={tableRef} style={{ background:'var(--bg-surface)',border:'1px solid var(--border-faint)',borderRadius:'var(--r-2xl)',overflow:'hidden',marginBottom:14,display:'flex',flexDirection:'column',boxShadow:'0 2px 10px rgba(0,0,0,0.02)' }}>
        <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',padding:'14px 22px',borderBottom:'1px solid var(--border-faint)',flexShrink:0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize:'14px',fontWeight:700,color:'var(--text-1)' }}>Raw Lead Sheets</span>
            <span className="pill" style={{ background: 'var(--bg-input)', color: 'var(--text-3)', fontSize: '10px' }}>
              {rawSheets.length} {rawSheets.length === 1 ? 'Sheet' : 'Sheets'}
            </span>
          </div>
          
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
              style={{ height:32, padding:'0 16px', fontSize: '12px', opacity:!selectedRawId ? 0.5 : 1 }}
            >
              Segregate
            </button>
          )}
        </div>

        <div style={{ overflowX:'auto', overflowY: 'auto', maxHeight: 'calc(100vh - 210px)' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead style={{ position: 'sticky', top: 0, zIndex: 10, background: 'var(--bg-surface)' }}>
              <tr style={{ borderBottom:'1px solid var(--border-faint)' }}>
                {['Lead ID', 'Lead Name', 'Country & Region', 'Niche', 'Service', 'Total Leads', 'Date', ''].map((c, i) => (
                  <th key={i} style={{ padding:'10px 18px',fontSize:'10px',fontWeight:600,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:'.07em',textAlign: i === 7 ? 'right' : 'left',whiteSpace:'nowrap',background:'var(--bg-surface)' }}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rawSheets.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding:'56px',textAlign:'center',color:'var(--text-3)',fontSize:'14px' }}>
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
                    {/* 3-Dots Options Menu */}
                    <td style={{ padding:'14px 18px',verticalAlign:'middle',textAlign:'right' }} onClick={e => e.stopPropagation()}>
                      <ThreeDotMenu items={[
                        { label: 'Preview Leads', icon: I.preview, onClick: () => setOpenRawSheet(sheet) },
                        { label: 'Rename Sheet', icon: I.edit, onClick: () => handleOpenRenameModal(sheet) },
                        { label: 'Export to CSV', icon: I.download, onClick: () => handleExportSheet(sheet) },
                        { label: 'Delete Sheet', icon: I.trash, danger: true, onClick: () => handleDeleteSheet(sheet) },
                      ]} />
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
          <div style={{
            position:'fixed',
            top: isRawFullScreen ? 0 : '50%',
            left: isRawFullScreen ? 0 : '50%',
            transform: isRawFullScreen ? 'none' : 'translate(-50%,-50%)',
            width: isRawFullScreen ? '100vw' : 'min(94vw,1000px)',
            height: isRawFullScreen ? '100vh' : 'auto',
            maxHeight: isRawFullScreen ? '100vh' : '82vh',
            background:'var(--bg-elevated)',
            border: isRawFullScreen ? 'none' : '1px solid var(--border-subtle)',
            borderRadius: isRawFullScreen ? 0 : 'var(--r-2xl)',
            zIndex:101,
            display:'flex',
            flexDirection:'column',
            overflow:'hidden',
            boxShadow: isRawFullScreen ? 'none' : '0 40px 100px rgba(0,0,0,.65)',
            transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
          }}>
            {/* Header */}
            <div
              onDoubleClick={() => setIsRawFullScreen(f => !f)}
              title="Double click to toggle fullscreen"
              style={{ padding:'20px 24px',borderBottom:'1px solid var(--border-faint)',display:'flex',alignItems:'center',justifyContent:'space-between',flexShrink:0,cursor:'pointer' }}
            >
              <div>
                <div style={{ display:'flex',alignItems:'center',gap:10,marginBottom:4 }}>
                  <span style={{ fontSize:'15px',fontWeight:700,color:'var(--text-1)' }}>{openRawSheet.name}</span>
                  <span className="pill" style={{ background:'var(--pink-dim)',color:'var(--pink-light)',fontSize:'10px' }}>RAW LEAD SHEET</span>
                  <span style={{ fontSize:'11px',color:'var(--text-3)',fontFamily:'monospace' }}>{openRawSheet.sheetId}</span>
                </div>
                <div style={{ fontSize:'12px',color:'var(--text-3)' }}>Service: {SERVICE_LABELS[openRawSheet.service as ServiceType]}</div>
              </div>
              <div style={{ display:'flex',alignItems:'center',gap:8 }} onClick={e => e.stopPropagation()}>
                {/* Fullscreen Toggle Button */}
                <button
                  onClick={() => setIsRawFullScreen(f => !f)}
                  title={isRawFullScreen ? "Exit Fullscreen" : "Fullscreen"}
                  style={{ width:30,height:30,display:'flex',alignItems:'center',justifyContent:'center',borderRadius:'var(--r-md)',color:'var(--text-3)',cursor:'pointer' }}
                  onMouseEnter={e=>(e.currentTarget.style.background='var(--bg-hover)')}
                  onMouseLeave={e=>(e.currentTarget.style.background='transparent')}
                >
                  {isRawFullScreen ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/>
                    </svg>
                  ) : (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
                    </svg>
                  )}
                </button>
                <button onClick={() => setOpenRawSheet(null)} className="btn btn-ghost btn-sm" style={{ padding: 6, cursor:'pointer' }}>
                  ✕
                </button>
              </div>
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
                        {['Lead ID', 'Business Name', 'Location', 'Website', 'Email'].map(col => (
                          <th key={col} style={{ padding:'8px 12px',fontSize:'10px',fontWeight:600,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:'.07em',textAlign:'left' }}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {previewLeads.map((l, idx) => {
                        const emailVal = l.contactEmail || l.email;
                        return (
                          <tr key={l.leadId || idx} style={{ borderBottom:'1px solid var(--border-faint)' }}>
                            <td style={{ padding:'10px 12px',fontSize:'11px',fontFamily:'monospace',color:'var(--text-3)' }}>{l.leadId || `${openRawSheet.sheetId}-${String(idx + 1).padStart(2, '0')}`}</td>
                            <td style={{ padding:'10px 12px',fontWeight:600,color:'var(--text-1)' }}>{l.businessName}</td>
                            <td style={{ padding:'10px 12px',color:'var(--text-2)' }}>{l.location}</td>
                            <td style={{ padding:'10px 12px',color:'var(--text-2)',fontSize:'12px' }}>
                              {l.websiteUrl ? (
                                <a href={l.websiteUrl.startsWith('http') ? l.websiteUrl : `https://${l.websiteUrl}`} target="_blank" rel="noreferrer" onClick={e=>e.stopPropagation()} style={{ color:'var(--blue)', textDecoration:'none' }}>
                                  {l.websiteUrl.replace(/^https?:\/\//, '').replace(/\/$/, '')}
                                </a>
                              ) : '—'}
                            </td>
                            <td style={{ padding:'10px 12px',fontSize:'12px' }}>
                              {emailVal ? (
                                <a 
                                  href={`mailto:${emailVal}`} 
                                  onClick={e => e.stopPropagation()} 
                                  style={{ color:'var(--pink)', textDecoration:'none', fontWeight:600, display:'inline-flex', alignItems:'center', gap:'4px' }}
                                  title="Send outreach email"
                                >
                                  <span>✉</span> {emailVal}
                                </a>
                              ) : (
                                <span style={{ color:'var(--text-3)' }}>{l.contactPhone || 'No email found'}</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* ── Direct In-Screen Delete Confirmation Modal ── */}
      {sheetToDelete && (
        <>
          <div 
            onClick={() => !isDeletingSheet && setSheetToDelete(null)} 
            style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.70)', backdropFilter:'blur(4px)', zIndex:300 }} 
          />
          <div style={{
            position:'fixed', top:'50%', left:'50%', transform:'translate(-50%,-50%)',
            width:'min(92vw, 440px)', background:'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
            borderRadius:'var(--r-xl)', zIndex:301, padding:'24px', boxShadow:'0 24px 60px rgba(0,0,0,.5)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
              <div style={{
                width: 40, height: 40, borderRadius: '50%', background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.25)', display: 'flex', alignItems: 'center',
                justifyContent: 'center', color: 'var(--red)', flexShrink: 0
              }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="3,6 5,6 21,6"/>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  <line x1="10" y1="11" x2="10" y2="17"/>
                  <line x1="14" y1="11" x2="14" y2="17"/>
                </svg>
              </div>
              <div>
                <h3 style={{ fontSize:'16px', fontWeight:700, color:'var(--text-1)', margin:0 }}>Delete Lead Sheet</h3>
                <span style={{ fontSize:'11px', color:'var(--text-3)', fontFamily:'monospace' }}>{sheetToDelete.sheetId}</span>
              </div>
            </div>

            <p style={{ fontSize:'13px', color:'var(--text-2)', lineHeight:1.5, marginBottom:18 }}>
              Are you sure you want to delete <strong style={{ color: 'var(--text-1)' }}>&ldquo;{sheetToDelete.name}&rdquo;</strong>? This action will permanently remove this sheet and its scraped leads.
            </p>

            {deleteSheetError && (
              <div style={{ padding: '8px 12px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--red)', borderRadius: 'var(--r-md)', color: 'var(--red)', fontSize: '12px', marginBottom: 16 }}>
                {deleteSheetError}
              </div>
            )}

            <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
              <button 
                onClick={() => setSheetToDelete(null)} 
                disabled={isDeletingSheet}
                className="btn btn-ghost" 
                style={{ padding:'8px 16px', fontSize:'12px' }}
              >
                Cancel
              </button>
              <button 
                onClick={confirmDeleteSheet} 
                disabled={isDeletingSheet}
                className="btn" 
                style={{ 
                  padding:'8px 18px', fontSize:'12px', fontWeight:600,
                  background: 'var(--red)', color: '#fff', border: 'none',
                  opacity: isDeletingSheet ? 0.7 : 1, cursor: isDeletingSheet ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', gap: 6
                }}
              >
                {isDeletingSheet ? 'Deleting...' : 'Delete Sheet'}
              </button>
            </div>
          </div>
        </>
      )}

    </div>
  );
}

const selectStyle = {
  background: 'var(--bg-surface)',
  border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--r-md)',
  padding: '0 12px',
  height: 38,
  color: 'var(--text-1)',
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

