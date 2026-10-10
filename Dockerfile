FROM python:3.11-slim

WORKDIR /app

# Show print()/logging output immediately in `docker logs` instead of
# being buffered until the container stops.
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# --server.address=0.0.0.0: without this, Streamlit binds to
# localhost *inside* the container, which is unreachable from the
# host machine even with -p 8501:8501.
# --server.headless=true: skips Streamlit's first-run "Welcome" email
# prompt, which otherwise waits on stdin and blocks the container from
# ever finishing startup.
CMD ["streamlit", "run", "io_gui/io_gui.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true"]
