-- Enable pgvector for retrieval over long filings.
-- LangGraph's PostgresSaver creates its own checkpoint tables via .setup().
CREATE EXTENSION IF NOT EXISTS vector;
