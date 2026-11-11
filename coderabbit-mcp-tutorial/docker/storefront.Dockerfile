FROM node:22-alpine
WORKDIR /app
COPY pkg/storefront/package*.json ./
RUN npm ci --omit=dev
COPY pkg/storefront/app.js ./
CMD ["node", "app.js"]
