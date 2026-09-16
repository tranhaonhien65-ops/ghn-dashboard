FROM python:3.9-slim
WORKDIR /app
COPY . /app
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "python3 server.py $PORT"]
