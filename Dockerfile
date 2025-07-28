FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directories and set permissions
RUN mkdir -p /app/data/backups && \
    chmod -R 777 /app/data && \
    chmod +x entrypoint.sh

EXPOSE 5010

ENTRYPOINT ["./entrypoint.sh"]