import type { Metadata } from 'next';
import './globals.css';
import { SidebarNavigation } from './components/SidebarNavigation';
import { TopBar } from './components/TopBar';

export const metadata: Metadata = {
  title: 'Leads — Dashboard',
  description: 'AI-Powered Lead Generation System',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="layout" style={{ background: 'var(--bg-nav)' }}>
          <SidebarNavigation />
          <div style={{ flex:1, display:'flex', flexDirection:'column', overflow:'hidden' }}>
            <TopBar />
            <main style={{ flex:1, overflow:'auto', padding:'28px 32px', background:'var(--bg-base)', borderTopLeftRadius: '24px', boxShadow: '-2px -2px 10px rgba(0,0,0,0.02)' }}>
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
