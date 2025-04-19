#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Export utilities for saving and analyzing results from batch processing.
Supports various export formats including JSON, CSV, and detailed reports.
"""

import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

# Configure logger
logger = logging.getLogger(__name__)


class ResultExporter:
    """
    Export and analyze batch processing results.
    """
    
    def __init__(self, export_dir: Optional[Union[str, Path]] = None):
        """
        Initialize the result exporter.
        
        Args:
            export_dir: Directory for saving export files (default: current directory)
        """
        self.export_dir = Path(export_dir) if export_dir else Path.cwd()
        
        # Create export directory if it doesn't exist
        if not self.export_dir.exists():
            logger.debug("Creating export directory: %s", self.export_dir)
            self.export_dir.mkdir(parents=True, exist_ok=True)
            
    def export_json(
        self, 
        data: Dict[str, Any], 
        filename: Optional[str] = None, 
        indent: int = 2
    ) -> Path:
        """
        Export data to a JSON file.
        
        Args:
            data: Dictionary data to export
            filename: Custom filename (default: auto-generated timestamp)
            indent: JSON indentation level
            
        Returns:
            Path to the saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results_{timestamp}.json"
            
        file_path = self.export_dir / filename
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            
            logger.info("Exported results to %s", file_path)
            return file_path
            
        except Exception as e:
            logger.error("Failed to export JSON: %s", str(e))
            raise
            
    def export_summary_csv(
        self, 
        results: List[Dict[str, Any]], 
        filename: Optional[str] = None
    ) -> Path:
        """
        Export a summary of multiple result objects to CSV.
        
        Args:
            results: List of result dictionaries
            filename: Custom filename (default: auto-generated timestamp)
            
        Returns:
            Path to the saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"summary_{timestamp}.csv"
            
        file_path = self.export_dir / filename
        
        try:
            # Extract summary data from results
            summary_data = []
            for i, result in enumerate(results):
                summary = result.get("summary", {})
                performance = result.get("performance", {})
                
                entry = {
                    "batch_id": i + 1,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "submitted": summary.get("submitted", 0),
                    "processed": summary.get("processed", 0),
                    "dropped": summary.get("dropped", 0),
                    "success_rate": summary.get("processed", 0) / summary.get("submitted", 1) * 100 
                        if summary.get("submitted", 0) > 0 else 0,
                }
                
                # Add performance metrics if available
                if performance:
                    time_data = performance.get("time", {})
                    throughput = performance.get("throughput", {})
                    
                    entry.update({
                        "total_time_seconds": time_data.get("total_seconds", 0),
                        "avg_call_time_seconds": time_data.get("avg_call_time", 0),
                        "entities_processed": throughput.get("entities_processed", 0),
                        "entities_per_second": throughput.get("entities_per_second", 0),
                    })
                    
                summary_data.append(entry)
            
            # Write to CSV
            if summary_data:
                fieldnames = summary_data[0].keys()
                
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(summary_data)
                
                logger.info("Exported summary to %s", file_path)
                return file_path
            else:
                logger.warning("No summary data to export")
                return file_path
                
        except Exception as e:
            logger.error("Failed to export CSV summary: %s", str(e))
            raise
            
    def export_errors_csv(
        self, 
        errors: List[Dict[str, Any]], 
        filename: Optional[str] = None
    ) -> Path:
        """
        Export error details to CSV.
        
        Args:
            errors: List of error dictionaries
            filename: Custom filename (default: auto-generated timestamp)
            
        Returns:
            Path to the saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"errors_{timestamp}.csv"
            
        file_path = self.export_dir / filename
        
        try:
            # Standardize error format
            error_data = []
            for i, error in enumerate(errors):
                entry = {
                    "error_id": i + 1,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "error_type": error.get("type", "Unknown"),
                    "message": error.get("message", "No message"),
                    "status_code": error.get("status_code", ""),
                    "file": error.get("file", ""),
                    "entity": error.get("entity", ""),
                }
                
                # Add any additional fields
                for key, value in error.items():
                    if key not in entry and not isinstance(value, (dict, list)):
                        entry[key] = value
                
                error_data.append(entry)
            
            # Write to CSV
            if error_data:
                fieldnames = error_data[0].keys()
                
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(error_data)
                
                logger.info("Exported error details to %s", file_path)
                return file_path
            else:
                logger.warning("No error data to export")
                return file_path
                
        except Exception as e:
            logger.error("Failed to export error details: %s", str(e))
            raise
            
    def generate_report(
        self,
        results: List[Dict[str, Any]],
        errors: List[Dict[str, Any]],
        filename: Optional[str] = None,
        include_performance: bool = True
    ) -> Path:
        """
        Generate a comprehensive HTML report.
        
        Args:
            results: List of result dictionaries
            errors: List of error dictionaries
            filename: Custom filename (default: auto-generated timestamp)
            include_performance: Whether to include performance metrics
            
        Returns:
            Path to the saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.html"
            
        file_path = self.export_dir / filename
        
        try:
            # Aggregate results
            total_submitted = sum(r.get("summary", {}).get("submitted", 0) for r in results)
            total_processed = sum(r.get("summary", {}).get("processed", 0) for r in results)
            total_dropped = sum(r.get("summary", {}).get("dropped", 0) for r in results)
            total_errors = len(errors)
            
            # Generate HTML
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Batch Processing Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ padding: 8px; text-align: left; border: 1px solid #ddd; }}
        th {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #f8f8f8; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .error {{ color: #b71c1c; }}
        .success {{ color: #2e7d32; }}
    </style>
</head>
<body>
    <h1>Batch Processing Report</h1>
    <p>Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    
    <div class="summary">
        <h2>Summary</h2>
        <p>Total submitted: <strong>{total_submitted}</strong></p>
        <p>Total processed: <strong class="success">{total_processed}</strong></p>
        <p>Total dropped: <strong class="error">{total_dropped}</strong></p>
        <p>Total errors: <strong class="error">{total_errors}</strong></p>
        <p>Success rate: <strong>{(total_processed / total_submitted * 100) if total_submitted else 0:.2f}%</strong></p>
    </div>
            """
            
            # Add results table
            if results:
                html_content += """
    <h2>Processing Results</h2>
    <table>
        <tr>
            <th>Batch</th>
            <th>Submitted</th>
            <th>Processed</th>
            <th>Dropped</th>
            <th>Success Rate</th>
                """
                
                if include_performance:
                    html_content += """
            <th>Avg Time (s)</th>
            <th>Entities/s</th>
                    """
                    
                html_content += """
        </tr>
                """
                
                for i, result in enumerate(results):
                    summary = result.get("summary", {})
                    submitted = summary.get("submitted", 0)
                    processed = summary.get("processed", 0)
                    dropped = summary.get("dropped", 0)
                    success_rate = (processed / submitted * 100) if submitted else 0
                    
                    html_content += f"""
        <tr>
            <td>{i + 1}</td>
            <td>{submitted}</td>
            <td>{processed}</td>
            <td>{dropped}</td>
            <td>{success_rate:.2f}%</td>
                    """
                    
                    if include_performance and "performance" in result:
                        performance = result["performance"]
                        time_data = performance.get("time", {})
                        throughput = performance.get("throughput", {})
                        
                        avg_time = time_data.get("avg_call_time", 0)
                        entities_per_sec = throughput.get("entities_per_second", 0)
                        
                        html_content += f"""
            <td>{avg_time:.4f}</td>
            <td>{entities_per_sec:.2f}</td>
                        """
                        
                    html_content += """
        </tr>
                    """
                    
                html_content += """
    </table>
                """
            
            # Add errors table
            if errors:
                html_content += """
    <h2>Errors</h2>
    <table>
        <tr>
            <th>ID</th>
            <th>Type</th>
            <th>Message</th>
            <th>Status Code</th>
            <th>File/Entity</th>
        </tr>
                """
                
                for i, error in enumerate(errors):
                    html_content += f"""
        <tr>
            <td>{i + 1}</td>
            <td>{error.get("type", "Unknown")}</td>
            <td>{error.get("message", "No message")}</td>
            <td>{error.get("status_code", "")}</td>
            <td>{error.get("file", error.get("entity", ""))}</td>
        </tr>
                    """
                    
                html_content += """
    </table>
                """
            
            # Add performance section if applicable
            if include_performance:
                perf_data = []
                for result in results:
                    if "performance" in result:
                        perf_data.append(result["performance"])
                
                if perf_data:
                    html_content += """
    <h2>Performance Metrics</h2>
    <table>
        <tr>
            <th>Batch</th>
            <th>Total Time (s)</th>
            <th>Avg Call Time (s)</th>
            <th>Min Time (s)</th>
            <th>Max Time (s)</th>
            <th>Entities Processed</th>
            <th>Entities/s</th>
            <th>API Calls</th>
            <th>Success Rate</th>
        </tr>
                    """
                    
                    for i, perf in enumerate(perf_data):
                        time_data = perf.get("time", {})
                        api_calls = perf.get("api_calls", {})
                        throughput = perf.get("throughput", {})
                        
                        total_time = time_data.get("total_seconds", 0)
                        avg_time = time_data.get("avg_call_time", 0)
                        min_time = time_data.get("min_call_time", 0)
                        max_time = time_data.get("max_call_time", 0)
                        
                        entities = throughput.get("entities_processed", 0)
                        entities_per_sec = throughput.get("entities_per_second", 0)
                        
                        total_calls = api_calls.get("total", 0)
                        success_calls = api_calls.get("success", 0)
                        success_rate = (success_calls / total_calls * 100) if total_calls else 0
                        
                        html_content += f"""
        <tr>
            <td>{i + 1}</td>
            <td>{total_time:.2f}</td>
            <td>{avg_time:.4f}</td>
            <td>{min_time:.4f}</td>
            <td>{max_time:.4f}</td>
            <td>{entities}</td>
            <td>{entities_per_sec:.2f}</td>
            <td>{total_calls}</td>
            <td>{success_rate:.2f}%</td>
        </tr>
                        """
                        
                    html_content += """
    </table>
                    """
            
            # Close HTML
            html_content += """
</body>
</html>
            """
            
            # Write to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            logger.info("Generated HTML report at %s", file_path)
            return file_path
            
        except Exception as e:
            logger.error("Failed to generate report: %s", str(e))
            raise
    
    def export_all(
        self,
        results: List[Dict[str, Any]],
        errors: List[Dict[str, Any]],
        base_filename: Optional[str] = None,
        include_report: bool = True
    ) -> Dict[str, Path]:
        """
        Export all data formats at once.
        
        Args:
            results: List of result dictionaries
            errors: List of error dictionaries
            base_filename: Base filename for all exports (timestamp will be added)
            include_report: Whether to generate HTML report
            
        Returns:
            Dictionary mapping export type to file path
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = base_filename or f"export_{timestamp}"
        
        export_files = {}
        
        try:
            # Export JSON results
            json_path = self.export_json(
                {"results": results, "errors": errors},
                filename=f"{base_name}.json"
            )
            export_files["json"] = json_path
            
            # Export CSV summary
            csv_path = self.export_summary_csv(
                results,
                filename=f"{base_name}_summary.csv"
            )
            export_files["csv_summary"] = csv_path
            
            # Export errors if any
            if errors:
                errors_path = self.export_errors_csv(
                    errors,
                    filename=f"{base_name}_errors.csv"
                )
                export_files["csv_errors"] = errors_path
            
            # Generate HTML report
            if include_report:
                report_path = self.generate_report(
                    results,
                    errors,
                    filename=f"{base_name}_report.html"
                )
                export_files["html_report"] = report_path
            
            logger.info("Exported all formats to %s", self.export_dir)
            return export_files
            
        except Exception as e:
            logger.error("Failed during combined export: %s", str(e))
            raise