import { NextRequest, NextResponse } from 'next/server';
import {
    ChatRequest,
    ChatResponseChunk,
    isErrorChunk
} from '@steven-universe/shared-schemas';

/**
 * Steven AI Query API Route
 *
 * BFF (Backend for Frontend) endpoint that handles Steven AI queries
 * by forwarding requests to the web-gateway.
 *
 * Always returns SSE stream format. The client (controller) decides
 * whether to consume it as streaming or wait for full response.
 *
 * Benefits:
 * - Hides backend API credentials from client
 * - Enables server-side authentication
 * - Type-safe with shared schemas
 * - Simple, consistent API interface
 */

// Environment variables
const WEB_GATEWAY_URL = process.env.WEB_GATEWAY_URL || 'https://api.liustev6.ca';
const WEB_GATEWAY_API_KEY = process.env.WEB_GATEWAY_API_KEY;

export async function POST(request: NextRequest) {
    try {
        const chatRequest: ChatRequest = await request.json();

        // Validate required fields
        if (!chatRequest.query || !chatRequest.query.trim()) {
            return NextResponse.json(
                { error: 'Query is required' },
                { status: 400 }
            );
        }

        // Validate API key
        if (!WEB_GATEWAY_API_KEY) {
            console.error('WEB_GATEWAY_API_KEY not configured');
            return NextResponse.json(
                { error: 'Server configuration error' },
                { status: 500 }
            );
        }

        // Forward request to web-gateway
        const response = await fetch(`${WEB_GATEWAY_URL}/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': WEB_GATEWAY_API_KEY
            },
            body: JSON.stringify(chatRequest)
        });

        if (!response.ok) {
            const error = await response.text();
            console.error('Web gateway error:', error);
            return NextResponse.json(
                { error: 'Backend service error' },
                { status: response.status }
            );
        }

        const reader = response.body?.getReader();
        if (!reader) {
            return NextResponse.json(
                { error: 'No response body' },
                { status: 500 }
            );
        }

        const decoder = new TextDecoder();

        // Always stream - return NDJSON (newline-delimited JSON)
        const encoder = new TextEncoder();
        const readable = new ReadableStream({
            async start(controller) {
                try {
                    let buffer = '';

                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\n');
                        buffer = lines.pop() || '';

                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                const data = line.slice(6);
                                try {
                                    const chunk: ChatResponseChunk = JSON.parse(data);

                                    // Send typed object as newline-delimited JSON
                                    const jsonLine = JSON.stringify(chunk) + '\n';
                                    controller.enqueue(encoder.encode(jsonLine));

                                    // Log errors only
                                    if (isErrorChunk(chunk)) {
                                        console.error('Error:', chunk.error);
                                    }
                                } catch (parseError) {
                                    console.error('Failed to parse chunk:', parseError);
                                }
                            }
                        }
                    }

                    controller.close();
                } catch (streamError) {
                    console.error('Stream error:', streamError);
                    controller.error(streamError);
                }
            }
        });

        return new Response(readable, {
            headers: {
                'Content-Type': 'application/x-ndjson', // Newline-delimited JSON
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
        });
    } catch (error) {
        console.error('Steven AI API Error:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
