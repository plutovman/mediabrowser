# MediaBrowser Copilot Instructions

## Overview
MediaBrowser is a Flask web application for browsing and searching media assets stored in a SQLite database. It provides pagination and search functionality for media metadata.

## Key Files
- `main.py`: Main Flask application with routing, database queries, and pagination logic
- `requirements.txt`: Dependencies (Flask only)
- `templates/index.html`: Jinja2 template for displaying media in a table with thumbnails
- `xglobalsub.py`: Utility script for database path updates

## Architecture
- Single-file Flask app serving static media files from `$DEPOT_ALL/assetdepot/media`
- SQLite database `db_media.sqlite3` in `$DEPOT_ALL/assetdepot/media/db/`
- No ORM; direct SQL queries with sqlite3
- Environment variable `$DEPOT_ALL` defines the base media depot path

## Database Schema
Media table fields: file, path, medium, format, resolution, length, genre, category, shot_size, shot_type, lighting, setting, people, source, source_id, tags, captions

## Running the App
```bash
export DEPOT_ALL=/path/to/depot
python main.py
```
App runs in debug mode on localhost:5000

## Conventions
- Use `os.path.join()` for path construction
- Database connections via `get_db_connection()` function
- Static files served from `path_base_media` directory
- Pagination uses `PER_PAGE = 10` with LIMIT/OFFSET

## Patterns
- Dynamic SQL queries for search: `WHERE source_id LIKE ?` with wildcards
- Pagination calculation: `offset = (page - 1) * PER_PAGE`
- Template rendering passes `media`, `page`, `total_pages`, `search_query`
- Thumbnails displayed using `url_for('static', filename=...)` with relative paths

## Development Notes
- No tests or build process; direct Python execution
- Database updates done via scripts like `xglobalsub.py`
- Template uses dark theme with custom CSS for table styling