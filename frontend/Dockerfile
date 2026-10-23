# syntax=docker/dockerfile:1

# Stage 1: Build the React/Vite single-page application
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies using package-lock for reproducible builds
COPY package.json package-lock.json ./
RUN npm ci

# Copy source code and build production bundle
COPY . .
RUN npm run build

# Stage 2: Production web server serving static assets and proxying API
FROM nginx:1.27-alpine AS runner

# Remove default nginx configuration
RUN rm -rf /etc/nginx/conf.d/default.conf

# Copy custom Nginx configuration with SPA routing and API proxy
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
