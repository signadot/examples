const express = require('express')
const app = express()
const port = 3001

app.get('/', (req, res) => {
  res.send('Baggage header seen by backend server: ' + req.get('baggage') + '\n')
})

app.listen(port, () => {
  console.log(`Backend server listening at http://localhost:${port}`)
})
