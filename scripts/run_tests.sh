#!/bin/bash
# Run tests with coverage reporting

# Exit on error
set -e

# Install test dependencies if needed
if [ "$1" == "--install" ]; then
    echo "Installing test dependencies..."
    pip install -e ".[dev]"
fi

# Run tests with coverage
echo "Running tests with coverage..."
python -m pytest tests/ --cov=sendDetections --cov-report=term --cov-report=html:coverage_report

# Open coverage report if requested
if [ "$1" == "--open" ] || [ "$2" == "--open" ]; then
    if [ -n "$(command -v open)" ]; then
        echo "Opening coverage report..."
        open coverage_report/index.html
    else
        echo "Coverage report generated at coverage_report/index.html"
    fi
fi

echo "Test run complete!"