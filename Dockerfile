FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY run.py .

# Create data directory for persistent storage
RUN mkdir -p data

# Expose the default port
EXPOSE 8080

# Must bind to 0.0.0.0 inside container so external requests can reach Flask
ENV APP_HOST=0.0.0.0

# Run the application
CMD ["python", "run.py"]
