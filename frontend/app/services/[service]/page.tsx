"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import LeadIntelligenceDrawer from "../../components/LeadIntelligenceDrawer";

export default function DedicatedServiceWorkspacePage() {
  const params = useParams();
  const serviceSlug = (params.service as string) || "website-development";

  const [leads, setLeads] = useState<any[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const titleMap: Record<string, { title: string; subtitle: string; primaryQuestion: string }> = {
    "website-development": {
      title: "Website Development Workspace",
      subtitle: "Targeting businesses needing a website with active social presence",
      primaryQuestion: "Which businesses need a website?",
    },
    "website-seo": {
      title: "Website SEO Workspace",
      subtitle: "Targeting active websites with technical & SSL optimization gaps",
      primaryQuestion: "Which businesses already have websites but have SEO problems?",
    },
    "social-media-management": {
      title: "Social Media Management Workspace",
      subtitle: "Targeting neglected social media channels relative to customer reach",
      primaryQuestion: "Which businesses need help managing their social media?",
    },
    "social-media-marketing": {
      title: "Social Media Marketing Workspace",
      subtitle: "Targeting high commercial intent & active ad campaign candidates",
      primaryQuestion: "Which businesses are good candidates for paid advertising?",
    },
  };

  const currentInfo = titleMap[serviceSlug] || {
    title: "Service Opportunity Workspace",
    subtitle: "Specialized service lead workspace",
    primaryQuestion: "Which businesses present high service opportunity?",
  };

  useEffect(() => {
    fetch(`http://localhost:8000/api/v1/services/${serviceSlug}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.records && data.records.length > 0) {
          setLeads(data.records);
        } else {
          setLeads([]);
        }
      })
      .catch(() => {});
  }, [serviceSlug]);

  const handleRowClick = (leadId: string) => {
    setSelectedLeadId(leadId);
    setDrawerOpen(true);
  };

  return (
    <div className="content space-y-8 max-w-7xl mx-auto font-sans text-white p-2">
      {/* PAGE HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#27272A] pb-4">
        <div>
          <span className="text-[10px] font-extrabold text-[#EC4899] uppercase tracking-wider">
            PRIMARY QUESTION: {currentInfo.primaryQuestion}
          </span>
          <h2 className="text-2xl font-extrabold text-white tracking-tight mt-0.5">
            {currentInfo.title}
          </h2>
          <p className="text-xs text-[#A1A1AA] mt-0.5">{currentInfo.subtitle}</p>
        </div>

        <div className="flex items-center space-x-3">
          <a
            href={`http://localhost:8000/api/v1/exports/${serviceSlug}`}
            className="px-4 py-2 bg-[#151515] border border-[#27272A] text-xs font-semibold text-white rounded-xl hover:border-[#3F3F46] flex items-center space-x-2"
          >
            <svg className="w-3.5 h-3.5 text-[#A1A1AA]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span>Export Service CSV</span>
          </a>
        </div>
      </div>

      {/* SPECIALIZED SERVICE TABLE */}
      <div className="glass-panel p-6 space-y-4">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-[#D4D4D8]">
            <thead className="bg-[#18181C] text-[#A1A1AA] uppercase text-[11px] font-bold tracking-wider border-b border-[#27272A]">
              <tr>
                <th className="py-4 px-5">Business</th>

                {serviceSlug === "website-development" && (
                  <>
                    <th className="py-4 px-5">Location</th>
                    <th className="py-4 px-5">Website</th>
                    <th className="py-4 px-5">Social</th>
                    <th className="py-4 px-5">Followers</th>
                    <th className="py-4 px-5">Email</th>
                    <th className="py-4 px-5">Phone</th>
                  </>
                )}

                {serviceSlug === "website-seo" && (
                  <>
                    <th className="py-4 px-5">Website</th>
                    <th className="py-4 px-5">SEO Score</th>
                    <th className="py-4 px-5">SSL</th>
                    <th className="py-4 px-5">Technical Issues</th>
                    <th className="py-4 px-5">Email</th>
                    <th className="py-4 px-5">Phone</th>
                  </>
                )}

                {serviceSlug === "social-media-management" && (
                  <>
                    <th className="py-4 px-5">Instagram</th>
                    <th className="py-4 px-5">Facebook</th>
                    <th className="py-4 px-5">Followers</th>
                    <th className="py-4 px-5">Activity</th>
                    <th className="py-4 px-5">Engagement</th>
                    <th className="py-4 px-5">Contact</th>
                  </>
                )}

                {serviceSlug === "social-media-marketing" && (
                  <>
                    <th className="py-4 px-5">Platform</th>
                    <th className="py-4 px-5">Followers</th>
                    <th className="py-4 px-5">Engagement</th>
                    <th className="py-4 px-5">Ads Active</th>
                    <th className="py-4 px-5">Contactability</th>
                  </>
                )}

                <th className="py-4 px-5 text-right">Opportunity Score</th>
                <th className="py-4 px-5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#27272A]/40 font-medium">
              {leads.map((l, idx) => {
                const isHighWebDevOpp =
                  serviceSlug === "website-development" &&
                  l.website_available === "N" &&
                  (l.instagram_available === "Y" || l.facebook_available === "Y");

                return (
                  <tr
                    key={l.canonical_lead_id || idx}
                    className="hover:bg-[#18181C] cursor-pointer transition-none"
                    onClick={() => handleRowClick(l.canonical_lead_id)}
                  >
                    <td className="py-4 px-5 font-bold text-white">
                      <div>{l.business_name}</div>
                      {isHighWebDevOpp && (
                        <span className="text-[10px] font-extrabold text-[#EC4899] uppercase tracking-wider">
                          ★ High Opportunity (No Web + Social Y)
                        </span>
                      )}
                    </td>

                    {serviceSlug === "website-development" && (
                      <>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.location}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.website_available}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">
                          {l.instagram_available === "Y" ? "IG" : ""}{" "}
                          {l.facebook_available === "Y" ? "FB" : ""}
                        </td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.followers || "N/A"}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.email || "N/A"}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.phone || "N/A"}</td>
                      </>
                    )}

                    {serviceSlug === "website-seo" && (
                      <>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.website_available}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.seo_score || 45} / 100</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.ssl_valid || "N"}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">
                          {l.technical_issues || "Schema Gaps"}
                        </td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.email || "N/A"}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.phone || "N/A"}</td>
                      </>
                    )}

                    {serviceSlug === "social-media-management" && (
                      <>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.instagram_available}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.facebook_available}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.followers || "N/A"}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.activity || "Inactive"}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.engagement || "1.5%"}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.phone || l.email || "N/A"}</td>
                      </>
                    )}

                    {serviceSlug === "social-media-marketing" && (
                      <>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.platform || "IG / FB"}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.followers || "N/A"}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.engagement || "1.5%"}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.ads_active || "N"}</td>
                        <td className="py-4 px-5 text-[#A1A1AA]">{l.contactability || "High"}</td>
                      </>
                    )}

                    <td className="py-4 px-5 text-right font-extrabold text-white">
                      {l.service_score || 79}
                    </td>

                    <td className="py-4 px-5 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRowClick(l.canonical_lead_id);
                        }}
                        className="px-3 py-1.5 rounded-lg bg-[#EC4899] text-white text-xs font-bold shadow-sm"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* LEAD INTELLIGENCE DRAWER */}
      <LeadIntelligenceDrawer
        lead={leads.find((l: any) => l.leadId === selectedLeadId || l.id === selectedLeadId) || null}
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
