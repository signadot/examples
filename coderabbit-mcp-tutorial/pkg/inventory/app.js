// Holds, retries and expiry share one transaction.
const express = require('express')
const crypto = require('crypto')
const { Pool } = require('pg')

const PORT = process.env.PORT || 8081
const HOLD_SECONDS = Number(process.env.HOLD_SECONDS || 900)
if (!Number.isFinite(HOLD_SECONDS) || HOLD_SECONDS <= 0) throw new Error('HOLD_SECONDS must be positive')
const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgres://boxoffice:boxoffice@postgres:5432/boxoffice',
  connectionTimeoutMillis: 5000,
})

function reservationId(key) {
  return `rsv_${crypto.createHash('sha256').update(key).digest('hex').slice(0, 24)}`
}

function validRequest({ showId, seats, idempotencyKey }) {
  return typeof showId === 'string' && showId.length > 0 && showId.length <= 100 &&
    typeof idempotencyKey === 'string' && idempotencyKey.length > 0 && idempotencyKey.length <= 200 &&
    Array.isArray(seats) && seats.length > 0 && seats.length <= 36 &&
    seats.every(s => typeof s === 'string' && /^[ABC](?:[1-9]|1[0-2])$/.test(s)) &&
    new Set(seats).size === seats.length
}

async function expireHolds(client, showId) {
  await client.query(
    `with expired as (
       update reservations set status = 'expired'
       where show_id = $1 and status = 'held' and expires_at <= clock_timestamp()
       returning show_id, seats
     ) update seats s set status = 'free' from expired r
       where s.show_id = r.show_id and s.seat = any(r.seats)`, [showId])
}

function response(row) {
  return { reservationId: row.reservation_id, status: row.status,
    seats: row.seats, expiresAt: row.expires_at.toISOString() }
}

const app = express()
app.use(express.json())
app.get('/healthz', (_req, res) => res.json({ status: 'ok' }))
app.get('/readyz', async (_req, res, next) => {
  try { await pool.query('select 1'); res.json({ status: 'ready' }) } catch (err) { next(err) }
})

app.get('/shows/:showId/seats', async (req, res, next) => {
  let client
  try {
    client = await pool.connect()
    await client.query('begin')
    await client.query('select pg_advisory_xact_lock(hashtextextended($1, 0))', [`show:${req.params.showId}`])
    await expireHolds(client, req.params.showId)
    const { rows } = await client.query(
      'select seat, status from seats where show_id = $1 order by seat', [req.params.showId])
    await client.query('commit')
    res.json({ showId: req.params.showId, seats: rows })
  } catch (err) {
    if (client) await client.query('rollback').catch(() => {})
    next(err)
  } finally { if (client) client.release() }
})

app.post('/reservations', async (req, res, next) => {
  const input = req.body || {}
  if (!validRequest(input)) return res.status(400).json({ error: 'valid showId, unique seats and idempotencyKey are required' })
  const { showId, idempotencyKey } = input
  const seats = [...input.seats].sort()
  const id = reservationId(idempotencyKey)
  let client
  try {
    client = await pool.connect()
    await client.query('begin')
    // Serialize reuse of one key, including requests for different shows.
    await client.query('select pg_advisory_xact_lock(hashtextextended($1, 0))', [`key:${idempotencyKey}`])
    // Coarse per-show locking is intentional for this 36-seat teaching app.
    // Expiry and new holds must not race across different seat sets.
    await client.query('select pg_advisory_xact_lock(hashtextextended($1, 0))', [`show:${showId}`])
    await expireHolds(client, showId)
    const existing = await client.query('select * from reservations where reservation_id = $1', [id])
    if (existing.rowCount) {
      const row = existing.rows[0]
      if (row.show_id !== showId || JSON.stringify(row.seats) !== JSON.stringify(seats)) {
        await client.query('rollback')
        return res.status(409).json({ error: 'idempotency key was used for a different reservation' })
      }
      if (row.status === 'held') {
        await client.query('commit')
        return res.json(response(row))
      }
    }
    // Lock ALL requested rows, including free seats. Locking only occupied rows
    // lets two callers both observe an empty result and both reserve the seats.
    const selected = await client.query(
      'select seat, status from seats where show_id = $1 and seat = any($2::text[]) order by seat for update',
      [showId, seats])
    if (selected.rowCount !== seats.length) {
      await client.query('rollback')
      return res.status(404).json({ error: 'show or seats do not exist' })
    }
    const unavailable = selected.rows.filter(r => r.status !== 'free').map(r => r.seat)
    if (unavailable.length) {
      await client.query('rollback')
      return res.status(409).json({ error: 'seats are not available', unavailable })
    }
    await client.query("update seats set status = 'held' where show_id = $1 and seat = any($2::text[])", [showId, seats])
    const held = await client.query(
      `insert into reservations (reservation_id, show_id, seats, status, expires_at)
       values ($1, $2, $3, 'held', clock_timestamp() + $4 * interval '1 second')
       on conflict (reservation_id) do update set status = 'held', expires_at = excluded.expires_at
       returning *`, [id, showId, seats, HOLD_SECONDS])
    await client.query('commit')
    res.status(201).json(response(held.rows[0]))
  } catch (err) {
    if (client) await client.query('rollback').catch(() => {})
    next(err)
  } finally { if (client) client.release() }
})

app.use((err, _req, res, _next) => {
  if (err.type === 'entity.parse.failed') return res.status(400).json({ error: 'invalid JSON' })
  console.error('inventory error', err.message)
  res.status(503).json({ error: 'inventory is unavailable' })
})
app.listen(PORT, () => console.log(`inventory listening on ${PORT}`))
