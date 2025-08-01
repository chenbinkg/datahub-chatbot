# Use pip for Gradio UI (pixi has template/path issues)
FROM python:3.11.11-slim

WORKDIR /app

# Copy requirements and install with pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 7860

CMD ["python", "app.py"]