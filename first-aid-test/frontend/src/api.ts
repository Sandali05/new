import axios from 'axios'

interface AgentResponse {
	triage?: {
		emergency: string;
		severity: number;
	};
	instructions?: {
		summary: string;
		steps: string[] | string;
	};
	error?: string;
	details?: string;
}

export type ChatRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
	role: ChatRole
	content: string
}

export interface ContinueResponse {
	ok: boolean
	messages: ChatMessage[]
	result: any
}

export async function sendMessage(message: string): Promise<AgentResponse> {
	try {
		const res = await axios.post<AgentResponse>('/api/chat', { message })
		return res.data
	} catch (error) {
		console.error('API call failed:', error)
		throw error // Re-throw the error to be caught by the calling component
	}
}

export async function continueChat(messages: ChatMessage[]): Promise<ContinueResponse> {
	const res = await axios.post<ContinueResponse>('/api/chat/continue', { messages })
	return res.data
}
