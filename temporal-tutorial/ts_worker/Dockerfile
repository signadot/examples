FROM node:22-slim AS build

WORKDIR /app

# Install dependencies first to leverage Docker cache
COPY package.json package-lock.json* ./
RUN npm install

# Copy sources and compile TypeScript
COPY tsconfig.json ./
COPY src/ src/
RUN npm run build

FROM node:22-slim

WORKDIR /app

COPY --from=build /app/package.json /app/package-lock.json* ./
COPY --from=build /app/node_modules node_modules/
COPY --from=build /app/lib lib/

USER node

# Command to run the Temporal worker
CMD ["node", "lib/worker.js"]
