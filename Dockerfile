FROM python:3.10-slim

ENV TZ=America/New_York

RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/Tree-Shu-Zhao/DailyArXivGPT.git .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 33678
ENV FLASK_ENV=production
CMD ["flask", "run", "--host=0.0.0.0", "--port=33678"]