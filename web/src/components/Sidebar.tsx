import { NavLink } from 'react-router-dom';
import { Activity, Settings, FileText, Box } from 'lucide-react';

export default function Sidebar() {
  const navItems = [
    { name: 'Analysis Matrix', path: '/', icon: <Activity className="w-5 h-5" /> },
    { name: 'History Reports', path: '/history', icon: <FileText className="w-5 h-5" /> },
    { name: 'Configuration', path: '/settings', icon: <Settings className="w-5 h-5" /> },
  ];

  return (
    <div className="w-64 bg-surface-containerLowest border-r border-border min-h-[100dvh] flex flex-col shadow-[1px_0_12px_rgba(0,0,0,0.02)] relative z-10">
      <div className="p-6 flex items-center gap-3 border-b border-surface-containerLow">
        <div className="p-2 bg-primary rounded-xl text-white shadow-sm">
          <Box className="w-5 h-5" />
        </div>
        <div className="flex flex-col">
          <h2 className="text-lg font-bold tracking-tight text-foreground leading-tight">Radar</h2>
          <span className="text-[10px] uppercase tracking-wider text-onSurface-variant font-semibold">Intelligence</span>
        </div>
      </div>
      
      <nav className="flex-1 p-4 space-y-1.5">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-primary/10 text-primary shadow-[inset_2px_0_0_0_hsl(var(--primary))]'
                  : 'text-onSurface-variant hover:bg-surface-containerLow hover:text-foreground'
              }`
            }
          >
            {item.icon}
            {item.name}
          </NavLink>
        ))}
      </nav>
      
      <div className="p-6 border-t border-surface-containerLow text-xs text-surface-dim font-medium text-center">
        Radar OS v2.0.0
      </div>
    </div>
  );
}
