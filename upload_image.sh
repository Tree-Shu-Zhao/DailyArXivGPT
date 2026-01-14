docker build --no-cache -t daily-ai-digest .
docker tag daily-ai-digest treepsu/daily-ai-digest:v01.14.2026
docker push treepsu/daily-ai-digest:v01.14.2026
