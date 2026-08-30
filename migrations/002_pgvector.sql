-- Optional: convert embeddings to pgvector and add an HNSW index.
--
-- Kept separate from 001 so the core schema installs on a stock Postgres.
-- Skipping this migration costs index speed, not correctness: cosine over
-- float8[] still works, it just scans.
--
-- Dimensionality is pinned to 1024 (voyage-3). A provider with a different
-- width needs its own migration, which is the right amount of friction for a
-- change that invalidates every stored vector.

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE search_representations
    ALTER COLUMN embedding TYPE vector(1024)
    USING embedding::vector(1024);

-- m and ef_construction follow Foxxy's measured configuration. Note that
-- ef_search defaults to 40 at query time, which silently caps a top-50
-- retrieval at 40 candidates unless it is raised per session (Foxxy D-041) --
-- that reads as a thin corpus rather than as a misconfiguration.
CREATE INDEX IF NOT EXISTS search_representations_hnsw_idx
    ON search_representations USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);
