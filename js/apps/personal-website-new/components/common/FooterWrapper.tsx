'use client';

import { usePathname } from 'next/navigation';
import Footer from './Footer';

/**
 * Wrapper component that conditionally renders Chatbot
 * based on current route
 *
 * Chatbot is hidden on:
 * - /server page (3D interactive experience)
 * - /stevenAi page (full Steven AI chat interface)
 */
export default function FooterWrapper() {
    const pathname = usePathname();

    // Hide chatbot on specific pages
    const shouldHideFooter = pathname.startsWith('/server');

    if (shouldHideFooter) {
        return null;
    }

    return <Footer />;
}
