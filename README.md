# Flower Inventory

**Live site: https://dezzacodes.github.io/flower-glossary/**

A sortable, filterable page of every flower in the inventory spreadsheet, with photos.

- `index.html` is the whole site. Its data sits in the `flower-data` JSON block.
- `images.json` holds the photos, resized to 360px WebP.
- `sync.py` rebuilds both from the Google Sheet. It reads the sheet ID from the `SHEET_ID` environment variable.
- `.github/workflows/sync.yml` runs `sync.py` every day at 19:00 UTC (6am Sydney) and commits any changes, which republishes the site through GitHub Pages. Run it by hand from the **Actions** tab with **Run workflow**.

The sheet must stay shared as "Anyone with the link can view", and the sheet ID is stored as the repository secret `SHEET_ID`.
