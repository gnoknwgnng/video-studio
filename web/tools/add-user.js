// Create a login for the web app.
//   node web/tools/add-user.js aviral 'a-strong-password'
// Copy the printed line into the USERS environment variable in Vercel (comma-separate several users).
const { hashPassword } = require("../lib/core");
const [name, password] = process.argv.slice(2);
if (!name || !password) { console.error("Usage: node web/tools/add-user.js USERNAME PASSWORD"); process.exit(1); }
if (!/^[a-z0-9._-]{2,32}$/i.test(name)) { console.error("Username: 2-32 letters, numbers, . _ -"); process.exit(1); }
if (password.length < 10) { console.error("Use a password of at least 10 characters."); process.exit(1); }
const { salt, hash } = hashPassword(password);
console.log(`${name.toLowerCase()}:${salt}:${hash}`);
