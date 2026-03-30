Module: GitHub Scheduled Workflow

1. Purpose
Provide a low-cost scheduler for private repositories where platform-native cron jobs are unavailable on the free plan.

2. Problem Solved
Triggers the backend daily pipeline from GitHub Actions when platform-native scheduler options are not preferred.

3. File Responsibilities
- daily-pipeline-trigger.yml: Scheduled GitHub Actions workflow that calls the protected pipeline endpoint.

4. Step-by-Step Flow
1. Workflow runs on schedule at 21:30 UTC (03:00 IST).
2. Reads secrets PIPELINE_TRIGGER_URL and CRON_SECRET.
3. Calls backend endpoint with Authorization header.
4. Fails workflow when HTTP status is not 2xx.

5. Interactions with Other Modules
- app/routers/jobs.py validates bearer token and triggers the scheduler function.
- app/schedulers/daily_pipeline.py executes scrape, sentiment, and prediction flow.

6. Assumptions
- GitHub repository supports Actions for scheduled workflows.
- Backend endpoint is reachable from public internet.
- CRON_SECRET is configured in both backend environment and GitHub Actions secrets.

7. Future Improvements
- Add retry with exponential backoff.
- Add Slack/Email notification on failure.
- Add response schema validation for stronger monitoring.
