import { NextRequest, NextResponse } from 'next/server';

/**
 * Steven AI Query API Route
 *
 * BFF (Backend for Frontend) endpoint that handles Steven AI queries
 * by building the appropriate API URL and forwarding requests to the backend.
 *
 * Benefits:
 * - Hides backend API URL from client
 * - Enables server-side processing and validation
 * - Allows for rate limiting, authentication, etc.
 * - Keeps API structure flexible
 */

interface QueryRequest {
    question: string;
    lastQuestion?: string;
    lastAnswer?: string;
    model: 'ChatGPT-4o' | 'LLaMA';
    rag: string[];
}

export async function POST(request: NextRequest) {
    try {
        const body: QueryRequest = await request.json();
        const { question, lastQuestion, lastAnswer, model, rag } = body;

        // Validate required fields
        if (!question || !question.trim()) {
            return NextResponse.json(
                { error: 'Question is required' },
                { status: 400 }
            );
        }

        // Build model slug
        const modelSlug = model === 'ChatGPT-4o' ? 'gpt4o' : 'llama';

        // Build RAG slug
        let ragSlug = '';
        const hasQA = rag.includes('QA Pairs');
        const hasDocs = rag.includes('Docs of Facts');
        if (hasQA && hasDocs) {
            ragSlug = 'qa-docs';
        } else if (hasQA) {
            ragSlug = 'qa';
        } else if (hasDocs) {
            ragSlug = 'docs';
        }

        // Build API URL
        const basePath = ragSlug ? `${modelSlug}-${ragSlug}` : modelSlug;
        const baseUrl = `https://server-lite.liustev6.ca/stevenai/${basePath}/query`;

        const urlParams = new URLSearchParams({ q: question });
        if (lastQuestion && lastAnswer) {
            urlParams.append('last_q', lastQuestion);
            urlParams.append('last_a', lastAnswer);
        }

        const fullUrl = `${baseUrl}?${urlParams.toString()}`;

        // Forward request to backend
        const response = await fetch(fullUrl, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        // Return response
        if (data.answer) {
            return NextResponse.json({ answer: data.answer });
        } else if (data.error) {
            return NextResponse.json(
                { error: data.error },
                { status: response.status }
            );
        } else {
            return NextResponse.json(
                { error: 'No response received from backend' },
                { status: 500 }
            );
        }
    } catch (error) {
        console.error('Steven AI API Error:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
