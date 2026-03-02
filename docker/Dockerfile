FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN useradd -m -u 1000 paidiver

COPY . .

RUN pip install 'poetry~=1.8.0' && \
    poetry config virtualenvs.in-project false && \
    poetry config virtualenvs.create false && \
    poetry install --with lint,test --all-extras && \
    apt-get update && apt-get install -y postgresql-client && \
    chown -R paidiver:paidiver /app

USER paidiver

CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
EXPOSE 8000
