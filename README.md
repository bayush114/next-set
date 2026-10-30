# Next Set
A minimal, mobile-friendly workout tracker. Set up exercises once; edit only changed weights and reps, and tap to complete sets. Includes session history, optional body weight, personal best weights and JSON export.

## Run
Serve `dist` with any static server, e.g. `python3 -m http.server 8000 --directory dist`.

## Data
Data stays in browser localStorage, with no analytics or remote database. Different devices do not sync. Export backups before clearing browser data. Export restoration and cloud sync are future improvements.

## Stack
Semantic HTML, responsive CSS, dependency-free JavaScript. No build step.
