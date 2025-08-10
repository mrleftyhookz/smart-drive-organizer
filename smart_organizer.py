#!/usr/bin/env python3
"""
Smart E-Drive Organizer (Refined Edition)
Intelligently focuses only on directories that benefit from organization.
Skips system, package, and already-organized directories.
"""

import os
import sys
import hashlib
import shutil
import signal
import sqlite3
import threading
import time
import json
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict, Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
import mimetypes

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

# Enhanced package detection
def check_package(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False

# Check for enhanced features
RICH_AVAILABLE = check_package('rich')
PIL_AVAILABLE = check_package('pillow', 'PIL')

# Import what's available
try:
    if RICH_AVAILABLE:
        from rich.console import Console
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, MofNCompleteColumn
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        console = Console()
    else:
        console = None
        
    if PIL_AVAILABLE:
        from PIL import Image, UnidentifiedImageError
        from PIL.ExifTags import TAGS
        
except ImportError as e:
    pass

# Configuration
E_DRIVE_PATHS = ['/mnt/e', '/media/e', 'E:', 'E:\\']
E_DRIVE_PATH = None
for path in E_DRIVE_PATHS:
    if os.path.exists(path) and os.path.isdir(path):
        E_DRIVE_PATH = path
        break

MAX_WORKERS = min(8, (os.cpu_count() or 1) + 2)  # Conservative for file I/O
CHUNK_SIZE = 65536

# Smart filtering rules
SYSTEM_FOLDERS = {
    # Package managers and installations
    'node_modules', '__pycache__', '.git', '.svn', '.hg',
    'site-packages', 'pip', 'conda', 'anaconda3', 'miniconda3',
    'venv', 'virtualenv', '.venv', 'env',
    
    # System and cache
    'System Volume Information', '$RECYCLE.BIN', 'Recovery',
    '.Trash', '.cache', 'cache', 'temp', 'tmp', 'Temp',
    'AppData', 'Application Data', 'ProgramData', 'Program Files',
    
    # Build and development
    'build', 'dist', 'target', 'bin', 'obj', '.vs', '.vscode',
    'Debug', 'Release', 'x64', 'x86',
    
    # Already organized
    'Organized_', 'Analysis_Report_', 'Backup_', 'Archive_'
}

SYSTEM_PATTERNS = {
    '$', '.', '~', '#',  # System prefixes
    '_cache', '_temp', '_backup',  # Common suffixes
}

def is_system_folder(folder_name: str, folder_path: str) -> bool:
    """Determine if a folder is system-related and should be skipped"""
    folder_lower = folder_name.lower()
    
    # Check exact matches
    if folder_lower in {s.lower() for s in SYSTEM_FOLDERS}:
        return True
    
    # Check patterns
    for pattern in SYSTEM_PATTERNS:
        if folder_name.startswith(pattern) or folder_lower.endswith(pattern):
            return True
    
    # Check for package/installation indicators
    package_indicators = ['setup', 'install', 'package', 'lib', 'include', 'share']
    if any(indicator in folder_lower for indicator in package_indicators):
        # Additional check - if it contains many .py, .exe, .dll files, likely a package
        try:
            files = os.listdir(folder_path)[:20]  # Sample first 20 files
            system_files = sum(1 for f in files if f.endswith(('.py', '.pyc', '.exe', '.dll', '.so', '.a')))
            if system_files > len(files) * 0.5:  # More than 50% system files
                return True
        except:
            pass
    
    return False

def analyze_folder_content(folder_path: str) -> Dict:
    """Analyze folder content to determine if it needs organization"""
    try:
        files = []
        for root, dirs, filenames in os.walk(folder_path):
            # Don't recurse too deep for initial analysis
            level = root[len(folder_path):].count(os.sep)
            if level > 2:
                dirs.clear()
                continue
            files.extend(filenames)
            if len(files) > 200:  # Sample limit for quick analysis
                break
        
        if not files:
            return {'needs_organization': False, 'reason': 'empty'}
        
        # Analyze file types
        extensions = [Path(f).suffix.lower() for f in files]
        extension_counts = Counter(extensions)
        
        # Categories
        media_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.mp4', '.avi', '.mov', '.mp3', '.wav'}
        document_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.xls', '.xlsx', '.ppt', '.pptx'}
        code_extensions = {'.py', '.js', '.html', '.css', '.cpp', '.java', '.sql', '.json', '.xml'}
        
        media_files = sum(count for ext, count in extension_counts.items() if ext in media_extensions)
        document_files = sum(count for ext, count in extension_counts.items() if ext in document_extensions)
        code_files = sum(count for ext, count in extension_counts.items() if ext in code_extensions)
        
        total_files = len(files)
        media_ratio = media_files / total_files if total_files > 0 else 0
        
        # Decision logic
        if total_files < 10:
            return {'needs_organization': False, 'reason': 'too_small', 'file_count': total_files}
        
        if media_ratio > 0.3:  # 30%+ media files
            return {
                'needs_organization': True, 
                'reason': 'media_rich', 
                'file_count': total_files,
                'media_files': media_files,
                'categories': {'media': media_files, 'documents': document_files, 'code': code_files}
            }
        
        if document_files > 20:  # Significant number of documents
            return {
                'needs_organization': True, 
                'reason': 'document_heavy',
                'file_count': total_files,
                'categories': {'media': media_files, 'documents': document_files, 'code': code_files}
            }
        
        # Mixed content with reasonable size
        if total_files > 50 and len(extension_counts) > 5:  # Diverse file types
            return {
                'needs_organization': True, 
                'reason': 'mixed_content',
                'file_count': total_files,
                'categories': {'media': media_files, 'documents': document_files, 'code': code_files}
            }
        
        return {
            'needs_organization': False, 
            'reason': 'not_beneficial',
            'file_count': total_files,
            'categories': {'media': media_files, 'documents': document_files, 'code': code_files}
        }
        
    except Exception as e:
        return {'needs_organization': False, 'reason': f'error: {e}'}

def discover_smart_directories(root_path: str):
    """Discover directories that actually benefit from organization"""
    if console:
        console.print(f"[blue]🧠 Smart scanning: {root_path}[/blue]")
    else:
        print(f"🧠 Smart scanning: {root_path}")
    
    candidates = []
    skipped = []
    
    try:
        items = os.listdir(root_path)
        
        if console and RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Analyzing directories...", total=len(items))
                
                for item in items:
                    if killer.kill_now:
                        break
                        
                    item_path = os.path.join(root_path, item)
                    progress.update(task, description=f"Checking {item}")
                    
                    if not os.path.isdir(item_path):
                        progress.advance(task)
                        continue
                    
                    # Check if system folder
                    if is_system_folder(item, item_path):
                        skipped.append({'name': item, 'reason': 'system_folder'})
                        progress.advance(task)
                        continue
                    
                    # Analyze content
                    analysis = analyze_folder_content(item_path)
                    
                    if analysis['needs_organization']:
                        candidates.append({
                            'path': item_path,
                            'name': item,
                            'analysis': analysis
                        })
                    else:
                        skipped.append({'name': item, 'reason': analysis['reason']})
                    
                    progress.advance(task)
        else:
            # Simple progress without Rich
            for i, item in enumerate(items):
                if killer.kill_now:
                    break
                    
                print(f"\rAnalyzing: {i+1}/{len(items)} - {item[:30]}", end="")
                
                item_path = os.path.join(root_path, item)
                if not os.path.isdir(item_path):
                    continue
                
                if is_system_folder(item, item_path):
                    skipped.append({'name': item, 'reason': 'system_folder'})
                    continue
                
                analysis = analyze_folder_content(item_path)
                if analysis['needs_organization']:
                    candidates.append({
                        'path': item_path,
                        'name': item,
                        'analysis': analysis
                    })
                else:
                    skipped.append({'name': item, 'reason': analysis['reason']})
            print()
        
    except PermissionError:
        if console:
            console.print(f"[red]❌ Permission denied accessing {root_path}[/red]")
        else:
            print(f"❌ Permission denied accessing {root_path}")
        return [], []
    
    return candidates, skipped

def display_smart_selection(candidates: List[Dict], skipped: List[Dict]):
    """Display smart directory selection"""
    if not candidates:
        print("🎯 Smart analysis complete - No directories need organization!")
        if skipped:
            print(f"   Skipped {len(skipped)} directories (system/already organized)")
        return []
    
    if console:
        # Show candidates
        table = Table(title="📁 Directories That Need Organization", show_header=True, header_style="bold green")
        table.add_column("#", width=3)
        table.add_column("Directory", style="cyan")
        table.add_column("Files", justify="right", style="blue")
        table.add_column("Reason", style="yellow")
        table.add_column("Content", style="white")
        
        for i, candidate in enumerate(candidates):
            analysis = candidate['analysis']
            content_desc = ""
            if 'categories' in analysis:
                cats = analysis['categories']
                content_parts = []
                if cats['media'] > 0:
                    content_parts.append(f"{cats['media']} media")
                if cats['documents'] > 0:
                    content_parts.append(f"{cats['documents']} docs")
                content_desc = ", ".join(content_parts)
            
            table.add_row(
                str(i + 1),
                candidate['name'],
                f"{analysis.get('file_count', 0):,}",
                analysis['reason'].replace('_', ' ').title(),
                content_desc
            )
        
        console.print(table)
        
        # Show skipped summary
        if skipped:
            skip_reasons = Counter(item['reason'] for item in skipped)
            skip_text = Text()
            skip_text.append(f"🔇 Skipped {len(skipped)} directories: ", style="dim")
            skip_text.append(", ".join(f"{reason.replace('_', ' ')} ({count})" for reason, count in skip_reasons.items()), style="dim cyan")
            console.print(skip_text)
    else:
        print(f"\n📁 Directories That Need Organization:")
        for i, candidate in enumerate(candidates):
            analysis = candidate['analysis']
            print(f"  {i+1:2d}) {candidate['name']:<30} {analysis.get('file_count', 0):>6,} files - {analysis['reason'].replace('_', ' ')}")
        
        if skipped:
            print(f"\n🔇 Skipped {len(skipped)} system/irrelevant directories")
    
    # Get selection
    while True:
        if killer.kill_now:
            return []
            
        try:
            choice = input(f"\n🎯 Select directories (1-{len(candidates)}, ranges like 1-3, or 'all'): ").strip()
            
            if choice.lower() == 'all':
                return [c['path'] for c in candidates]
            
            selected = []
            for part in choice.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    for i in range(start-1, end):
                        if 0 <= i < len(candidates):
                            selected.append(candidates[i]['path'])
                else:
                    i = int(part) - 1
                    if 0 <= i < len(candidates):
                        selected.append(candidates[i]['path'])
            
            return selected
            
        except (ValueError, KeyboardInterrupt):
            if killer.kill_now:
                return []
            print("❌ Invalid selection. Try again.")

def calculate_hash(file_path: str) -> Optional[str]:
    """Calculate SHA-256 hash of file"""
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                if killer.kill_now:
                    return None
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def get_file_metadata(file_path: str) -> Optional[Dict]:
    """Get file metadata efficiently"""
    if killer.kill_now:
        return None
        
    try:
        stat = os.stat(file_path)
        
        # Basic info
        size = stat.st_size
        modified_date = datetime.fromtimestamp(stat.st_mtime)
        
        # Only hash files that might be duplicates (reasonable size range)
        file_hash = None
        if 100 < size < 100 * 1024 * 1024:  # Between 100 bytes and 100MB
            file_hash = calculate_hash(file_path)
        
        # Simple category
        ext = Path(file_path).suffix.lower()
        if ext in {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.avi', '.mov'}:
            category = 'media'
        elif ext in {'.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx'}:
            category = 'document'
        elif ext in {'.py', '.js', '.html', '.css', '.sql', '.json'}:
            category = 'code'
        else:
            category = 'other'
        
        return {
            'path': file_path,
            'size': size,
            'hash': file_hash,
            'modified': modified_date,
            'category': category,
            'extension': ext
        }
    except Exception:
        return None

def process_directory_smart(directory_path: str):
    """Smart processing of a directory"""
    if killer.kill_now:
        return
        
    dir_name = os.path.basename(directory_path)
    
    if console:
        console.print(f"\n[green]🚀 Processing: {dir_name}[/green]")
    else:
        print(f"\n🚀 Processing: {dir_name}")
    
    # Collect files efficiently
    all_files = []
    for root, dirs, files in os.walk(directory_path):
        if killer.kill_now:
            break
        # Skip already organized folders
        dirs[:] = [d for d in dirs if not d.startswith(('Organized_', 'Analysis_Report_'))]
        
        for file in files:
            all_files.append(os.path.join(root, file))
            if len(all_files) % 1000 == 0 and killer.kill_now:
                break
    
    if killer.kill_now:
        print("⏹️  Processing interrupted")
        return
    
    if not all_files:
        print("📭 No files found")
        return
    
    print(f"📁 Found {len(all_files):,} files")
    
    # Process files with progress
    processed_files = []
    start_time = time.time()
    
    if console and RICH_AVAILABLE:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Processing files...", total=len(all_files))
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # Submit work in chunks to allow interruption
                chunk_size = 100
                for i in range(0, len(all_files), chunk_size):
                    if killer.kill_now:
                        break
                        
                    chunk = all_files[i:i+chunk_size]
                    future_to_file = {executor.submit(get_file_metadata, f): f for f in chunk}
                    
                    for future in as_completed(future_to_file):
                        if killer.kill_now:
                            break
                        result = future.result()
                        if result:
                            processed_files.append(result)
                        progress.advance(task)
    else:
        # Simple processing
        for i, file_path in enumerate(all_files):
            if killer.kill_now:
                break
            if i % 100 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                print(f"\rProcessing: {i+1}/{len(all_files)} ({rate:.1f} files/sec)", end="")
            
            result = get_file_metadata(file_path)
            if result:
                processed_files.append(result)
        print()
    
    if killer.kill_now:
        print("⏹️  Processing interrupted - saving partial results...")
    
    # Find duplicates among hashed files
    hash_groups = defaultdict(list)
    for file_data in processed_files:
        if file_data['hash']:
            hash_groups[file_data['hash']].append(file_data)
    
    duplicates = {h: files for h, files in hash_groups.items() if len(files) > 1}
    
    # Generate report
    generate_smart_report(directory_path, processed_files, duplicates)

def generate_smart_report(directory_path: str, files: List[Dict], duplicates: Dict):
    """Generate focused analysis report"""
    report_dir = os.path.join(directory_path, f"Smart_Analysis_{datetime.now():%Y%m%d_%H%M%S}")
    
    try:
        os.makedirs(report_dir, exist_ok=True)
    except:
        # Fallback to current directory if can't create in target
        report_dir = f"Smart_Analysis_{os.path.basename(directory_path)}_{datetime.now():%Y%m%d_%H%M%S}"
        os.makedirs(report_dir, exist_ok=True)
    
    # Calculate statistics
    total_size = sum(f['size'] for f in files)
    duplicate_files = sum(len(group) for group in duplicates.values())
    duplicate_size = sum(sum(f['size'] for f in group[1:]) for group in duplicates.values())
    
    categories = Counter(f['category'] for f in files)
    extensions = Counter(f['extension'] for f in files)
    
    # Create summary
    summary = {
        'directory': directory_path,
        'analysis_time': datetime.now().isoformat(),
        'interrupted': killer.kill_now,
        'total_files': len(files),
        'total_size_bytes': total_size,
        'total_size_formatted': format_size(total_size),
        'duplicate_groups': len(duplicates),
        'duplicate_files': duplicate_files,
        'potential_savings_bytes': duplicate_size,
        'potential_savings_formatted': format_size(duplicate_size),
        'file_categories': dict(categories),
        'top_extensions': dict(extensions.most_common(10)),
        'largest_files': [
            {'path': f['path'], 'size': f['size'], 'size_formatted': format_size(f['size'])}
            for f in sorted(files, key=lambda x: x['size'], reverse=True)[:10]
        ]
    }
    
    # Save JSON report
    json_path = os.path.join(report_dir, 'analysis_summary.json')
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    # Save duplicates if found
    if duplicates:
        duplicates_path = os.path.join(report_dir, 'duplicates_found.json')
        with open(duplicates_path, 'w') as f:
            json.dump({h: files for h, files in duplicates.items()}, f, indent=2, default=str)
    
    # Display results
    if console:
        status = "⚠️ Interrupted" if killer.kill_now else "✅ Complete"
        panel = Panel(
            f"[bold]{status} - Smart Analysis Results[/bold]\n\n"
            f"📁 Files Analyzed: {summary['total_files']:,}\n"
            f"💾 Total Size: {summary['total_size_formatted']}\n"
            f"🔍 Duplicate Groups: {summary['duplicate_groups']:,}\n"
            f"♻️  Potential Savings: {summary['potential_savings_formatted']}\n"
            f"📊 Report Location: {report_dir}",
            title="📈 Analysis Results",
            border_style="green" if not killer.kill_now else "yellow"
        )
        console.print(panel)
    else:
        status = "⚠️ Interrupted" if killer.kill_now else "✅ Complete"
        print(f"\n📈 {status} - Smart Analysis Results:")
        print(f"   📁 Files Analyzed: {summary['total_files']:,}")
        print(f"   💾 Total Size: {summary['total_size_formatted']}")
        print(f"   🔍 Duplicate Groups: {summary['duplicate_groups']:,}")
        print(f"   ♻️  Potential Savings: {summary['potential_savings_formatted']}")
        print(f"   📊 Report Location: {report_dir}")

def format_size(num_bytes: int) -> str:
    """Format bytes into human-readable string"""
    if num_bytes is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"

def main():
    """Main execution with graceful handling"""
    print("="*70)
    print("🧠 SMART E-DRIVE ORGANIZER (REFINED EDITION)")
    print("="*70)
    print("   • Skips system/package directories")
    print("   • Focuses on content that needs organization") 
    print("   • Graceful shutdown with Ctrl+C")
    print("="*70)
    
    try:
        # Check E drive
        e_drive_path = E_DRIVE_PATH
        if not e_drive_path:
            print("\n❌ E drive not found. Checked paths:")
            for path in E_DRIVE_PATHS:
                print(f"   📂 {path}")
            
            manual_path = input("\n📂 Enter E drive path manually: ").strip()
            if manual_path and os.path.exists(manual_path):
                e_drive_path = manual_path
            else:
                print("❌ Invalid path. Exiting.")
                return
        
        print(f"\n✅ E Drive found: {e_drive_path}")
        
        # Smart discovery
        candidates, skipped = discover_smart_directories(e_drive_path)
        
        if killer.kill_now:
            print("\n🛑 Shutdown requested during discovery. Exiting.")
            return
        
        # Selection
        selected_dirs = display_smart_selection(candidates, skipped)
        
        if not selected_dirs or killer.kill_now:
            print("\n👋 Exiting gracefully.")
            return
        
        print(f"\n🚀 Processing {len(selected_dirs)} directories...")
        print("   💡 Press Ctrl+C anytime for graceful shutdown")
        
        # Process each directory
        for i, directory in enumerate(selected_dirs, 1):
            if killer.kill_now:
                break
                
            print(f"\n📁 [{i}/{len(selected_dirs)}] Processing directory...")
            process_directory_smart(directory)
        
        if killer.kill_now:
            print("\n🛑 Processing interrupted but data saved!")
        else:
            print("\n🎉 Smart analysis complete!")
            
    except KeyboardInterrupt:
        print("\n🛑 Graceful shutdown initiated...")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print("   Saving any progress and exiting...")
    finally:
        print("👋 Thanks for using Smart E-Drive Organizer!")

if __name__ == "__main__":
    main()