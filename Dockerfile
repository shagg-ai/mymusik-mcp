FROM python:3.13-slim
WORKDIR /app
COPY plugins/mymusik/mymusik_mcp/ /app/mymusik_mcp/
USER 65534:65534
CMD ["python", "-B", "-m", "mymusik_mcp.cli", "stdio"]
