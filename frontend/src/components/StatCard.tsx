import React from 'react';
import { LucideIcon } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line } from 'recharts';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: 'up' | 'down';
  sparklineData?: { value: number }[];
  colorTheme?: 'purple' | 'green' | 'blue' | 'white';
}

export default function StatCard({ title, value, icon: Icon, trend, sparklineData, colorTheme = 'white' }: StatCardProps) {
  let iconColor = 'text-white';
  let strokeColor = '#ffffff';
  let trendColor = 'text-gray-400';

  if (colorTheme === 'purple') {
    iconColor = 'text-[#7c3aed]';
    strokeColor = '#7c3aed';
  } else if (colorTheme === 'green') {
    iconColor = 'text-[#00ff9f]';
    strokeColor = '#00ff9f';
  } else if (colorTheme === 'blue') {
    iconColor = 'text-blue-400';
    strokeColor = '#60a5fa';
  }

  if (trend === 'up') trendColor = 'text-[#00ff9f]';
  if (trend === 'down') trendColor = 'text-red-400';

  return (
    <div className="glass-card rounded-xl p-6 relative overflow-hidden flex flex-col justify-between h-36">
      <div className="flex justify-between items-start z-10">
        <div>
          <p className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-1">{title}</p>
          <div className="flex items-end gap-3">
            <h3 className="text-3xl font-bold font-mono text-white tracking-tight">{value}</h3>
            {trend && (
              <span className={`text-sm mb-1 font-bold ${trendColor}`}>
                {trend === 'up' ? '↑' : '↓'}
              </span>
            )}
          </div>
        </div>
        <div className={`p-2 rounded-lg bg-white/5 border border-white/10 ${iconColor}`}>
          <Icon size={24} />
        </div>
      </div>
      
      {sparklineData && sparklineData.length > 0 && (
        <div className="absolute bottom-0 left-0 right-0 h-16 opacity-30 pointer-events-none">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sparklineData}>
              <Line 
                type="monotone" 
                dataKey="value" 
                stroke={strokeColor} 
                strokeWidth={2} 
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
