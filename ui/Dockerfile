FROM nginxinc/nginx-unprivileged:1.27.4-alpine

# Update base Alpine packages to patch known CVEs
USER root
RUN apk update && apk upgrade --no-cache

# Copy non-root nginx configuration and static HTML chat UI
COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html

# Explicit non-root user (UID 101 is the unprivileged nginx user)
USER 101

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
