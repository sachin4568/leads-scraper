"use client";

import React from "react";

export default function ModelIntelligencePage() {
  return (
    <div className="space-y-8 max-w-6xl mx-auto font-sans text-white p-2">
      {/* PAGE HEADER */}
      <div className="border-b border-[#27272A] pb-4">
        <h2 className="text-2xl font-extrabold text-white tracking-tight">
          Model Intelligence Registry
        </h2>
        <p className="text-xs text-[#A1A1AA] mt-1">
          Frozen Genuineness Champion & Productivity Challenger Staging Candidate registry
        </p>
      </div>

      {/* GOVERNANCE LOCKS WARNING */}
      <div className="glass-panel p-4 flex items-center justify-between text-xs border-l-2 border-l-[#EC4899]">
        <div className="space-y-0.5">
          <div className="font-extrabold text-white">GOVERNANCE LOCKS ACTIVE</div>
          <div className="text-[#A1A1AA]">
            Automatic Retraining: <span className="text-[#EC4899] font-bold">OFF</span> | Automatic Promotion: <span className="text-[#EC4899] font-bold">OFF</span>
          </div>
        </div>
        <span className="px-3 py-1 bg-[#151515] border border-[#27272A] text-white font-bold rounded-lg text-[10px] uppercase">
          READ_ONLY / FROZEN
        </span>
      </div>

      {/* MODEL 1: GENUINENESS CHAMPION */}
      <div className="glass-panel p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#27272A] pb-4">
          <div>
            <span className="text-[10px] font-bold text-[#A1A1AA] uppercase tracking-wider">
              PRIMARY CHAMPION MODEL
            </span>
            <h3 className="text-xl font-extrabold text-white">Genuineness Model</h3>
            <div className="text-xs font-bold text-[#EC4899] mt-0.5">real_model_v2_1</div>
          </div>
          <span className="px-3 py-1.5 bg-[#EC4899]/15 border border-[#EC4899] text-white rounded-xl text-xs font-bold">
            FROZEN LIMITED PRODUCTION
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          <div className="glass-card p-4 space-y-1">
            <div className="text-[10px] text-[#A1A1AA] uppercase">Ensemble Alpha</div>
            <div className="text-xl font-extrabold text-white">0.10</div>
          </div>
          <div className="glass-card p-4 space-y-1">
            <div className="text-[10px] text-[#A1A1AA] uppercase">Frozen Threshold</div>
            <div className="text-xl font-extrabold text-white">0.40</div>
          </div>
          <div className="glass-card p-4 space-y-1">
            <div className="text-[10px] text-[#A1A1AA] uppercase">Precision</div>
            <div className="text-xl font-extrabold text-white">100.0%</div>
          </div>
          <div className="glass-card p-4 space-y-1">
            <div className="text-[10px] text-[#A1A1AA] uppercase">Recall</div>
            <div className="text-xl font-extrabold text-[#EC4899]">100.0%</div>
          </div>
        </div>
      </div>

      {/* MODEL 2: PRODUCTIVITY CHALLENGER */}
      <div className="glass-panel p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#27272A] pb-4">
          <div>
            <span className="text-[10px] font-bold text-[#A1A1AA] uppercase tracking-wider">
              STAGING CHALLENGER MODEL
            </span>
            <h3 className="text-xl font-extrabold text-white">Productivity Model</h3>
            <div className="text-xs font-bold text-[#EC4899] mt-0.5">productivity_model_v1_1</div>
          </div>
          <span className="px-3 py-1.5 bg-[#151515] border border-[#27272A] text-white rounded-xl text-xs font-bold">
            FROZEN CHALLENGER STAGING CANDIDATE
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          <div className="glass-card p-4 space-y-1">
            <div className="text-[10px] text-[#A1A1AA] uppercase">Frozen Threshold</div>
            <div className="text-xl font-extrabold text-white">0.30</div>
          </div>
          <div className="glass-card p-4 space-y-1">
            <div className="text-[10px] text-[#A1A1AA] uppercase">Feature Count</div>
            <div className="text-xl font-extrabold text-white">12 Pre-prediction</div>
          </div>
          <div className="glass-card p-4 space-y-1">
            <div className="text-[10px] text-[#A1A1AA] uppercase">Specificity</div>
            <div className="text-xl font-extrabold text-white">100.0%</div>
          </div>
          <div className="glass-card p-4 space-y-1">
            <div className="text-[10px] text-[#A1A1AA] uppercase">FP Rejection</div>
            <div className="text-xl font-extrabold text-[#EC4899]">100.0%</div>
          </div>
        </div>
      </div>
    </div>
  );
}
