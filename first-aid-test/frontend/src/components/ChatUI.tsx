import React, { useMemo, useState } from 'react'
import { continueChat, ChatMessage } from '../api'
import './ChatUI.css'

type QuickVideo = {
  id: string
  title: string
  description: string
}

const mapSearchUrl = 'https://www.google.com/maps/search/nearest+hospitals%2Fmedi+help/'

export default function ChatUI() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const quickVideos: QuickVideo[] = useMemo(
    () => [
      {
        id: '6wxN4cQ_kJw',
        title: 'Severe bleeding',
        description: 'Stop bleeding fast with direct pressure and elevation.'
      },
      {
        id: 'By5-H7Y5KQM',
        title: 'CPR basics',
        description: 'Hands-only CPR technique for adults and teens.'
      },
      {
        id: 'G8kG3CNs8Ts',
        title: 'Burn treatment',
        description: 'Cool the burn and cover it safely until help arrives.'
      }
    ],
    []
  )

  const onSend = async () => {
    if (!input.trim()) return
    setLoading(true)
    setError(null)
    try {
      const userMsg: ChatMessage = { role: 'user', content: input }
      const next = [...messages, userMsg]
      setMessages(next)
      const data = await continueChat(next)
      setMessages(data.messages)
    } catch (err) {
      setError('Failed to get a response from the assistant. Please try again.')
      console.error(err)
    } finally {
      setLoading(false)
      setInput('')
    }
  }

  return (
    <div className="chat-app">
      <div className="chat-shell">
        <header className="chat-header">
          <div>
            <h1>First-Aid Guide</h1>
            <p>Calm, step-by-step help. Not a substitute for professional care.</p>
          </div>
          <div className="header-actions">
            <button className="pill-button">Emergency</button>
            <button className="pill-button primary">Stop</button>
          </div>
        </header>

        <div className="chat-layout">
          <aside className="sidebar">
            <section className="sidebar-card">
              <h2>Nearby Help</h2>
              <p>Find urgent care centers and hospitals close to you.</p>
              <div className="map-container">
                <iframe
                  title="Nearby hospitals map"
                  src="https://www.google.com/maps?q=nearest%20hospitals%2Fmedi%20help&output=embed"
                  allowFullScreen
                  loading="lazy"
                  referrerPolicy="no-referrer-when-downgrade"
                />
                <a href={mapSearchUrl} target="_blank" rel="noopener noreferrer">
                  Open in Google Maps
                </a>
              </div>
              <a className="map-button" href={mapSearchUrl} target="_blank" rel="noopener noreferrer">
                Open in Google Maps
              </a>
            </section>

            <section className="sidebar-card">
              <h2>Quick Reference</h2>
              <p>Watch essential first-aid refreshers while help is on the way.</p>
              <div className="video-grid">
                {quickVideos.map(video => (
                  <a
                    key={video.id}
                    className="video-card"
                    href={`https://www.youtube.com/watch?v=${video.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <img
                      src={`https://img.youtube.com/vi/${video.id}/hqdefault.jpg`}
                      alt={`${video.title} thumbnail`}
                      loading="lazy"
                    />
                    <div>
                      <h3>{video.title}</h3>
                      <span>{video.description}</span>
                    </div>
                  </a>
                ))}
              </div>
            </section>
          </aside>

          <main className="main-panel">
            <section className="conversation-card">
              <div className="conversation-header">
                <div>
                  <div className="status-text">
                    <span className="status-dot" />
                    Live assistant
                  </div>
                  <p style={{ color: '#6b6b80', margin: '6px 0 0', fontSize: 14 }}>
                    Conversation
                  </p>
                </div>
                <div className="tag-row">
                  <span className="tag">CPR steps</span>
                  <span className="tag">Stopping bleeding</span>
                  <span className="tag">Burn care</span>
                  <span className="tag">Sprain support</span>
                </div>
              </div>

              <div className="messages">
                {messages.length === 0 ? (
                  <div className="message assistant">
                    <label>Assistant</label>
                    <div className="message-content">
                      Hi! I&apos;m your First-Aid guide. Who needs help and where are you?
                    </div>
                  </div>
                ) : (
                  messages.map((m, idx) => (
                    <div key={idx} className={`message ${m.role}`}>
                      <label>{m.role === 'assistant' ? 'Assistant' : m.role === 'user' ? 'You' : 'System'}</label>
                      <div className="message-content">{m.content}</div>
                    </div>
                  ))
                )}
              </div>
            </section>

            <section className="input-card">
              <textarea
                className="chat-input"
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Describe the situation (e.g., adult with a cut on the forearm)."
              />
              <div className="action-row">
                <span className="hint">The assistant will answer with calm, clear steps.</span>
                <button className="send-button" onClick={onSend} disabled={loading}>
                  {loading ? 'Thinking…' : 'Send'}
                </button>
              </div>
              {error && <div className="error-banner">{error}</div>}
            </section>
          </main>
        </div>
      </div>
    </div>
  )
}
