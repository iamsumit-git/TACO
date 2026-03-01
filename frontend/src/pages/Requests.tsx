// src/pages/Requests.tsx — Paginated request log table
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { fetchRequests } from '../lib/api';

function fmt(v?: number | null, decimals = 6) {
    if (v === undefined || v === null) return '—';
    return `$${v.toFixed(decimals)}`;
}
function fmtMs(v?: number | null) { return v !== undefined && v !== null ? `${v}ms` : '—'; }
function fmtDate(s: string) {
    try { return new Date(s).toLocaleString(); } catch { return s; }
}

export default function Requests() {
    const [userId, setUserId] = useState('');
    const [model, setModel] = useState('');

    const LIMIT = 20;

    const [filter, setFilter] = useState({ user_id: '', model: '', page: 1 });

    const { data, isLoading, isError } = useQuery({
        queryKey: ['requests', filter],
        queryFn: () => fetchRequests({
            user_id: filter.user_id || undefined,
            model: filter.model || undefined,
            page: filter.page,
            limit: LIMIT,
        }),
    });

    const apply = () => { setFilter({ user_id: userId, model, page: 1 }); };
    const goPage = (p: number) => setFilter(f => ({ ...f, page: p }));

    const totalPages = data ? Math.ceil(data.total / LIMIT) : 1;

    return (
        <div>
            <div className="page-title">📋 Request Log</div>

            {/* Filters */}
            <div className="filters">
                <input id="req-user-filter" className="filter-input" placeholder="Filter by user_id..." value={userId} onChange={e => setUserId(e.target.value)} style={{ width: 200 }} />
                <input id="req-model-filter" className="filter-input" placeholder="Filter by model..." value={model} onChange={e => setModel(e.target.value)} style={{ width: 180 }} />
                <button id="req-apply-btn" className="btn btn-primary" onClick={apply}>Apply</button>
            </div>

            {isLoading && <div className="loading">Loading requests…</div>}
            {isError && <div className="error-msg">Failed to load requests. Is the backend running?</div>}

            {data && (
                <div className="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>User</th>
                                <th>Model</th>
                                <th>Tier</th>
                                <th>Tokens</th>
                                <th>Cost</th>
                                <th>Latency</th>
                                <th>Sliced</th>
                                <th>Status</th>
                                <th>Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.items.length === 0 && (
                                <tr><td colSpan={9} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>No requests yet — POST to /v1/chat first</td></tr>
                            )}
                            {data.items.map(row => (
                                <tr key={row.id}>
                                    <td>{row.user_id}</td>
                                    <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{row.model_used ?? '—'}</td>
                                    <td>
                                        <span className={`badge ${row.task_type === 'simple' ? 'badge-green' : 'badge-purple'}`}>
                                            {row.task_type ?? '—'}
                                        </span>
                                    </td>
                                    <td>{row.total_tokens?.toLocaleString() ?? '—'}</td>
                                    <td style={{ fontFamily: 'monospace' }}>{fmt(row.cost_usd)}</td>
                                    <td>{fmtMs(row.latency_ms)}</td>
                                    <td>
                                        {row.was_sliced
                                            ? <span className="badge badge-amber">yes</span>
                                            : <span className="badge badge-green">no</span>}
                                    </td>
                                    <td>
                                        <span className={`badge ${row.status_code === 200 ? 'badge-green' : 'badge-amber'}`}>
                                            {row.status_code ?? '—'}
                                        </span>
                                    </td>
                                    <td style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{fmtDate(row.created_at)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>

                    {/* Pagination */}
                    <div className="pagination">
                        <button id="req-prev-btn" className="page-btn" disabled={filter.page <= 1} onClick={() => goPage(filter.page - 1)}>← Prev</button>
                        <span className="page-info">Page {filter.page} of {totalPages} &nbsp;·&nbsp; {data.total} total</span>
                        <button id="req-next-btn" className="page-btn" disabled={filter.page >= totalPages} onClick={() => goPage(filter.page + 1)}>Next →</button>
                    </div>
                </div>
            )}
        </div>
    );
}
