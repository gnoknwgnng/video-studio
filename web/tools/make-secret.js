// Prints a random SESSION_SECRET for Vercel:  node web/tools/make-secret.js
console.log(require("crypto").randomBytes(32).toString("hex"));
