import React, { useState } from 'react'
import { continueChat, ChatMessage } from '../api'

export default function ChatUI() {
	const [input, setInput] = useState('user: im bleeding')
	const [messages, setMessages] = useState<ChatMessage[]>([])
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState<string | null>(null)

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
		<div style={{ maxWidth: 800, margin: '40px auto', fontFamily: 'Inter, system-ui' }}>
			<h1>First Aid Guide</h1>
			<p>Multi‑agent assistant for emergencies.</p>
			<div style={{ border: '1px solid #ddd', borderRadius: 12, padding: 12, minHeight: 300 }}>
				{messages.length === 0 && (
					<div style={{ color: '#666' }}>Start by describing your situation. Example: "user: im bleeding"</div>
				)}
				{messages.map((m, idx) => (
					<div key={idx} style={{ margin: '8px 0' }}>
						<div style={{ fontWeight: 600, marginBottom: 4 }}>
							{m.role === 'assistant' ? 'AI Chatbot said:' : m.role === 'user' ? 'You said:' : 'System:'}
						</div>
						<div style={{ whiteSpace: 'pre-wrap', background: m.role === 'assistant' ? '#f8fafc' : '#fff', border: '1px solid #eee', borderRadius: 8, padding: 10 }}>
							{m.content}
						</div>
					</div>
				))}
			</div>
			<div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
				<input
					style={{ flex: 1, padding: 12, borderRadius: 8, border: '1px solid #ccc' }}
					value={input} onChange={e => setInput(e.target.value)}
					placeholder="Describe your situation..."
				/>
				<button onClick={onSend} disabled={loading} style={{ padding: '12px 16px', borderRadius: 8 }}>
					{loading ? 'Thinking...' : 'Send'}
				</button>
			</div>
			{error && (
				<div style={{ marginTop: 16, padding: 12, background: '#ffdddd', color: '#d8000c', borderRadius: 12 }}>
					{error}
				</div>
			)}
		</div>
	)
}
