'use client';

import { usePathname } from 'next/navigation';
import Chatbot from './Chatbot';

/**
 * Wrapper component that conditionally renders Chatbot
 * based on current route
 *
 * Chatbot is hidden on:
 * - /server page (3D interactive experience)
 * - /stevenAi page (full Steven AI chat interface)
 */
export default function ChatbotWrapper() {
    const pathname = usePathname();

    // Hide chatbot on specific pages
    const shouldHideChatbot = pathname.startsWith('/server') || pathname.startsWith('/stevenAi');

    if (shouldHideChatbot) {
        return null;
    }

    return <Chatbot />;
}
