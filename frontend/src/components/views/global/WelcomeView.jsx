import React from 'react'

function WelcomeView() {
    return (
        <div className="right-panel">
            <div className="panel-content">
                <div className="panel-header">
                    <span className="breadcrumb-current">Latest Analyses</span>
                </div>
                <div className="home-content">
                    <p className="placeholder-text">
                        Latest completed company analyses will be displayed here.
                    </p>
                </div>
            </div>
        </div>
    )
}

export default WelcomeView
