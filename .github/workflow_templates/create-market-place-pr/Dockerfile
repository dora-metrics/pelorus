FROM python:3.11

# TODO create repo for this action and use poetry and dependabot to look the
# python dependencies
RUN pip install "pydantic==1.5.1" "pygithub==1.58.0"

COPY ./main.py /app/main.py

CMD ["python", "/app/main.py"]
