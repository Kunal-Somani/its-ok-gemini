import { useState, useEffect } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { LayoutDashboard, ListTodo, Settings as SettingsIcon, Menu, X, Terminal } from 'lucide-react';
import { format } from 'date-fns';

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const navItems = [
    { to: "/", icon: LayoutDashboard, label: "Dashboard" },
    { to: "/tasks", icon: ListTodo, label: "Tasks" },
    { to: "/settings", icon: SettingsIcon, label: "Settings" }
  ];

  return (
    <div className="flex h-screen bg-[#0a0a0f] text-slate-300 overflow-hidden font-sans">
      {/* Mobile sidebar toggle */}
      <div className="md:hidden fixed top-4 left-4 z-50">
        <button onClick={() => setMobileOpen(!mobileOpen)} className="p-2 bg-gray-800 rounded-md">
          {mobileOpen ? <X className="text-white" /> : <Menu className="text-white" />}
        </button>
      </div>

      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-40 w-64 glass-card border-r border-white/5 transform transition-transform duration-300 ease-in-out md:translate-x-0 md:static ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="h-full flex flex-col">
          <div className="p-6 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#7c3aed] flex items-center justify-center shadow-[0_0_15px_rgba(124,58,237,0.5)]">
              <Terminal size={18} className="text-white" />
            </div>
            <h1 className="text-xl font-bold tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-[#00ff9f]">
              ACC
            </h1>
          </div>

          <nav className="flex-1 px-4 py-6 space-y-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => 
                  `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                    isActive 
                      ? 'bg-white/5 text-white border-l-2 border-[#00ff9f] shadow-[inset_4px_0_0_rgba(0,255,159,0.2)]' 
                      : 'text-slate-400 hover:bg-white/5 hover:text-slate-200 border-l-2 border-transparent'
                  }`
                }
                onClick={() => setMobileOpen(false)}
              >
                {({ isActive }) => (
                  <>
                    <item.icon size={20} className={isActive ? 'text-[#00ff9f]' : ''} />
                    <span className="font-medium">{item.label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Top Header */}
        <header className="h-16 glass-card border-b border-white/5 flex items-center justify-between px-6 shrink-0 z-30">
          <div className="flex items-center gap-4 hidden md:flex pl-10 md:pl-0">
             <span className="text-sm text-slate-400 font-mono tracking-widest uppercase">Agent Command Center</span>
          </div>
          
          <div className="flex items-center gap-6 ml-auto">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-[#00ff9f] animate-pulse-dot shadow-[0_0_8px_#00ff9f]"></div>
              <span className="text-xs text-[#00ff9f] font-mono tracking-wide uppercase">System Online</span>
            </div>
            <div className="text-sm font-mono text-slate-400 hidden sm:block">
              {format(time, 'HH:mm:ss')}
            </div>
          </div>
        </header>

        {/* Scrollable Main */}
        <main className="flex-1 overflow-y-auto p-6 scrollbar-hide">
          <div className="max-w-7xl mx-auto w-full pb-10">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
