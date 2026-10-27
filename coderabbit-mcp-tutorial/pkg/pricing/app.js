// pricing quotes a seat selection. Amounts are integers in the currency's
// minor unit (cents, not dollars). Exchange rates use basis points.
const express = require('express')
const redis = require('redis')

const PORT = process.env.PORT || 8082
const CACHE_SECONDS = Number(process.env.CACHE_SECONDS || 60)
// Baseline and sandbox share Redis, but must not share computed quotes.
const CACHE_NAMESPACE = process.env.CACHE_NAMESPACE || 'baseline-v2'

const client = redis.createClient({ url: process.env.REDIS_URL || 'redis://redis:6379' })
client.on('error', (err) => console.error('redis error', err))
client.connect().catch((err) => console.error('redis connect failed', err))

// Row A is the expensive one. Prices are per seat, in minor units.
const SEAT_PRICE = { A: 4500, B: 3500, C: 2500 }
const DEFAULT_PRICE = 2000
const FEE_BASIS_POINTS = 500 // 5% booking fee
const RATE_FROM_USD = { USD: 10000, EUR: 9200, GBP: 7900 }

function seatPrice(seat) {
  return SEAT_PRICE[seat[0]] ?? DEFAULT_PRICE
}

// Integer arithmetic throughout. Converting currency rounds once, at the end of
// each component, so subtotal + fees always equals total.
function quote(seats, currency) {
  const rate = RATE_FROM_USD[currency]
  const subtotalUsd = seats.reduce((sum, seat) => sum + seatPrice(seat), 0)
  const subtotal = Math.round(subtotalUsd * rate / 10000)
  const fees = Math.round((subtotal * FEE_BASIS_POINTS) / 10000)
  return { currency, subtotal, fees, total: subtotal + fees }
}

// Include the runtime namespace, show, currency and canonical seat selection.
function cacheKey(showId, seats, currency) {
  return `quote:${CACHE_NAMESPACE}:${showId}:${currency}:${[...seats].sort().join(',')}`
}

const app = express()
app.use(express.json())

app.get('/healthz', (_req, res) => res.json({ status: 'ok' }))
app.get('/readyz', async (_req, res, next) => {
  try { await client.ping(); res.json({ status: 'ready' }) } catch (err) { next(err) }
})

app.post('/quotes', async (req, res, next) => {
  const { showId, seats, currency = 'USD' } = req.body || {}
  if (typeof showId !== 'string' || !showId || showId.length > 100 ||
      !Array.isArray(seats) || seats.length === 0 || seats.length > 36 ||
      !seats.every(s => typeof s === 'string' && /^[ABC](?:[1-9]|1[0-2])$/.test(s)) ||
      new Set(seats).size !== seats.length) {
    return res.status(400).json({ error: 'showId and a non-empty seats array are required' })
  }
  if (typeof currency !== 'string' || !Object.hasOwn(RATE_FROM_USD, currency)) {
    return res.status(400).json({ error: 'currency must be USD, EUR or GBP' })
  }

  try {
    const key = cacheKey(showId, seats, currency)
    const cached = await client.get(key)
    if (cached) {
      return res.json(JSON.parse(cached))
    }

    const result = quote(seats, currency)
    await client.setEx(key, CACHE_SECONDS, JSON.stringify(result))
    res.json(result)
  } catch (err) {
    next(err)
  }
})

app.use((err, _req, res, _next) => {
  if (err.type === 'entity.parse.failed') return res.status(400).json({ error: 'invalid JSON' })
  console.error('pricing error', err.message)
  res.status(500).json({ error: 'pricing is unavailable' })
})

app.listen(PORT, () => console.log(`pricing listening on ${PORT}`))
