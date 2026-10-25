# Video Studio website (Vercel)

A private website with username/password login. Type a topic → it starts the GitHub
"Make video" workflow directly → live progress → the finished video plays on the page.

Your GitHub token and the passwords live only in Vercel's encrypted environment variables,
never in the browser or the repo. Passwords are stored as scrypt hashes; sessions are signed
HttpOnly cookies that last 7 days.

## 1. Create a GitHub token (lets the website start videos)
GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token
- Repository access: **Only select repositories** → `video-studio`
- Permissions → Repository: **Actions: Read and write**, **Contents: Read-only** (Metadata is added automatically)
- Copy the token (`github_pat_…`).

## 2. Make the logins (on your computer, inside the repo folder)
```bash
node web/tools/add-user.js aviral 'your-strong-password'     # prints one line: aviral:salt:hash
node web/tools/add-user.js friend 'their-strong-password'    # one line per person
node web/tools/make-secret.js                                # prints a random SESSION_SECRET
```
Passwords must be at least 10 characters. Usernames can use letters, numbers, `.`, `_` and `-`.

## 3. Deploy on Vercel
1. vercel.com → **Add New… → Project** → import `gnoknwgnng/video-studio`.
2. **Root Directory: `web`** (important). Framework preset: **Other**. Leave build settings empty.
3. **Environment Variables** (Production):

| Name | Value |
|---|---|
| `GH_TOKEN` | the `github_pat_…` token from step 1 |
| `USERS` | the `add-user` lines joined with commas: `aviral:…:…,friend:…:…` |
| `SESSION_SECRET` | the output of `make-secret.js` |
| `GH_OWNER` | `gnoknwgnng` (optional; this is the default) |
| `GH_REPO` | `video-studio` (optional; this is the default) |

4. **Deploy**. Open the URL Vercel gives you and log in.

## Managing users
- **Add someone:** run `add-user.js`, add the line to `USERS` (comma-separated), then *Deployments → ⋯ → Redeploy*.
- **Remove someone:** delete their entry from `USERS` and redeploy. Their session stops working immediately.
- **Log everyone out:** change `SESSION_SECRET` and redeploy.

## Test locally (optional)
```bash
LOCAL_DEV=1 GH_TOKEN=github_pat_... SESSION_SECRET=$(node web/tools/make-secret.js) \
USERS="$(node web/tools/add-user.js me 'test-password-123')" node web/dev-server.js
# open http://localhost:3000 and log in as me / test-password-123
```
