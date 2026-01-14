docker build --no-cache -t arxivgpt .
docker tag arxivgpt treepsu/arxivgpt:v01.13.2026
docker push treepsu/arxivgpt:v01.13.2026
