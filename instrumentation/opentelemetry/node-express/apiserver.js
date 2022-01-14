const http = require('http')

const express = require('express')
const app = express()
const port = 3000

app.get('/', (req, res) => {
  let resp = 'Baggage header seen by API server: ' + req.get('baggage') + '\n'

  http.get('http://localhost:3001/', (backendRes) => {
    let data = ''
    backendRes.on('data', (chunk) => { data += chunk; })
    backendRes.on('end', () => {
      resp += data
      res.send(resp)
    })
  })
})

app.listen(port, () => {
  console.log(`API server listening at http://localhost:${port}`)
})
