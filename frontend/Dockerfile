# Stage 1: Build
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
# Nginx config for SPA routing
RUN echo 'server { \
    listen 3010; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { try_files $uri $uri/ /index.html; } \
    location /api { proxy_pass http://api:8010; } \
    location /health { proxy_pass http://api:8010; } \
}' > /etc/nginx/conf.d/default.conf
EXPOSE 3010
CMD ["nginx", "-g", "daemon off;"]
