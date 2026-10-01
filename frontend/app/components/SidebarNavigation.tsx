'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React, { useState } from 'react';

const I: Record<string, React.ReactNode> = {
  bolt: <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M13 2L4.5 13.5H12L11 22L19.5 10.5H12L13 2Z" fill="#ec4899" stroke="#ec4899" strokeWidth="1.2" strokeLinejoin="round"/></svg>,
  menu: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>,
  grid: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>,
  users: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="9" cy="7" r="4"/><path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"/><path d="M16 3.13a4 4 0 0 1 0 7.75M21 21v-2a4 4 0 0 0-3-3.87"/></svg>,
  ops: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>,
  file: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>,
  wave: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><polyline points="22,12 18,12 15,21 9,3 6,12 2,12"/></svg>,
  monitor: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>,
  circle: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9"/></svg>,
  gear: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>,
  table: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2v-4M9 21H5a2 2 0 0 1-2-2v-4m0 0h18"/></svg>,
  plus: <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
};

interface NavItemProps {
  href: string;
  icon: React.ReactNode;
  label: string;
  isPlus?: boolean;
  isExpanded: boolean;
}

function NavItem({ href, icon, label, isPlus, isExpanded }: NavItemProps) {
  const path = usePathname();
  const active = path === href || (href !== '/' && path.startsWith(href));
  return (
    <Link href={href}>
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: '9px',
          padding: '7px 10px', borderRadius: 'var(--r-md)',
          background: active ? 'var(--pink)' : 'transparent',
          color: active ? '#fff' : 'var(--text-2)',
          fontWeight: active ? 500 : 400, fontSize: '13px',
          transition: 'background var(--ease), color var(--ease)',
          cursor: 'pointer', userSelect: 'none',
        }}
        onMouseEnter={e => {
          if (!active) {
            (e.currentTarget as HTMLDivElement).style.background = 'var(--bg-hover)';
            (e.currentTarget as HTMLDivElement).style.color = 'var(--text-1)';
          }
        }}
        onMouseLeave={e => {
          if (!active) {
            (e.currentTarget as HTMLDivElement).style.background = 'transparent';
            (e.currentTarget as HTMLDivElement).style.color = 'var(--text-2)';
          }
        }}
      >
        <span style={{ display: 'flex', flexShrink: 0, justifyContent: 'center', width: isExpanded ? 'auto' : '100%' }}>{isPlus ? I.plus : icon}</span>
        {isExpanded && <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>}
      </div>
    </Link>
  );
}

function Section({ label, children, isExpanded }: { label: string; children: React.ReactNode; isExpanded: boolean }) {
  return (
    <div style={{ marginTop: '20px' }}>
      {isExpanded && (
        <div style={{
          fontSize: '10px', fontWeight: 600, letterSpacing: '0.09em',
          textTransform: 'uppercase', color: 'var(--text-4)',
          padding: '0 10px', marginBottom: '4px',
        }}>{label}</div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>{children}</div>
    </div>
  );
}

export function SidebarNavigation() {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <nav style={{
      width: isExpanded ? 'var(--sidebar)' : '54px', flexShrink: 0, height: '100vh',
      background: 'transparent', borderRight: 'none',
      display: 'flex', flexDirection: 'column', padding: '14px 10px', overflow: 'hidden',
      transition: 'width 0.2s ease',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: isExpanded ? 'flex-end' : 'center',
        padding: '2px 4px 14px', borderBottom: '1px solid var(--border-faint)', marginBottom: '4px',
      }}>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          style={{ color: 'var(--text-3)', display: 'flex', alignItems: 'center', padding: '4px' }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-1)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-3)'; }}
        >{I.menu}</button>
      </div>
      <div style={{ flex: 1, overflow: 'auto', overflowX: 'hidden' }}>
        <Section label="Leads & Revenue Lifecycle" isExpanded={isExpanded}>
          <NavItem href="/leads"            icon={I.users}   label="Leads" isExpanded={isExpanded} />
          <NavItem href="/operations"       icon={I.ops}     label="Operations" isExpanded={isExpanded} />
          <NavItem href="/operations/leads" icon={I.file}    label="Lead Operations" isExpanded={isExpanded} />
          <NavItem href="/crm"              icon={I.grid}    label="CRM Pipeline" isExpanded={isExpanded} />
          <NavItem href="/proposals"        icon={I.file}    label="Proposals & Quotes" isExpanded={isExpanded} />
          <NavItem href="/delivery"         icon={I.monitor} label="Delivery & Projects" isExpanded={isExpanded} />
          <NavItem href="/success"          icon={I.wave}    label="Customer Success & MRR" isExpanded={isExpanded} />
          <NavItem href="/outreach"         icon={I.wave}    label="Outreach Funnel" isExpanded={isExpanded} />
        </Section>
        <Section label="Intelligence & Analytics" isExpanded={isExpanded}>
          <NavItem href="/analytics"    icon={I.monitor} label="Executive Analytics" isExpanded={isExpanded} />
          <NavItem href="/intelligence" icon={I.file}    label="Intelligence" isExpanded={isExpanded} />
          <NavItem href="/system"       icon={I.circle}  label="System" isExpanded={isExpanded} />
        </Section>
        <Section label="System" isExpanded={isExpanded}>
          <NavItem href="/operations/observability" icon={I.monitor} label="Observability & Health" isExpanded={isExpanded} />
          <NavItem href="/system/logic"     icon={I.circle} label="Logic" isExpanded={isExpanded} />
          <NavItem href="/system/settings"  icon={I.gear}   label="Lead Settings" isExpanded={isExpanded} />
          <NavItem href="/system/lamicales" icon={I.table}  label="Lamicales" isExpanded={isExpanded} />
        </Section>
      </div>
    </nav>
  );
}
