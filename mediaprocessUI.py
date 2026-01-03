#!/usr/bin/env python3
"""
Media Repository Builder - GUI for batch media ingestion
Imports media files into centralized repository with metadata extraction,
VLC playback, batch templates, and queue-based processing.
"""

import os
import sys
import sqlite3
import json
import time
import random
import shutil
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
import vlc

# Import configuration from mediabrowser
depot_local = os.getenv('DEPOT_ALL')
if not depot_local:
    print("ERROR: DEPOT_ALL environment variable not set!")
    sys.exit(1)

path_base_media = os.path.join(depot_local, 'assetdepot', 'media')
path_db_media = os.path.join(depot_local, 'assetdepot', 'media', 'dummy', 'db')
file_media_sqlite = 'media_dummy.sqlite'
path_db_full = os.path.join(path_db_media, file_media_sqlite)

# Storage paths
path_videos = os.path.join(path_base_media, 'videos')
path_images = os.path.join(path_base_media, 'images')
path_other = os.path.join(path_base_media, 'other')

# Persistence files
QUEUE_FILE = os.path.expanduser('~/.mediabrowser_queue.json')
TEMPLATES_FILE = os.path.expanduser('~/.mediabrowser_templates.json')

# Lists from mediabrowser
list_file_types = ['mp4', 'jpg', 'psd', 'prproj', 'docx', 'xlsx', 'pptx', 'hip', 'nk', 'obj']
list_genres = ['noir', 'modern', 'vintage', 'abstract', 'realism', 'fantasy', 'sci-fi']
list_lighting = ['natural', 'studio', 'low-key', 'high-key', 'mixed', 'golden-hour', 'ambient']
list_setting = ['indoor', 'outdoor', 'urban', 'nature', 'studio', 'industrial', 'abstract']

# Field definitions - all 18 database columns
DB_COLUMNS = ['file_id', 'file_name', 'file_path', 'file_type', 'file_format',
              'file_resolution', 'file_duration', 'shot_size', 'shot_type',
              'source', 'source_id', 'genre', 'subject', 'category',
              'lighting', 'setting', 'tags', 'captions']

# Read-only fields (auto-populated)
READONLY_FIELDS = ['file_id', 'file_name', 'file_path', 'file_type', 'file_resolution']

# Editable fields (user input required)
EDITABLE_FIELDS = ['file_format', 'file_duration', 'shot_size', 'shot_type',
                   'source', 'source_id', 'genre', 'subject', 'category',
                   'lighting', 'setting', 'tags', 'captions']


def db_get_connection():
    """Connect to SQLite database - replicates mediabrowser.py pattern"""
    conn = sqlite3.connect(path_db_full)
    conn.row_factory = sqlite3.Row
    return conn


class QueueItem:
    """Represents a file in the processing queue"""
    
    def __init__(self, source_path: str):
        self.source_path = source_path
        self.filename = os.path.basename(source_path)
        self.file_type = os.path.splitext(self.filename)[1][1:].lower()
        
        # Determine destination path based on file type
        if self.file_type in ['mp4', 'mov', 'avi', 'mkv']:
            self.dest_path = os.path.join(path_videos, self.filename)
            self.category = 'mp4'
        elif self.file_type in ['jpg', 'jpeg', 'png', 'psd']:
            self.dest_path = os.path.join(path_images, self.filename)
            self.category = 'images'
        else:
            self.dest_path = os.path.join(path_other, self.filename)
            self.category = 'other'
        
        self.status = '⏳ Pending'
        self.error_msg = ''
        self.metadata_cache = {}
    
    def to_dict(self) -> dict:
        """Serialize for JSON persistence"""
        return {
            'source_path': self.source_path,
            'dest_path': self.dest_path,
            'filename': self.filename,
            'file_type': self.file_type,
            'category': self.category,
            'status': self.status,
            'error_msg': self.error_msg
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Deserialize from JSON"""
        item = cls(data['source_path'])
        item.dest_path = data.get('dest_path', item.dest_path)
        item.status = data.get('status', '⏳ Pending')
        item.error_msg = data.get('error_msg', '')
        return item


class FileQueue:
    """Manages the processing queue with persistence"""
    
    def __init__(self):
        self.items: List[QueueItem] = []
        self.current_index = -1
    
    def add_files(self, file_paths: List[str]):
        """Add multiple files to queue"""
        for path in file_paths:
            if os.path.exists(path) and os.path.isfile(path):
                # Check for duplicates in queue
                if not any(item.source_path == path for item in self.items):
                    item = QueueItem(path)
                    # Check if already in database or destination exists
                    if self.check_duplicate(item):
                        item.status = '🔄 Duplicate'
                    self.items.append(item)
    
    def add_folder(self, folder_path: str):
        """Recursively add files from folder"""
        file_list = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                file_list.append(full_path)
        self.add_files(file_list)
    
    def check_duplicate(self, item: QueueItem) -> bool:
        """Check if file already exists in database or destination"""
        # Check physical file existence
        if os.path.exists(item.dest_path):
            return True
        
        # Check database
        try:
            conn = db_get_connection()
            cursor = conn.execute(
                "SELECT file_path FROM media WHERE file_path LIKE ?",
                (f'%/{item.filename}',)
            )
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception:
            return False
    
    def get_next_pending(self) -> Optional[QueueItem]:
        """Get next pending item in queue"""
        for i, item in enumerate(self.items):
            if item.status == '⏳ Pending':
                self.current_index = i
                return item
        return None
    
    def mark_status(self, item: QueueItem, status: str, error_msg: str = ''):
        """Update item status"""
        item.status = status
        item.error_msg = error_msg
        self.save_to_file()
    
    def get_stats(self) -> dict:
        """Get queue statistics"""
        total = len(self.items)
        pending = sum(1 for item in self.items if '⏳' in item.status)
        completed = sum(1 for item in self.items if '✓' in item.status)
        skipped = sum(1 for item in self.items if '⏭️' in item.status)
        duplicate = sum(1 for item in self.items if '🔄' in item.status)
        error = sum(1 for item in self.items if '✗' in item.status)
        
        return {
            'total': total,
            'pending': pending,
            'completed': completed,
            'skipped': skipped,
            'duplicate': duplicate,
            'error': error
        }
    
    def clear_completed(self):
        """Remove completed items from queue"""
        self.items = [item for item in self.items if '✓' not in item.status]
        self.save_to_file()
    
    def clear_all(self):
        """Clear entire queue"""
        self.items = []
        self.current_index = -1
        self.save_to_file()
    
    def save_to_file(self):
        """Persist queue to JSON file"""
        try:
            data = {
                'items': [item.to_dict() for item in self.items],
                'timestamp': datetime.now().isoformat()
            }
            with open(QUEUE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving queue: {e}")
    
    def load_from_file(self) -> bool:
        """Load queue from JSON file"""
        try:
            if not os.path.exists(QUEUE_FILE):
                return False
            
            with open(QUEUE_FILE, 'r') as f:
                data = json.load(f)
            
            self.items = [QueueItem.from_dict(item_data) for item_data in data.get('items', [])]
            # Validate source files still exist
            self.items = [item for item in self.items if os.path.exists(item.source_path)]
            return len(self.items) > 0
        except Exception as e:
            print(f"Error loading queue: {e}")
            return False


class MediaProcessUI(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        self.title("Media Repository Builder")
        self.geometry("1600x900")
        
        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Initialize components
        self.queue = FileQueue()
        self.templates = self.load_templates()
        self.undo_stack = []
        self.current_item: Optional[QueueItem] = None
        self.vlc_instance = None
        self.vlc_player = None
        self.form_widgets = {}
        
        # Create destination directories
        for path in [path_videos, path_images, path_other]:
            os.makedirs(path, exist_ok=True)
        
        # Build UI
        self.build_ui()
        
        # Try to restore previous queue
        if self.queue.load_from_file():
            if self.show_restore_dialog():
                self.refresh_queue_list()
            else:
                self.queue.clear_all()
        
        # Bind keyboard shortcuts
        self.bind_shortcuts()
    
    def build_ui(self):
        """Build the main UI layout"""
        # Main container
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Top section (3 panels)
        top_frame = ctk.CTkFrame(main_frame)
        top_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Left panel - Queue (22%)
        self.build_queue_panel(top_frame)
        
        # Center panel - Form (40%)
        self.build_form_panel(top_frame)
        
        # Right panel - VLC Player (28%)
        self.build_player_panel(top_frame)
        
        # Bottom panel - Progress and controls (10%)
        self.build_bottom_panel(main_frame)
    
    def build_queue_panel(self, parent):
        """Build left panel with queue list"""
        queue_frame = ctk.CTkFrame(parent)
        queue_frame.pack(side="left", fill="both", expand=False, padx=(0, 5))
        queue_frame.pack_propagate(False)
        queue_frame.configure(width=260)
        
        # Title
        title = ctk.CTkLabel(queue_frame, text="Processing Queue", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Buttons row 1
        btn_frame1 = ctk.CTkFrame(queue_frame)
        btn_frame1.pack(pady=5)
        
        ctk.CTkButton(btn_frame1, text="Add Files", command=self.add_files, width=100).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame1, text="Add Folder", command=self.add_folder, width=100).pack(side="left", padx=2)
        
        # Buttons row 2
        btn_frame2 = ctk.CTkFrame(queue_frame)
        btn_frame2.pack(pady=5)
        
        ctk.CTkButton(btn_frame2, text="Clear Completed", command=self.clear_completed, width=100).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame2, text="Clear All", command=self.clear_all, width=100).pack(side="left", padx=2)
        
        # Queue stats label
        self.stats_label = ctk.CTkLabel(queue_frame, text="Queue: 0 items", font=("Arial", 10))
        self.stats_label.pack(pady=5)
        
        # Info label (replaces drag-and-drop instructions)
        info_label = ctk.CTkLabel(
            queue_frame,
            text="Use 'Add Files' or 'Add Folder' buttons above\nto build your processing queue",
            font=("Arial", 10),
            text_color="gray"
        )
        info_label.pack(pady=5)
        
        # Queue listbox
        list_frame = ctk.CTkFrame(queue_frame)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Use tkinter Listbox for proper selection support
        import tkinter as tk
        self.queue_listbox = tk.Listbox(
            list_frame, 
            font=("Courier", 10),
            bg="#2b2b2b",
            fg="#f0f0f0",
            selectbackground="#1f6aa5",
            selectforeground="white",
            relief="flat",
            highlightthickness=0
        )
        self.queue_listbox.pack(fill="both", expand=True)
        self.queue_listbox.bind('<<ListboxSelect>>', self.on_queue_select)
    
    def build_form_panel(self, parent):
        """Build center panel with form fields"""
        form_frame = ctk.CTkFrame(parent)
        form_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        # Title
        title = ctk.CTkLabel(form_frame, text="Media Metadata", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Scrollable frame for form fields
        scroll_frame = ctk.CTkScrollableFrame(form_frame, height=600)
        scroll_frame.pack(fill="both", expand=True, padx=10)
        
        # Read-only section
        readonly_frame = ctk.CTkFrame(scroll_frame, fg_color="#2b2b2b")
        readonly_frame.pack(fill="x", pady=10, padx=5)
        
        readonly_label = ctk.CTkLabel(readonly_frame, text="Auto-Generated Fields (Read-Only)", 
                                      font=("Arial", 12, "bold"))
        readonly_label.pack(pady=5)
        
        for field in READONLY_FIELDS:
            row = ctk.CTkFrame(readonly_frame)
            row.pack(fill="x", padx=10, pady=3)
            
            label = ctk.CTkLabel(row, text=field.replace('_', ' ').title() + ":", width=150, anchor="w")
            label.pack(side="left", padx=5)
            
            entry = ctk.CTkEntry(row, state="disabled")
            entry.pack(side="left", fill="x", expand=True, padx=5)
            self.form_widgets[field] = entry
        
        # Editable section
        editable_frame = ctk.CTkFrame(scroll_frame)
        editable_frame.pack(fill="x", pady=10, padx=5)
        
        editable_label = ctk.CTkLabel(editable_frame, text="Required Fields", 
                                      font=("Arial", 12, "bold"))
        editable_label.pack(pady=5)
        
        for field in EDITABLE_FIELDS:
            row = ctk.CTkFrame(editable_frame)
            row.pack(fill="x", padx=10, pady=3)
            
            label = ctk.CTkLabel(row, text=field.replace('_', ' ').title() + ":", width=150, anchor="w")
            label.pack(side="left", padx=5)
            
            # Use combo box for dropdowns, textbox for long text, entry for others
            if field == 'file_type':
                widget = ctk.CTkComboBox(row, values=list_file_types)
                widget.pack(side="left", fill="x", expand=True, padx=5)
            elif field == 'genre':
                widget = ctk.CTkComboBox(row, values=list_genres)
                widget.pack(side="left", fill="x", expand=True, padx=5)
            elif field == 'lighting':
                widget = ctk.CTkComboBox(row, values=list_lighting)
                widget.pack(side="left", fill="x", expand=True, padx=5)
            elif field == 'setting':
                widget = ctk.CTkComboBox(row, values=list_setting)
                widget.pack(side="left", fill="x", expand=True, padx=5)
            elif field in ['tags', 'captions']:
                widget = ctk.CTkTextbox(row, height=60)
                widget.pack(side="left", fill="x", expand=True, padx=5)
            else:
                widget = ctk.CTkEntry(row)
                widget.pack(side="left", fill="x", expand=True, padx=5)
            
            self.form_widgets[field] = widget
        
        # Template button
        template_btn = ctk.CTkButton(scroll_frame, text="Apply Template to Queue", 
                                     command=self.show_template_dialog)
        template_btn.pack(pady=10)
    
    def build_player_panel(self, parent):
        """Build right panel with VLC player"""
        player_frame = ctk.CTkFrame(parent)
        player_frame.pack(side="left", fill="both", expand=True)
        player_frame.pack_propagate(False)
        player_frame.configure(width=450)
        
        # Title
        title = ctk.CTkLabel(player_frame, text="Video Preview", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Thumbnail preview
        self.thumbnail_label = ctk.CTkLabel(player_frame, text="No thumbnail", width=400, height=225)
        self.thumbnail_label.pack(pady=5)
        
        # VLC video frame
        self.video_frame = ctk.CTkFrame(player_frame, width=400, height=225, fg_color="black")
        self.video_frame.pack(pady=5)
        self.video_frame.pack_forget()  # Hide initially
        
        # Video controls
        controls_frame = ctk.CTkFrame(player_frame)
        controls_frame.pack(fill="x", padx=10, pady=10)
        
        # Play/Pause button
        self.play_btn = ctk.CTkButton(controls_frame, text="▶ Play", command=self.toggle_play, width=80, state="disabled")
        self.play_btn.pack(side="left", padx=5)
        
        # Seek slider
        self.seek_slider = ctk.CTkSlider(controls_frame, from_=0, to=100, command=self.on_seek)
        self.seek_slider.pack(side="left", fill="x", expand=True, padx=5)
        self.seek_slider.set(0)
        
        # Time label
        self.time_label = ctk.CTkLabel(controls_frame, text="00:00 / 00:00", width=100)
        self.time_label.pack(side="left", padx=5)
        
        # Volume slider
        vol_label = ctk.CTkLabel(player_frame, text="Volume:")
        vol_label.pack()
        
        self.volume_slider = ctk.CTkSlider(player_frame, from_=0, to=100, command=self.on_volume)
        self.volume_slider.pack(fill="x", padx=20)
        self.volume_slider.set(50)
        
        # Capture frame button
        self.capture_btn = ctk.CTkButton(player_frame, text="Capture Current Frame as Thumbnail",
                                         command=self.capture_frame)
        self.capture_btn.pack(pady=10)
    
    def build_bottom_panel(self, parent):
        """Build bottom panel with progress and action buttons"""
        bottom_frame = ctk.CTkFrame(parent)
        bottom_frame.pack(fill="x", padx=5, pady=5)
        
        # File-level progress
        progress_frame = ctk.CTkFrame(bottom_frame)
        progress_frame.pack(fill="x", padx=10, pady=5)
        
        self.file_progress_label = ctk.CTkLabel(progress_frame, text="Ready", anchor="w")
        self.file_progress_label.pack(fill="x", padx=5)
        
        self.file_progress_bar = ctk.CTkProgressBar(progress_frame)
        self.file_progress_bar.pack(fill="x", padx=5, pady=3)
        self.file_progress_bar.set(0)
        
        # Overall progress
        self.overall_progress_label = ctk.CTkLabel(progress_frame, text="Batch Progress: 0/0", anchor="w")
        self.overall_progress_label.pack(fill="x", padx=5, pady=3)
        
        self.overall_progress_bar = ctk.CTkProgressBar(progress_frame)
        self.overall_progress_bar.pack(fill="x", padx=5, pady=3)
        self.overall_progress_bar.set(0)
        
        # Action buttons
        btn_frame = ctk.CTkFrame(bottom_frame)
        btn_frame.pack(pady=5)
        
        self.process_btn = ctk.CTkButton(btn_frame, text="Process Next (Ctrl+N)", 
                                         command=self.process_next, width=150)
        self.process_btn.pack(side="left", padx=5)
        
        self.submit_btn = ctk.CTkButton(btn_frame, text="Submit & Next (Ctrl+Enter)", 
                                        command=self.submit_and_next, width=160)
        self.submit_btn.pack(side="left", padx=5)
        
        self.skip_btn = ctk.CTkButton(btn_frame, text="Skip (Ctrl+S)", 
                                      command=self.skip_current, width=120)
        self.skip_btn.pack(side="left", padx=5)
        
        self.retry_btn = ctk.CTkButton(btn_frame, text="Retry Last (Ctrl+R)", 
                                       command=self.retry_last, width=140, state="disabled")
        self.retry_btn.pack(side="left", padx=5)
        
        self.undo_btn = ctk.CTkButton(btn_frame, text="Undo Last (Ctrl+Z)", 
                                      command=self.undo_last, width=140, state="disabled")
        self.undo_btn.pack(side="left", padx=5)
    
    def bind_shortcuts(self):
        """Bind keyboard shortcuts"""
        self.bind('<Control-n>', lambda e: self.process_next())
        self.bind('<Control-Return>', lambda e: self.submit_and_next())
        self.bind('<Control-s>', lambda e: self.skip_current())
        self.bind('<Control-r>', lambda e: self.retry_last())
        self.bind('<Control-z>', lambda e: self.undo_last())
        self.bind('<Control-t>', lambda e: self.show_template_dialog())
        self.bind('<Control-q>', lambda e: self.on_closing())
    
    # Queue management methods
    def add_files(self):
        """Open file dialog to add files"""
        from tkinter import filedialog
        files = filedialog.askopenfilenames(
            title="Select Media Files",
            filetypes=[
                ("All Media", "*.mp4 *.mov *.avi *.mkv *.jpg *.jpeg *.png *.psd"),
                ("Video files", "*.mp4 *.mov *.avi *.mkv"),
                ("Image files", "*.jpg *.jpeg *.png *.psd"),
                ("All files", "*.*")
            ]
        )
        if files:
            self.queue.add_files(list(files))
            self.refresh_queue_list()
    
    def add_folder(self):
        """Open folder dialog to add folder"""
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="Select Folder with Media Files")
        if folder:
            # Show progress feedback for large folders
            self.file_progress_label.configure(text=f"Scanning folder: {os.path.basename(folder)}...")
            self.update_idletasks()
            
            self.queue.add_folder(folder)
            self.refresh_queue_list()
            
            self.file_progress_label.configure(text="Ready")
    
    def clear_completed(self):
        """Clear completed items from queue"""
        self.queue.clear_completed()
        self.refresh_queue_list()
    
    def clear_all(self):
        """Clear all items from queue"""
        if self.show_confirm_dialog("Clear all items from queue?"):
            self.queue.clear_all()
            self.refresh_queue_list()
    
    def on_queue_select(self, event):
        """Handle queue item selection"""
        selection = self.queue_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index < len(self.queue.items):
            item = self.queue.items[index]
            
            # Store current item
            self.current_item = item
            
            # Check if file has been processed (copied to destination)
            if os.path.exists(item.dest_path):
                # Load the already-processed file
                self.load_item_to_form(item)
            else:
                # File not yet processed - extract metadata from source
                self.file_progress_label.configure(text=f"Loading: {item.filename}...")
                self.update_idletasks()
                
                # Extract metadata
                item.metadata_cache = self.extract_metadata(item.source_path, item.file_type)
                
                # Generate temporary file_id
                file_id = f"MED{int(time.time()*1000)}{random.randint(100,999)}"
                
                # Set read-only fields
                self.set_field_value('file_id', file_id)
                self.set_field_value('file_name', item.filename)
                rel_path = item.dest_path.replace(depot_local, '$DEPOT_ALL')
                self.set_field_value('file_path', rel_path)
                self.set_field_value('file_type', item.file_type)
                
                # Set extracted metadata
                if 'file_resolution' in item.metadata_cache:
                    self.set_field_value('file_resolution', item.metadata_cache['file_resolution'])
                if 'file_format' in item.metadata_cache:
                    self.set_field_value('file_format', item.metadata_cache['file_format'])
                if 'file_duration' in item.metadata_cache:
                    self.set_field_value('file_duration', item.metadata_cache['file_duration'])
                
                # Load template if available
                category = item.category
                if category in self.templates:
                    template = self.templates[category]
                    for field, value in template.items():
                        if field in EDITABLE_FIELDS and field not in ['file_format', 'file_duration']:
                            self.set_field_value(field, value)
                
                # For videos, initialize VLC player with source file
                if item.file_type in ['mp4', 'mov', 'avi', 'mkv']:
                    print(f"Loading video into player: {item.source_path}")
                    self.init_vlc_player(item.source_path)
                else:
                    self.hide_vlc_player()
                
                self.file_progress_label.configure(text="Ready")
    
    def refresh_queue_list(self):
        """Update queue listbox display"""
        self.queue_listbox.delete(0, "end")
        
        for i, item in enumerate(self.queue.items):
            line = f"{i+1:3d}. {item.status} {item.filename[:35]}"
            self.queue_listbox.insert("end", line)
        
        # Update stats
        stats = self.queue.get_stats()
        stats_text = (f"Total: {stats['total']} | Pending: {stats['pending']} | "
                     f"Completed: {stats['completed']} | Skipped: {stats['skipped']} | "
                     f"Duplicate: {stats['duplicate']} | Error: {stats['error']}")
        self.stats_label.configure(text=stats_text)
        
        # Update overall progress
        if stats['total'] > 0:
            progress = (stats['completed'] + stats['skipped'] + stats['duplicate']) / stats['total']
            self.overall_progress_bar.set(progress)
            self.overall_progress_label.configure(
                text=f"Batch Progress: {stats['completed']}/{stats['total']}"
            )
    
    # Template management
    def load_templates(self) -> dict:
        """Load field templates from JSON"""
        default_templates = {'mp4': {}, 'images': {}, 'other': {}}
        try:
            if os.path.exists(TEMPLATES_FILE):
                with open(TEMPLATES_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading templates: {e}")
        return default_templates
    
    def save_templates(self):
        """Save field templates to JSON"""
        try:
            with open(TEMPLATES_FILE, 'w') as f:
                json.dump(self.templates, f, indent=2)
        except Exception as e:
            print(f"Error saving templates: {e}")
    
    def show_template_dialog(self):
        """Show dialog to apply template to queue items"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Apply Template to Queue")
        dialog.geometry("400x500")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Select fields to copy to all pending items:", 
                    font=("Arial", 12, "bold")).pack(pady=10)
        
        checkboxes = {}
        for field in EDITABLE_FIELDS:
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(dialog, text=field.replace('_', ' ').title(), variable=var)
            cb.pack(anchor="w", padx=20, pady=2)
            checkboxes[field] = var
        
        # Select all/none buttons
        btn_frame = ctk.CTkFrame(dialog)
        btn_frame.pack(pady=10)
        
        def select_all():
            for var in checkboxes.values():
                var.set(True)
        
        def select_none():
            for var in checkboxes.values():
                var.set(False)
        
        ctk.CTkButton(btn_frame, text="Select All", command=select_all).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Select None", command=select_none).pack(side="left", padx=5)
        
        # Apply button
        def apply_template():
            # Get current form values for selected fields
            template_values = {}
            for field, var in checkboxes.items():
                if var.get():
                    template_values[field] = self.get_field_value(field)
            
            # Apply to templates - this will be used when loading next items
            if self.current_item:
                category = self.current_item.category
                if category not in self.templates:
                    self.templates[category] = {}
                self.templates[category].update(template_values)
                self.save_templates()
            
            dialog.destroy()
            self.show_info_dialog(f"Template applied to {len(template_values)} fields")
        
        ctk.CTkButton(dialog, text="Apply", command=apply_template).pack(pady=10)
    
    # File processing
    def process_next(self):
        """Process next file in queue"""
        item = self.queue.get_next_pending()
        if not item:
            self.show_info_dialog("No pending items in queue")
            return
        
        self.current_item = item
        self.queue.mark_status(item, '⚙️ Processing')
        self.refresh_queue_list()
        
        # Run file processing in thread to keep UI responsive
        thread = threading.Thread(target=self.process_file_thread, args=(item,))
        thread.daemon = True
        thread.start()
    
    def process_file_thread(self, item: QueueItem):
        """Process file in background thread"""
        try:
            # Copy file with progress
            self.update_file_progress(f"Copying {item.filename}...", 0)
            self.copy_file_with_progress(item.source_path, item.dest_path)
            
            # Extract metadata
            self.update_file_progress("Extracting metadata...", 0.8)
            metadata = self.extract_metadata(item.dest_path, item.file_type)
            item.metadata_cache = metadata
            
            # Generate thumbnail for videos
            if item.file_type in ['mp4', 'mov', 'avi', 'mkv']:
                self.update_file_progress("Generating thumbnail...", 0.9)
                self.generate_thumbnail(item.dest_path)
            
            self.update_file_progress("Ready", 1.0)
            
            # Update UI on main thread
            self.after(0, lambda: self.load_item_to_form(item))
            
        except Exception as e:
            self.after(0, lambda: self.show_error_dialog(f"Error processing file: {str(e)}"))
            self.queue.mark_status(item, '✗ Error', str(e))
            self.after(0, self.refresh_queue_list)
    
    def copy_file_with_progress(self, src: str, dst: str):
        """Copy file with progress updates"""
        file_size = os.path.getsize(src)
        copied = 0
        
        with open(src, 'rb') as fsrc:
            with open(dst, 'wb') as fdst:
                while True:
                    chunk = fsrc.read(65536)  # 64KB chunks
                    if not chunk:
                        break
                    fdst.write(chunk)
                    copied += len(chunk)
                    progress = copied / file_size
                    self.update_file_progress(
                        f"Copying {os.path.basename(dst)}: {copied/1024/1024:.1f}/{file_size/1024/1024:.1f} MB",
                        progress
                    )
    
    def extract_metadata(self, file_path: str, file_type: str) -> dict:
        """Extract metadata from media file"""
        metadata = {}
        
        try:
            if file_type in ['mp4', 'mov', 'avi', 'mkv']:
                # Extract video metadata
                cap = cv2.VideoCapture(file_path)
                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    
                    metadata['file_resolution'] = f"{width}x{height}"
                    metadata['file_duration'] = f"{frame_count/fps:.1f}" if fps > 0 else "0"
                    
                    # Get codec
                    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                    codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
                    metadata['file_format'] = codec
                    
                    cap.release()
            
            elif file_type in ['jpg', 'jpeg', 'png']:
                # Extract image metadata
                img = Image.open(file_path)
                metadata['file_resolution'] = f"{img.width}x{img.height}"
                metadata['file_format'] = img.format
        
        except Exception as e:
            print(f"Error extracting metadata: {e}")
        
        return metadata
    
    def generate_thumbnail(self, video_path: str, vlc_position: Optional[float] = None):
        """Generate thumbnail from video"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if vlc_position is not None and self.vlc_player:
                # Use VLC position
                frame_num = int(total_frames * vlc_position)
            else:
                # Use middle frame
                frame_num = total_frames // 2
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            
            if ret:
                thumbnail_path = os.path.splitext(video_path)[0] + '.jpg'
                cv2.imwrite(thumbnail_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            cap.release()
        
        except Exception as e:
            print(f"Error generating thumbnail: {e}")
    
    def load_item_to_form(self, item: QueueItem):
        """Load file data into form"""
        # Store current item
        self.current_item = item
        
        # Clear form
        self.clear_form()
        
        # Generate file_id
        file_id = f"MED{int(time.time()*1000)}{random.randint(100,999)}"
        
        # Set read-only fields
        self.set_field_value('file_id', file_id)
        self.set_field_value('file_name', item.filename)
        
        # Convert to $DEPOT_ALL format
        rel_path = item.dest_path.replace(depot_local, '$DEPOT_ALL')
        self.set_field_value('file_path', rel_path)
        self.set_field_value('file_type', item.file_type)
        
        # Set metadata from extraction
        if 'file_resolution' in item.metadata_cache:
            self.set_field_value('file_resolution', item.metadata_cache['file_resolution'])
        
        # Auto-fill file_format and file_duration from metadata
        if 'file_format' in item.metadata_cache:
            self.set_field_value('file_format', item.metadata_cache['file_format'])
        if 'file_duration' in item.metadata_cache:
            self.set_field_value('file_duration', item.metadata_cache['file_duration'])
        
        # Load template for file category
        category = item.category
        if category in self.templates:
            template = self.templates[category]
            for field, value in template.items():
                if field in EDITABLE_FIELDS and field not in ['file_format', 'file_duration']:
                    self.set_field_value(field, value)
        
        # Override with extracted metadata (but not template-provided format/duration)
        for field, value in item.metadata_cache.items():
            if field in EDITABLE_FIELDS:
                self.set_field_value(field, value)
        
        # Load thumbnail
        thumbnail_path = os.path.splitext(item.dest_path)[0] + '.jpg'
        if os.path.exists(thumbnail_path):
            self.load_thumbnail(thumbnail_path)
        
        # Initialize VLC player for videos
        if item.file_type in ['mp4', 'mov', 'avi', 'mkv']:
            # Always load from source path where the original file actually exists
            video_path = item.source_path
            print(f"Loading video from source: {video_path}")
            if os.path.exists(video_path):
                self.init_vlc_player(video_path)
            else:
                print(f"Warning: Video file not found at {video_path}")
                self.hide_vlc_player()
        else:
            self.hide_vlc_player()
    
    def load_thumbnail(self, thumbnail_path: str):
        """Load and display thumbnail"""
        try:
            img = Image.open(thumbnail_path)
            img.thumbnail((400, 225))
            photo = ImageTk.PhotoImage(img)
            self.thumbnail_label.configure(image=photo, text="")
            self.thumbnail_label.image = photo  # Keep reference
        except Exception as e:
            self.thumbnail_label.configure(text=f"Thumbnail error: {e}")
    
    # VLC player methods
    def init_vlc_player(self, video_path: str):
        """Initialize VLC player for video"""
        print(f"\n=== Initializing VLC Player ===")
        print(f"Video path: {video_path}")
        
        # Clean up existing player
        self.cleanup_vlc()
        
        try:
            # Verify video file exists
            if not os.path.exists(video_path):
                print(f"ERROR: Video file not found: {video_path}")
                self.hide_vlc_player()
                return
            
            print(f"File exists, size: {os.path.getsize(video_path)} bytes")
            
            # Create VLC instance with minimal args to avoid compatibility issues
            print("Creating VLC instance...")
            vlc_args = ['--no-video-title-show']
            
            # Try to disable hardware decoding on macOS
            if sys.platform == 'darwin':
                vlc_args.append('--avcodec-hw=none')
            
            self.vlc_instance = vlc.Instance(vlc_args)
            
            if not self.vlc_instance:
                print("ERROR: Failed to create VLC instance")
                self.hide_vlc_player()
                return
            
            print("VLC instance created successfully")
            
            # Create media player
            self.vlc_player = self.vlc_instance.media_player_new()
            
            if not self.vlc_player:
                print("ERROR: Failed to create VLC media player")
                self.hide_vlc_player()
                return
            
            print("Media player created successfully")
            
            # Load media
            print(f"Loading media: {video_path}")
            media = self.vlc_instance.media_new(video_path)
            
            if not media:
                print("ERROR: Failed to create media object")
                self.hide_vlc_player()
                return
            
            self.vlc_player.set_media(media)
            print("Media set successfully")
            
            # Show video frame
            self.video_frame.pack(pady=5)
            self.update_idletasks()
            print("Video frame shown")
            
            # Give the frame time to render before embedding (critical for macOS)
            if sys.platform == 'darwin':
                print("Scheduling delayed VLC embedding for macOS...")
                self.after(200, lambda: self._complete_vlc_init())
            else:
                self._complete_vlc_init()
            
        except Exception as e:
            print(f"EXCEPTION in init_vlc_player: {e}")
            import traceback
            traceback.print_exc()
            self.hide_vlc_player()
    
    def _complete_vlc_init(self):
        """Complete VLC initialization after frame is ready"""
        print("\n=== Completing VLC Initialization ===")
        try:
            if not self.vlc_player:
                print("ERROR: VLC player not initialized")
                return
            
            print(f"Platform: {sys.platform}")
            print(f"Video frame window ID: {self.video_frame.winfo_id()}")
            
            # Get window handle (platform specific)
            if sys.platform.startswith('linux'):
                print("Setting Linux xwindow...")
                self.vlc_player.set_xwindow(self.video_frame.winfo_id())
            elif sys.platform == 'win32':
                print("Setting Windows hwnd...")
                self.vlc_player.set_hwnd(self.video_frame.winfo_id())
            elif sys.platform == 'darwin':
                # macOS requires NSView handle
                print("Setting macOS nsobject...")
                window_id = int(self.video_frame.winfo_id())
                print(f"Window ID as int: {window_id}")
                self.vlc_player.set_nsobject(window_id)
            
            print("Window handle set successfully")
            
            # Enable play button now that video is loaded
            self.play_btn.configure(state="normal")
            print("Play button enabled")
            
            # Start position update loop
            self.update_player_position()
            
            print("=== VLC Initialization Complete ===\n")
            
        except Exception as e:
            print(f"EXCEPTION in _complete_vlc_init: {e}")
            import traceback
            traceback.print_exc()
            self.play_btn.configure(state="disabled")
    
    def hide_vlc_player(self):
        """Hide VLC player widget"""
        self.video_frame.pack_forget()
        self.play_btn.configure(state="disabled")
        self.cleanup_vlc()
    
    def cleanup_vlc(self):
        """Clean up VLC resources"""
        try:
            if self.vlc_player:
                if self.vlc_player.is_playing():
                    self.vlc_player.stop()
                self.vlc_player.release()
                self.vlc_player = None
        except:
            pass
        
        try:
            if self.vlc_instance:
                self.vlc_instance.release()
                self.vlc_instance = None
        except:
            pass
    
    def toggle_play(self):
        """Toggle play/pause"""
        if not self.vlc_player:
            return
        
        try:
            if self.vlc_player.is_playing():
                self.vlc_player.pause()
                self.play_btn.configure(text="▶ Play")
            else:
                # Ensure media is parsed before playing
                self.vlc_player.play()
                self.play_btn.configure(text="⏸ Pause")
        except Exception as e:
            print(f"Error toggling play: {e}")
            self.play_btn.configure(text="▶ Play")
    
    def on_seek(self, value):
        """Handle seek slider change"""
        if self.vlc_player and not self.vlc_player.is_playing():
            self.vlc_player.set_position(float(value) / 100.0)
    
    def on_volume(self, value):
        """Handle volume slider change"""
        if self.vlc_player:
            self.vlc_player.audio_set_volume(int(value))
    
    def update_player_position(self):
        """Update player position display"""
        if self.vlc_player:
            try:
                position = self.vlc_player.get_position()
                length = self.vlc_player.get_length() / 1000  # milliseconds to seconds
                current = position * length
                
                self.seek_slider.set(position * 100)
                
                current_str = f"{int(current//60):02d}:{int(current%60):02d}"
                length_str = f"{int(length//60):02d}:{int(length%60):02d}"
                self.time_label.configure(text=f"{current_str} / {length_str}")
            except:
                pass
            
            # Schedule next update
            self.after(100, self.update_player_position)
    
    def capture_frame(self):
        """Capture current frame as thumbnail"""
        if not self.vlc_player or not self.current_item:
            return
        
        try:
            position = self.vlc_player.get_position()
            self.generate_thumbnail(self.current_item.dest_path, position)
            
            # Reload thumbnail
            thumbnail_path = os.path.splitext(self.current_item.dest_path)[0] + '.jpg'
            self.load_thumbnail(thumbnail_path)
            
            self.show_info_dialog("Thumbnail updated")
        except Exception as e:
            self.show_error_dialog(f"Error capturing frame: {e}")
    
    # Form management
    def clear_form(self):
        """Clear all form fields"""
        for field, widget in self.form_widgets.items():
            if isinstance(widget, ctk.CTkEntry):
                widget.configure(state="normal")
                widget.delete(0, "end")
                if field in READONLY_FIELDS:
                    widget.configure(state="disabled")
            elif isinstance(widget, ctk.CTkTextbox):
                widget.delete("1.0", "end")
            elif isinstance(widget, ctk.CTkComboBox):
                widget.set("")
    
    def get_field_value(self, field: str) -> str:
        """Get value from form field"""
        widget = self.form_widgets.get(field)
        if not widget:
            return ""
        
        if isinstance(widget, ctk.CTkEntry):
            return widget.get()
        elif isinstance(widget, ctk.CTkTextbox):
            return widget.get("1.0", "end-1c")
        elif isinstance(widget, ctk.CTkComboBox):
            return widget.get()
        return ""
    
    def set_field_value(self, field: str, value: str):
        """Set value in form field"""
        widget = self.form_widgets.get(field)
        if not widget:
            return
        
        if isinstance(widget, ctk.CTkEntry):
            was_disabled = str(widget.cget("state")) == "disabled"
            if was_disabled:
                widget.configure(state="normal")
            widget.delete(0, "end")
            widget.insert(0, str(value))
            if was_disabled:
                widget.configure(state="disabled")
        elif isinstance(widget, ctk.CTkTextbox):
            widget.delete("1.0", "end")
            widget.insert("1.0", str(value))
        elif isinstance(widget, ctk.CTkComboBox):
            widget.set(str(value))
    
    def validate_form(self) -> Tuple[bool, List[str]]:
        """Validate all required fields are filled"""
        missing = []
        
        for field in EDITABLE_FIELDS:
            value = self.get_field_value(field).strip()
            if not value:
                missing.append(field.replace('_', ' ').title())
        
        return len(missing) == 0, missing
    
    # Database operations
    def submit_and_next(self):
        """Submit current item to database and load next"""
        if not self.current_item:
            self.show_error_dialog("No item loaded")
            return
        
        # Validate form
        valid, missing = self.validate_form()
        if not valid:
            self.show_error_dialog(f"Missing required fields:\n" + "\n".join(missing))
            return
        
        # Collect all field values
        values = {}
        for field in DB_COLUMNS:
            values[field] = self.get_field_value(field)
        
        # Insert into database
        try:
            conn = db_get_connection()
            placeholders = ','.join(['?'] * len(DB_COLUMNS))
            sql = f"INSERT INTO media ({','.join(DB_COLUMNS)}) VALUES ({placeholders})"
            
            cursor = conn.execute(sql, [values[field] for field in DB_COLUMNS])
            conn.commit()
            conn.close()
            
            # Save to undo stack
            self.undo_stack.append({
                'file_id': values['file_id'],
                'video_path': self.current_item.dest_path,
                'thumbnail_path': os.path.splitext(self.current_item.dest_path)[0] + '.jpg'
            })
            self.undo_btn.configure(state="normal")
            
            # Save template
            category = self.current_item.category
            if category not in self.templates:
                self.templates[category] = {}
            for field in EDITABLE_FIELDS:
                self.templates[category][field] = values[field]
            self.save_templates()
            
            # Mark complete
            self.queue.mark_status(self.current_item, '✓ Completed')
            self.refresh_queue_list()
            
            # Clean up VLC
            self.cleanup_vlc()
            
            # Process next
            self.current_item = None
            self.process_next()
            
        except sqlite3.Error as e:
            # Database error - rollback files
            self.rollback_files(self.current_item)
            self.show_error_dialog(f"Database error: {e}")
            self.queue.mark_status(self.current_item, '✗ Error', str(e))
            self.refresh_queue_list()
            self.retry_btn.configure(state="normal")
    
    def rollback_files(self, item: QueueItem):
        """Delete copied files on database failure"""
        try:
            if os.path.exists(item.dest_path):
                os.remove(item.dest_path)
            
            thumbnail_path = os.path.splitext(item.dest_path)[0] + '.jpg'
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
        except Exception as e:
            print(f"Error during rollback: {e}")
    
    def skip_current(self):
        """Skip current item"""
        if self.current_item:
            self.queue.mark_status(self.current_item, '⏭️ Skipped')
            self.refresh_queue_list()
            self.cleanup_vlc()
            self.current_item = None
            self.process_next()
    
    def retry_last(self):
        """Retry last failed submission"""
        if self.current_item:
            self.retry_btn.configure(state="disabled")
            self.submit_and_next()
    
    def undo_last(self):
        """Undo last database insertion"""
        if not self.undo_stack:
            return
        
        if not self.show_confirm_dialog("Undo last submission? This will delete the database record and files."):
            return
        
        try:
            last = self.undo_stack.pop()
            
            # Delete from database
            conn = db_get_connection()
            conn.execute("DELETE FROM media WHERE file_id = ?", (last['file_id'],))
            conn.commit()
            conn.close()
            
            # Delete files
            if os.path.exists(last['video_path']):
                os.remove(last['video_path'])
            if os.path.exists(last['thumbnail_path']):
                os.remove(last['thumbnail_path'])
            
            if not self.undo_stack:
                self.undo_btn.configure(state="disabled")
            
            self.show_info_dialog("Last submission undone")
            self.refresh_queue_list()
            
        except Exception as e:
            self.show_error_dialog(f"Error during undo: {e}")
    
    # UI update helpers
    def update_file_progress(self, text: str, progress: float):
        """Update file progress display"""
        self.file_progress_label.configure(text=text)
        self.file_progress_bar.set(progress)
    
    # Dialog helpers
    def show_restore_dialog(self) -> bool:
        """Ask user if they want to restore previous queue"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Restore Queue")
        dialog.geometry("400x150")
        dialog.transient(self)
        dialog.grab_set()
        
        result = [False]
        
        ctk.CTkLabel(dialog, text="Previous queue found. Restore it?", 
                    font=("Arial", 12)).pack(pady=20)
        
        btn_frame = ctk.CTkFrame(dialog)
        btn_frame.pack(pady=10)
        
        def yes():
            result[0] = True
            dialog.destroy()
        
        def no():
            result[0] = False
            dialog.destroy()
        
        ctk.CTkButton(btn_frame, text="Yes", command=yes, width=100).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="No", command=no, width=100).pack(side="left", padx=10)
        
        self.wait_window(dialog)
        return result[0]
    
    def show_confirm_dialog(self, message: str) -> bool:
        """Show confirmation dialog"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm")
        dialog.geometry("400x150")
        dialog.transient(self)
        dialog.grab_set()
        
        result = [False]
        
        ctk.CTkLabel(dialog, text=message, font=("Arial", 12)).pack(pady=20)
        
        btn_frame = ctk.CTkFrame(dialog)
        btn_frame.pack(pady=10)
        
        def yes():
            result[0] = True
            dialog.destroy()
        
        def no():
            result[0] = False
            dialog.destroy()
        
        ctk.CTkButton(btn_frame, text="Yes", command=yes, width=100).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="No", command=no, width=100).pack(side="left", padx=10)
        
        self.wait_window(dialog)
        return result[0]
    
    def show_info_dialog(self, message: str):
        """Show information dialog"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Information")
        dialog.geometry("400x150")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text=message, font=("Arial", 12)).pack(pady=20)
        ctk.CTkButton(dialog, text="OK", command=dialog.destroy, width=100).pack(pady=10)
    
    def show_error_dialog(self, message: str):
        """Show error dialog"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Error")
        dialog.geometry("500x200")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Error:", font=("Arial", 12, "bold"), 
                    text_color="red").pack(pady=10)
        
        text = ctk.CTkTextbox(dialog, height=100)
        text.pack(fill="both", expand=True, padx=20, pady=10)
        text.insert("1.0", message)
        text.configure(state="disabled")
        
        ctk.CTkButton(dialog, text="OK", command=dialog.destroy, width=100).pack(pady=10)
    
    def on_closing(self):
        """Handle window close"""
        self.queue.save_to_file()
        self.cleanup_vlc()
        self.destroy()


def main():
    """Main entry point"""
    # Suppress macOS IMKClient console messages
    if sys.platform == 'darwin':
        import warnings
        warnings.filterwarnings('ignore')
        # Redirect stderr to suppress IMKClient messages
        devnull = open(os.devnull, 'w')
        old_stderr = sys.stderr
        sys.stderr = devnull
    
    # Validate environment
    if not os.path.exists(path_db_full):
        if sys.platform == 'darwin':
            sys.stderr = old_stderr  # Restore stderr for error message
        print(f"ERROR: Database not found at {path_db_full}")
        print("Please ensure DEPOT_ALL is set correctly and database exists.")
        sys.exit(1)
    
    try:
        # Create and run app
        app = MediaProcessUI()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    finally:
        # Restore stderr on exit
        if sys.platform == 'darwin':
            sys.stderr = old_stderr
            devnull.close()


if __name__ == '__main__':
    main()
