import React, { useEffect, useRef } from 'react'
import { useUpload } from '../../../contexts/UploadContext'
import ReactMarkdown from 'react-markdown'
import './MissionControl.css'

function MissionControlLog({ focusedDocumentId }) {
    const { processingLogs, isStreaming } = useUpload()
    const logEndRef = useRef(null)
    const containerRef = useRef(null)

    const logs = processingLogs.get(focusedDocumentId) || []

    // Sticky scroll to bottom
    const scrollToBottom = () => {
        if (logEndRef.current) {
            logEndRef.current.scrollIntoView({ behavior: 'smooth' })
        }
    }

    useEffect(() => {
        scrollToBottom()
    }, [logs.length])

    return (
        <div className="panel-content mission-control-log" ref={containerRef}>
            <div className="log-header">
                <h3>Intelligence Stream</h3>
            </div>

            <div className="chat-stream">
                {logs.length === 0 ? (
                    <div className="empty-log-state">
                        <p>Waiting for intelligence data...</p>
                    </div>
                ) : (
                    logs.map((log, idx) => {
                        const source = log.source?.toLowerCase() || 'system'
                        const isAI = source === 'gemini'
                        const isTransformer = source === 'tiger-transformer'
                        const isRightSide = isAI || isTransformer

                        return (
                            <div key={idx} className={`chat-message ${source} ${isRightSide ? 'right-side' : 'left-side'}`}>
                                {source === 'system' && <span className="source-tag system">[SYSTEM]</span>}
                                {isRightSide && (
                                    <div className="ai-avatar">
                                        <div className="avatar-icon">{isAI ? '🤖' : '🐯'}</div>
                                        <span className={`source-tag ${source}`}>{source.replace('-', ' ').toUpperCase()}</span>
                                    </div>
                                )}
                                <div className="message-bubble">
                                    <div className="message-content">
                                        <ReactMarkdown>{log.message}</ReactMarkdown>
                                    </div>
                                    <span className="message-time">
                                        {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                    </span>
                                </div>
                            </div>
                        )
                    })
                )}
                <div ref={logEndRef} />
            </div>

            {isStreaming && (
                <div className="streaming-footer">
                    <div className="streaming-indicator">
                        <span className="spinner"></span>
                        System is thinking...
                    </div>
                </div>
            )}
        </div>
    )
}

export default MissionControlLog
