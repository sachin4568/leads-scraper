'use client';
import { Lead, ServiceType, SERVICE_LABELS } from '../lib/data';

const SC: Record<string,{bg:string;text:string}> = {
  new:{bg:'rgba(148,163,184,.12)',text:'#94a3b8'},assigned:{bg:'rgba(96,165,250,.12)',text:'#60a5fa'},
  called:{bg:'rgba(245,158,11,.12)',text:'#fbbf24'},warm:{bg:'rgba(236,72,153,.15)',text:'#f472b6'},converted:{bg:'rgba(34,197,94,.12)',text:'#4ade80'},
};

export function LeadDetailDrawer({ lead, service, onClose }: { lead: Lead; service: ServiceType; onClose: () => void }) {
  return (
    <>
      <div onClick={onClose} style={{ position:'fixed',inset:0,zIndex:200 }} />
      <div style={{ position:'fixed',top:0,right:0,bottom:0,width:'min(440px,92vw)',background:'var(--bg-elevated)',borderLeft:'1px solid var(--border-subtle)',zIndex:201,display:'flex',flexDirection:'column',overflow:'hidden',boxShadow:'-20px 0 60px rgba(0,0,0,.5)' }}>
        {/* Header */}
        <div style={{ padding:'18px 22px',borderBottom:'1px solid var(--border-faint)',display:'flex',alignItems:'flex-start',justifyContent:'space-between' }}>
          <div>
            <div style={{ fontSize:'14px',fontWeight:700,color:'var(--text-1)',marginBottom:3 }}>{lead.businessName}</div>
            <div style={{ display:'flex',alignItems:'center',gap:6 }}>
              <span style={{ fontFamily:'monospace',fontSize:'10px',color:'var(--text-3)' }}>{lead.leadId}</span>
              <span className="pill" style={{ background:SC[lead.status].bg,color:SC[lead.status].text,textTransform:'capitalize',fontSize:'9px' }}>{lead.status}</span>
            </div>
          </div>
          <button onClick={onClose} style={{ width:28,height:28,display:'flex',alignItems:'center',justifyContent:'center',borderRadius:'var(--r-md)',color:'var(--text-3)' }}
            onMouseEnter={e=>(e.currentTarget.style.background='var(--bg-hover)')} onMouseLeave={e=>(e.currentTarget.style.background='transparent')}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <div style={{ flex:1,overflow:'auto',padding:'18px 22px' }}>
          {/* Scores */}
          <div style={{ display:'flex',gap:10,marginBottom:20 }}>
            <Score label="Priority" value={`${lead.priorityScore}`} color={lead.priorityScore>=80?'var(--green)':lead.priorityScore>=60?'var(--amber)':'var(--text-2)'} />
            <Score label="Genuineness" value={`${lead.genuineness}%`} color="var(--pink-light)" />
            {lead.seoScore!==undefined && <Score label="SEO Score" value={`${lead.seoScore}`} color={lead.seoScore<35?'var(--red)':lead.seoScore<60?'var(--amber)':'var(--green)'} />}
            {lead.socialScore!==undefined && <Score label="Social Score" value={`${lead.socialScore}`} color="var(--purple)" />}
          </div>

          <Sec title="Contact Information">
            <Row label="Location" value={lead.location} />
            {lead.contactPhone && <Row label="Phone" value={lead.contactPhone} highlight />}
            {lead.contactEmail && <Row label="Email" value={lead.contactEmail} highlight />}
            {lead.websiteUrl && <Row label="Website" value={lead.websiteUrl} isLink href={`https://${lead.websiteUrl}`} />}
          </Sec>

          {(lead.instagramHandle||lead.facebookHandle) && (
            <Sec title="Social Media">
              {lead.instagramHandle && <Row label="Instagram" value={lead.instagramHandle} isLink href={`https://instagram.com/${lead.instagramHandle.replace('@','')}`} />}
              {lead.facebookHandle && <Row label="Facebook" value={lead.facebookHandle} isLink href={`https://facebook.com/${lead.facebookHandle}`} />}
              {lead.followersCount && <Row label="Followers" value={lead.followersCount.toLocaleString()} />}
            </Sec>
          )}

          <Sec title="Service Context">
            <Row label="Service" value={SERVICE_LABELS[service]} />
            <Row label="Source" value={lead.source.replace('_',' ')} />
            <Row label="Added" value={lead.addedAt} />
          </Sec>

          <Sec title="Notes">
            <textarea placeholder="Add call notes…" defaultValue={lead.notes||''} style={{ width:'100%',background:'var(--bg-input)',border:'1px solid var(--border-subtle)',borderRadius:'var(--r-md)',padding:'10px',fontSize:'12px',color:'var(--text-2)',resize:'vertical',minHeight:80,outline:'none',lineHeight:1.6 }}
              onFocus={e=>(e.currentTarget.style.borderColor='var(--border-pink)')}
              onBlur={e=>(e.currentTarget.style.borderColor='var(--border-subtle)')}
            />
          </Sec>
        </div>

        <div style={{ padding:'14px 22px',borderTop:'1px solid var(--border-faint)',display:'flex',gap:8,flexShrink:0 }}>
          <button className="btn btn-pink" style={{ flex:1,justifyContent:'center' }}>Mark Called</button>
          <button className="btn btn-ghost" style={{ flex:1,justifyContent:'center' }}>Mark Warm</button>
        </div>
      </div>
    </>
  );
}

function Sec({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom:20 }}>
      <div style={{ fontSize:'9px',fontWeight:700,textTransform:'uppercase',letterSpacing:'.09em',color:'var(--text-4)',marginBottom:10 }}>{title}</div>
      {children}
    </div>
  );
}
function Row({ label, value, highlight, isLink, href }: { label:string; value:string; highlight?: boolean; isLink?: boolean; href?: string }) {
  return (
    <div style={{ display:'flex',justifyContent:'space-between',padding:'7px 0',borderBottom:'1px solid var(--border-faint)',gap:16 }}>
      <span style={{ fontSize:'12px',color:'var(--text-3)',flexShrink:0 }}>{label}</span>
      {isLink && href
        ? <a href={href} target="_blank" rel="noreferrer" style={{ fontSize:'12px',color:'var(--blue)',textAlign:'right',wordBreak:'break-all' }}>{value}</a>
        : <span style={{ fontSize:'12px',color:highlight?'var(--text-1)':'var(--text-2)',fontWeight:highlight?600:400,textAlign:'right',wordBreak:'break-all' }}>{value}</span>
      }
    </div>
  );
}
function Score({ label, value, color }: { label:string; value:string; color:string }) {
  return (
    <div style={{ flex:1,background:'var(--bg-card)',border:'1px solid var(--border-subtle)',borderRadius:'var(--r-lg)',padding:'12px',textAlign:'center' }}>
      <div style={{ fontSize:'20px',fontWeight:800,color,marginBottom:2 }}>{value}</div>
      <div style={{ fontSize:'9px',textTransform:'uppercase',letterSpacing:'.07em',color:'var(--text-3)' }}>{label}</div>
    </div>
  );
}
