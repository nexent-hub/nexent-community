FROM nexent/nexent-base
LABEL authors="nexent"

# Set correct permissions as root
USER root
COPY backend /opt/backend
COPY make/start.sh /opt/deployment/start.sh

# Update SDK
COPY sdk /opt/sdk
RUN cd /opt/sdk && pip install --user --no-cache-dir . -i https://mirrors.aliyun.com/pypi/simple

WORKDIR /opt

# Expose the service port
EXPOSE 5010

# Set the entrypoint
RUN chmod +x /opt/deployment/start.sh
ENTRYPOINT ["sh", "-c", "umask 0022 && /opt/deployment/start.sh"]