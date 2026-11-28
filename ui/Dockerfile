FROM nginx/nginx-unprivileged:1.30.8-alpine@sha256:637c35e46af7bc0dd3d3bcf7162e004e13ab3b370fde7cd416e2ac410b5a985a

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
