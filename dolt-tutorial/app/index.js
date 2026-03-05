const express = require("express");
const mysql = require("mysql2/promise");

const app = express();
const PORT = process.env.PORT || 3000;

// Connection config from environment variables.
// MYSQL_DBNAME is either "location" (baseline, serves main branch)
// or "location/branchname" (sandbox, serves the sandbox branch).
// The mysql2 driver passes this value directly to Dolt as the database name.
const dbConfig = {
  host: process.env.MYSQL_HOST || "127.0.0.1",
  port: parseInt(process.env.MYSQL_PORT || "3306", 10),
  user: process.env.MYSQL_USER || "root",
  password: process.env.MYSQL_PASSWORD || "",
  database: process.env.MYSQL_DBNAME || "location",
};

let pool;

function getPool() {
  if (!pool) {
    pool = mysql.createPool({
      ...dbConfig,
      waitForConnections: true,
      connectionLimit: 5,
      queueLimit: 0,
    });
  }
  return pool;
}

// GET /locations - list all locations
app.get("/locations", async (req, res) => {
  try {
    const [rows] = await getPool().query("SELECT id, name, coordinates FROM locations ORDER BY id");
    res.json(rows);
  } catch (err) {
    console.error("Error querying locations:", err.message);
    res.status(500).json({ error: err.message });
  }
});

// GET /locations/:id - get a single location
app.get("/locations/:id", async (req, res) => {
  try {
    const [rows] = await getPool().query(
      "SELECT id, name, coordinates FROM locations WHERE id = ?",
      [req.params.id]
    );
    if (rows.length === 0) {
      return res.status(404).json({ error: "Location not found" });
    }
    res.json(rows[0]);
  } catch (err) {
    console.error("Error querying location:", err.message);
    res.status(500).json({ error: err.message });
  }
});

// GET /health - liveness/readiness check
app.get("/health", async (req, res) => {
  try {
    await getPool().query("SELECT 1");
    res.json({ status: "ok", database: dbConfig.database });
  } catch (err) {
    res.status(503).json({ status: "unhealthy", error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Location service listening on port ${PORT}`);
  console.log(`Database: ${dbConfig.host}:${dbConfig.port}/${dbConfig.database}`);
});