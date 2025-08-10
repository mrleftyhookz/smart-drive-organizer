In your project folder (the same one containing your Python script), create a new file.

Name the file exactly README.md. The .md extension tells GitHub to interpret the text as Markdown.

Paste the copied text into this new file and save it.

When you push your project to GitHub, this file will be automatically displayed as the front page of your repository.

Per-Root File Organization & Archival Script
Version 2.1

A powerful and safe Python script for organizing massive collections of files on large drives. It operates on a "per-root" basis, intelligently sorting files by date, managing duplicates, and creating a clean, new, and verified copy of your data.

Overview
This script provides a robust solution for taming chaotic file collections (photos, videos, documents). The core philosophy is non-destructive. It meticulously creates a new, cleanly organized copy of your data, allowing you to verify the results before making any permanent changes to the original files.

It intelligently sorts files based on their true creation date (e.g., EXIF data for photos) and manages duplicates and folder sizes to create a clean, navigable archive. Each top-level folder you select is treated as a self-contained project, ensuring that files from different projects are never mixed.

🚀 Key Features
Interactive Root Selection: Scans specified drives and allows you to interactively choose which folders (roots) to process.

Intelligent Sorting: Performs a fast initial size estimation to process smaller jobs first, providing quicker feedback.

Scoped Duplicate Detection: Uses SHA-256 hashing to find and flag duplicate files within each root's context.

Chronological Organization: Sorts files based on their best-available creation date, prioritizing embedded metadata (like EXIF DateTimeOriginal) over less reliable filesystem dates.

Automatic Pagination: Prevents destination folders from becoming too large. It creates new paginated folders (e.g., 2010-05_2) when a file count (~1000) or size limit (~25 GB) is reached.

Safe, Non-Destructive Copy: Copies all files to a new Organized_... directory, leaving your original files completely untouched for peace of mind.

Dry Run & Approval: Generates a detailed "execution plan" for your review and approval before any file operations begin.

Empty Folder Pruning: After a successful organization, it offers to clean up the original directory by removing any folders that have become empty.

🛠️ How to Use
1. Prerequisites
Python 3.6+

Pillow Library: This is required for reading image metadata. Install it using pip:

Bash

pip install Pillow
2. Configuration
Save the code as a Python file (e.g., organize_files.py). Open the script and modify the configuration variables at the top to match your setup.

Python

# ------------------- CONFIGURATION -------------------

# Drives to scan for root folders.
# Windows: ['E:\\', 'F:\\']
# Linux/macOS: ['/media/ssd1', '/mnt/archive']
DRIVES_TO_SCAN = ['E:\\']

# The maximum number of files in a single destination folder.
FILE_COUNT_LIMIT = 1000

# The maximum size (in Gigabytes) of a single destination folder.
FOLDER_SIZE_LIMIT_GB = 25.0

# -----------------------------------------------------
3. Execution
Open a terminal or command prompt, navigate to the directory where you saved the script, and run it:

Bash

python organize_files.py
The script will then guide you through the process:

Select the root folders you wish to process.

Review and confirm the execution plan for each root.

Approve the final, optional pruning of empty source directories.

⚠️ Disclaimer
This software is provided "as is". While designed to be safe and non-destructive, the author and associated entities are not liable for any potential data loss.

It is strongly recommended that you have a complete and verified backup of your data before running this script.

License
MIT License

Copyright (c) 2025 Corey M. Francis | coreyfrancis1981@outlook.com | courtesy of Penguin Protect LLC

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.