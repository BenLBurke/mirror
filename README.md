# mirror — family photo uploader

This branch/repo is a small static site, separate from the full Magic Mirror
install (see the `master` branch), whose only job is to let family members
add or remove the photos shown on the mirror without touching Git or GitHub
directly.

- `index.html` — the uploader page. Lists the photos currently in
  `Photos/` on the `master` branch, lets you pick new photos or mark old
  ones for removal, and on "Save Changes" commits those adds/deletes
  straight to `master` via the GitHub API.
- `build.sh` — at deploy time, replaces the `MIRROR_TOKEN_PLACEHOLDER`
  string in `index.html` with a real GitHub token (from the `GITHUB_TOKEN`
  environment variable) and writes the result to `dist/index.html`.

## How the photos get to the mirror

The uploader page commits image files to the `Photos/` folder on the
`master` branch of this same repo — the same place you'd normally push to
by hand. Whatever process already pulls that branch onto the Magic Mirror
device will pick up the changes the same way it always has.

## Deploying (Render)

1. Create a GitHub **fine-grained personal access token**
   (https://github.com/settings/personal-access-tokens/new):
   - Repository access: **only** this repository (`BenLBurke/mirror`).
   - Permissions: **Contents: Read and write**. Nothing else.
   - This limits the damage if the token ever leaks — it can only touch
     photos in this one repo, not your account or other repos.
2. In Render, create a **Static Site** pointed at this branch of the repo.
   - Build command: `bash build.sh`
   - Publish directory: `dist`
   - Environment variable: `GITHUB_TOKEN` = the token from step 1.
3. Deploy. Share the resulting Render URL with your family — that's the
   whole login they need.

## Security notes

- The token is baked into the built `index.html` and is visible to anyone
  who loads the page (view source / network tab). Treat the URL like a
  house key: only share it with people you trust, and don't post it
  publicly.
- If you ever suspect the token leaked, revoke it in GitHub settings and
  issue a new one — since it's scoped to just this repo's contents, the
  blast radius is limited to the mirror's photos.
- `dist/` is git-ignored so a locally built copy with a real token
  injected never accidentally gets committed.

## Local testing

`build.sh` requires `GITHUB_TOKEN` to be set, since `index.html` is not
usable until the placeholder is replaced:

```sh
GITHUB_TOKEN=ghp_your_token_here bash build.sh
python3 -m http.server -d dist 8000
```

Then open http://localhost:8000.
