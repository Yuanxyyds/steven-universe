import { NextRequest, NextResponse } from 'next/server';

/**
 * Food 101 Image Classification API Route
 *
 * BFF (Backend for Frontend) endpoint that handles food image classification
 * by forwarding file uploads to the backend ML service.
 *
 * Benefits:
 * - Hides backend API URL from client
 * - Enables server-side processing and validation
 * - Allows for rate limiting, authentication, etc.
 * - Keeps API structure flexible
 */

export async function POST(request: NextRequest) {
    try {
        const formData = await request.formData();
        const file = formData.get('file');

        // Validate file
        if (!file || !(file instanceof File)) {
            return NextResponse.json(
                { error: 'File is required' },
                { status: 400 }
            );
        }

        // Forward request to backend
        const backendFormData = new FormData();
        backendFormData.append('file', file);

        const response = await fetch('https://server-lite.liustev6.ca/food101/classify', {
            method: 'POST',
            body: backendFormData,
        });

        const data = await response.json();

        // Return response
        if (data.predictions) {
            return NextResponse.json({ predictions: data.predictions });
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
        console.error('Food 101 API Error:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
