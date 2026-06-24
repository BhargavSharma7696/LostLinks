# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Set the working directory in the container
ENV APP_HOME /app
WORKDIR $APP_HOME

# Copy only requirements.txt first to leverage Docker cache
COPY requirements.txt ./

# Install production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . ./

# Run the web service on container startup.
# We bind to 0.0.0.0 and listen to the PORT environment variable injected by Cloud Run.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
