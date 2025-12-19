'use client';

import { useState, useRef, useEffect } from "react";
import { FiSend } from "react-icons/fi";
import clsx from "clsx";

/**
 * Floating chatbot component
 *
 * Features:
 * - Fixed position at bottom-right corner
 * - Toggle between icon and chat window
 * - Chat with Steven AI (GPT-4o + QA + Docs RAG)
 * - Click outside to close
 * - Animated neon border
 * - Message history with context awareness
 */
export default function Chatbot() {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState<Array<{ sender: string; text: string }>>([]);
    const [messageInput, setMessageInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const chatbotRef = useRef<HTMLDivElement>(null);

    const toggleChat = () => setIsOpen(!isOpen);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!messageInput.trim() || isLoading) return;

        const userMessage = messageInput.trim();
        setMessageInput("");
        setMessages((prev) => [...prev, { sender: "You", text: userMessage }]);
        setIsLoading(true);

        // Determine last Q and A from message history
        let lastQuestion: string | undefined = undefined;
        let lastAnswer: string | undefined = undefined;
        for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].sender === "You" && !lastQuestion) lastQuestion = messages[i].text;
            if (messages[i].sender === "AI" && !lastAnswer) lastAnswer = messages[i].text;
            if (lastQuestion && lastAnswer) break;
        }

        try {
            // Use Next.js API route with fixed configuration (GPT-4o + QA + Docs)
            const response = await fetch('/api/stevenai', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    question: userMessage,
                    lastQuestion,
                    lastAnswer,
                    model: 'ChatGPT-4o',
                    rag: ['QA Pairs', 'Docs of Facts'],
                }),
            });

            const data = await response.json();

            if (data.answer) {
                setMessages((prev) => [...prev, { sender: "AI", text: data.answer }]);
            } else if (data.error) {
                setMessages((prev) => [...prev, { sender: "AI", text: `Error: ${data.error}` }]);
            } else {
                setMessages((prev) => [...prev, { sender: "AI", text: "No response received." }]);
            }
        } catch (error) {
            setMessages((prev) => [...prev, { sender: "AI", text: `Error: ${(error as Error).message}` }]);
        } finally {
            setIsLoading(false);
        }
    };

    // Click outside to close
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (chatbotRef.current && !chatbotRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        if (isOpen) {
            document.addEventListener("mousedown", handleClickOutside);
        }

        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [isOpen]);

    return (
        <div className="fixed bottom-[5vh] right-[5vw] z-99" ref={chatbotRef}>
            {/* Chatbot Icon */}
            {!isOpen && (
                <img
                    src="/project/stevenai.webp"
                    alt="Chatbot"
                    className="w-25 h-25 cursor-pointer animate-[fadeIn_0.2s_ease-in-out]"
                    onClick={toggleChat}
                />
            )}

            {/* Chat Window */}
            {isOpen && (
                <div
                    className="p-0.5 rounded-xl bg-[linear-gradient(90deg,#ff00cc,#00ccff,#8000ff,#b300ff,#ff00cc)] bg-size-[400%_100%] animate-[neonColorFlow_6s_linear_infinite,fadeIn_0.2s_ease-in-out]"
                >
                    <div className="w-[80vw] max-w-85 h-112.5 bg-[#0f172a] rounded-xl flex flex-col overflow-hidden">
                        {/* Header */}
                        <p
                            className="bg-[#0a0a23] text-white p-3 mb-0 font-semibold cursor-pointer"
                            onClick={toggleChat}
                        >
                            Ask Steven AI 🤖
                        </p>

                        {/* Messages */}
                        <div className="flex-1 p-3 overflow-y-auto text-[#e0e0e0]">
                            {messages.map((msg, idx) => (
                                <div
                                    key={idx}
                                    className={clsx(
                                        "mb-2 text-[13px] px-3 py-2 rounded-lg w-[80%]",
                                        msg.sender === 'You'
                                            ? "text-[#61dafb] bg-[rgb(27,41,75)]"
                                            : "text-white bg-[rgb(27,41,75)]"
                                    )}
                                >
                                    {msg.text}
                                </div>
                            ))}
                        </div>

                        {/* Input Form */}
                        <form className="flex p-2.5" onSubmit={handleSubmit}>
                            <input
                                type="text"
                                value={messageInput}
                                onChange={(e) => setMessageInput(e.target.value)}
                                placeholder="Type your message..."
                                className="flex-1 px-2.5 py-2 rounded-lg min-w-0 border-none outline-none text-sm bg-[#0a0a23] text-white"
                            />
                            <button
                                type="submit"
                                className="bg-transparent border-none text-white cursor-pointer flex items-center justify-center p-1"
                                aria-label="Send"
                                disabled={isLoading}
                            >
                                <FiSend size={20} />
                            </button>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
