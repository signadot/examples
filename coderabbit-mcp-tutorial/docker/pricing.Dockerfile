FROM node:22-alpine
WORKDIR /app
COPY pkg/pricing/package*.json ./
RUN npm ci --omit=dev
COPY pkg/pricing/app.js ./
CMD ["node", "app.js"]
