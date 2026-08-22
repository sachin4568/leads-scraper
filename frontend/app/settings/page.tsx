"use client";

import React, { useState } from "react";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("api");
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Form states for settings
  const [googleKey, setGoogleKey] = useState("AIzaSyB_configured_key_xxxx");
  const [yelpKey, setYelpKey] = useState("yelp_fusion_active_token_xxxx");
  const [foursquareKey, setFoursquareKey] = useState("fsq3_configured_active");
  const [smtpHost, setSmtpHost] = useState("smtp.leadintel.app");
  const [smtpPort, setSmtpPort] = useState("587");
  const [senderEmail, setSenderEmail] = useState("outreach@leadintel.app");
  const [genuinenessThreshold, setGenuinenessThreshold] = useState("70");
  const [priorityScoreCutoff, setPriorityScoreCutoff] = useState("60");
  const [exportFormat, setExportFormat] = useState("csv");

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto font-sans text-white p-2">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#27272A] pb-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">System Settings & Parameters</h2>
          <p className="text-xs text-[#A1A1AA] mt-0.5">
            Manage provider credentials, API integration keys, email SMTP parameters, and ML cutoffs
          </p>
        </div>
        {saveSuccess && (
          <div className="px-3.5 py-1.5 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-bold flex items-center space-x-2">
            <span>✓ Settings saved successfully!</span>
          </div>
        )}
      </div>

      {/* Settings Navigation Tabs */}
      <div className="flex space-x-2 border-b border-[#27272A] pb-3 text-xs font-bold">
        <button
          onClick={() => setActiveTab("api")}
          className={`px-4 py-2 rounded-xl transition-all ${
            activeTab === "api"
              ? "bg-[#EC4899] text-white shadow-md shadow-[#EC4899]/20"
              : "bg-[#121215] text-[#A1A1AA] hover:text-white border border-[#27272A]"
          }`}
        >
          🔑 API Credentials
        </button>
        <button
          onClick={() => setActiveTab("smtp")}
          className={`px-4 py-2 rounded-xl transition-all ${
            activeTab === "smtp"
              ? "bg-[#EC4899] text-white shadow-md shadow-[#EC4899]/20"
              : "bg-[#121215] text-[#A1A1AA] hover:text-white border border-[#27272A]"
          }`}
        >
          📧 Email Outreach (SMTP)
        </button>
        <button
          onClick={() => setActiveTab("ml")}
          className={`px-4 py-2 rounded-xl transition-all ${
            activeTab === "ml"
              ? "bg-[#EC4899] text-white shadow-md shadow-[#EC4899]/20"
              : "bg-[#121215] text-[#A1A1AA] hover:text-white border border-[#27272A]"
          }`}
        >
          🤖 ML & Thresholds
        </button>
        <button
          onClick={() => setActiveTab("sheets")}
          className={`px-4 py-2 rounded-xl transition-all ${
            activeTab === "sheets"
              ? "bg-[#EC4899] text-white shadow-md shadow-[#EC4899]/20"
              : "bg-[#121215] text-[#A1A1AA] hover:text-white border border-[#27272A]"
          }`}
        >
          📊 Google Sheets Sync
        </button>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* TAB 1: API KEYS */}
        {activeTab === "api" && (
          <div className="space-y-4">
            <div className="glass-panel p-6 space-y-4 rounded-2xl border border-[#27272A] bg-[#121215]">
              <div className="text-xs font-bold text-white uppercase tracking-wider">
                Scraping & Data Provider API Keys
              </div>
              <div className="space-y-4 text-xs">
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-[#A1A1AA]">Google Places API Key</label>
                  <input
                    type="password"
                    value={googleKey}
                    onChange={(e) => setGoogleKey(e.target.value)}
                    className="w-full bg-[#18181C] border border-[#27272A] rounded-xl p-3 text-white font-mono focus:outline-none focus:border-[#EC4899]"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-[#A1A1AA]">Yelp Fusion API Key</label>
                  <input
                    type="password"
                    value={yelpKey}
                    onChange={(e) => setYelpKey(e.target.value)}
                    className="w-full bg-[#18181C] border border-[#27272A] rounded-xl p-3 text-white font-mono focus:outline-none focus:border-[#EC4899]"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-[#A1A1AA]">Foursquare Places API Key</label>
                  <input
                    type="password"
                    value={foursquareKey}
                    onChange={(e) => setFoursquareKey(e.target.value)}
                    className="w-full bg-[#18181C] border border-[#27272A] rounded-xl p-3 text-white font-mono focus:outline-none focus:border-[#EC4899]"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: SMTP OUTREACH */}
        {activeTab === "smtp" && (
          <div className="space-y-4">
            <div className="glass-panel p-6 space-y-4 rounded-2xl border border-[#27272A] bg-[#121215]">
              <div className="text-xs font-bold text-white uppercase tracking-wider">
                Outreach Email Server (SMTP)
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-[#A1A1AA]">SMTP Host</label>
                  <input
                    type="text"
                    value={smtpHost}
                    onChange={(e) => setSmtpHost(e.target.value)}
                    className="w-full bg-[#18181C] border border-[#27272A] rounded-xl p-3 text-white focus:outline-none focus:border-[#EC4899]"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-[#A1A1AA]">SMTP Port</label>
                  <input
                    type="text"
                    value={smtpPort}
                    onChange={(e) => setSmtpPort(e.target.value)}
                    className="w-full bg-[#18181C] border border-[#27272A] rounded-xl p-3 text-white focus:outline-none focus:border-[#EC4899]"
                  />
                </div>
                <div className="space-y-1.5 md:col-span-2">
                  <label className="text-[11px] font-bold text-[#A1A1AA]">Sender Email Address</label>
                  <input
                    type="email"
                    value={senderEmail}
                    onChange={(e) => setSenderEmail(e.target.value)}
                    className="w-full bg-[#18181C] border border-[#27272A] rounded-xl p-3 text-white focus:outline-none focus:border-[#EC4899]"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: ML THRESHOLDS */}
        {activeTab === "ml" && (
          <div className="space-y-4">
            <div className="glass-panel p-6 space-y-4 rounded-2xl border border-[#27272A] bg-[#121215]">
              <div className="text-xs font-bold text-white uppercase tracking-wider">
                Machine Learning & Scoring Thresholds
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-[#A1A1AA]">
                    Genuineness Confidence Cutoff (%)
                  </label>
                  <input
                    type="number"
                    value={genuinenessThreshold}
                    onChange={(e) => setGenuinenessThreshold(e.target.value)}
                    className="w-full bg-[#18181C] border border-[#27272A] rounded-xl p-3 text-white focus:outline-none focus:border-[#EC4899]"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-[#A1A1AA]">
                    Priority Score Cutoff (0-100)
                  </label>
                  <input
                    type="number"
                    value={priorityScoreCutoff}
                    onChange={(e) => setPriorityScoreCutoff(e.target.value)}
                    className="w-full bg-[#18181C] border border-[#27272A] rounded-xl p-3 text-white focus:outline-none focus:border-[#EC4899]"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: GOOGLE SHEETS */}
        {activeTab === "sheets" && (
          <div className="space-y-4">
            <div className="glass-panel p-6 space-y-4 rounded-2xl border border-[#27272A] bg-[#121215]">
              <div className="text-xs font-bold text-white uppercase tracking-wider">
                Google Sheets Automated Export Sync
              </div>
              <p className="text-xs text-[#A1A1AA]">
                Connect your Google Account to automatically stream qualified leads directly to Google Sheets spreadsheets.
              </p>
              <div className="flex items-center space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => alert("Google OAuth Authentication initiated.")}
                  className="px-4 py-2.5 bg-white text-black font-bold text-xs rounded-xl flex items-center space-x-2 shadow-md hover:bg-gray-100 transition-all"
                >
                  <span>Connect Google Account 🚀</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Submit Button */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            className="px-6 py-3 bg-[#EC4899] text-white font-bold text-xs rounded-xl shadow-lg shadow-[#EC4899]/25 hover:bg-[#EC4899]/90 transition-all"
          >
            Save Configuration Settings
          </button>
        </div>
      </form>
    </div>
  );
}
