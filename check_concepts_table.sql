-- Run this in your database to check if concepts table has data
-- Connect to database first:
-- docker-compose exec db psql -U syncboard -d syncboard

-- Check total concepts in concepts table
SELECT COUNT(*) as total_concepts FROM concepts;

-- Check concepts per document
SELECT
    d.doc_id,
    d.filename,
    COUNT(c.id) as concept_count
FROM documents d
LEFT JOIN concepts c ON c.document_id = d.id
GROUP BY d.doc_id, d.filename
ORDER BY concept_count DESC
LIMIT 10;

-- Show sample concepts
SELECT
    d.doc_id,
    d.filename,
    c.name,
    c.category,
    c.confidence
FROM documents d
INNER JOIN concepts c ON c.document_id = d.id
LIMIT 20;

-- Compare: concepts table vs document_summaries key_concepts
SELECT
    'concepts_table' as source,
    COUNT(*) as count
FROM concepts
UNION ALL
SELECT
    'document_summaries' as source,
    COUNT(*) as count
FROM document_summaries
WHERE key_concepts IS NOT NULL;
