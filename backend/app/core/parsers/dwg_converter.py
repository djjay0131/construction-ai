"""
DWG to DXF Converter Module
Converts proprietary DWG files to open DXF format using LibreDWG
"""

import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DWGConverter:
    """
    Converts DWG files to DXF format using LibreDWG's dwg2dxf utility.

    LibreDWG is an open-source library for reading and writing DWG files.
    The dwg2dxf command-line tool is installed in the Docker container.
    """

    def __init__(self):
        self.temp_dir = None

    def is_dwg_file(self, file_path: Path) -> bool:
        """Check if file is a DWG file by extension and magic bytes."""
        if file_path.suffix.lower() != '.dwg':
            return False

        # Check DWG magic bytes (starts with "AC" for AutoCAD)
        try:
            with open(file_path, 'rb') as f:
                header = f.read(6)
                return header.startswith(b'AC')
        except Exception as e:
            logger.error(f"Error checking DWG magic bytes: {e}")
            return False

    def convert_to_dxf(self, dwg_path: Path, output_path: Optional[Path] = None) -> Tuple[bool, Optional[Path], str]:
        """
        Convert DWG file to DXF format.

        Args:
            dwg_path: Path to the DWG file
            output_path: Optional path for output DXF file. If None, creates temp file.

        Returns:
            Tuple of (success: bool, dxf_path: Optional[Path], message: str)
        """
        if not dwg_path.exists():
            return False, None, f"DWG file not found: {dwg_path}"

        if not self.is_dwg_file(dwg_path):
            return False, None, f"File is not a valid DWG file: {dwg_path}"

        # Create output path if not provided
        if output_path is None:
            self.temp_dir = tempfile.mkdtemp()
            output_path = Path(self.temp_dir) / f"{dwg_path.stem}.dxf"

        try:
            # Use dwg2dxf command from LibreDWG
            # -y: Overwrite existing files without prompting
            # -o: Output file path
            cmd = ['dwg2dxf', '-y', '-o', str(output_path), str(dwg_path)]

            logger.info(f"Converting DWG to DXF: {dwg_path.name}")
            logger.debug(f"Command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )

            if result.returncode == 0 and output_path.exists():
                logger.info(f"Successfully converted {dwg_path.name} to DXF")
                return True, output_path, "Conversion successful"
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                logger.error(f"DWG conversion failed: {error_msg}")
                return False, None, f"Conversion failed: {error_msg}"

        except subprocess.TimeoutExpired:
            error_msg = "Conversion timed out after 60 seconds"
            logger.error(error_msg)
            return False, None, error_msg

        except FileNotFoundError:
            error_msg = "dwg2dxf command not found. LibreDWG tools not installed."
            logger.error(error_msg)
            return False, None, error_msg

        except Exception as e:
            error_msg = f"Unexpected error during conversion: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def cleanup(self):
        """Clean up temporary files created during conversion."""
        if self.temp_dir and Path(self.temp_dir).exists():
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup temp files."""
        self.cleanup()
