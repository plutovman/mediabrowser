# MediaBrowser Copilot Instructions

## Overview
MediaBrowser is a Flask web application for browsing, searching, and managing media assets (images and videos) stored in a SQLite database. Features include multi-field search, pagination, grid/table views, modal previews, and a session-based cart system.

## Architecture & Data Flow
- **Single-file Flask app** ([mediabrowser.py](../mediabrowser.py)) with no ORM - uses direct sqlite3 queries
- **Media storage**: All files served from `$DEPOT_ALL/assetdepot/media` (defined in `path_base_media`)
- **Database**: SQLite at `$DEPOT_ALL/assetdepot/media/dummy/db/media_dummy.sqlite`
- **Static file serving**: Flask serves the entire media directory as `static_folder=path_base_media`
- **Path enrichment pattern**: `enrich_media_paths()` transforms DB paths (`$DEPOT_ALL/...`) to relative paths for Flask's `url_for('static', filename=...)`

## Database Schema (media table)
```python
# Full column list from get_db_connection():
file_id, file_name, file_path, file_type, file_format, 
file_resolution, file_duration, shot_size, shot_type, 
source, source_id, genre, subject, category, lighting, 
setting, tags, captions
```

## Key Routes & Responsibilities
- **`/` (index)**: Displays random media item from database
- **`/search`**: Main search interface with dual GET/POST behavior:
  - GET: Query parameters for search/filter/pagination
  - POST: Add selected items to cart (stores `file_id` in session)
- **`/cart`**: View items in cart (session-stored `file_id` list)
- **`/clear_cart`**: Empties cart and redirects

## Search Implementation Patterns
1. **Standard filters** (subject/setting/lighting/file_type): SQL `LIKE` with wildcards
2. **Caption search**: Special handling - filters in Python using regex word boundary matching across sentence splits
3. **Dynamic PER_PAGE**: Table view = 10 items, Grid view = 30 items
4. **Pagination**: Standard LIMIT/OFFSET with `math.ceil(total/per_page)` for page count

## Critical Path Enrichment Logic
The `enrich_media_paths()` function is essential for serving files:
1. Replaces `$DEPOT_ALL` placeholder with actual path from environment
2. Computes `relative_path` from `path_base_media` for Flask static serving
3. **Video thumbnail logic**: For `.mp4` files, checks for corresponding `.jpg`/`.png` with same basename

## Template Architecture
All templates ([templates/](../templates/)) share:
- Dark theme (`#242424` background, `#f0f0f0` text)
- Modal system for full-size image/video preview
- Play button overlay for videos using `data-open-video` attributes
- Cart indicator in top-right corner showing `session.get('cart', [])|length`

## Environment Setup & Running
```bash
export DEPOT_ALL=/path/to/depot  # REQUIRED - defines media root
python mediabrowser.py           # Runs in debug mode on localhost:5000
```

## Development Conventions
- **Path construction**: Always use `os.path.join()`, never string concatenation
- **Database access**: Use `get_db_connection()` with `conn.row_factory = sqlite3.Row` for dict-like access
- **No dependency injection**: Global `depot_local` and `path_base_media` at module level
- **Session key**: Hardcoded `'your_secret_key_here'` (not production-ready)
- **No authentication**: Open access to all media

## Maintenance Scripts
- [xglobalsub.py](../xglobalsub.py): Bulk path substitution in database (e.g., migrating from `assetdepot/photo` to `assetdepot/media`)

## UI Behavior Notes
- **Grid vs Table**: Grid shows 3 columns with checkboxes, table shows detailed metadata
- **Modal video playback**: Pauses by default, user must click play (no autoplay)
- **Cart persistence**: Session-based only (cleared on server restart)
- **Search state**: URL parameters preserve search/filter/page/view across navigation