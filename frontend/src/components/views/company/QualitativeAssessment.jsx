import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../../contexts/AuthContext';
import { API_BASE_URL } from '../../../config';
import './QualitativeAssessment.css';

const QualitativeAssessment = ({ companyId }) => {
    const { token, isAuthenticated } = useAuth();
    const [assessment, setAssessment] = useState(null);
    const [loading, setLoading] = useState(true);
    const [rerunning, setRerunning] = useState(false);
    const [error, setError] = useState(null);

    const fetchAssessment = async () => {
        if (!companyId) return;

        try {
            setLoading(true);
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {};

            try {
                const response = await axios.get(
                    `${API_BASE_URL}/companies/${companyId}/qualitative-assessment`,
                    { headers }
                );
                setAssessment(response.data);
                setError(null);
            } catch (err) {
                if (err.response && err.response.status === 404) {
                    setAssessment(null);
                } else {
                    console.error("Error fetching assessment:", err);
                    setError("Failed to load assessment");
                }
            }
        } catch (err) {
            console.error(err);
            setError("Network error");
        } finally {
            setLoading(false);
        }
    };

    const handleRerun = async () => {
        try {
            setRerunning(true);
            setError(null);
            const headers = isAuthenticated && token ? { 'Authorization': `Bearer ${token}` } : {};

            const response = await axios.post(
                `${API_BASE_URL}/companies/${companyId}/qualitative-assessment/rerun`,
                {},
                { headers }
            );

            setAssessment(response.data);
        } catch (err) {
            console.error(err);
            const msg = err.response?.data?.detail || "Failed to re-run assessment";
            setError(msg);
        } finally {
            setRerunning(false);
        }
    };

    useEffect(() => {
        if (companyId) {
            fetchAssessment();
        }
    }, [companyId, isAuthenticated, token]);

    const getBadgeClass = (type, label) => {
        let status = 'neutral';

        if (type === 'moat') {
            if (label === 'Wide') status = 'success';
            else if (label === 'Narrow') status = 'neutral';
            else if (label === 'None') status = 'warning';
        } else if (type === 'growth') {
            if (label === 'Faster') status = 'success';
            else if (label === 'Steady') status = 'neutral';
            else if (label === 'Slower') status = 'warning';
        } else if (type === 'predict') {
            if (label === 'High') status = 'success';
            else if (label === 'Mid') status = 'neutral';
            else if (label === 'Low') status = 'warning';
        }

        return status;
    };

    if (loading) {
        return <div className="qa-loading">Loading qualitative assessment...</div>;
    }

    return (
        <div className="qa-container">
            <div className="qa-header">
                <h3 className="qa-title">Qualitative Assessment</h3>
            </div>

            {error && (
                <div className="qa-error-banner">
                    {error}
                </div>
            )}

            <div className="qa-panel-grid">
                {!assessment ? (
                    <div className="qa-empty-state">
                        No qualitative assessment available. Click "Re-run Assessment" below to generate insights.
                    </div>
                ) : (
                    <>
                        {/* Header Row */}
                        <div className="qa-panel-header-row">
                            <div className="qa-header-item">
                                <span>Economic Moat</span>
                                <span
                                    className={`qa-badge ${getBadgeClass('moat', assessment.economic_moat_label)}`}
                                >
                                    {assessment.economic_moat_label || 'Unknown'}
                                </span>
                            </div>
                            <div className="qa-header-item">
                                <span>Near-term Growth</span>
                                <span
                                    className={`qa-badge ${getBadgeClass('growth', assessment.near_term_growth_label)}`}
                                >
                                    {assessment.near_term_growth_label || 'Unknown'}
                                </span>
                            </div>
                            <div className="qa-header-item">
                                <span>Revenue Predictability</span>
                                <span
                                    className={`qa-badge ${getBadgeClass('predict', assessment.revenue_predictability_label)}`}
                                >
                                    {assessment.revenue_predictability_label || 'Unknown'}
                                </span>
                            </div>
                        </div>

                        {/* Content Row */}
                        <div className="qa-panel-content">
                            {/* Economic Moat Content */}
                            <div className="qa-panel-item">
                                <p className="qa-rationale-text">
                                    {assessment.economic_moat_rationale || "No rationale provided."}
                                </p>
                            </div>

                            {/* Near-term Growth Content */}
                            <div className="qa-panel-item">
                                <p className="qa-rationale-text">
                                    {assessment.near_term_growth_rationale || "No rationale provided."}
                                </p>
                            </div>

                            {/* Revenue Predictability Content */}
                            <div className="qa-panel-item">
                                <p className="qa-rationale-text">
                                    {assessment.revenue_predictability_rationale || "No rationale provided."}
                                </p>
                            </div>
                        </div>
                    </>
                )}

                <div className="qa-footer">
                    <button
                        className="qa-run-button"
                        onClick={handleRerun}
                        disabled={rerunning}
                    >
                        {rerunning ? "Analyzing..." : "Re-run Assessment"}
                    </button>
                    <span className="qa-timestamp">
                        Last Updated: {assessment?.updated_at ? new Date(assessment.updated_at).toLocaleString() : 'Never'}
                    </span>
                </div>
            </div>
        </div>
    );
};

export default QualitativeAssessment;
