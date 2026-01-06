import React from 'react'

export default function OrganicGrowthTable({ data, formatNumber }) {
  if (!data) return null

  return (
    <div className="balance-sheet-container">
      <div className="balance-sheet-table-container">
        <table className="balance-sheet-table">
          <thead>
            <tr>
              <th className="col-name">Metric</th>
              <th className="text-right col-value">Amount</th>
              <th className="col-unit">Unit</th>
            </tr>
          </thead>
          <tbody>
            {data.prior_period_revenue !== null && (
              <tr>
                <td className="col-name">Prior Period Revenue</td>
                <td className="text-right col-value">{formatNumber(data.prior_period_revenue, data.prior_period_revenue_unit)}</td>
                <td className="col-unit">{data.prior_period_revenue_unit ? data.prior_period_revenue_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
            {data.current_period_revenue !== null && (
              <tr>
                <td className="col-name">Current Period Revenue</td>
                <td className="text-right col-value">{formatNumber(data.current_period_revenue, data.current_period_revenue_unit)}</td>
                <td className="col-unit">{data.current_period_revenue_unit ? data.current_period_revenue_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
            {data.acquisition_revenue_impact !== null && (
              <tr>
                <td className="col-name">Acquisition Revenue Impact</td>
                <td className="text-right col-value">{formatNumber(data.acquisition_revenue_impact, data.acquisition_revenue_impact_unit)}</td>
                <td className="col-unit">{data.acquisition_revenue_impact_unit ? data.acquisition_revenue_impact_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
            {data.current_period_adjusted_revenue !== null && (
              <tr>
                <td className="col-name">Adjusted Revenue</td>
                <td className="text-right col-value">{formatNumber(data.current_period_adjusted_revenue, data.current_period_adjusted_revenue_unit)}</td>
                <td className="col-unit">{data.current_period_adjusted_revenue_unit ? data.current_period_adjusted_revenue_unit.replace('_', ' ') : 'N/A'}</td>
              </tr>
            )}
            {data.simple_revenue_growth !== null && (
              <tr>
                <td className="col-name">Simple Revenue Growth</td>
                <td className="text-right col-value">{parseFloat(data.simple_revenue_growth).toFixed(2)}%</td>
                <td className="col-unit">—</td>
              </tr>
            )}
            {data.organic_revenue_growth !== null && (
              <tr>
                <td className="col-name">Organic Revenue Growth</td>
                <td className="text-right col-value">{parseFloat(data.organic_revenue_growth).toFixed(2)}%</td>
                <td className="col-unit">—</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
