# View All 69 AI Decisions

## Quick Summary
docker-compose exec -T db psql -U syncboard -d syncboard -c "SELECT decision_type, COUNT(*) as count, ROUND(AVG(confidence_score)*100,1) as avg_confidence_pct FROM ai_decisions WHERE username = 'daz2208' GROUP BY decision_type;"

## Recent 10 Decisions  
docker-compose exec -T db psql -U syncboard -d syncboard -c "SELECT id, decision_type, confidence_score, LEFT(CAST(output_data AS TEXT), 80) as decision_preview, created_at FROM ai_decisions WHERE username = 'daz2208' ORDER BY created_at DESC LIMIT 10;"

## All Low-Confidence Decisions (<70%)
docker-compose exec -T db psql -U syncboard -d syncboard -c "SELECT id, decision_type, confidence_score, created_at FROM ai_decisions WHERE username = 'daz2208' AND confidence_score < 0.7 ORDER BY confidence_score ASC;"

## View Specific Decision Details
docker-compose exec -T db psql -U syncboard -d syncboard -c "SELECT * FROM ai_decisions WHERE username = 'daz2208' AND id = 61;"
