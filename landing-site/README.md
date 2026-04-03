# Caye Garden Casita — Landing Page

Static landing page for [Caye Garden Casita](https://nm90.github.io/booking-site-mar17) in San Pedro Town, Belize.

## Setup

1. Place the casita exterior photo as `images/casita-exterior.jpg`
2. Deploy to any static hosting (GitHub Pages, Cloudflare Pages, Netlify, etc.)

## Deployment

### GitHub Pages
Push to `main` branch and enable Pages in repo settings.

### Cloudflare Pages
Connect the repo and set the build output directory to `/` (root).

### Netlify
Connect the repo, no build command needed, publish directory: `.`

## CDN Caching

All assets are static and can be cached indefinitely at the CDN edge. The `_headers` file configures caching for Cloudflare Pages / Netlify.
