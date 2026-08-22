"use client";

import { useEffect, useRef, useState } from "react";

interface HeaderProps {
  onOpenSettings: () => void;
  onOpenRawLeads: () => void;
  onOpenHistory: () => void;
}

export function Header({ onOpenSettings, onOpenRawLeads, onOpenHistory }: HeaderProps) {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(true);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const toggleTheme = () => {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
  };

  const handleAuthToggle = () => {
    setIsLoggedIn(!isLoggedIn);
    setIsProfileOpen(false);
  };

  // Close profile dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsProfileOpen(false);
      }
    };
    if (isProfileOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isProfileOpen]);

  return (
    <header className="header-bar">
      {/* Left side: Gear icon, Raw leads button, History button */}
      <div style={{ display: "flex", alignItems: "center", gap: "18px" }}>
        <button className="gear-btn" onClick={onOpenSettings} title="Settings">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" />
          </svg>
        </button>

        <button
          onClick={onOpenRawLeads}
          style={{
            background: "none",
            border: "none",
            fontSize: "0.95rem",
            fontWeight: "600",
            color: "var(--text-dark)",
            cursor: "pointer",
            padding: "4px 8px",
          }}
        >
          Raw leads
        </button>

        <button
          onClick={onOpenHistory}
          style={{
            background: "none",
            border: "none",
            fontSize: "0.95rem",
            fontWeight: "600",
            color: "var(--text-dark)",
            cursor: "pointer",
            padding: "4px 8px",
          }}
        >
          History
        </button>
      </div>

      {/* Right side: Profile Icon with Click-Outside Dropdown */}
      <div className="profile-container" ref={dropdownRef}>
        <div
          className="profile-avatar"
          onClick={() => setIsProfileOpen(!isProfileOpen)}
        >
          👤
        </div>

        {isProfileOpen && (
          <div className="profile-dropdown">
            <div
              style={{
                padding: "8px 12px",
                borderBottom: "1px solid var(--border-color)",
                marginBottom: "4px",
              }}
            >
              <div style={{ fontWeight: "600", fontSize: "0.85rem", color: "var(--text-dark)" }}>
                {isLoggedIn ? "Admin User" : "Not logged in"}
              </div>
            </div>

            <button className="dropdown-item" onClick={handleAuthToggle}>
              {isLoggedIn ? "Logout" : "Login"}
            </button>

            <button className="dropdown-item" onClick={toggleTheme}>
              {theme === "light" ? "Dark Theme" : "Light Theme"}
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
