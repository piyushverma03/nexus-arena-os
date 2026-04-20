FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=True \
    # Cloud Run relies on the PORT environment variable
    PORT=8080

WORKDIR /app

# Copy requirements
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Initialize the Nexus Arena mock database for the container
RUN python -c "from backend.database import init_db, seed_data; init_db(); seed_data()"

# Expose the Cloud Run port
EXPOSE 8080

# Command to run the Fast API backend server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
