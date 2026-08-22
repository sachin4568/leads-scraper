"use client";

import React from "react";

export default function GovernancePage() {
  return (
    <div className="space-y-8 max-w-6xl mx-auto font-sans text-white p-2">
      {/* PAGE HEADER */}
      <div className="border-b border-[#27272A] pb-4">
        <h2 className="text-2xl font-extrabold text-white tracking-tight">
          Production Governance & Compliance
        </h2>
        <p className="text-xs text-[#A1A1AA] mt-1">
          Security workspace: Systemic governance controls, kill switches, and immutable audit safety rules
        </p>
      </div>

      {/* MANDATORY GOVERNANCE LOCKS */}
      <div className="glass-panel p-6 space-y-4">
        <div className="text-xs font-bold text-[#EC4899] uppercase tracking-wider">
          Mandatory Production Governance Locks
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="glass-card p-4 space-y-1 border-l-2 border-l-[#EC4899]">
            <div className="text-[10px] text-[#A1A1AA] uppercase">Automatic Retraining</div>
            <div className="text-xl font-extrabold text-white">DISABLED (OFF)</div>
            <div className="text-[10px] text-[#EC4899] font-bold">Lock Armed</div>
          </div>

          <div className="glass-card p-4 space-y-1 border-l-2 border-l-[#EC4899]">
            <div className="text-[10px] text-[#A1A1AA] uppercase">Champion Promotion</div>
            <div className="text-xl font-extrabold text-white">DISABLED (OFF)</div>
            <div className="text-[10px] text-[#EC4899] font-bold">Lock Armed</div>
          </div>

          <div className="glass-card p-4 space-y-1 border-l-2 border-l-[#EC4899]">
            <div className="text-[10px] text-[#A1A1AA] uppercase">Unrestricted Scraping</div>
            <div className="text-xl font-extrabold text-white">DISABLED (OFF)</div>
            <div className="text-[10px] text-[#EC4899] font-bold">Lock Armed</div>
          </div>
        </div>
      </div>

      {/* PRODUCTION STATUS & AUDIT LOG ROWS */}
      <div className="glass-panel p-6 space-y-4">
        <div className="text-xs font-bold text-[#EC4899] uppercase tracking-wider">
          Production Safety & Audit Registry
        </div>

        <div className="space-y-3 text-xs">
          <div className="glass-card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="font-bold text-white">ProductionKillSwitch (Emergency Stop)</div>
              <div className="text-[10px] text-[#A1A1AA]">Immediate system-wide execution stop guard</div>
            </div>
            <span className="px-3 py-1 bg-[#151515] border border-[#27272A] text-white font-bold rounded-lg text-xs">
              ARMED & OPERATIONAL
            </span>
          </div>

          <div className="glass-card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="font-bold text-white">BatchHealthMonitor (Drift Guard)</div>
              <div className="text-[10px] text-[#A1A1AA]">Longitudinal statistical distribution monitoring</div>
            </div>
            <span className="px-3 py-1 bg-[#151515] border border-[#27272A] text-[#EC4899] font-bold rounded-lg text-xs">
              OPERATIONAL (PSI: 0.042)
            </span>
          </div>

          <div className="glass-card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="font-bold text-white">ImmutablePredictionHistory</div>
              <div className="text-[10px] text-[#A1A1AA]">Append-only prediction history audit log</div>
            </div>
            <span className="px-3 py-1 bg-[#151515] border border-[#27272A] text-white font-bold rounded-lg text-xs">
              APPEND_ONLY (VERIFIED)
            </span>
          </div>

          <div className="glass-card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="font-bold text-white">Zero Data Loss Invariant Audit</div>
              <div className="text-[10px] text-[#A1A1AA]">Canonical identity preservation checks</div>
            </div>
            <span className="px-3 py-1 bg-[#EC4899]/15 border border-[#EC4899] text-white font-bold rounded-lg text-xs">
              PASSED (0 DATA LOSS)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
