CSS = """
body {
    background-color: #1f1f2e;
    color: #f5f5f5;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.gradio-container {
    border-radius: 12px;
    padding: 20px;
}

.tab-content {
    background-color: #2c2c3e;
    border-radius: 8px;
    padding: 20px;
    margin-top: 10px;
}

.gr-button {
    background-color: #4f46e5;
    color: white;
    border-radius: 8px;
    border: none;
    padding: 10px 20px;
    font-weight: bold;
    margin: 5px;
}

.gr-button:hover {
    background-color: #6366f1;
}

.clear-btn {
    background-color: #dc2626 !important;
}

.clear-btn:hover {
    background-color: #ef4444 !important;
}

.gradio-tabs button {
    background-color: #3b3b4e;
    color: #f5f5f5;
    border-radius: 8px 8px 0 0;
    padding: 10px 20px;
    margin-right: 2px;
    font-weight: bold;
}

.gradio-tabs button:focus {
    outline: none;
    background-color: #57577f;
}

.status-text {
    color: #10b981;
    font-weight: bold;
    margin: 10px 0;
}

.recording-status {
    color: #f59e0b;
    font-weight: bold;
}

/* Make conversation history scrollable */
.conversation-history {
    max-height: 400px;
    overflow-y: auto;
    border: 1px solid #4b5563;
    border-radius: 8px;
    padding: 10px;
    background-color: #374151;
}

/* Scrollbar styling for conversation history */
.conversation-history::-webkit-scrollbar {
    width: 8px;
}

.conversation-history::-webkit-scrollbar-track {
    background: #4b5563;
    border-radius: 4px;
}

.conversation-history::-webkit-scrollbar-thumb {
    background: #6b7280;
    border-radius: 4px;
}

.conversation-history::-webkit-scrollbar-thumb:hover {
    background: #9ca3af;
}
"""