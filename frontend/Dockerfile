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
EXPOSE 80
