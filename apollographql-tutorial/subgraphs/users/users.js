const { ApolloServer, gql } = require('apollo-server');
const { buildSubgraphSchema } = require('@apollo/subgraph');
const { readFileSync } = require('fs');

const port = process.env.APOLLO_PORT || 4000;

const users = [
    { email: 'support@apollographql.com', name: "Apollo Studio Support", phoneNumber: "(555) 010-1234", totalProductsCreated: 4 },
    { email: 'support@signadot.com', name: "Signadot Support", phoneNumber: "(555) 030-5678", totalProductsCreated: 7 }
]

const typeDefs = gql(readFileSync('./users.graphql', { encoding: 'utf-8' }));
const resolvers = {
    Query: {
        allUsers: (_, args, context) => {
            return users;
        },
        user: (_, args, context) => {
            return users.find(p => p.email == args.email);
        }
    },
    User: {
        __resolveReference: (reference) => {
            return users.find(u => u.email == reference.email);
        }
    }
}
const server = new ApolloServer({ schema: buildSubgraphSchema({ typeDefs, resolvers }) });
server.listen( {port: port} ).then(({ url }) => {
  console.log(`🚀 Users subgraph ready at ${url}`);
}).catch(err => {console.error(err)});
