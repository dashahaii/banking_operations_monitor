FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python3 -m pip install --upgrade pip && \
    pip3 install -r requirements.txt && \
    pip3 install coreapi pyyaml djangorestframework

# Copy the entire project into the container
COPY . /app

# Expose port 8000 so the container is accessible
EXPOSE 8000

# Set configuration environment variables
ENV DJANGO_SETTINGS_MODULE=banking_operations_monitor.settings
ENV MONGODB_URI=mongodb://mongodb-service:27017/banking_operations_monitor

# Run database migrations and then start the Django development server
CMD python3 manage.py migrate && python3 manage.py runserver 0.0.0.0:8000