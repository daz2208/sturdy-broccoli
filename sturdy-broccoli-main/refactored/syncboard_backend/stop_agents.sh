# HOW TO STOP/CONTROL AGENTS TO SAVE API COSTS

## OPTION 1: Stop Agent Workers Completely (RECOMMENDED)
# Stop Learning Agent (observes patterns, makes autonomous decisions)
docker-compose stop celery-worker-learning

# Stop Maverick Agent (challenges decisions, tests hypotheses)  
docker-compose stop celery-worker-maverick

# Stop Beat Scheduler (triggers periodic agent tasks)
docker-compose stop celery-beat

## OPTION 2: Restart Agents When Needed
# Start them back up
docker-compose start celery-worker-learning
docker-compose start celery-worker-maverick
docker-compose start celery-beat

## OPTION 3: Permanently Disable in docker-compose.yml
# Comment out these services in docker-compose.yml:
# - celery-worker-learning
# - celery-worker-maverick  
# - celery-beat
# Then: docker-compose up -d

## CHECK AGENT STATUS
docker-compose ps | grep celery

## VIEW WHAT AGENTS ARE DOING RIGHT NOW
docker-compose logs --tail=20 celery-worker-learning
docker-compose logs --tail=20 celery-worker-maverick

## COST BREAKDOWN
# - Learning Agent: Runs every 5 minutes, makes 1-2 API calls (checking patterns)
# - Maverick Agent: Runs every 10-15 minutes, makes 1-3 API calls (testing)
# - These are MINIMAL costs (~$0.01-0.05/day with gpt-4o-mini)
# - Main API costs come from: document uploads, concept extraction, build suggestions

## KEEP THESE RUNNING (ESSENTIAL):
# - celery-worker-uploads (processes document uploads)
# - celery-worker-analysis (concept extraction, clustering)
# - backend (API server)
