# Media Processor - Flask-Based Workflow

## Overview
Flask-based media processing interface integrated into MediaBrowser for adding new media files to the database. No VLC dependencies - uses HTML5 video playback in the browser.

## Access Points

### From Cart Page
Click the blue **"Append DB"** button (right of the red "Prune DB" button) to launch the processor.

### Direct URL
```
http://localhost:5000/processor
```

## Features

### 1. Drag & Drop File Upload ✅
- Drag video/image files directly into the drop zone
- Or click the drop zone to browse files
- Supports multiple file selection

### 2. Processing Queue ✅
- View all files waiting to be processed
- Click any file in the queue to load it
- Clear queue with "Clear All" button

### 3. Automatic Metadata Extraction ✅
- **Videos**: Resolution, duration, codec (via cv2)
- **Images**: Resolution, format (via PIL)
- Auto-generates unique file_id

### 4. File Copy with Progress Tracking ✅
- Copies files to repository structure:
  - Videos → `$DEPOT_ALL/assetdepot/media/videos/`
  - Images → `$DEPOT_ALL/assetdepot/media/images/`
  - Other → `$DEPOT_ALL/assetdepot/media/other/`
- Polls for progress every 500ms
- Shows copy percentage in real-time

### 5. Video Preview Thumbnails ✅
- Click "Generate Preview Thumbnails" button
- Creates 4 thumbnails at 25%, 50%, 75%, 100% positions
- Thumbnails saved to `$DEPOT_ALL/assetdepot/media/dummy/thumbnails/video_previews/`
- Click thumbnail to seek video to that position

### 6. HTML5 Video Playback ✅
- Native browser video controls (play, pause, seek, volume)
- No VLC required - uses browser codecs
- Works reliably on macOS without segmentation faults

### 7. Metadata Form ✅
- **Read-only fields** (auto-populated):
  - File ID, Name, Path, Type, Resolution, Format, Duration
- **Editable fields** (required):
  - Genre (dropdown), Subject, Category, Setting, Lighting, Tags, Captions
- Save to database or skip to next file

## Workflow

1. **Add Files**
   - Drag files into drop zone or browse
   - Files added to processing queue

2. **Select File**
   - Click file in queue to load
   - Progress bar shows:
     - Metadata extraction (0-30%)
     - File copy to repository (30-90%)
     - Completion (100%)

3. **Review & Edit**
   - Auto-populated fields shown (read-only)
   - Fill in required fields (genre, subject)
   - Add optional metadata (tags, captions)

4. **Generate Thumbnails** (videos only)
   - Click "Generate Preview Thumbnails"
   - 4 thumbnails created at 25% intervals
   - Click thumbnails to preview video at that timestamp

5. **Save or Skip**
   - Click "Save to Database" to commit
   - Or "Skip" to move to next file
   - Automatically advances through queue

## API Endpoints

### POST /api/processor/add_files
```json
{
  "files": ["/path/to/file1.mp4", "/path/to/file2.jpg"]
}
```

### POST /api/processor/extract_metadata
```json
{
  "file_path": "/path/to/file.mp4"
}
```

### POST /api/processor/copy_file
```json
{
  "source_path": "/path/to/file.mp4",
  "file_type": "mp4"
}
```

### GET /api/processor/copy_progress/{copy_id}
Returns:
```json
{
  "percent": 75,
  "status": "copying"
}
```

### POST /api/processor/generate_thumbnails
```json
{
  "file_path": "/path/to/video.mp4"
}
```

### POST /api/processor/submit
```json
{
  "file_id": "MED1704304123456",
  "file_name": "video.mp4",
  "file_path": "$DEPOT_ALL/assetdepot/media/videos/video.mp4",
  "file_type": "mp4",
  "genre": "noir",
  "subject": "urban landscape",
  "tags": "city, night, timelapse",
  "captions": "City lights at night"
}
```

### POST /api/processor/clear_queue
Clears the processing queue from session

## Technical Details

### Session Storage
- Processing queue stored in Flask session
- Current index tracked for sequential processing
- Copy progress tracked per copy_id

### File Organization
```
$DEPOT_ALL/assetdepot/media/
├── videos/           # MP4, MOV, AVI, MKV
├── images/           # JPG, JPEG, PNG, PSD
├── other/            # Other file types
└── dummy/
    └── thumbnails/
        └── video_previews/  # Generated thumbnails
```

### Database Integration
- Uses same `db_get_connection()` as search/cart
- Inserts into `media` table
- Path format: `$DEPOT_ALL/...` (replaced at runtime)

### Browser Compatibility
- Tested on Chrome/Firefox
- HTML5 video support required
- Drag-and-drop API required
- Fetch API for AJAX requests

## Advantages Over VLC/tkinter

1. **No Segmentation Faults** - Browser handles video decoding
2. **Better UX** - HTML/CSS/JavaScript vs tkinter
3. **Code Reuse** - Leverages existing MediaBrowser infrastructure
4. **Cross-Platform** - Works anywhere Flask + browser runs
5. **Easier Maintenance** - Standard web stack
6. **Native Controls** - Browser video controls are familiar

## Future Enhancements

### Potential Improvements
- [ ] Batch template application
- [ ] Undo/redo functionality
- [ ] Real-time video preview (WebSocket streaming)
- [ ] Advanced thumbnail scrubbing
- [ ] Folder scanning with progress
- [ ] Export queue as JSON
- [ ] Import from spreadsheet

### Electron Packaging (Optional)
```bash
# Package as standalone desktop app
npm install -g electron
electron-packager . MediaProcessor --platform=darwin --arch=x64
```

## Troubleshooting

### Files Not Showing in Queue
- Check file permissions
- Verify `DEPOT_ALL` environment variable is set
- Check Flask console for errors

### Video Won't Play
- Ensure browser supports H.264 codec
- Try generating thumbnails instead
- Check file isn't corrupted

### Copy Progress Stuck
- Increase polling interval in JavaScript
- Check disk space in destination folder
- Verify write permissions

### Database Errors
- Confirm `media_dummy.sqlite` exists
- Check database schema matches expected fields
- Verify `DEPOT_ALL` path is correct

## Support
See main MediaBrowser README for environment setup and database configuration.
