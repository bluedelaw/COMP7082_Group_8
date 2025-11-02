CSS = """
/* ---- Base theme ---- */
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

/* ---- Buttons ---- */
.gr-button {
    background-color: #4f46e5;
    color: white;
    border-radius: 8px;
    border: none;
    padding: 10px 20px;
    font-weight: bold;
    margin: 5px;
    min-height: 40px; /* stable */
}
.gr-button:hover { background-color: #6366f1; }
.clear-btn { background-color: #dc2626 !important; }
.clear-btn:hover { background-color: #ef4444 !important; }
.button_row { gap: 8px; }

/* ---- Tabs ---- */
.gradio-tabs button {
    background-color: #3b3b4e;
    color: #f5f5f5;
    border-radius: 8px 8px 0 0;
    padding: 10px 20px;
    margin-right: 2px;
    font-weight: bold;
}
.gradio-tabs button:focus { outline: none; background-color: #57577f; }

/* ---- Status & info ---- */
.status-text { color: #10b981; font-weight: bold; margin: 10px 0; }
.recording-status { color: #f59e0b; font-weight: bold; }

/* ---- Live tab stable grid ---- */
.live-grid {
    display: grid !important;
    grid-template-columns: 360px minmax(0, 1fr);
    gap: 16px;
    align-items: start;
}

/* Controls column header spacing */
#controls_header .prose { margin: 0 !important; }

/* Reserve fixed height for banner & metrics to prevent layout shift */
#status_banner,
#status_banner .prose {
    min-height: 28px;
    line-height: 28px;
    margin: 0 !important;
    display: block;
}
#metrics_bar,
#metrics_bar .prose {
    min-height: 24px;
    line-height: 24px;
    margin: 8px 0 0 0 !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    letter-spacing: 0.2px;
}

/* Pin heights of the two main text areas */
#transcription_box textarea {
    height: 56px !important;     /* ~2 lines */
    min-height: 56px !important;
    resize: none !important;
}
#ai_reply_box textarea {
    height: 160px !important;    /* ~6-7 lines */
    min-height: 160px !important;
    resize: vertical;            /* allow manual, but has min-height */
}

/* Conversation history – fixed height and stable scrollbar */
.conversation-history {
    max-height: 320px;
    height: 320px;
    overflow-y: auto !important;
    border: 1px solid #4b5563 !important;
    border-radius: 8px;
    padding: 10px;
    background-color: #374151 !important;
}
.conversation-history::-webkit-scrollbar { width: 8px; }
.conversation-history::-webkit-scrollbar-track { background: #4b5563; border-radius: 4px; }
.conversation-history::-webkit-scrollbar-thumb { background: #6b7280; border-radius: 4px; }
.conversation-history::-webkit-scrollbar-thumb:hover { background: #9ca3af; }

/* Minor: trim default markdown margins globally to avoid bumps */
.gr-markdown, .gr-prose, .prose { margin-top: 0.25rem; margin-bottom: 0.25rem; }
"""
