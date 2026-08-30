-- Core persistence for the retrieval fabric (sections 7.1 and 7.3).
--
-- Four tables and two join tables, mirroring the contracts exactly: sources,
-- blocks, learning objects, search representations. The contracts are the
-- authority; this schema stores them and adds nothing of its own, so a column
-- here with no field there is a bug rather than a feature.
--
-- Vectors are float8[] in this migration. 002_pgvector.sql converts them to
-- vector(1024) with an HNSW index where the extension is available. Keeping the
-- core schema installable on a stock Postgres is worth more than one file.

CREATE TABLE IF NOT EXISTS sources (
    source_id            text PRIMARY KEY,
    title                text     NOT NULL,
    publisher            text     NOT NULL,
    board                text,
    edition              text     NOT NULL,
    checksum_sha256      char(64) NOT NULL,
    authority_tier       text     NOT NULL,
    language             text     NOT NULL,
    -- QUARANTINED until a named human moves a specific checksum to APPROVED
    -- (section 5). The CHECK is the point: an APPROVED row without a rights
    -- record and a completed scan cannot exist in this table at all.
    approval_state       text     NOT NULL DEFAULT 'QUARANTINED',
    rights               jsonb,
    supersedes_source_id text,
    parser_version       text,
    scanned_clean_at     timestamptz,
    CONSTRAINT approved_sources_carry_rights CHECK (
        approval_state <> 'APPROVED'
        OR (rights IS NOT NULL AND scanned_clean_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS blocks (
    block_id          text PRIMARY KEY,
    source_id         text NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    document_id       text NOT NULL,
    order_index       integer NOT NULL CHECK (order_index >= 0),
    block_type        text NOT NULL,
    raw_label         text,
    page              integer NOT NULL CHECK (page >= 1),
    region_x          double precision NOT NULL,
    region_y          double precision NOT NULL,
    region_width      double precision NOT NULL,
    region_height     double precision NOT NULL,
    text              text,
    latex             text,
    image_uri         text,
    parse_strategy    text NOT NULL,
    parser_version    text NOT NULL,
    parser_confidence double precision,
    linked_block_id   text,
    -- A block that carries nothing cannot anchor a gold label. Enforced here as
    -- well as in the contract, because the database outlives the process.
    CONSTRAINT block_carries_something CHECK (
        text IS NOT NULL OR latex IS NOT NULL OR image_uri IS NOT NULL
    )
);

-- Deletes from sources cascade through this. Unindexed it is a sequential scan
-- per source, which is the defect Foxxy recorded as D-042.
CREATE INDEX IF NOT EXISTS blocks_source_idx ON blocks (source_id);
CREATE INDEX IF NOT EXISTS blocks_document_order_idx ON blocks (document_id, order_index);

CREATE TABLE IF NOT EXISTS learning_objects (
    object_id                text PRIMARY KEY,
    object_type              text NOT NULL,
    source_id                text NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    board                    text NOT NULL,
    curriculum_version       text NOT NULL,
    grade                    text NOT NULL,
    subject                  text NOT NULL,
    unit_id                  text NOT NULL,
    concept_ids              text[] NOT NULL,
    prerequisite_concept_ids text[] NOT NULL DEFAULT '{}',
    heading_path             text NOT NULL,
    text                     text NOT NULL,
    language                 text NOT NULL,
    modality                 text NOT NULL,
    authority_tier           text NOT NULL,
    disclosure_class         text NOT NULL,
    tenant_scope             text,
    parent_object_id         text,
    misconception_id         text,
    tool_proof_required      boolean NOT NULL DEFAULT false,
    composition_version      text NOT NULL,
    content_hash             char(64) NOT NULL,
    approval_state           text NOT NULL DEFAULT 'QUARANTINED',
    retired_at               timestamptz,
    -- Answer protection is structural, not a downstream filter.
    CONSTRAINT solutions_are_never_public CHECK (
        object_type NOT IN ('assessment_solution', 'rubric', 'answer')
        OR disclosure_class <> 'public'
    )
);

CREATE INDEX IF NOT EXISTS learning_objects_source_idx ON learning_objects (source_id);

-- The filter every query applies before ranking (section 5): grade, subject,
-- board, version, and live content only.
CREATE INDEX IF NOT EXISTS learning_objects_curriculum_idx
    ON learning_objects (grade, subject, board, curriculum_version)
    WHERE approval_state = 'APPROVED' AND retired_at IS NULL;

CREATE TABLE IF NOT EXISTS learning_object_blocks (
    object_id text NOT NULL REFERENCES learning_objects(object_id) ON DELETE CASCADE,
    block_id  text NOT NULL REFERENCES blocks(block_id) ON DELETE RESTRICT,
    position  integer NOT NULL,
    PRIMARY KEY (object_id, block_id)
);

CREATE INDEX IF NOT EXISTS learning_object_blocks_block_idx ON learning_object_blocks (block_id);

CREATE TABLE IF NOT EXISTS search_representations (
    representation_id      text PRIMARY KEY,
    object_id              text NOT NULL REFERENCES learning_objects(object_id) ON DELETE CASCADE,
    search_text            text NOT NULL,
    representation_version text NOT NULL,
    content_hash           char(64) NOT NULL,
    heading_path           text NOT NULL DEFAULT '',
    modality               text NOT NULL DEFAULT 'text',
    embedding_model        text,
    embedding_version      text,
    embedding              double precision[],
    -- A vector without the model that produced it cannot be reproduced or
    -- re-embedded, and a model without a vector is a claim about nothing.
    CONSTRAINT embedding_names_its_model CHECK (
        (embedding IS NULL) = (embedding_model IS NULL)
    ),
    CONSTRAINT search_text_is_present CHECK (length(btrim(search_text)) > 0)
);

CREATE INDEX IF NOT EXISTS search_representations_object_idx
    ON search_representations (object_id);

-- Two chunkings coexist during a rechunk, so queries must be able to pick one.
CREATE INDEX IF NOT EXISTS search_representations_version_idx
    ON search_representations (representation_version);

CREATE INDEX IF NOT EXISTS search_representations_fts_idx
    ON search_representations USING gin (to_tsvector('english', search_text));

CREATE TABLE IF NOT EXISTS representation_blocks (
    representation_id text NOT NULL
        REFERENCES search_representations(representation_id) ON DELETE CASCADE,
    block_id          text NOT NULL REFERENCES blocks(block_id) ON DELETE RESTRICT,
    position          integer NOT NULL,
    PRIMARY KEY (representation_id, block_id)
);

CREATE INDEX IF NOT EXISTS representation_blocks_block_idx ON representation_blocks (block_id);
