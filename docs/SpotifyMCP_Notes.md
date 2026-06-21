# Spotify MCP — Setup, Usage & Lessons

_Last updated: 2026-06-22_

## What it is
Local MCP server giving Claude Code full Spotify control (playback, search, playlist read/write). Server: **imprvhub/mcp-claude-spotify**.

## Setup
1. **Clone + build**
   ```
   git clone https://github.com/imprvhub/mcp-claude-spotify ~/Documents/mcp-claude-spotify
   cd ~/Documents/mcp-claude-spotify && npm install && npm run build
   ```
   Build output: `~/Documents/mcp-claude-spotify/build/index.js`
2. **Spotify app (developer dashboard)** — reuse existing app; add redirect URI:
   `http://127.0.0.1:8888/callback`
3. **Register MCP** (local scope, project `claude_code_jshao`):
   ```
   claude mcp add spotify -- node ~/Documents/mcp-claude-spotify/build/index.js
   ```
   Env vars: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `PORT=8888`
4. **Authenticate** — run the `auth-spotify` tool. Opens browser login at `http://127.0.0.1:8888/login`. Self-manages tokens (no manual refresh).

## What we did with it
- **Midnight Lounge Café** (100 tracks, public) — cloned the *vibe* (not the tracks) of a "New York Lounge Café" reference playlist: organic-house / bossa-jazz lounge.
- **Nordic Café** (60 tracks, public) — Icelandic neoclassical + Norwegian jazz/indie/downtempo café vibe.
- Built playlists by fanning out `search-spotify` across the artist family, filtering off-vibe results, then `create-playlist` + `add-tracks-to-playlist`.
- Cleaned up library: deleted 3 empty duplicate playlists via `delete-playlist`.

## Notes & lessons
- **Old server was read-only** — playlist writes failed (`Cannot read properties of undefined (reading 'total')`, missing `playlist-modify` scope). This server fixed it.
- **403 on reading some playlists** — Spotify blocks API reads of editorial/algorithmic playlists (Discover Weekly, curated mixes). Workaround: fetch the public web page with WebFetch to get the tracklist.
- **`public: false` doesn't stick** — playlists create as public regardless. Flip visibility manually in-app if needed.
- **Cover upload is clunky** — `upload-playlist-cover` wants base64 JPEG inline. Full-size base64 (~58KB) exceeds the file-read token cap and truncates. Shrink to ~400×400 / <15KB first, or just set the cover manually in the desktop app.
- **Search returns noise** — keyword searches pull in unrelated rap/EDM tracks; always eyeball results before adding.
- `delete-playlist` only **unfollows** (removes from your library) — the playlist still exists on Spotify.
