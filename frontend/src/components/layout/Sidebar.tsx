import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Network,
  MessageSquare,
  Upload,
} from 'lucide-react';

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/graph', icon: Network, label: 'Knowledge Graph' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/ingest', icon: Upload, label: 'Upload' },

];

export default function Sidebar() {
  return (
    <aside className="w-64 bg-white border-r border-slate-200 flex flex-col min-h-screen">
      <div className="px-6 py-6 border-b border-slate-200">
        <h1 className="text-xl font-bold text-primary flex items-center gap-2">
          <span className="text-2xl">🎨</span>
          Clinical Picasso
        </h1>
        <p className="text-xs text-muted mt-1">Document Intelligence Platform</p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-50 text-primary'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-6 py-4 border-t border-slate-200">
        <p className="text-[10px] text-slate-400 leading-tight">
          Powered by OmniGraph + Claude
          <br />
          Biorce Hackathon 2026
        </p>
      </div>
    </aside>
  );
}
