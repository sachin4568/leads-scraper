"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function HeaderNavigation() {
  const pathname = usePathname();
  const [isServicesOpen, setIsServicesOpen] = useState(false);

  const navItems = [
    { label: "Dashboard", href: "/" },
    { label: "Raw Leads", href: "/raw-leads" },
    {
      label: "Services",
      isDropdown: true,
      children: [
        { label: "Website Development", href: "/services/website-development" },
        { label: "Website SEO", href: "/services/website-seo" },
        { label: "Social Media Management", href: "/services/social-media-management" },
        { label: "Social Media Marketing", href: "/services/social-media-marketing" },
      ],
    },
    { label: "Scraping", href: "/#scraping" },
    { label: "Outreach", href: "/#outreach" },
    { label: "Analytics", href: "/#analytics" },
    { label: "Governance", href: "/#governance" },
  ];

  return (
    <header className="bg-slate-900 border-b border-slate-800 text-white sticky top-0 z-50 shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-lg text-white shadow-sm">
            L
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
              Lead Intelligence System
            </span>
            <span className="ml-2 px-2 py-0.5 text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full">
              Post-Phase 17
            </span>
          </div>
        </div>

        <nav className="hidden md:flex items-center space-x-1">
          {navItems.map((item) => {
            if (item.isDropdown) {
              return (
                <div key={item.label} className="relative">
                  <button
                    onClick={() => setIsServicesOpen(!isServicesOpen)}
                    className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center space-x-1 ${
                      pathname.startsWith("/services")
                        ? "bg-slate-800 text-indigo-400"
                        : "text-slate-300 hover:bg-slate-800 hover:text-white"
                    }`}
                  >
                    <span>{item.label}</span>
                    <svg className="w-4 h-4 fill-current" viewBox="0 0 20 20">
                      <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
                    </svg>
                  </button>

                  {isServicesOpen && (
                    <div
                      onMouseLeave={() => setIsServicesOpen(false)}
                      className="absolute left-0 mt-2 w-64 rounded-lg shadow-xl bg-slate-800 border border-slate-700 py-2 z-50"
                    >
                      {item.children?.map((sub) => (
                        <Link
                          key={sub.label || sub.href || "#"}
                          href={sub.href || "#"}
                          onClick={() => setIsServicesOpen(false)}
                          className="block px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-700 hover:text-indigo-400 transition-colors"
                        >
                          {sub.label}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              );
            }

            const itemHref = item.href || "#";
            const isActive = pathname === itemHref;
            return (
              <Link
                key={item.label || itemHref}
                href={itemHref}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-slate-800 text-indigo-400"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
