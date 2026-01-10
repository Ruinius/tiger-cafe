import React, { useState } from 'react';

const DuplicateConfirmationModal = ({
    isOpen,
    onClose,
    onSignIn, // Not used but good to have signature consistency
    duplicateResults, // Array of { filename, is_potential_duplicate, existing_document }
    onProceed // Callback(filesToUpload)
}) => {
    const [selectedFiles, setSelectedFiles] = useState(
        duplicateResults.map(r => r.filename) // Default select all, or maybe deselect duplicates? Let's select all but warn.
    );

    if (!isOpen) return null;

    const toggleFile = (filename) => {
        setSelectedFiles(prev =>
            prev.includes(filename)
                ? prev.filter(f => f !== filename)
                : [...prev, filename]
        );
    };

    const handleProceed = () => {
        onProceed(selectedFiles);
        onClose();
    };

    const duplicatesCount = duplicateResults.filter(r => r.is_potential_duplicate).length;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-lg bg-[#1C1C1E] border border-white/10 rounded-2xl shadow-2xl overflow-hidden scale-in-95 zoom-in-95 duration-200">

                {/* Header */}
                <div className="p-6 border-b border-white/10">
                    <h2 className="text-xl font-semibold text-white">
                        {duplicatesCount > 0 ? "Duplicate Files Detected" : "Confirm Upload"}
                    </h2>
                    <p className="mt-2 text-sm text-white/60">
                        {duplicatesCount > 0
                            ? "Some files appear to be duplicates. Please confirm which files you want to upload."
                            : "Please review the files before uploading."}
                    </p>
                </div>

                {/* File List */}
                <div className="max-h-[300px] overflow-y-auto p-4 space-y-2">
                    {duplicateResults.map((result, idx) => (
                        <div
                            key={idx}
                            onClick={() => toggleFile(result.filename)}
                            className={`
                group flex items-center justify-between p-3 rounded-xl border transition-all cursor-pointer
                ${selectedFiles.includes(result.filename)
                                    ? 'bg-white/5 border-white/20'
                                    : 'bg-transparent border-transparent opacity-50 hover:bg-white/5'}
              `}
                        >
                            <div className="flex items-center gap-3 overflow-hidden">
                                {/* Checkbox */}
                                <div className={`
                  w-5 h-5 rounded-full border flex items-center justify-center transition-colors
                  ${selectedFiles.includes(result.filename)
                                        ? 'bg-blue-500 border-blue-500'
                                        : 'border-white/30 group-hover:border-white/50'}
                `}>
                                    {selectedFiles.includes(result.filename) && (
                                        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                        </svg>
                                    )}
                                </div>

                                <div className="flex flex-col overflow-hidden">
                                    <span className="text-sm font-medium text-white truncate">{result.filename}</span>
                                    {result.is_potential_duplicate && result.existing_document && (
                                        <span className="text-xs text-orange-400">
                                            Duplicate of {result.existing_document.filename} (Uploaded by {result.existing_document.uploaded_by})
                                        </span>
                                    )}
                                    {!result.is_potential_duplicate && (
                                        <span className="text-xs text-green-400">New File</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-white/10 flex justify-end gap-3 bg-[#1C1C1E]">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-white/60 hover:text-white transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleProceed}
                        disabled={selectedFiles.length === 0}
                        className={`
              px-4 py-2 text-sm font-semibold rounded-lg bg-white text-black transition-all
              ${selectedFiles.length === 0 ? 'opacity-50 cursor-not-allowed' : 'hover:scale-[1.02] active:scale-[0.98]'}
            `}
                    >
                        Upload {selectedFiles.length} Files
                    </button>
                </div>
            </div>
        </div>
    );
};

export default DuplicateConfirmationModal;
