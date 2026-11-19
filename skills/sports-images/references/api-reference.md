# Sports Images: API Reference

Source: Wikimedia Commons (files and licenses) through Wikidata (entity resolution). No API key.

## Commands

### find_images

Open-licensed photos of a sports person, team or venue.

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `name` | string | | Name to look up. Required unless `qid` is given |
| `qid` | string | | Wikidata id such as `Q9617`. Skips the name lookup |
| `kind` | string | | `person`, `team` or `venue`. Also accepts `player`, `coach`, `driver`, `club`, `stadium`, `arena` |
| `min_long_edge` | int | 3000 | Smallest accepted long edge in pixels. 3840 is 4K |
| `limit` | int | 10 | 1 to 50 |
| `orientation` | string | `any` | `any`, `landscape`, `portrait` or `square` |
| `allow_sharealike` | bool | true | `false` leaves CC BY-SA images out |
| `sort` | string | `recent` | `recent` (files whose title names the entity first, then date taken) or `largest` (pixel count) |
| `width` | int | 3840 | Width of the `preview_url` rendition, 100 to 12000 |
| `language` | string | `en` | Language of the name lookup and of the labels, such as `pt` or `es` |

Returns `entity`, `images`, `count`, `filters`, `skipped`, `alternatives`, `usage_notes` and `source`. When nothing passes the filters, `count` is 0 and `message` says why.

### search_entities

Sports people, teams and venues on Wikidata that match a name.

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `query` | string | | Required |
| `kind` | string | | `person`, `team` or `venue` |
| `limit` | int | 5 | 1 to 8 |
| `language` | string | `en` | |

Returns `entities`: each with `qid`, `label`, `description`, `kind`, `commons_category` and `wikidata_url`.

### get_image

License, author, credit line and a sized rendition for one Commons file.

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `file` | string | | Required. `File:Name.jpg`, `Name.jpg` or a `commons.wikimedia.org/wiki/File:` URL |
| `width` | int | 3840 | Width of the `preview_url` rendition |

Returns `image` and `usage_notes`. Fails with a message when the file does not exist, is not a photo, or is not under an accepted license.

## Image fields

| Field | Meaning |
|---|---|
| `title` | Commons file title |
| `file_page` | The file's page on Commons, with the full license text |
| `original_url` | Full-resolution file |
| `width`, `height`, `megapixels` | Size of the original |
| `orientation` | `landscape`, `portrait` or `square` |
| `mime` | `image/jpeg`, `image/tiff` or `image/webp` |
| `preview_url`, `preview_width`, `preview_height` | Rendition at the requested `width`; the original when it is narrower |
| `license.name`, `license.url` | For example `CC BY-SA 4.0` |
| `license.family` | `public-domain`, `cc-by`, `cc-by-sa` or `attribution` |
| `license.attribution_required` | `false` only for public domain and CC0 |
| `license.sharealike` | `true` for CC BY-SA |
| `author` | Photographer or uploader, as written on Commons |
| `credit` | Ready credit line: author, license, "via Wikimedia Commons" |
| `date` | Date taken (`YYYY-MM-DD` or a year), or null |
| `description` | Uploader's description, plain text, up to 300 characters |
| `restrictions` | Rights beyond copyright that Commons flags, such as `personality` or `trademark` |
| `match` | `depicts` or `category`: how the file was found (`file` for `get_image`) |

## Accepted licenses

Public domain and CC0, CC BY, CC BY-SA, and the Commons "Attribution" license. Files under other terms (GFDL only, Free Art License, non-commercial or no-derivatives variants) are counted in `skipped.license` and not returned.

## Limits and behavior

- Photos only: JPEG, TIFF and WebP. Logos, crests and diagrams (SVG, PNG) are left out; use `metadata` for logos.
- Each Commons query returns the 50 newest uploads that pass a loose size floor; the exact filters run after that.
- People are searched through their whole Commons category tree. Teams and venues use the top category only, because their trees reach unrelated people and places.
- Responses are cached in memory for 15 minutes. Requests are rate limited to about 2 per second.
- `SPORTS_SKILLS_REPLAY` record and replay apply to this module.
