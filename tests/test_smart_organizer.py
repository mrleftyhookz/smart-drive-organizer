import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the root directory to the Python path to allow importing smart_organizer
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from smart_organizer import is_system_folder, analyze_folder_content, _analyze_one_directory

class TestSmartOrganizerLogic(unittest.TestCase):

    def test_is_system_folder(self):
        # Test cases that should be identified as system folders
        self.assertTrue(is_system_folder('node_modules', '/fake/path/node_modules'))
        self.assertTrue(is_system_folder('.git', '/fake/path/.git'))
        self.assertTrue(is_system_folder('__pycache__', '/fake/path/__pycache__'))
        self.assertTrue(is_system_folder('$RECYCLE.BIN', '/fake/path/$RECYCLE.BIN'))
        self.assertTrue(is_system_folder('System Volume Information', '/fake/path/System Volume Information'))
        self.assertTrue(is_system_folder('venv', '/fake/path/venv'))
        self.assertTrue(is_system_folder('build', '/fake/path/build'))
        self.assertTrue(is_system_folder('Organized_Photos', '/fake/path/Organized_Photos'))
        self.assertTrue(is_system_folder('my-project.cache', '/fake/path/my-project.cache')) # Ends with pattern
        self.assertTrue(is_system_folder('.temp', '/fake/path/.temp')) # Starts with pattern

        # Test cases that should NOT be identified as system folders
        self.assertFalse(is_system_folder('My Photos', '/fake/path/My Photos'))
        self.assertFalse(is_system_folder('Important Documents', '/fake/path/Important Documents'))
        self.assertFalse(is_system_folder('project_files', '/fake/path/project_files'))
        self.assertFalse(is_system_folder('my_build_scripts', '/fake/path/my_build_scripts'))

    @patch('os.walk')
    def test_analyze_folder_content_media_rich(self, mock_walk):
        # Simulate a folder with many media files
        mock_walk.return_value = [
            ('/fake/path', [], ['1.jpg', '2.png', '3.gif', '4.mp4', '5.txt', '6.pdf'])
        ]

        analysis = analyze_folder_content('/fake/path')
        self.assertTrue(analysis['needs_organization'])
        self.assertEqual(analysis['reason'], 'media_rich')

    @patch('os.walk')
    def test_analyze_folder_content_document_heavy(self, mock_walk):
        # Simulate a folder with many document files
        files = [f'doc_{i}.pdf' for i in range(25)]
        mock_walk.return_value = [
            ('/fake/path', [], files)
        ]

        analysis = analyze_folder_content('/fake/path')
        self.assertTrue(analysis['needs_organization'])
        self.assertEqual(analysis['reason'], 'document_heavy')

    @patch('os.walk')
    def test_analyze_folder_content_too_small(self, mock_walk):
        # Simulate a folder with too few non-media files
        mock_walk.return_value = [
            ('/fake/path', [], ['file1.log', 'file2.txt'])
        ]

        analysis = analyze_folder_content('/fake/path')
        self.assertFalse(analysis['needs_organization'])
        self.assertEqual(analysis['reason'], 'too_small')

    @patch('os.walk')
    def test_analyze_folder_content_empty(self, mock_walk):
        # Simulate an empty folder
        mock_walk.return_value = [
            ('/fake/path', [], [])
        ]

        analysis = analyze_folder_content('/fake/path')
        self.assertFalse(analysis['needs_organization'])
        self.assertEqual(analysis['reason'], 'empty')

    @patch('smart_organizer.is_system_folder', return_value=False)
    @patch('smart_organizer.analyze_folder_content')
    def test_analyze_one_directory_candidate(self, mock_analyze, mock_is_system):
        # Test when a directory is a candidate for organization
        mock_analyze.return_value = {'needs_organization': True, 'reason': 'media_rich'}

        with patch('os.path.isdir', return_value=True):
            result = _analyze_one_directory(('My Photos', '/fake/root'))

        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'candidate')
        self.assertEqual(result['name'], 'My Photos')
        self.assertEqual(result['analysis']['reason'], 'media_rich')

    @patch('smart_organizer.is_system_folder', return_value=True)
    def test_analyze_one_directory_is_system(self, mock_is_system):
        # Test when a directory is a system folder
        with patch('os.path.isdir', return_value=True):
            result = _analyze_one_directory(('.git', '/fake/root'))

        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'skipped')
        self.assertEqual(result['reason'], 'system_folder')

    @patch('os.path.isdir', return_value=False)
    def test_analyze_one_directory_not_a_dir(self, mock_isdir):
        # Test when the item is not a directory
        result = _analyze_one_directory(('myfile.txt', '/fake/root'))
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
