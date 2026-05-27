FROM registry.access.redhat.com/ubi9/python-312:1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY example.py .
COPY response.txt .
USER 1001
EXPOSE 8080
CMD ["python", "example.py"]
