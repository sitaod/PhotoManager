FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
# libgl1-mesa-glx is often needed for opencv-python if used, but here we use Pillow.
# Pillow usually works fine with wheels, but we install basic build tools just in case.
RUN apt-get update && apt-get install -y \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create upload directories if they don't exist (though they should be mounted)
RUN mkdir -p app/static/uploads/originals app/static/uploads/thumbnails

EXPOSE 5000

CMD ["python", "run.py"]
