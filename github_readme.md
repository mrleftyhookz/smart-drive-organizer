# Smart Drive Organizer 🧠

An intelligent file organization and analysis tool that focuses on directories that actually benefit from organization, while intelligently skipping system folders and package installations.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

## ✨ Features

- **🎯 Smart Directory Detection**: Automatically identifies directories that need organization while skipping system folders, package installations, and already-organized content
- **⚡ High-Performance Processing**: Multi-threaded file analysis with configurable worker pools
- **🔍 Duplicate Detection**: SHA-256 based duplicate identification with size-aware hashing
- **📊 Comprehensive Analytics**: Detailed reports on file categories, sizes, and potential space savings
- **🛡️ Graceful Shutdown**: Interrupt-safe processing with progress preservation
- **🎨 Rich UI**: Beautiful progress bars and tables (when Rich library is available)
- **📱 Cross-Platform**: Works on Windows, Linux, and macOS

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/mrleftyhookz/smart-drive-organizer.git
cd smart-drive-organizer
pip install -r requirements.txt
```

### Basic Usage

```bash
python smart_organizer.py
```

The tool will:
1. 🔍 Scan your E drive (or specified path) for directories
2. 🧠 Intelligently filter out system/package folders  
3. 📋 Present candidates that would benefit from organization
4. 🚀 Process your selected directories with detailed analysis

## 📋 Requirements

### Core Requirements
- Python 3.8+
- Standard library modules (os, threading, concurrent.futures, etc.)

### Optional Enhancements
```bash
pip install rich pillow
```
- **Rich**: Beautiful terminal UI with progress bars and tables
- **Pillow**: Enhanced image metadata extraction

## 🧠 How It Works

### Smart Filtering
The tool uses intelligent heuristics to identify directories worth organizing:

- **Skips System Folders**: `node_modules`, `__pycache__`, `.git`, `Program Files`, etc.
- **Skips Package Installations**: `conda`, `pip`, `venv`, build directories
- **Focuses on Content**: Media-rich folders, document collections, mixed content

### Analysis Criteria
A directory is flagged for organization if it has:
- 30%+ media files (photos, videos)
- 20+ document files
- 50+ files with 5+ different file types (mixed content)

### Performance Optimizations
- **Selective Hashing**: Only hashes files 100B-100MB (likely duplicates)
- **Multi-threading**: Configurable worker pools for I/O operations
- **Chunked Processing**: Allows graceful interruption
- **Memory Efficient**: Processes files in batches

## 📊 Output

The tool generates comprehensive reports including:

- **File Statistics**: Total files, size breakdown by category
- **Duplicate Analysis**: Groups of identical files with space savings potential
- **Top Extensions**: Most common file types in your directories
- **Largest Files**: Space usage leaders
- **JSON Reports**: Machine-readable analysis data

## 🔧 Configuration

### Environment Variables
```bash
export SMART_ORGANIZER_WORKERS=16  # Custom thread count
export SMART_ORGANIZER_CHUNK_SIZE=131072  # Custom read chunk size
```

### Customizing Paths
Modify the `E_DRIVE_PATHS` list in the script to target different drives:
```python
E_DRIVE_PATHS = ['/mnt/data', '/home/user/Documents', 'D:', 'F:\\']
```

## 🛡️ Safety Features

- **Read-Only Analysis**: Never modifies your files
- **Graceful Shutdown**: Ctrl+C saves progress and exits cleanly  
- **Permission Handling**: Safely skips inaccessible directories
- **Error Recovery**: Continues processing despite individual file errors

## 💡 Use Cases

- **Storage Cleanup**: Identify duplicate files and space wasters
- **Migration Planning**: Analyze directory structure before moves
- **Backup Strategy**: Understand your data patterns
- **Performance Optimization**: Find directories slowing down your system
- **Compliance Auditing**: Generate detailed file inventories

## 🔮 Future Enhancements

- [ ] **Auto-Organization**: Optional file moving/organizing actions
- [ ] **Cloud Integration**: Support for cloud storage analysis
- [ ] **Web Dashboard**: Browser-based reporting interface
- [ ] **Scheduled Scans**: Automated monitoring and reporting
- [ ] **Machine Learning**: Smart categorization based on content analysis

## 🤝 Contributing

Contributions are welcome! Please feel free to:

1. 🐛 Report bugs or suggest features via Issues
2. 🔀 Submit Pull Requests with improvements
3. 📚 Improve documentation
4. ⭐ Star the repo if you find it useful!

### Development Setup
```bash
git clone https://github.com/mrleftyhookz/smart-drive-organizer.git
cd smart-drive-organizer
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
```

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 About the Developer

**Corey M. Francis** - Former accounting professional transitioning into technology roles that blend financial expertise with technical automation skills. This project demonstrates proficiency in Python, system programming, and building user-focused automation tools that deliver real business value.

**Background**: CPA with deep understanding of business processes, efficiency optimization, and data analysis. Currently developing technical skills to create solutions at the intersection of finance, automation, and AI.

**Technical Skills Demonstrated**:
- Python development with modern patterns (threading, type hints, dataclasses)
- System programming and cross-platform compatibility
- Performance optimization and memory management
- User experience design and error handling
- Project organization and open source development

**Professional Vision**: Building bridges between business domain expertise and technical implementation, especially in the evolving landscape where AI augments traditional business functions.

## 🎯 Project Impact

This tool showcases the practical application of programming skills to solve real business problems:

- **Cost Savings**: Replaces expensive commercial file organization software
- **Efficiency Gains**: Automates time-consuming manual file management tasks
- **Data Intelligence**: Provides actionable insights about storage usage and optimization
- **Risk Mitigation**: Safe, read-only analysis protects valuable data assets

## 🚀 Career Transition Context

This project represents the kind of **practical automation** that modern businesses need as AI transforms traditional workflows. It demonstrates:

- **Business Acumen**: Understanding what problems are worth solving
- **Technical Execution**: Implementing robust, professional-quality solutions  
- **User Focus**: Creating tools that non-technical users can actually use
- **Professional Standards**: Code quality suitable for enterprise environments

Perfect for roles in FinTech, Business Analysis, Technical Accounting, or any position where business domain knowledge combines with technical automation capabilities.

## 🙏 Acknowledgments

- Built with Python's excellent standard library
- Enhanced by the [Rich](https://github.com/willmcgugan/rich) library for beautiful terminal output
- Inspired by the need for intelligent, not just automated, file organization
- Developed as part of a career transition from accounting to technology

## 📞 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/mrleftyhookz/smart-drive-organizer/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/mrleftyhookz/smart-drive-organizer/discussions)
- 📧 **Contact**: [mrcoreyfrancis@gmail.com](mailto:mrcoreyfrancis@gmail.com)
- 💼 **LinkedIn**: Connect for opportunities in tech-enabled business roles

---

**Made with ❤️ by someone who values intelligent automation over brute force solutions.**  
*Building bridges between business expertise and technical innovation.*