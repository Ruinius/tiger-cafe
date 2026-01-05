import React from 'react'

export default function OrganicGrowthTable({ data, formatNumber }) {
  if (!data) return null

  return (
    <div className="balance-sheet-container">
      <div className="balance-sheet-table-container">
        <table className="balance-sheet-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th className="text-right">Value</th>
              <th>Unit</th>
            </tr>
          </thead>
          <tbody>
            {data.prior_period_revenue !== null && (
              <tr>
                <td>Prior Period Revenue</td>
                <td className="text-right">{formatNumber(data.prior_period_revenue, data.prior_period_revenue_unit)}</td>
                <td>{data.prior_period_revenue_unit ? data.prior_period_revenue_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
            {data.current_period_revenue !== null && (
              <tr>
                <td>Current Period Revenue</td>
                <td className="text-right">{formatNumber(data.current_period_revenue, data.current_period_revenue_unit)}</td>
                <td>{data.current_period_revenue_unit ? data.current_period_revenue_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
            {data.acquisition_revenue_impact !== null && (
              <tr>
                <td>Acquisition Revenue Impact</td>
                <td className="text-right">{formatNumber(data.acquisition_revenue_impact, data.acquisition_revenue_impact_unit)}</td>
                <td>{data.acquisition_revenue_impact_unit ? data.acquisition_revenue_impact_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
            {data.current_period_adjusted_revenue !== null && (
              <tr>
                <td>Adjusted Revenue</td>
                <td className="text-right">{formatNumber(data.current_period_adjusted_revenue, data.current_period_adjusted_revenue_unit)}</td>
                <td>{data.current_period_adjusted_revenue_unit ? data.current_period_adjusted_revenue_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
            {data.simple_revenue_growth !== null && (
              <tr>
                <td>Simple Revenue Growth</td>
                <td className="text-right">{parseFloat(data.simple_revenue_growth).toFixed(2)}%</td>
                <td>—</td>
              </tr>
            )}
            {data.organic_revenue_growth !== null && (
              <tr>
                <td>Organic Revenue Growth</td>
                <td className="text-right">{parseFloat(data.organic_revenue_growth).toFixed(2)}%</td>
                <td>—</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
