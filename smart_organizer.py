#!/usr/bin/env python3
"""
Smart E-Drive Organizer (Refined Edition)
Intelligently focuses only on directories that benefit from organization.
Skips system, package, and already-organized directories.
"""

import os
import sys
import hashlib
import signal
import threading
import time
import json
import argparse
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Set

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
MAX_WORKERS = min(8, (os.cpu_count() or 1) + 2)  # Default value, can be overridden by CLI
CHUNK_SIZE = 65536

# Smart filtering and analysis rules
ANALYSIS_CONFIG = {
    'MAX_ANALYSIS_DEPTH': 2,
    'MAX_ANALYSIS_FILES': 200,
    'MIN_FILES_FOR_ORGANIZATION': 10,
    'MEDIA_RICH_RATIO': 0.3,
    'DOCUMENT_HEAVY_COUNT': 20,
    'MIXED_CONTENT_FILE_COUNT': 50,
    'MIXED_CONTENT_EXT_COUNT': 5,
}

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
    '.cache', '_temp', '_backup', '.tmp',  # Common suffixes
}

def is_system_folder(folder_name: str, folder_path: str) -> bool:
    """Determine if a folder is system-related and should be skipped"""
    folder_lower = folder_name.lower()
    
    # Check for matches or prefixes from the SYSTEM_FOLDERS list
    for system_folder in SYSTEM_FOLDERS:
        if folder_name.startswith(system_folder):
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
            if level > ANALYSIS_CONFIG['MAX_ANALYSIS_DEPTH']:
                dirs.clear()
                continue
            files.extend(filenames)
            if len(files) > ANALYSIS_CONFIG['MAX_ANALYSIS_FILES']:  # Sample limit
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
        # Prioritize media-rich folders even if they are small
        if media_ratio > ANALYSIS_CONFIG['MEDIA_RICH_RATIO']:
            return {
                'needs_organization': True, 
                'reason': 'media_rich', 
                'file_count': total_files,
                'media_files': media_files,
                'categories': {'media': media_files, 'documents': document_files, 'code': code_files}
            }

        if total_files < ANALYSIS_CONFIG['MIN_FILES_FOR_ORGANIZATION']:
            return {'needs_organization': False, 'reason': 'too_small', 'file_count': total_files}
        
        if document_files > ANALYSIS_CONFIG['DOCUMENT_HEAVY_COUNT']:
            return {
                'needs_organization': True, 
                'reason': 'document_heavy',
                'file_count': total_files,
                'categories': {'media': media_files, 'documents': document_files, 'code': code_files}
            }
        
        # Mixed content with reasonable size
        if (total_files > ANALYSIS_CONFIG['MIXED_CONTENT_FILE_COUNT'] and
            len(extension_counts) > ANALYSIS_CONFIG['MIXED_CONTENT_EXT_COUNT']):
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

def _analyze_one_directory(item_tuple):
    """Helper function for analyzing a single directory in a process pool."""
    item, root_path = item_tuple
    item_path = os.path.join(root_path, item)

    if not os.path.isdir(item_path):
        return None

    if is_system_folder(item, item_path):
        return {'type': 'skipped', 'name': item, 'reason': 'system_folder'}

    analysis = analyze_folder_content(item_path)
    if analysis['needs_organization']:
        return {
            'type': 'candidate',
            'path': item_path,
            'name': item,
            'analysis': analysis
        }
    else:
        return {'type': 'skipped', 'name': item, 'reason': analysis['reason']}

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
        
        # Prepare arguments for parallel processing
        item_tuples = [(item, root_path) for item in items]

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
                
                # Using a ThreadPoolExecutor for I/O-bound tasks
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    # Map each item to the analysis function
                    futures = [executor.submit(_analyze_one_directory, item_tuple) for item_tuple in item_tuples]
                    
                    for future in as_completed(futures):
                        if killer.kill_now:
                            break

                        result = future.result()
                        if result:
                            if result['type'] == 'candidate':
                                candidates.append(result)
                            else:
                                skipped.append(result)

                        progress.advance(task)
        else:
            # Simple progress without Rich
            for i, item_tuple in enumerate(item_tuples):
                if killer.kill_now:
                    break
                
                print(f"\rAnalyzing: {i+1}/{len(items)} - {item_tuple[0][:30]}", end="")
                result = _analyze_one_directory(item_tuple)
                if result:
                    if result['type'] == 'candidate':
                        candidates.append(result)
                    else:
                        skipped.append(result)
            print()

    except PermissionError:
        if console:
            console.print(f"[red]❌ Permission denied accessing {root_path}[/red]")
        else:
            print(f"❌ Permission denied accessing {root_path}")
        return [], []
    except Exception as e:
        if console:
            console.print(f"[red]❌ An unexpected error occurred during discovery: {e}[/red]")
        else:
            print(f"❌ An unexpected error occurred during discovery: {e}")
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
    """Get file metadata (excluding hash)"""
    if killer.kill_now:
        return None
        
    try:
        stat = os.stat(file_path)
        
        # Basic info
        size = stat.st_size
        modified_date = datetime.fromtimestamp(stat.st_mtime)
        
        # Simple category based on extension
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
            'hash': None,  # Hash will be calculated later only if needed
            'modified': modified_date,
            'category': category,
            'extension': ext
        }
    except Exception:
        return None

def _hash_files(file_list: List[Dict]) -> List[Dict]:
    """Calculate hashes for a list of files, intended for files of the same size."""
    for file_data in file_list:
        if killer.kill_now:
            break
        file_data['hash'] = calculate_hash(file_data['path'])
    return file_list

def process_directory_smart(directory_path: str, output_dir: Optional[str] = None):
    """Smart processing of a directory using optimized duplicate detection."""
    if killer.kill_now:
        return
        
    dir_name = os.path.basename(directory_path)
    
    if console:
        console.print(f"\n[green]🚀 Processing: {dir_name}[/green]")
    else:
        print(f"\n🚀 Processing: {dir_name}")
    
    # Step 1: Collect all file paths
    all_files = []
    for root, dirs, files in os.walk(directory_path):
        if killer.kill_now: break
        dirs[:] = [d for d in dirs if not d.startswith(('Organized_', 'Analysis_Report_'))]
        for file in files:
            all_files.append(os.path.join(root, file))
    
    if killer.kill_now: print("⏹️  File collection interrupted"); return
    if not all_files: print("📭 No files found"); return
    
    print(f"📁 Found {len(all_files):,} files. Analyzing metadata...")

    # Step 2: Get metadata for all files (concurrently)
    processed_files = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_file = {executor.submit(get_file_metadata, f): f for f in all_files}
        for future in as_completed(future_to_file):
            if killer.kill_now: break
            result = future.result()
            if result:
                processed_files.append(result)
    
    if killer.kill_now: print("⏹️  Metadata analysis interrupted"); return
    
    # Step 3: Group files by size
    size_groups = defaultdict(list)
    for file_data in processed_files:
        if file_data['size'] > 0:  # Ignore empty files for duplication
            size_groups[file_data['size']].append(file_data)

    potential_duplicates = [group for group in size_groups.values() if len(group) > 1]

    if not potential_duplicates:
        print("✅ No potential duplicates found based on file size.")
        generate_smart_report(directory_path, processed_files, {}, output_dir)
        return

    print(f"🔍 Found {len(potential_duplicates)} groups of files with identical sizes. Hashing to find duplicates...")

    # Step 4: Hash only the potential duplicates (concurrently)
    duplicates = {}
    
    if console and RICH_AVAILABLE:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), MofNCompleteColumn(), console=console) as progress:
            task = progress.add_task("Hashing files...", total=len(potential_duplicates))
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_group = {executor.submit(_hash_files, group): group for group in potential_duplicates}
                for future in as_completed(future_to_group):
                    if killer.kill_now: break
                    hashed_group = future.result()
                    
                    # Group by hash within the size-group
                    hash_groups = defaultdict(list)
                    for file_data in hashed_group:
                        if file_data['hash']:
                            hash_groups[file_data['hash']].append(file_data)

                    for h, files in hash_groups.items():
                        if len(files) > 1:
                            duplicates[h] = files
                    progress.advance(task)
    else:
        # Simple progress
        for i, group in enumerate(potential_duplicates):
            if killer.kill_now: break
            print(f"\rHashing group {i+1}/{len(potential_duplicates)}", end="")
            hashed_group = _hash_files(group)
            hash_groups = defaultdict(list)
            for file_data in hashed_group:
                if file_data['hash']:
                    hash_groups[file_data['hash']].append(file_data)
            for h, files in hash_groups.items():
                if len(files) > 1:
                    duplicates[h] = files
        print()

    if killer.kill_now:
        print("⏹️  Hashing interrupted - saving partial results...")

    # Update the main file list with hash info
    for group in potential_duplicates:
        for file_data in group:
            # This is not the most efficient way, but it ensures the main list has hashes
            # for the report. A better way might be a dict lookup.
            next((f for f in processed_files if f['path'] == file_data['path']), {})['hash'] = file_data['hash']

    # Generate report
    generate_smart_report(directory_path, processed_files, duplicates, output_dir)

def generate_smart_report(
    directory_path: str,
    files: List[Dict],
    duplicates: Dict,
    output_dir: Optional[str] = None
):
    """Generate focused analysis report"""
    report_base_dir = output_dir if output_dir else directory_path

    report_dir_name = f"Smart_Analysis_{os.path.basename(directory_path)}_{datetime.now():%Y%m%d_%H%M%S}"
    report_dir = os.path.join(report_base_dir, report_dir_name)
    
    try:
        os.makedirs(report_dir, exist_ok=True)
    except Exception as e:
        if console:
            console.print(f"[red]❌ Error creating report directory: {e}[/red]")
        else:
            print(f"❌ Error creating report directory: {e}")
        # Fallback to current directory
        report_dir = report_dir_name
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
    parser = argparse.ArgumentParser(
        description="Smart Drive Organizer (Refined Edition)",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""\
Example usage:
  python smart_organizer.py /path/to/your/drive
  python smart_organizer.py C:\\Users\\YourUser\\Downloads --workers 12
"""
    )

    parser.add_argument("directory", help="The directory to scan and organize.")
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=min(8, (os.cpu_count() or 1) + 2),
        help=f"Number of worker threads for file processing. Default: {min(8, (os.cpu_count() or 1) + 2)}"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Directory to save analysis reports. Defaults to a sub-folder in the scanned directory."
    )

    args = parser.parse_args()

    # Update MAX_WORKERS from args
    global MAX_WORKERS
    MAX_WORKERS = args.workers

    print("="*70)
    print("🧠 SMART DRIVE ORGANIZER (REFINED EDITION)")
    print("="*70)
    print("   • Skips system/package directories")
    print("   • Focuses on content that needs organization") 
    print("   • Graceful shutdown with Ctrl+C")
    print("="*70)
    
    try:
        target_path = args.directory
        if not os.path.isdir(target_path):
            print(f"\n❌ Error: Provided path is not a valid directory: {target_path}")
            return
            
        print(f"\n✅ Target directory: {target_path}")
        
        # Smart discovery
        candidates, skipped = discover_smart_directories(target_path)
        
        if killer.kill_now:
            print("\n🛑 Shutdown requested during discovery. Exiting.")
            return
        
        # Selection
        selected_dirs = display_smart_selection(candidates, skipped)
        
        if not selected_dirs or killer.kill_now:
            print("\n👋 Exiting gracefully.")
            return
        
        print(f"\n🚀 Processing {len(selected_dirs)} selected directories...")
        print("   💡 Press Ctrl+C anytime for graceful shutdown")
        
        # Process each directory
        for i, directory in enumerate(selected_dirs, 1):
            if killer.kill_now:
                break
                
            print(f"\n📁 [{i}/{len(selected_dirs)}] Processing: {os.path.basename(directory)}")
            process_directory_smart(directory, output_dir=args.output_dir)
        
        if killer.kill_now:
            print("\n🛑 Processing interrupted but reports for completed directories are saved!")
        else:
            print("\n🎉 Smart analysis complete!")
            
    except KeyboardInterrupt:
        print("\n🛑 Graceful shutdown initiated...")
    except Exception as e:
        if console:
            console.print_exception()
        else:
            print(f"\n💥 Unexpected error: {e}")
        print("   Saving any progress and exiting...")
    finally:
        print("👋 Thanks for using Smart Drive Organizer!")

if __name__ == "__main__":
    main()