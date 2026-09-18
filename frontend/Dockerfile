FROM node:24-alpine AS base
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM base AS development
COPY . .
EXPOSE 4200

FROM base AS build
COPY . .
RUN npm run build

FROM nginx:1.29-alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/husky-tracking/browser /usr/share/nginx/html
COPY runtime-config.template.js /etc/nginx/templates/runtime-config.template.js
COPY docker/40-runtime-config.sh /docker-entrypoint.d/40-runtime-config.sh
RUN chmod 755 /docker-entrypoint.d/40-runtime-config.sh
EXPOSE 80
