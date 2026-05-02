import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getTasks } from '../api/client';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import { Activity, CheckCircle, Clock, PieChart as PieChartIcon } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, Legend } from 'recharts';
import { format, subDays } from 'date-fns';
import { Link } from 'react-router-dom';

const STATUS_COLORS = {
  QUEUED: '#64748b',
  ANALYZING: '#3b82f6',
  GENERATING: '#7c3aed',
  DEPLOYING: '#f97316',
  SUCCESS: '#00ff9f',
  FAILED: '#ef4444'
};

export default function Dashboard() {
  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: getTasks,
    refetchInterval: 5000,
  });

  const stats = useMemo(() => {
    if (!tasks.length) return { total: 0, active: 0, queueDepth: 0, successRate: 0, avgDuration: 0, pieData: [], areaData: [] };

    const active = tasks.filter(t => !['SUCCESS', 'FAILED'].includes(t.status)).length;
    const completed = tasks.filter(t => t.status === 'SUCCESS').length;
    const failed = tasks.filter(t => t.status === 'FAILED').length;
    const successRate = completed + failed > 0 ? Math.round((completed / (completed + failed)) * 100) : 0;
    
    const durations = tasks.filter(t => t.duration_seconds).map(t => t.duration_seconds!);
    const avgDuration = durations.length > 0 ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) : 0;

    const statusCounts = tasks.reduce((acc, t) => {
      acc[t.status] = (acc[t.status] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    const pieData = Object.entries(statusCounts).map(([name, value]) => ({ name, value }));

    const areaData = [];
    for (let i = 6; i >= 0; i--) {
      const date = subDays(new Date(), i);
      const dateStr = format(date, 'MMM dd');
      const dayTasks = tasks.filter(t => format(new Date(t.created_at), 'MMM dd') === dateStr);
      areaData.push({
        date: dateStr,
        SUCCESS: dayTasks.filter(t => t.status === 'SUCCESS').length,
        FAILED: dayTasks.filter(t => t.status === 'FAILED').length,
        OTHER: dayTasks.filter(t => !['SUCCESS', 'FAILED'].includes(t.status)).length,
      });
    }

    return { total: tasks.length, active, queueDepth: tasks.filter(t => ['QUEUED', 'ANALYZING'].includes(t.status)).length, successRate, avgDuration, pieData, areaData };
  }, [tasks]);

  const recentTasks = tasks.slice(0, 5);

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Total Tasks" value={stats.total} icon={PieChartIcon} colorTheme="purple" />
        <StatCard title="Success Rate" value={`${stats.successRate}%`} icon={CheckCircle} colorTheme="green" />
        <div className={`transition-all duration-1000 ${stats.queueDepth > 0 ? 'shadow-[0_0_20px_rgba(249,115,22,0.3)] rounded-xl' : ''}`}>
          <StatCard title="Queue Depth" value={stats.queueDepth} icon={Activity} colorTheme="orange" />
        </div>
        <StatCard title="Avg Duration" value={`${stats.avgDuration}s`} icon={Clock} colorTheme="white" />
      </div>

      <div className="flex items-center gap-3 p-4 glass-card rounded-xl border border-white/5">
        <div className="w-2 h-2 rounded-full bg-[#00ff9f] animate-pulse"></div>
        <span className="text-sm font-medium text-slate-300">1 worker connected</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="glass-card rounded-xl p-6 lg:col-span-2">
          <h3 className="text-lg font-semibold text-white mb-6">Tasks Over Time</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={stats.areaData}>
                <defs>
                  <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={STATUS_COLORS.SUCCESS} stopOpacity={0.3}/>
                    <stop offset="95%" stopColor={STATUS_COLORS.SUCCESS} stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorFailed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={STATUS_COLORS.FAILED} stopOpacity={0.3}/>
                    <stop offset="95%" stopColor={STATUS_COLORS.FAILED} stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#0f0f16', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                <Legend />
                <Area type="monotone" dataKey="SUCCESS" stackId="1" stroke={STATUS_COLORS.SUCCESS} fill="url(#colorSuccess)" />
                <Area type="monotone" dataKey="FAILED" stackId="1" stroke={STATUS_COLORS.FAILED} fill="url(#colorFailed)" />
                <Area type="monotone" dataKey="OTHER" stackId="1" stroke={STATUS_COLORS.ANALYZING} fill="transparent" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass-card rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white mb-6">Distribution</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={stats.pieData} innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                  {stats.pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={STATUS_COLORS[entry.name as keyof typeof STATUS_COLORS] || '#ffffff'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: '#0f0f16', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="glass-card rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Recent Activity</h3>
        <div className="space-y-3">
          {recentTasks.map(task => (
            <Link key={task.id} to={`/tasks/${task.id}`} className="block">
              <div className="flex items-center justify-between p-4 rounded-lg bg-white/5 border border-white/5 hover:bg-white/10 transition-colors">
                <div className="flex items-center gap-4">
                  <StatusBadge status={task.status} />
                  <span className="font-medium text-slate-200">{task.task_name}</span>
                </div>
                <span className="text-sm text-slate-500 font-mono">{format(new Date(task.created_at), 'HH:mm:ss')}</span>
              </div>
            </Link>
          ))}
          {!recentTasks.length && !isLoading && <p className="text-slate-500 italic">No tasks found.</p>}
        </div>
      </div>
    </div>
  );
}
