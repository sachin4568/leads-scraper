"use client";

import React, { useState } from "react";

export default function OutreachPage() {
  const [outreachLeads] = useState<any[]>([
    {
      id: "out-001",
      business_name: "Business Company",
      service: "Website SEO",
      contact: "(808) 355-4686",
      score: 88,
      state: "Ready for Outreach",
      outcome: "Pending",
      next_action: "Send Cold Email",
    },
    {
      id: "out-002",
      business_name: "Business Stop",
      service: "Social Media Mgt",
      contact: "(803) 399-9030",
      score: 74,
      state: "Contacted",
      outcome: "Awaiting Response",
      next_action: "Follow up in 3 days",
    },
    {
      id: "out-003",
      business_name: "Design Pust",
      service: "Website Dev",
      contact: "artik@example.com",
      score: 84,
      state: "Owner Reached",
      outcome: "Meeting Scheduled",
      next_action: "Send Pitch Deck",
    },
    {
      id: "out-004",
      business_name: "Dava Market",
      service: "Website SEO",
      contact: "(808) 397-7550",
      score: 79,
      state: "Productive",
      outcome: "Client Converted",
      next_action: "Onboarding",
    },
  ]);

  return (
    <div className="space-y-8 max-w-6xl mx-auto font-sans text-white p-2">
      {/* PAGE HEADER */}
      <div className="border-b border-[#27272A] pb-4">
        <h2 className="text-2xl font-extrabold text-white tracking-tight">Outreach Operations</h2>
        <p className="text-xs text-[#A1A1AA] mt-1">
          CRM-style outreach workflow and ground-truth productivity tracking
        </p>
      </div>

      {/* WORKFLOW STAGE METRICS */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 text-xs">
        <div className="glass-panel p-3.5 space-y-1">
          <div className="text-[10px] text-[#A1A1AA] uppercase font-bold">Ready for Outreach</div>
          <div className="text-xl font-extrabold text-white">420</div>
        </div>
        <div className="glass-panel p-3.5 space-y-1">
          <div className="text-[10px] text-[#A1A1AA] uppercase font-bold">Contacted</div>
          <div className="text-xl font-extrabold text-white">310</div>
        </div>
        <div className="glass-panel p-3.5 space-y-1">
          <div className="text-[10px] text-[#A1A1AA] uppercase font-bold">Owner Reached</div>
          <div className="text-xl font-extrabold text-[#EC4899]">145</div>
        </div>
        <div className="glass-panel p-3.5 space-y-1 border-l-2 border-l-[#EC4899]">
          <div className="text-[10px] text-[#EC4899] uppercase font-bold">Productive</div>
          <div className="text-xl font-extrabold text-white">78</div>
        </div>
        <div className="glass-panel p-3.5 space-y-1">
          <div className="text-[10px] text-[#A1A1AA] uppercase font-bold">Unproductive</div>
          <div className="text-xl font-extrabold text-[#71717A]">42</div>
        </div>
        <div className="glass-panel p-3.5 space-y-1">
          <div className="text-[10px] text-[#A1A1AA] uppercase font-bold">Not Resolved</div>
          <div className="text-xl font-extrabold text-[#71717A]">5</div>
        </div>
      </div>

      {/* OUTREACH WORKFLOW LIST */}
      <div className="glass-panel p-6 space-y-4">
        <div className="text-xs font-bold text-[#EC4899] uppercase tracking-wider">
          Active Outreach Cohort Queue
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-[#D4D4D8]">
            <thead className="bg-[#18181C] text-[#A1A1AA] uppercase text-[11px] font-bold tracking-wider border-b border-[#27272A]">
              <tr>
                <th className="py-4 px-5">Business</th>
                <th className="py-4 px-5">Service</th>
                <th className="py-4 px-5">Contact</th>
                <th className="py-4 px-5">Score</th>
                <th className="py-4 px-5">Outreach State</th>
                <th className="py-4 px-5">Outcome</th>
                <th className="py-4 px-5 text-right">Next Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#27272A]/40 font-medium">
              {outreachLeads.map((item) => (
                <tr key={item.id} className="hover:bg-[#18181C] transition-none">
                  <td className="py-4 px-5 font-bold text-white">{item.business_name}</td>
                  <td className="py-4 px-5 text-[#A1A1AA]">{item.service}</td>
                  <td className="py-4 px-5 text-[#A1A1AA]">{item.contact}</td>
                  <td className="py-4 px-5 font-extrabold text-[#EC4899]">{item.score}</td>
                  <td className="py-4 px-5 text-white font-bold">{item.state}</td>
                  <td className="py-4 px-5 text-[#A1A1AA]">{item.outcome}</td>
                  <td className="py-4 px-5 text-right">
                    <button className="px-3 py-1.5 rounded-lg bg-[#EC4899] text-white text-xs font-bold shadow-sm">
                      {item.next_action}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
