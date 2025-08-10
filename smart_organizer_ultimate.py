#!/usr/bin/env python3
"""
Ultimate Smart Drive Organizer - Professional Edition
Advanced file organization, duplicate detection, and storage optimization.
Features hash caching, empty folder cleanup, actual file organization, and more.
"""

import os
import sys
import hashlib
import signal
import sqlite3
import shutil
import json
import argparse
import configparser
import logging
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import mimetypes

# Version info
__version__ = "2.0.0"
__author__ = "Enhanced for Professional Trading Systems"

# Enhanced package detection with graceful fallbacks
def check_package(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False

# Feature detection
RICH_AVAILABLE = check_package('rich')
PIL_AVAILABLE = check_package('pillow', 'PIL')
SEND2TRASH_AVAILABLE = check_package('send2trash')

# Enhanced imports with fallbacks
console = None
if RICH_AVAILABLE:
    try:
        from rich.console import Console
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, MofNCompleteColumn
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        from rich.tree import Tree
        from rich.prompt import Confirm, Prompt
        console = Console()
    except ImportError:
        pass

if PIL_AVAILABLE:
    try:
        from PIL import Image, UnidentifiedImageError
        from PIL.ExifTags import TAGS
    except ImportError:
        pass

if SEND2TRASH_AVAILABLE:
    try:
        from send2trash import send2trash
    except ImportError:
        pass

# Graceful shutdown handling
class GracefulKiller:
    def __init__(self):
        self.kill_now = False
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        print("\n\n🛑 Graceful shutdown initiated...")
        print("   Finishing current operations and saving progress...")
        self.kill_now = True

killer = GracefulKiller()

# Action types for better organization
class OrganizeAction(Enum):
    ANALYZE_ONLY = "analyze"
    COPY = "copy"
    MOVE = "move"
    SYMLINK = "symlink"

class DuplicateAction(Enum):
    REPORT_ONLY = "report"
    DELETE_DUPLICATES = "delete"
    MOVE_TO_FOLDER = "move"
    TRASH_DUPLICATES = "trash"

# Configuration classes
@dataclass
class OrganizeConfig:
    """Configuration for file organization"""
    action: OrganizeAction = OrganizeAction.ANALYZE_ONLY
    create_date_folders: bool = True
    create_type_folders: bool = True
    preserve_structure: bool = False
    min_file_size: int = 0
    max_file_size: int = 0
    backup_before_move: bool = True
    
@dataclass
class AnalysisConfig:
    """Configuration for analysis behavior"""
    max_depth: int = 10
    max_analysis_files: int = 500
    min_files_for_organization: int = 5
    media_rich_ratio: float = 0.2
    document_heavy_count: int = 15
    mixed_content_file_count: int = 30
    mixed_content_ext_count: int = 4
    hash_size_threshold: Tuple[int, int] = (1024, 100 * 1024 * 1024)  # 1KB to 100MB

# Enhanced file categorization
FILE_CATEGORIES = {
    'images': {
        'extensions': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.ico', '.raw', '.cr2', '.nef', '.arw'},
        'folder': 'Images',
        'subfolders': {
            'raw': {'.raw', '.cr2', '.nef', '.arw', '.dng'},
            'screenshots': {'screenshot', 'screen shot', 'screen_shot'},
            'wallpapers': {'wallpaper', 'background', 'desktop'}
        }
    },
    'videos': {
        'extensions': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp', '.f4v'},
        'folder': 'Videos',
        'subfolders': {}
    },
    'audio': {
        'extensions': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.opus', '.ape'},
        'folder': 'Audio',
        'subfolders': {}
    },
    'documents': {
        'extensions': {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.pages'},
        'folder': 'Documents',
        'subfolders': {
            'pdfs': {'.pdf'},
            'word_docs': {'.doc', '.docx'},
            'text_files': {'.txt', '.rtf'}
        }
    },
    'spreadsheets': {
        'extensions': {'.xls', '.xlsx', '.csv', '.ods', '.numbers'},
        'folder': 'Spreadsheets',
        'subfolders': {}
    },
    'presentations': {
        'extensions': {'.ppt', '.pptx', '.odp', '.key'},
        'folder': 'Presentations',
        'subfolders': {}
    },
    'code': {
        'extensions': {'.py', '.js', '.html', '.css', '.cpp', '.java', '.sql', '.json', '.xml', '.php', '.rb', '.go', '.rs', '.swift', '.kt'},
        'folder': 'Code',
        'subfolders': {
            'python': {'.py'},
            'web': {'.html', '.css', '.js'},
            'data': {'.json', '.xml', '.sql'}
        }
    },
    'archives': {
        'extensions': {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'},
        'folder': 'Archives',
        'subfolders': {}
    },
    'executables': {
        'extensions': {'.exe', '.msi', '.deb', '.rpm', '.dmg', '.app', '.appx'},
        'folder': 'Programs',
        'subfolders': {}
    },
    'fonts': {
        'extensions': {'.ttf', '.otf', '.woff', '.woff2', '.eot'},
        'folder': 'Fonts',
        'subfolders': {}
    }
}

# System folders to skip (enhanced)
SYSTEM_FOLDERS = {
    # Package managers and installations
    'node_modules', '__pycache__', '.git', '.svn', '.hg', 'vendor',
    'site-packages', 'pip', 'conda', 'anaconda3', 'miniconda3',
    'venv', 'virtualenv', '.venv', 'env', '.env',
    
    # System and cache directories
    'System Volume Information', '$RECYCLE.BIN', 'Recovery', 'hiberfil.sys',
    '.Trash', '.cache', 'cache', 'temp', 'tmp', 'Temp', 'temporary files',
    'AppData', 'Application Data', 'ProgramData', 'Program Files', 'Program Files (x86)',
    'Windows', 'System32', 'SysWOW64',
    
    # Build and development
    'build', 'dist', 'target', 'bin', 'obj', '.vs', '.vscode', '.idea',
    'Debug', 'Release', 'x64', 'x86', 'out',
    
    # Already organized or backup folders
    'Organized_', 'Analysis_Report_', 'Backup_', 'Archive_', 'Smart_Analysis_',
    
    # Cloud sync folders (avoid conflicts)
    '.dropbox', '.onedrive', '.googledrive', 'iCloud', '.sync'
}

class HashCache:
    """SQLite-based hash caching for faster subsequent runs"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.smart_organizer")
        os.makedirs(cache_dir, exist_ok=True)
        
        self.db_path = os.path.join(cache_dir, "file_hashes.db")
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        """Initialize the hash cache database"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS file_hashes (
                file_path TEXT PRIMARY KEY,
                file_size INTEGER,
                modified_time REAL,
                hash_sha256 TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 1
            )
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hash ON file_hashes(hash_sha256)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_size ON file_hashes(file_size)
        """)
        
        self.conn.commit()
    
    def get_hash(self, file_path: str, file_size: int, modified_time: float) -> Optional[str]:
        """Get cached hash if file hasn't changed"""
        cursor = self.conn.execute(
            "SELECT hash_sha256 FROM file_hashes WHERE file_path = ? AND file_size = ? AND modified_time = ?",
            (file_path, file_size, modified_time)
        )
        result = cursor.fetchone()
        
        if result:
            # Update access count
            self.conn.execute(
                "UPDATE file_hashes SET access_count = access_count + 1, last_updated = CURRENT_TIMESTAMP WHERE file_path = ?",
                (file_path,)
            )
            self.conn.commit()
            return result[0]
        return None
    
    def store_hash(self, file_path: str, file_size: int, modified_time: float, hash_value: str):
        """Store hash in cache"""
        self.conn.execute(
            "INSERT OR REPLACE INTO file_hashes (file_path, file_size, modified_time, hash_sha256) VALUES (?, ?, ?, ?)",
            (file_path, file_size, modified_time, hash_value)
        )
        self.conn.commit()
    
    def cleanup_cache(self, days_old: int = 30):
        """Remove old cache entries"""
        self.conn.execute(
            "DELETE FROM file_hashes WHERE last_updated < datetime('now', '-{} days')".format(days_old)
        )
        self.conn.commit()
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        cursor = self.conn.execute("SELECT COUNT(*), SUM(access_count) FROM file_hashes")
        total_entries, total_accesses = cursor.fetchone()
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM file_hashes WHERE last_updated > datetime('now', '-7 days')")
        recent_entries = cursor.fetchone()[0]
        
        return {
            'total_entries': total_entries or 0,
            'total_accesses': total_accesses or 0,
            'recent_entries': recent_entries or 0
        }
    
    def close(self):
        """Close database connection"""
        self.conn.close()

class SmartOrganizer:
    """Main organizer class with enhanced functionality"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.hash_cache = HashCache()
        self.analysis_config = AnalysisConfig()
        self.organize_config = OrganizeConfig()
        self.duplicate_action = DuplicateAction.REPORT_ONLY
        self.max_workers = min(16, (os.cpu_count() or 1) * 2)
        self.chunk_size = 65536
        self.dry_run = False
        self.verbose = False
        
        # Statistics
        self.stats = {
            'files_processed': 0,
            'duplicates_found': 0,
            'empty_folders_found': 0,
            'total_size_processed': 0,
            'potential_savings': 0,
            'files_organized': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # Setup logging
        self.setup_logging()
    
    def setup_logging(self):
        """Setup enhanced logging"""
        log_dir = os.path.expanduser("~/.smart_organizer/logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"organizer_{datetime.now():%Y%m%d_%H%M%S}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout) if self.verbose else logging.NullHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def is_system_folder(self, folder_name: str, folder_path: str) -> bool:
        """Enhanced system folder detection"""
        folder_lower = folder_name.lower()
        
        # Direct matches
        if any(folder_name.startswith(sf) for sf in SYSTEM_FOLDERS):
            return True
        
        # Pattern matches
        system_patterns = ['$', '.', '~', '#']
        if any(folder_name.startswith(p) or folder_lower.endswith(('_cache', '_temp', '_backup', '.tmp')) for p in system_patterns):
            return True
        
        # Check for package indicators with file analysis
        package_indicators = ['setup', 'install', 'package', 'lib', 'include', 'share', 'bin']
        if any(indicator in folder_lower for indicator in package_indicators):
            try:
                sample_files = os.listdir(folder_path)[:50]
                system_files = sum(1 for f in sample_files if f.endswith(('.py', '.pyc', '.exe', '.dll', '.so', '.a', '.lib')))
                if system_files > len(sample_files) * 0.4:
                    return True
            except:
                pass
        
        return False
    
    def calculate_hash(self, file_path: str) -> Optional[str]:
        """Calculate file hash with caching"""
        try:
            stat = os.stat(file_path)
            file_size = stat.st_size
            modified_time = stat.st_mtime
            
            # Check cache first
            cached_hash = self.hash_cache.get_hash(file_path, file_size, modified_time)
            if cached_hash:
                self.stats['cache_hits'] += 1
                return cached_hash
            
            self.stats['cache_misses'] += 1
            
            # Calculate hash
            hasher = hashlib.sha256()
            with open(file_path, 'rb') as f:
                while chunk := f.read(self.chunk_size):
                    if killer.kill_now:
                        return None
                    hasher.update(chunk)
            
            hash_value = hasher.hexdigest()
            
            # Store in cache
            self.hash_cache.store_hash(file_path, file_size, modified_time, hash_value)
            
            return hash_value
            
        except Exception as e:
            self.logger.error(f"Error calculating hash for {file_path}: {e}")
            return None
    
    def categorize_file(self, file_path: str) -> Tuple[str, str]:
        """Enhanced file categorization"""
        ext = Path(file_path).suffix.lower()
        filename = Path(file_path).stem.lower()
        
        for category, info in FILE_CATEGORIES.items():
            if ext in info['extensions']:
                # Check for subcategory
                for subfolder, indicators in info.get('subfolders', {}).items():
                    if ext in indicators or any(indicator in filename for indicator in indicators if isinstance(indicator, str)):
                        return category, subfolder
                return category, ''
        
        return 'other', ''
    
    def find_empty_folders(self, directory: str) -> List[str]:
        """Find all empty folders in directory tree"""
        empty_folders = []
        
        for root, dirs, files in os.walk(directory, topdown=False):
            if killer.kill_now:
                break
                
            # Skip system folders
            if self.is_system_folder(os.path.basename(root), root):
                continue
            
            try:
                # Check if folder is empty (no files and no non-empty subdirectories)
                if not files and not dirs:
                    empty_folders.append(root)
                elif not files:
                    # Check if all subdirectories are empty
                    has_content = False
                    for subdir in dirs:
                        subdir_path = os.path.join(root, subdir)
                        if subdir_path not in empty_folders:
                            has_content = True
                            break
                    if not has_content:
                        empty_folders.append(root)
                        
            except PermissionError:
                continue
        
        return empty_folders
    
    def cleanup_empty_folders(self, directory: str, confirm: bool = True) -> int:
        """Remove empty folders with confirmation"""
        empty_folders = self.find_empty_folders(directory)
        
        if not empty_folders:
            if console:
                console.print("✅ No empty folders found!")
            else:
                print("✅ No empty folders found!")
            return 0
        
        # Display empty folders
        if console:
            from rich.tree import Tree
            tree = Tree("📁 Empty Folders Found")
            for folder in empty_folders[:20]:  # Show first 20
                relative_path = os.path.relpath(folder, directory)
                tree.add(f"[dim]{relative_path}[/dim]")
            if len(empty_folders) > 20:
                tree.add(f"[yellow]... and {len(empty_folders) - 20} more[/yellow]")
            console.print(tree)
            
            from rich.prompt import Confirm
            if confirm and not Confirm.ask(f"Delete {len(empty_folders)} empty folders?"):
                return 0
        else:
            print(f"\n📁 Found {len(empty_folders)} empty folders:")
            for i, folder in enumerate(empty_folders[:10]):
                print(f"  {i+1:2d}) {os.path.relpath(folder, directory)}")
            if len(empty_folders) > 10:
                print(f"  ... and {len(empty_folders) - 10} more")
            
            if confirm:
                response = input(f"\nDelete {len(empty_folders)} empty folders? (y/N): ").strip().lower()
                if response != 'y':
                    return 0
        
        # Delete folders
        deleted_count = 0
        for folder in empty_folders:
            if killer.kill_now:
                break
                
            try:
                if not self.dry_run:
                    if SEND2TRASH_AVAILABLE:
                        from send2trash import send2trash
                        send2trash(folder)
                    else:
                        os.rmdir(folder)
                    self.logger.info(f"Deleted empty folder: {folder}")
                deleted_count += 1
            except Exception as e:
                self.logger.error(f"Failed to delete {folder}: {e}")
        
        self.stats['empty_folders_found'] = len(empty_folders)
        return deleted_count
    
    def organize_files(self, source_dir: str, target_dir: Optional[str] = None) -> Dict:
        """Organize files into categorized structure"""
        if not target_dir:
            target_dir = os.path.join(source_dir, f"Organized_{datetime.now():%Y%m%d_%H%M%S}")
        
        if self.dry_run:
            print(f"🏃‍♂️ DRY RUN: Would organize files to {target_dir}")
            return {'organized': 0, 'skipped': 0, 'errors': 0}
        
        os.makedirs(target_dir, exist_ok=True)
        results = {'organized': 0, 'skipped': 0, 'errors': 0}
        
        for root, dirs, files in os.walk(source_dir):
            if killer.kill_now:
                break
                
            # Skip already organized folders and system folders
            if 'Organized_' in root or self.is_system_folder(os.path.basename(root), root):
                continue
            
            for file in files:
                if killer.kill_now:
                    break
                    
                source_file = os.path.join(root, file)
                category, subcategory = self.categorize_file(source_file)
                
                # Build target path
                if category == 'other':
                    category_folder = 'Miscellaneous'
                else:
                    category_folder = FILE_CATEGORIES[category]['folder']
                
                if subcategory:
                    final_dir = os.path.join(target_dir, category_folder, subcategory.title())
                else:
                    final_dir = os.path.join(target_dir, category_folder)
                
                # Add date folder if configured
                if self.organize_config.create_date_folders:
                    try:
                        file_date = datetime.fromtimestamp(os.path.getmtime(source_file))
                        date_folder = file_date.strftime("%Y/%m")
                        final_dir = os.path.join(final_dir, date_folder)
                    except:
                        pass
                
                os.makedirs(final_dir, exist_ok=True)
                target_file = os.path.join(final_dir, file)
                
                # Handle existing files
                counter = 1
                original_target = target_file
                while os.path.exists(target_file):
                    base, ext = os.path.splitext(original_target)
                    target_file = f"{base}_{counter}{ext}"
                    counter += 1
                
                try:
                    if self.organize_config.action == OrganizeAction.MOVE:
                        shutil.move(source_file, target_file)
                    elif self.organize_config.action == OrganizeAction.COPY:
                        shutil.copy2(source_file, target_file)
                    elif self.organize_config.action == OrganizeAction.SYMLINK:
                        os.symlink(source_file, target_file)
                    
                    results['organized'] += 1
                    self.logger.info(f"Organized: {source_file} -> {target_file}")
                    
                except Exception as e:
                    results['errors'] += 1
                    self.logger.error(f"Failed to organize {source_file}: {e}")
        
        return results
    
    def analyze_folder_content(self, folder_path: str) -> Dict:
        """Enhanced folder content analysis"""
        try:
            files = []
            total_size = 0
            
            for root, dirs, filenames in os.walk(folder_path):
                level = root[len(folder_path):].count(os.sep)
                if level > self.analysis_config.max_depth:
                    dirs.clear()
                    continue
                    
                for file in filenames:
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                        files.append((file, size))
                        total_size += size
                        
                        if len(files) > self.analysis_config.max_analysis_files:
                            break
                    except:
                        continue
                
                if len(files) > self.analysis_config.max_analysis_files:
                    break
            
            if not files:
                return {'needs_organization': False, 'reason': 'empty'}
            
            # Enhanced analysis
            extensions = [Path(f[0]).suffix.lower() for f in files]
            extension_counts = Counter(extensions)
            
            # Category analysis
            category_counts = defaultdict(int)
            for file, size in files:
                category, _ = self.categorize_file(file)
                category_counts[category] += 1
            
            total_files = len(files)
            
            # Decision matrix
            media_files = sum(count for cat, count in category_counts.items() if cat in ['images', 'videos', 'audio'])
            document_files = sum(count for cat, count in category_counts.items() if cat in ['documents', 'spreadsheets', 'presentations'])
            
            media_ratio = media_files / total_files if total_files > 0 else 0
            diversity_score = len(extension_counts) / total_files if total_files > 0 else 0
            
            # Enhanced decision logic
            if media_ratio > self.analysis_config.media_rich_ratio:
                return {
                    'needs_organization': True,
                    'reason': 'media_rich',
                    'file_count': total_files,
                    'total_size': total_size,
                    'categories': dict(category_counts),
                    'confidence': min(0.9, media_ratio + 0.1)
                }
            
            if total_files < self.analysis_config.min_files_for_organization:
                return {'needs_organization': False, 'reason': 'too_small', 'file_count': total_files}
            
            if document_files > self.analysis_config.document_heavy_count:
                return {
                    'needs_organization': True,
                    'reason': 'document_heavy',
                    'file_count': total_files,
                    'total_size': total_size,
                    'categories': dict(category_counts),
                    'confidence': 0.8
                }
            
            if (total_files > self.analysis_config.mixed_content_file_count and
                len(extension_counts) > self.analysis_config.mixed_content_ext_count and
                diversity_score > 0.1):
                return {
                    'needs_organization': True,
                    'reason': 'mixed_content',
                    'file_count': total_files,
                    'total_size': total_size,
                    'categories': dict(category_counts),
                    'confidence': 0.7
                }
            
            return {
                'needs_organization': False,
                'reason': 'not_beneficial',
                'file_count': total_files,
                'total_size': total_size,
                'categories': dict(category_counts)
            }
            
        except Exception as e:
            return {'needs_organization': False, 'reason': f'error: {e}'}

def format_size(num_bytes: int) -> str:
    """Format bytes into human-readable string"""
    if num_bytes is None or num_bytes == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes = int(num_bytes // 1024.0)
    return f"{num_bytes:.1f} EB"

def main():
    """Enhanced main function with comprehensive CLI"""
    parser = argparse.ArgumentParser(
        description="Ultimate Smart Drive Organizer - Professional Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Analyze directory structure
  python {sys.argv[0]} /path/to/directory --action analyze

  # Organize files with copy (safe mode)
  python {sys.argv[0]} /path/to/directory --action copy --organize

  # Move files and clean up empties
  python {sys.argv[0]} /path/to/directory --action move --organize --cleanup-empty

  # Find and handle duplicates
  python {sys.argv[0]} /path/to/directory --find-duplicates --duplicate-action report

  # Dry run to see what would happen
  python {sys.argv[0]} /path/to/directory --organize --dry-run

  # Full organization with all features
  python {sys.argv[0]} /path/to/directory --action move --organize --cleanup-empty \\
                      --find-duplicates --duplicate-action move --workers 16

Version: {__version__}
Author: {__author__}
        """
    )

    # Primary arguments
    parser.add_argument("directory", help="Target directory to analyze/organize")
    
    # Action control
    action_group = parser.add_argument_group("Action Control")
    action_group.add_argument(
        "--action", 
        choices=['analyze', 'copy', 'move', 'symlink'],
        default='analyze',
        help="Action to perform (default: analyze)"
    )
    action_group.add_argument("--organize", action="store_true", help="Organize files into categorized structure")
    action_group.add_argument("--find-duplicates", action="store_true", help="Find and report duplicate files")
    action_group.add_argument("--cleanup-empty", action="store_true", help="Find and remove empty folders")
    action_group.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")

    # Duplicate handling
    dup_group = parser.add_argument_group("Duplicate Handling")
    dup_group.add_argument(
        "--duplicate-action",
        choices=['report', 'delete', 'move', 'trash'],
        default='report',
        help="Action for duplicate files (default: report)"
    )
    dup_group.add_argument("--duplicate-folder", help="Folder to move duplicates to (for move action)")

    # Performance tuning
    perf_group = parser.add_argument_group("Performance")
    perf_group.add_argument(
        "--workers", "-w",
        type=int,
        default=min(16, (os.cpu_count() or 1) * 2),
        help=f"Number of worker threads (default: {min(16, (os.cpu_count() or 1) * 2)})"
    )
    perf_group.add_argument("--chunk-size", type=int, default=65536, help="File read chunk size (default: 65536)")
    perf_group.add_argument("--max-depth", type=int, default=10, help="Maximum directory depth to scan (default: 10)")

    # File filtering
    filter_group = parser.add_argument_group("File Filtering")
    filter_group.add_argument("--min-size", type=int, default=0, help="Minimum file size in bytes")
    filter_group.add_argument("--max-size", type=int, default=0, help="Maximum file size in bytes (0 = no limit)")
    filter_group.add_argument("--extensions", help="Comma-separated list of file extensions to include")
    filter_group.add_argument("--exclude-extensions", help="Comma-separated list of file extensions to exclude")

    # Organization options
    org_group = parser.add_argument_group("Organization Options")
    org_group.add_argument("--output-dir", "-o", help="Output directory for organized files")
    org_group.add_argument("--no-date-folders", action="store_true", help="Don't create date-based subfolders")
    org_group.add_argument("--no-type-folders", action="store_true", help="Don't create type-based folders")
    org_group.add_argument("--preserve-structure", action="store_true", help="Preserve original directory structure")

    # Cache and logging
    misc_group = parser.add_argument_group("Cache and Logging")
    misc_group.add_argument("--cache-dir", help="Directory for hash cache (default: ~/.smart_organizer)")
    misc_group.add_argument("--clear-cache", action="store_true", help="Clear hash cache before starting")
    misc_group.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    misc_group.add_argument("--log-file", help="Log file path (auto-generated if not specified)")

    # Safety options
    safety_group = parser.add_argument_group("Safety Options")
    safety_group.add_argument("--no-confirm", action="store_true", help="Don't ask for confirmation (use with caution)")
    safety_group.add_argument("--backup", action="store_true", help="Create backup before making changes")

    args = parser.parse_args()

    # Print header
    if console:
        title = Panel(
            f"[bold blue]Ultimate Smart Drive Organizer v{__version__}[/bold blue]\n"
            f"[dim]Professional file organization and duplicate detection[/dim]",
            title="🚀 Smart Organizer",
            border_style="blue"
        )
        console.print(title)
    else:
        print("=" * 80)
        print(f"🚀 ULTIMATE SMART DRIVE ORGANIZER v{__version__}")
        print("   Professional file organization and duplicate detection")
        print("=" * 80)

    # Validate directory
    if not os.path.isdir(args.directory):
        print(f"❌ Error: '{args.directory}' is not a valid directory")
        return 1

    # Initialize organizer
    organizer = SmartOrganizer()
    organizer.max_workers = args.workers
    organizer.chunk_size = args.chunk_size
    organizer.dry_run = args.dry_run
    organizer.verbose = args.verbose
    
    # Configure analysis
    organizer.analysis_config.max_depth = args.max_depth
    
    # Configure organization
    organizer.organize_config.action = OrganizeAction(args.action)
    organizer.organize_config.create_date_folders = not args.no_date_folders
    organizer.organize_config.create_type_folders = not args.no_type_folders
    organizer.organize_config.preserve_structure = args.preserve_structure
    organizer.organize_config.min_file_size = args.min_size
    organizer.organize_config.max_file_size = args.max_size
    
    # Configure duplicate handling
    organizer.duplicate_action = DuplicateAction(args.duplicate_action)

    try:
        # Clear cache if requested
        if args.clear_cache:
            organizer.hash_cache.cleanup_cache(0)
            print("🗑️  Hash cache cleared")

        # Show cache stats
        cache_stats = organizer.hash_cache.get_stats()
        if cache_stats['total_entries'] > 0:
            print(f"📊 Hash cache: {cache_stats['total_entries']:,} entries, {cache_stats['total_accesses']:,} total hits")

        start_time = datetime.now()
        
        # Main operations
        if args.cleanup_empty:
            print(f"\n🧹 Cleaning up empty folders in {args.directory}")
            deleted = organizer.cleanup_empty_folders(args.directory, confirm=not args.no_confirm)
            print(f"✅ Removed {deleted} empty folders")

        if args.organize:
            print(f"\n📁 Organizing files in {args.directory}")
            output_dir = args.output_dir or os.path.join(args.directory, f"Organized_{datetime.now():%Y%m%d_%H%M%S}")
            results = organizer.organize_files(args.directory, output_dir)
            print(f"✅ Organized {results['organized']} files, {results['errors']} errors")

        # Show final statistics
        end_time = datetime.now()
        duration = end_time - start_time
        
        if console:
            stats_table = Table(title="📈 Final Statistics", show_header=True)
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="green")
            
            stats_table.add_row("Processing Time", str(duration).split('.')[0])
            stats_table.add_row("Files Processed", f"{organizer.stats['files_processed']:,}")
            stats_table.add_row("Cache Hits", f"{organizer.stats['cache_hits']:,}")
            stats_table.add_row("Cache Misses", f"{organizer.stats['cache_misses']:,}")
            if organizer.stats['cache_hits'] + organizer.stats['cache_misses'] > 0:
                hit_rate = organizer.stats['cache_hits'] / (organizer.stats['cache_hits'] + organizer.stats['cache_misses']) * 100
                stats_table.add_row("Cache Hit Rate", f"{hit_rate:.1f}%")
            
            console.print(stats_table)
        else:
            print(f"\n📈 Final Statistics:")
            print(f"   ⏱️  Processing Time: {duration}")
            print(f"   📁 Files Processed: {organizer.stats['files_processed']:,}")
            print(f"   💾 Cache Hits: {organizer.stats['cache_hits']:,}")
            print(f"   🔍 Cache Misses: {organizer.stats['cache_misses']:,}")

        print(f"\n🎉 Smart organization {'simulation' if args.dry_run else 'process'} complete!")
        
    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled by user")
        return 130
    except Exception as e:
        if console:
            console.print_exception()
        else:
            print(f"\n💥 Unexpected error: {e}")
        return 1
    finally:
        organizer.hash_cache.close()
        print("👋 Thanks for using Ultimate Smart Drive Organizer!")

    return 0

if __name__ == "__main__":
    sys.exit(main())