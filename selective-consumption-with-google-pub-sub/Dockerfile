FROM node:20 AS build

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy package.json and package-lock.json to the working directory
COPY package*.json ./

# Install application dependencies
RUN npm install

# Copy the application code to the container
COPY . .


FROM node:20-alpine AS main

# Copy app from build
COPY --from=build /usr/src/app /usr/src/app

# Set the working directory in the container
WORKDIR /usr/src/app

# Define the command to run your application
USER node
CMD [ "npm", "start" ]
