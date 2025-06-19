# frontend/Dockerfile

# ---- Build Stage ----
FROM node:20-slim AS build

WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the frontend code
COPY . .

# Vite automatically loads .env files (like .env.production or .env) during build.
# If you need to pass build arguments from docker-compose to override .env files:
# ARG VITE_API_BASE_URL
# ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
# ARG VITE_WEBSOCKET_URL_PREFIX
# ENV VITE_WEBSOCKET_URL_PREFIX=${VITE_WEBSOCKET_URL_PREFIX}

# Build the React app
RUN npm run build

# ---- Serve Stage ----
FROM nginx:1.25-alpine AS final

# Copy built static files from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80 (Nginx default)
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
