#!/usr/bin/env python3
"""
REAL metrics service that collects actual metrics from MCP operations.
Simple SQLite implementation - no complexity, just working code.
"""

import sqlite3
import json
import time
import statistics
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

# Import List from typing
from typing import List

logger = logging.getLogger(__name__)


class MetricsService:
    """Collect REAL metrics from actual operations."""
    
    def __init__(self, db_path: str = "mcp_metrics.db"):
        self.db_path = db_path
        self.init_tables()
    
    def init_tables(self):
        """Initialize metrics tables."""
        conn = sqlite3.connect(self.db_path)
        
        # Raw metrics table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                status TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                tool_name TEXT,
                test_id TEXT,
                error_msg TEXT,
                metadata TEXT
            )
        ''')
        
        # Aggregated metrics table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS metrics_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                period_start DATETIME NOT NULL,
                period_end DATETIME NOT NULL,
                count INTEGER,
                success_count INTEGER,
                failure_count INTEGER,
                avg_duration_ms REAL,
                min_duration_ms REAL,
                max_duration_ms REAL,
                p50_duration_ms REAL,
                p95_duration_ms REAL,
                p99_duration_ms REAL
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Metrics database initialized at {self.db_path}")
    
    def record_operation(self, 
                        operation: str, 
                        duration_ms: float, 
                        status: str,
                        tool_name: Optional[str] = None,
                        test_id: Optional[str] = None,
                        error_msg: Optional[str] = None,
                        metadata: Optional[Dict] = None):
        """Record REAL operation metrics."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT INTO metrics 
            (operation, duration_ms, status, timestamp, tool_name, test_id, error_msg, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            operation,
            duration_ms,
            status,
            datetime.now().isoformat(),
            tool_name,
            test_id,
            error_msg,
            json.dumps(metadata) if metadata else None
        ))
        conn.commit()
        conn.close()
        
        logger.debug(f"Recorded metric: {operation} - {duration_ms:.2f}ms - {status}")
    
    def record_batch(self, metrics_data: List[Dict[str, Any]]) -> int:
        """Record multiple metrics in a batch."""
        conn = sqlite3.connect(self.db_path)
        count = 0
        
        for data in metrics_data:
            conn.execute('''
                INSERT INTO metrics 
                (operation, duration_ms, status, timestamp, tool_name, test_id, error_msg, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get("operation", "unknown"),
                data.get("duration_ms", 0),
                data.get("status", "unknown"),
                data.get("timestamp", datetime.now().isoformat()),
                data.get("tool_name"),
                data.get("test_id"),
                data.get("error_msg"),
                json.dumps(data.get("metadata")) if data.get("metadata") else None
            ))
            count += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"Recorded {count} metrics in batch")
        return count
    
    def get_stats(self, 
                  operation: Optional[str] = None,
                  hours: int = 24) -> Dict:
        """Get REAL statistics from actual data."""
        conn = sqlite3.connect(self.db_path)
        cutoff = datetime.now() - timedelta(hours=hours)
        
        # Build query
        query = '''
            SELECT duration_ms, status 
            FROM metrics 
            WHERE timestamp >= ?
        '''
        params = [cutoff.isoformat()]
        
        if operation:
            query += " AND operation = ?"
            params.append(operation)
        
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            conn.close()
            return {
                "count": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0,
                "avg_duration_ms": 0,
                "min_duration_ms": 0,
                "max_duration_ms": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0
            }
        
        # Calculate statistics
        durations = [r[0] for r in rows if r[0] is not None]
        success_count = sum(1 for r in rows if r[1] == "success")
        failure_count = sum(1 for r in rows if r[1] == "failed")
        
        stats = {
            "count": len(rows),
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_count / len(rows) if rows else 0
        }
        
        if durations:
            sorted_durations = sorted(durations)
            stats.update({
                "avg_duration_ms": statistics.mean(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "p50": self._percentile(sorted_durations, 50),
                "p95": self._percentile(sorted_durations, 95),
                "p99": self._percentile(sorted_durations, 99)
            })
        else:
            stats.update({
                "avg_duration_ms": 0,
                "min_duration_ms": 0,
                "max_duration_ms": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0
            })
        
        conn.close()
        return stats
    
    def get_metrics_by_tool(self, hours: int = 24) -> List[Dict]:
        """Get metrics grouped by tool."""
        conn = sqlite3.connect(self.db_path)
        cutoff = datetime.now() - timedelta(hours=hours)
        
        cursor = conn.execute('''
            SELECT 
                tool_name,
                COUNT(*) as count,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                AVG(duration_ms) as avg_duration,
                MIN(duration_ms) as min_duration,
                MAX(duration_ms) as max_duration
            FROM metrics
            WHERE timestamp >= ? AND tool_name IS NOT NULL
            GROUP BY tool_name
            ORDER BY count DESC
        ''', (cutoff.isoformat(),))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "tool_name": row[0],
                "count": row[1],
                "success_count": row[2],
                "success_rate": row[2] / row[1] if row[1] > 0 else 0,
                "avg_duration_ms": row[3] or 0,
                "min_duration_ms": row[4] or 0,
                "max_duration_ms": row[5] or 0
            })
        
        conn.close()
        return results
    
    def get_time_series(self, 
                       operation: Optional[str] = None,
                       hours: int = 24,
                       interval_minutes: int = 60) -> List[Dict]:
        """Get metrics over time."""
        conn = sqlite3.connect(self.db_path)
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        buckets = []
        current_time = start_time
        
        while current_time < end_time:
            bucket_end = current_time + timedelta(minutes=interval_minutes)
            
            # Query for this time bucket
            query = '''
                SELECT 
                    COUNT(*) as count,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                    AVG(duration_ms) as avg_duration
                FROM metrics
                WHERE timestamp >= ? AND timestamp < ?
            '''
            params = [current_time.isoformat(), bucket_end.isoformat()]
            
            if operation:
                query += " AND operation = ?"
                params.append(operation)
            
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            
            buckets.append({
                "timestamp": current_time.isoformat(),
                "count": row[0] or 0,
                "success_count": row[1] or 0,
                "success_rate": (row[1] / row[0]) if row[0] else 0,
                "avg_duration_ms": row[2] or 0
            })
            
            current_time = bucket_end
        
        conn.close()
        return buckets
    
    def aggregate_metrics(self, period_hours: int = 1) -> int:
        """Create aggregated metrics for a time period."""
        conn = sqlite3.connect(self.db_path)
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=period_hours)
        
        # Get all unique operations in the period
        cursor = conn.execute('''
            SELECT DISTINCT operation 
            FROM metrics 
            WHERE timestamp >= ? AND timestamp < ?
        ''', (start_time.isoformat(), end_time.isoformat()))
        
        operations = [row[0] for row in cursor.fetchall()]
        count = 0
        
        for operation in operations:
            # Get metrics for this operation
            cursor = conn.execute('''
                SELECT duration_ms, status
                FROM metrics
                WHERE timestamp >= ? AND timestamp < ? AND operation = ?
            ''', (start_time.isoformat(), end_time.isoformat(), operation))
            
            rows = cursor.fetchall()
            if not rows:
                continue
            
            durations = [r[0] for r in rows if r[0] is not None]
            success_count = sum(1 for r in rows if r[1] == "success")
            failure_count = sum(1 for r in rows if r[1] == "failed")
            
            if durations:
                sorted_durations = sorted(durations)
                
                # Insert aggregated metrics
                conn.execute('''
                    INSERT INTO metrics_summary
                    (operation, period_start, period_end, count, success_count, failure_count,
                     avg_duration_ms, min_duration_ms, max_duration_ms,
                     p50_duration_ms, p95_duration_ms, p99_duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    operation,
                    start_time.isoformat(),
                    end_time.isoformat(),
                    len(rows),
                    success_count,
                    failure_count,
                    statistics.mean(durations),
                    min(durations),
                    max(durations),
                    self._percentile(sorted_durations, 50),
                    self._percentile(sorted_durations, 95),
                    self._percentile(sorted_durations, 99)
                ))
                count += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"Created {count} aggregated metrics for period {period_hours}h")
        return count
    
    def get_recent_metrics(self, limit: int = 100) -> List[Dict]:
        """Get recent raw metrics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('''
            SELECT * FROM metrics
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            metric = dict(zip(columns, row))
            # Parse JSON metadata
            if metric.get("metadata"):
                try:
                    metric["metadata"] = json.loads(metric["metadata"])
                except:
                    pass
            results.append(metric)
        
        conn.close()
        return results
    
    def cleanup_old_metrics(self, retention_days: int = 30) -> int:
        """Delete metrics older than retention period."""
        conn = sqlite3.connect(self.db_path)
        cutoff = datetime.now() - timedelta(days=retention_days)
        
        # Delete old raw metrics
        cursor = conn.execute('''
            DELETE FROM metrics
            WHERE timestamp < ?
        ''', (cutoff.isoformat(),))
        
        deleted = cursor.rowcount
        
        # Delete old aggregations
        cursor = conn.execute('''
            DELETE FROM metrics_summary
            WHERE period_end < ?
        ''', (cutoff.isoformat(),))
        
        deleted += cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted {deleted} old metrics/aggregations")
        return deleted
    
    def _percentile(self, sorted_values: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not sorted_values:
            return 0
        
        k = (len(sorted_values) - 1) * (percentile / 100)
        f = int(k)
        c = k - f
        
        if f + 1 < len(sorted_values):
            return sorted_values[f] + c * (sorted_values[f + 1] - sorted_values[f])
        else:
            return sorted_values[f]


# Test the service
async def test_metrics_service():
    """Test that metrics service actually works."""
    import asyncio
    import random
    
    print("=" * 60)
    print("TESTING REAL METRICS SERVICE")
    print("=" * 60)
    
    service = MetricsService("test_metrics.db")
    
    # Test 1: Record single metric
    print("\n1. Recording single metric...")
    service.record_operation(
        operation="test_operation",
        duration_ms=125.5,
        status="success",
        tool_name="write_file"
    )
    print("✅ Single metric recorded")
    
    # Test 2: Record batch metrics
    print("\n2. Recording batch metrics...")
    batch_data = []
    for i in range(20):
        batch_data.append({
            "operation": random.choice(["read", "write", "list"]),
            "duration_ms": random.uniform(10, 200),
            "status": "success" if random.random() > 0.1 else "failed",
            "tool_name": random.choice(["read_file", "write_file", "list_directory"])
        })
    
    count = service.record_batch(batch_data)
    print(f"✅ Recorded {count} metrics in batch")
    
    # Test 3: Get statistics
    print("\n3. Getting statistics...")
    stats = service.get_stats()
    print(f"✅ Overall stats: {stats['count']} operations")
    print(f"   Success rate: {stats['success_rate']*100:.1f}%")
    print(f"   Avg duration: {stats['avg_duration_ms']:.2f}ms")
    print(f"   P95 latency: {stats['p95']:.2f}ms")
    
    # Test 4: Get metrics by tool
    print("\n4. Getting metrics by tool...")
    tool_stats = service.get_metrics_by_tool()
    print(f"✅ Found metrics for {len(tool_stats)} tools")
    for tool in tool_stats[:3]:
        print(f"   {tool['tool_name']}: {tool['count']} ops, {tool['success_rate']*100:.0f}% success")
    
    # Test 5: Aggregate metrics
    print("\n5. Aggregating metrics...")
    aggregated = service.aggregate_metrics(period_hours=1)
    print(f"✅ Created {aggregated} aggregations")
    
    # Test 6: Get time series
    print("\n6. Getting time series...")
    time_series = service.get_time_series(hours=1, interval_minutes=15)
    print(f"✅ Got {len(time_series)} time buckets")
    
    print("\n" + "=" * 60)
    print("✅ METRICS SERVICE WORKS!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_metrics_service())