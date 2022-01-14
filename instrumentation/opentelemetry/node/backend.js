const http = require('http');

const hostname = '127.0.0.1';
const port = 3001;

const server = http.createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain');
  res.end('Baggage header seen by backend server: ' + req.headers.baggage + '\n');
});

server.listen(port, hostname, () => {
  console.log(`Backend server running at http://${hostname}:${port}/`);
});
