// src/pages/Overview.tsx — Spend overview dashboard
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    BarChart, Bar, Cell,
} from 'recharts';
import { fetchOverview, fetchTimeseries } from '../lib/api';

const COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ec4899', '#14b8a6'];

function KpiCard({ label, value, sub, colorClass = '' }: { label: string; value: string; sub?: string; colorClass?: string }) {
    return (
        <div className="kpi-card">
            <div className="kpi-label">{label}</div>
            <div className={`kpi-value ${colorClass}`}>{value}</div>
            {sub && <div className="kpi-sub">{sub}</div>}
        </div>
    );
}

export default function Overview() {
    const [userId, setUserId] = useState('');
    const [period, setPeriod] = useState<'7d' | '30d' | 'mtd'>('30d');
    const [filter, setFilter] = useState({ user_id: '', period: '30d' as '7d' | '30d' | 'mtd' });

    const overview = useQuery({
        queryKey: ['overview', filter],
        queryFn: () => fetchOverview({ user_id: filter.user_id || undefined, period: filter.period }),
    });

    const timeseries = useQuery({
        queryKey: ['timeseries', filter],
        queryFn: () => fetchTimeseries({ user_id: filter.user_id || undefined, days: filter.period === '7d' ? 7 : 30 }),
    });

    const apply = () => setFilter({ user_id: userId, period });

    const d = overview.data;

    return (
        <div>
            <div className="page-title">📊 Spend Overview</div>

            {/* Filters */}
            <div className="filters">
                <input id="ov-user-filter" className="filter-input" placeholder="Filter by user_id..." value={userId} onChange={e => setUserId(e.target.value)} style={{ width: 220 }} />
                <select id="ov-period-select" className="filter-select" value={period} onChange={e => setPeriod(e.target.value as any)}>
                    <option value="7d">Last 7 days</option>
                    <option value="30d">Last 30 days</option>
                    <option value="mtd">Month to date</option>
                </select>
                <button id="ov-apply-btn" className="btn btn-primary" onClick={apply}>Apply</button>
            </div>

            {/* KPI Cards */}
            {overview.isLoading && <div className="loading">Loading overview…</div>}
            {overview.isError && <div className="error-msg">Failed to load overview. Is the backend running?</div>}
            {d && (
                <>
                    <div className="kpi-grid">
                        <KpiCard label="Total Cost" value={`$${d.total_cost_usd.toFixed(4)}`} sub="All providers" colorClass="kpi-purple" />
                        <KpiCard label="Total Requests" value={d.total_requests.toLocaleString()} sub="API calls" />
                        <KpiCard label="Cheap Tier %" value={`${d.cheap_tier_pct.toFixed(1)}%`} sub="Routed to cheap" colorClass="kpi-green" />
                        <KpiCard label="Savings" value={`$${d.savings_usd.toFixed(4)}`} sub="vs smart-tier-only" colorClass="kpi-amber" />
                    </div>

                    {/* Charts */}
                    <div className="chart-row">
                        {/* Daily Cost AreaChart */}
                        <div className="chart-card">
                            <h3>Daily Cost (USD)</h3>
                            {timeseries.isLoading && <div className="loading">Loading chart…</div>}
                            {timeseries.data && timeseries.data.length > 0 ? (
                                <ResponsiveContainer width="100%" height={220}>
                                    <AreaChart data={timeseries.data} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
                                        <defs>
                                            <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                                                <stop offset="95%" stopColor="#6366f1" stopOpacity={0.02} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" />
                                        <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} />
                                        <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={v => `$${v.toFixed(3)}`} />
                                        <Tooltip
                                            contentStyle={{ background: '#1a1d27', border: '1px solid #2d3148', borderRadius: 8 }}
                                            labelStyle={{ color: '#94a3b8' }}
                                            itemStyle={{ color: '#818cf8' }}
                                            formatter={(v: any) => [`$${(v as number).toFixed(6)}`, 'Cost']}
                                        />
                                        <Area type="monotone" dataKey="cost_usd" stroke="#6366f1" fill="url(#costGrad)" strokeWidth={2} dot={false} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            ) : timeseries.data && <div className="loading" style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>No data yet — send some requests first</div>}
                        </div>

                        {/* Top Models BarChart */}
                        <div className="chart-card">
                            <h3>Top Models by Cost</h3>
                            {d.top_models.length > 0 ? (
                                <ResponsiveContainer width="100%" height={220}>
                                    <BarChart data={d.top_models} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" horizontal={false} />
                                        <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={v => `$${v.toFixed(4)}`} />
                                        <YAxis type="category" dataKey="model" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} width={110} />
                                        <Tooltip
                                            contentStyle={{ background: '#1a1d27', border: '1px solid #2d3148', borderRadius: 8 }}
                                            formatter={(v: any) => [`$${(v as number).toFixed(6)}`, 'Cost']}
                                        />
                                        <Bar dataKey="cost_usd" radius={[0, 4, 4, 0]}>
                                            {d.top_models.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : <div className="loading" style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>No model data yet</div>}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
