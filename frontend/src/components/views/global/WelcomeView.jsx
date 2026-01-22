import React, { useEffect, useState, useMemo } from 'react'
import axios from 'axios'
import { API_BASE_URL } from '../../../config'
import {
    ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    ReferenceLine, Cell, Legend
} from 'recharts'
import './Dashboard.css'

// Generate vibrant colors that work in both light and dark mode
const stringToColor = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }

    // Use HSL for better control over brightness
    // Hue: 0-360 (full color spectrum)
    // Saturation: 70% (vibrant but not oversaturated)
    // Lightness: 60% (bright enough for dark mode, not too bright for light mode)
    const hue = Math.abs(hash) % 360;
    return `hsl(${hue}, 70%, 60%)`;
}

const formatPercent = (value) => `${(value).toFixed(1)}%`;
const formatDate = (tick) => new Date(tick).toLocaleDateString(undefined, { month: 'short', year: '2-digit' });

const getValuationColor = (percent) => {
    if (percent > 0.30) return '#10b981'; // Green (Undervalued)
    if (percent < -0.15) return '#ef4444'; // Red (Overvalued)
    return '#f59e0b'; // Yellow (Fair)
}

function WelcomeView() {
    const [data, setData] = useState({ valuation_history: [], rule_of_40: [] });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await axios.get(`${API_BASE_URL}/dashboard/charts`);
                setData(response.data);
            } catch (err) {
                console.error("Failed to fetch dashboard data", err);
                setError("Failed to load dashboard data.");
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    // Transform History Data
    const historyData = useMemo(() => {
        return data.valuation_history.map(item => ({
            ...item,
            x: new Date(item.date).getTime(),
            y: item.percent_undervalued * 100
        }));
    }, [data.valuation_history]);

    // Transform Rule of 40 Data
    // Already x/y from backend? Backend sends "margin", "growth" (percentages).
    // Let's verify backend output in Step 669. "margin": margin * 100.
    const ruleOf40Data = data.rule_of_40;

    if (loading) return <div className="panel-content"><div className="loading">Loading dashboard...</div></div>;
    if (error) return <div className="panel-content"><div className="error-message">{error}</div></div>;

    return (
        <div className="right-panel">
            <div className="panel-content">
                <div className="panel-header">
                    <span className="breadcrumb-current">Global Analysis Dashboard</span>
                </div>

                <div className="dashboard-charts-container" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '2rem', overflowY: 'auto' }}>

                    {/* 1. Valuation History Chart */}
                    <div className="chart-card" style={{ background: 'var(--bg-surface)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border)' }}>
                        <h3 style={{ marginBottom: '1rem', fontWeight: 600 }}>Valuation History</h3>
                        <div style={{ height: 400 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                    <XAxis
                                        type="number"
                                        dataKey="x"
                                        name="Date"
                                        domain={['auto', 'auto']}
                                        tickFormatter={formatDate}
                                        stroke="var(--text-secondary)"
                                        style={{ fontSize: '0.8rem' }}
                                    />
                                    <YAxis
                                        type="number"
                                        dataKey="y"
                                        name="Undervalued %"
                                        unit="%"
                                        stroke="var(--text-secondary)"
                                        style={{ fontSize: '0.8rem' }}
                                    />
                                    <Tooltip
                                        cursor={{ strokeDasharray: '3 3' }}
                                        content={({ active, payload }) => {
                                            if (active && payload && payload.length) {
                                                const pt = payload[0].payload;
                                                return (
                                                    <div className="custom-tooltip" style={{ background: 'var(--bg-overlay)', padding: '0.5rem', border: '1px solid var(--border)', borderRadius: '4px' }}>
                                                        <p className="label" style={{ fontWeight: 600 }}>{pt.name} ({pt.ticker})</p>
                                                        <p>{new Date(pt.x).toLocaleDateString()}</p>
                                                        <p style={{ color: getValuationColor(pt.percent_undervalued) }}>
                                                            {Math.abs(pt.y).toFixed(1)}% {pt.y >= 0 ? 'Undervalued' : 'Overvalued'}
                                                        </p>
                                                    </div>
                                                );
                                            }
                                            return null;
                                        }}
                                    />
                                    <ReferenceLine y={0} stroke="var(--text-primary)" strokeDasharray="3 3" />
                                    <Scatter name="Valuations" data={historyData}>
                                        {historyData.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={stringToColor(entry.ticker)} />
                                        ))}
                                    </Scatter>
                                </ScatterChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* 2. Rule of 40 Chart */}
                    <div className="chart-card" style={{ background: 'var(--bg-surface)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border)' }}>
                        <h3 style={{ marginBottom: '1rem', fontWeight: 600 }}>Rule of 40 (Growth vs Profitability)</h3>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                            X: EBITA Margin (%), Y: Revenue Growth (%). Color indicates Valuation status.
                        </p>
                        <div style={{ height: 400 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                    <XAxis
                                        type="number"
                                        dataKey="margin"
                                        name="Margin"
                                        unit="%"
                                        stroke="var(--text-secondary)"
                                        style={{ fontSize: '0.8rem' }}
                                        label={{ value: 'EBITA Margin', position: 'bottom', offset: 0, fill: 'var(--text-secondary)' }}
                                    />
                                    <YAxis
                                        type="number"
                                        dataKey="growth"
                                        name="Growth"
                                        unit="%"
                                        stroke="var(--text-secondary)"
                                        style={{ fontSize: '0.8rem' }}
                                        label={{ value: 'Rev Growth', angle: -90, position: 'insideLeft', fill: 'var(--text-secondary)' }}
                                    />
                                    <Tooltip
                                        cursor={{ strokeDasharray: '3 3' }}
                                        content={({ active, payload }) => {
                                            if (active && payload && payload.length) {
                                                const pt = payload[0].payload;
                                                return (
                                                    <div className="custom-tooltip" style={{ background: 'var(--bg-overlay)', padding: '0.5rem', border: '1px solid var(--border)', borderRadius: '4px' }}>
                                                        <p className="label" style={{ fontWeight: 600 }}>{pt.name} ({pt.ticker})</p>
                                                        {pt.period && <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '0.25rem' }}>{pt.period}</p>}
                                                        <p>Growth: {formatPercent(pt.growth)}</p>
                                                        <p>Margin: {formatPercent(pt.margin)}</p>
                                                        <p>Score: {formatPercent(pt.growth + pt.margin)}</p>
                                                        <p style={{ color: getValuationColor(pt.undervalued) }}>
                                                            {Math.abs(pt.undervalued * 100).toFixed(1)}% {pt.undervalued >= 0 ? 'Undervalued' : 'Overvalued'}
                                                        </p>
                                                    </div>
                                                );
                                            }
                                            return null;
                                        }}
                                    />
                                    {/* Rule of 40 Line: growth + margin = 40% */}
                                    {/* Using a separate Line component with dummy data for the diagonal */}
                                    <Scatter
                                        name="Rule of 40"
                                        data={[
                                            { margin: -20, growth: 60 },
                                            { margin: 0, growth: 40 },
                                            { margin: 20, growth: 20 },
                                            { margin: 40, growth: 0 },
                                            { margin: 60, growth: -20 }
                                        ]}
                                        line={{ stroke: 'var(--primary)', strokeWidth: 2, strokeDasharray: '5 5' }}
                                        shape={() => null}
                                        legendType="line"
                                    />

                                    <Scatter name="Companies" data={ruleOf40Data}>
                                        {ruleOf40Data.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={getValuationColor(entry.undervalued)} />
                                        ))}
                                    </Scatter>
                                </ScatterChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default WelcomeView
