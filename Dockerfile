FROM python:3.8-slim

ENV TZ=America/New_York

WORKDIR /usr/src/app
COPY . /usr/src/app
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 33678
ENV FLASK_ENV=production
CMD ["flask", "run", "--host=0.0.0.0", "--port=33678"]