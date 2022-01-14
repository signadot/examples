const http = require('http');

const hostname = '127.0.0.1';
const port = 3000;

const server = http.createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain');
  res.write('Baggage header seen by API server: ' + req.headers.baggage + '\n');
  http.get('http://localhost:3001/', (backendRes) => {
    let data = '';
    backendRes.on('data', (chunk) => { data += chunk; });
    backendRes.on('end', () => {
      res.end(data);
    });
  });
});

server.listen(port, hostname, () => {
  console.log(`API server running at http://${hostname}:${port}/`);
});
