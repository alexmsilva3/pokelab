# Estagio de desenvolvimento: servidor do Vite com recarga automatica.
#
# Escuta na porta 80 de proposito, para reaproveitar o mapeamento que o
# docker-compose.yml ja declara (WEB_PORT:80) sem que o override precise
# redeclarar portas — portas em override sao somadas, nao substituidas, e
# redeclarar causaria conflito de bind.
FROM node:24-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm ci
EXPOSE 80
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "80"]

FROM node:24-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
