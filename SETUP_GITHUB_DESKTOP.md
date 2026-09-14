# Complete setup: GitHub Desktop -> GHCR -> Docker Compose

This guide assumes Windows for GitHub Desktop and a Linux Docker host.

## 1. Put the project somewhere easy

Download/extract the project folder. The folder you want GitHub Desktop to manage is the folder containing `Dockerfile`, `compose.yaml`, `.env.example`, `app/`, and `.github/`.

Do **not** create or commit a real `.env` file. `.gitignore` already excludes it.

## 2. Create the GitHub repository with GitHub Desktop

1. Open GitHub Desktop and sign into GitHub.
2. Choose **File -> Add local repository** if you already have the folder, then browse to the project folder. If Desktop says it is not a Git repository, choose the option to create/initialize it there.
3. Give the repository a name such as `mediaart-router`.
4. In the repository bar, click **Publish repository**.
5. For a personal repository, leave Organization as your personal account. Choose **Keep this code private** only if you want the source private.
6. Click **Publish Repository**.

GitHub Desktop supports adding an existing local project and publishing it this way. See the official guide if a button is named slightly differently in your version.

## 3. Make your first commit

In GitHub Desktop you should now see the project files under **Changes**.

Use this commit message:

```text
Initial Media Art Router implementation
```

Click **Commit to main**, then **Push origin**.

## 4. Wait for GitHub Actions to build the container

Open the repository in your browser and click **Actions**. The workflow in `.github/workflows/docker.yml` builds for both `linux/amd64` and `linux/arm64` and publishes to `ghcr.io/<your-account>/<your-repository>`.

The workflow uses the automatically generated `GITHUB_TOKEN` with package-write permission, which is GitHub's documented pattern for publishing to GHCR.

For your first build, wait until the workflow is green before doing anything on the Docker server.

## 5. Make the GHCR package public

For a public self-hosted image that your Docker server can pull anonymously, open the package under your GitHub profile's **Packages** area. Open the container package settings and change visibility to **Public**.

GitHub's Container registry permits anonymous pulls for public container packages. Private packages require authentication.

## 6. Prepare the Linux Docker server

Create a directory such as:

```text
/opt/mediaart-router
```

Inside it create:

```text
/opt/mediaart-router/compose.yaml
/opt/mediaart-router/.env
/opt/mediaart-router/cache/
```

Copy `compose.yaml` and `.env.example` from this project to the server, rename `.env.example` to `.env`, and edit the values.

Change the image line in `compose.yaml` from:

```yaml
image: ghcr.io/REPLACE_ME/mediaart-router:latest
```

to your actual image, for example:

```yaml
image: ghcr.io/tylerwiebe/mediaart-router:latest
```

Use lowercase for the GHCR owner/repository name.

## 7. Minimum .env

```dotenv
TMDB_API_KEY=your_tmdb_key
TVDB_API_KEY=your_tvdb_key
MDBLIST_API_KEY=your_mdblist_key
ACCESS_KEY=make-a-long-random-secret
```

The MDBList key is optional for basic art resolution and custom MDBList trending lists, but it enables the PostersPlus-derived award/keyword sash data. MDBList documents a free API tier and its API endpoint is `https://api.mdblist.com`.

## 8. Start it

On the Linux server:

```bash
cd /opt/mediaart-router
docker compose pull
docker compose up -d
```

Check it:

```bash
docker compose ps
docker compose logs -f --tail=100 mediaart-router
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

You should see JSON containing `{"ok":true}`.

## 9. Put it behind HTTPS

For production, do not expose port 8000 directly to the public internet. Put the container behind your existing reverse proxy (Caddy, Traefik, Nginx Proxy Manager, etc.). Keep `ACCESS_KEY` enabled if the endpoint can be reached by anyone except the intended clients.

## 10. AIOMetadata URLs

Use:

```text
https://YOUR-DOMAIN/poster/tmdb:{type}:{tmdb_id?}&imdb:{imdb_id?}&tvdb:{tvdb_id?}.jpg
https://YOUR-DOMAIN/backdrop/tmdb:{type}:{tmdb_id?}&imdb:{imdb_id?}&tvdb:{tvdb_id?}.jpg
https://YOUR-DOMAIN/logo/tmdb:{type}:{tmdb_id?}&imdb:{imdb_id?}&tvdb:{tvdb_id?}.png
```

The optional `?` placeholders are compatible with the behavior you described: an unavailable identity becomes blank rather than causing the whole URL to be discarded.

## 11. Updating later

The normal loop becomes:

1. Change code/config locally.
2. Open GitHub Desktop.
3. Review **Changes**.
4. Enter a commit message.
5. Click **Commit to main**.
6. Click **Push origin**.
7. GitHub Actions builds a new `latest` image.
8. On the Docker server:

```bash
cd /opt/mediaart-router
docker compose pull
docker compose up -d
```

You do not need to rebuild the image on the Linux server.
