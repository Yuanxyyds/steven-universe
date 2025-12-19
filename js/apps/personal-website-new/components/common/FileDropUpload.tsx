'use client';

import { useState } from 'react';
import { IoTrashBin } from 'react-icons/io5';
import Typewriter from 'typewriter-effect';

/**
 * File drop and upload component
 *
 * Features:
 * - Drag & drop file upload
 * - Click to select file
 * - Image preview after selection
 * - Submit and delete actions
 * - Processing state with typewriter animation
 */

interface FileDropUploadProps {
    submitText: string;
    onSubmit: (file: File) => void;
    isProcessing?: boolean;
    processingMessage?: string;
}

export default function FileDropUpload({
    submitText,
    onSubmit,
    isProcessing = false,
    processingMessage = ""
}: FileDropUploadProps) {
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [isDragging, setIsDragging] = useState(false);

    // Handle file selection or drop
    const handleFileAdded = (file: File) => {
        setSelectedFile(file);
        setPreviewUrl(URL.createObjectURL(file));
    };

    const handleFileRemoved = () => {
        if (previewUrl != null) {
            URL.revokeObjectURL(previewUrl);
        }
        setPreviewUrl(null);
        setSelectedFile(null);
    };

    // Handle manual file selection
    const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            handleFileAdded(file);
        }
    };

    // Handle drag events
    const handleDragOver = (event: React.DragEvent) => {
        event.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    // Handle file drop
    const handleDrop = (event: React.DragEvent) => {
        event.preventDefault();
        setIsDragging(false);
        const file = event.dataTransfer.files[0];
        if (file) {
            handleFileAdded(file);
        }
    };

    return (
        <div className="flex justify-center text-center">
            {previewUrl == null ? (
                <form className="animate-[fadeIn_0.3s_ease-in-out]">
                    <input
                        type="file"
                        className="hidden"
                        id="fileInput"
                        onChange={handleInputChange}
                        accept="image/*"
                    />

                    <label
                        htmlFor="fileInput"
                        className={`
                            block w-[min(80vw,800px)] text-center border-4 border-dashed p-20 cursor-pointer
                            transition-colors border-primary
                            ${isDragging ? 'bg-white/20' : ''}
                        `}
                    >
                        <div
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                        >
                            <p className="text-white text-lg">
                                Drag & drop a file here, or click to select one
                            </p>
                        </div>
                    </label>
                </form>
            ) : (
                <div>
                    <div className="w-[min(80vw,800px)] text-center border-4 border-dashed border-primary p-2.5 cursor-pointer">
                        <img src={previewUrl} alt="Preview" className="w-full" />
                    </div>
                    {isProcessing ? (
                        <div className="pt-4 ml-2 text-white text-[1.2em] font-medium" style={{ fontFamily: "'Courier Prime', serif" }}>
                            <Typewriter
                                options={{
                                    strings: [processingMessage],
                                    cursor: '_',
                                    autoStart: true,
                                    loop: true,
                                    deleteSpeed: 200,
                                }}
                            />
                        </div>
                    ) : (
                        <ul className="mt-2.5 list-none p-0 flex gap-2.5 justify-center">
                            <button
                                onClick={() => selectedFile && onSubmit(selectedFile)}
                                type="button"
                                className="bg-transparent border-none text-white cursor-pointer text-lg transition-transform hover:scale-110"
                            >
                                {submitText}
                            </button>
                            <button
                                onClick={handleFileRemoved}
                                type="button"
                                className="bg-transparent border-none text-white cursor-pointer text-lg flex items-center transition-transform hover:scale-110"
                            >
                                <IoTrashBin />
                            </button>
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}
