FROM python:3.13-slim
WORKDIR /app
ENV XDG_CONFIG_HOME=/var/lib/mymusik MYMUSIK_DOCKER_DESKTOP=1
RUN mkdir -p /var/lib/mymusik/mymusik-mcp && chown 65534:65534 /var/lib/mymusik/mymusik-mcp && chmod 0700 /var/lib/mymusik/mymusik-mcp
COPY plugins/mymusik/mymusik_mcp/ /app/mymusik_mcp/
COPY LICENSE /app/LICENSE
USER 65534:65534
CMD ["python", "-B", "-m", "mymusik_mcp.cli", "stdio"]
