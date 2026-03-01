// src/lib/api.ts — Typed API functions calling TACO backend
import axios from 'axios';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const api = axios.create({ baseURL: BASE, timeout: 15000 });

// ── Types ────────────────────────────────────────────────────────────────────
export interface ModelBreakdown { model: string; request_count: number; cost_usd: number; }

export interface OverviewData {
    total_cost_usd: number;
    total_requests: number;
    total_tokens: number;
    avg_cost_per_request: number;
    cheap_tier_pct: number;
    savings_usd: number;
    top_models: ModelBreakdown[];
}

export interface TimeseriesPoint {
    date: string;
    cost_usd: number;
    request_count: number;
    total_tokens: number;
}

export interface RequestLogRow {
    id: string;
    user_id: string;
    org_id?: string;
    task_type?: string;
    provider?: string;
    model_used?: string;
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
    cost_usd?: number;
    latency_ms?: number;
    was_sliced: boolean;
    status_code?: number;
    created_at: string;
}

export interface PaginatedRequests {
    items: RequestLogRow[];
    total: number;
    page: number;
    limit: number;
}

export interface OverviewParams { user_id?: string; org_id?: string; period?: '7d' | '30d' | 'mtd'; }
export interface TimeseriesParams { user_id?: string; org_id?: string; days?: number; }
export interface RequestsParams { user_id?: string; org_id?: string; model?: string; page?: number; limit?: number; }

// ── API functions ─────────────────────────────────────────────────────────────
export const fetchOverview = (params: OverviewParams = {}) =>
    api.get<OverviewData>('/analytics/overview', { params }).then(r => r.data);

export const fetchTimeseries = (params: TimeseriesParams = {}) =>
    api.get<TimeseriesPoint[]>('/analytics/timeseries', { params }).then(r => r.data);

export const fetchRequests = (params: RequestsParams = {}) =>
    api.get<PaginatedRequests>('/analytics/requests', { params }).then(r => r.data);

export const fetchHealth = () =>
    api.get('/health').then(r => r.data);
