FROM node:22-alpine
WORKDIR /app
COPY pkg/inventory/package*.json ./
RUN npm ci --omit=dev
COPY pkg/inventory/app.js ./
CMD ["node", "app.js"]
