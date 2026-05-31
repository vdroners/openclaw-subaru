FROM python:3.12-slim

WORKDIR /app

COPY services/subaru-bridge/requirements.txt /tmp/bridge-req.txt
RUN pip install --no-cache-dir -r /tmp/bridge-req.txt

COPY scripts/lib /app/scripts/lib
COPY services/subaru-bridge/app.py /app/app.py

COPY services/subaru-bridge/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONPATH=/app/scripts/lib
EXPOSE 8790

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8790"]
