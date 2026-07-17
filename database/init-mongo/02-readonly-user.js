// Read-only role only: no readWrite/dbAdmin. Combined with the adapter never exposing a
// write method, this is the server-side half of MongoDB's double no-write guarantee.
const demoPassword = process.env.MONGO_DEMO_PASSWORD;
if (!demoPassword) {
  throw new Error("MONGO_DEMO_PASSWORD is required to create mcp_readonly");
}

db.createUser({
  user: "mcp_readonly",
  pwd: demoPassword,
  roles: [{ role: "read", db: db.getName() }],
});
