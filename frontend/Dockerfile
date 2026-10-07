# syntax=docker/dockerfile:1
# Контекст сборки — корень репозитория (нужен deploy/nginx). Итоговый образ — nginx со статикой SPA.
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/yarn.lock ./
RUN yarn install --frozen-lockfile
COPY frontend/ ./
RUN yarn build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 101
EXPOSE 8080 8443
