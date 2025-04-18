"""
Legacy/utility script for converting CSV to Payload JSON.
Main logic now lives in sendDetections/csv_converter.py (CSVConverter class).
This script simply calls the package logic for experimentation or ad-hoc use.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))  # For direct script use
from sendDetections.csv_converter import CSVConverter

def main():
    converter = CSVConverter()
    converter.run()

if __name__ == '__main__':
    main()
