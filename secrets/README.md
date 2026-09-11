# secrets/

Real credentials that shouldn't go anywhere near git, kept here instead of
scattered across Downloads/Desktop so they're findable later. Everything in
this folder is gitignored except this file — the folder itself still shows
up in the repo (so it's not forgotten), nothing inside it does.

## What lives here

- `firebase-adminsdk.json` — Firebase Admin SDK service account key for the
  `ai-voice-labs-473713` project (reused from the prior project on purpose,
  see `CLAUDE.md`). Referenced from `backend/.env`'s `FIREBASE_CREDENTIALS_PATH`.
  Get a new one anytime from the Firebase console: Project settings →
  Service accounts → Generate new private key.

Add future ones (R2 access keys if you'd rather keep the raw values here too,
etc.) the same way — drop the file in, note what it is above.
