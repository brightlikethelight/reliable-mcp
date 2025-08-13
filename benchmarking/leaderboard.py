#!/usr/bin/env python3
"""
Leaderboard system for tracking MCP server performance.
Maintains rankings across different workloads and metrics.
"""

import sqlite3
import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import sys

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class Leaderboard:
    """Track and display MCP server performance rankings."""
    
    def __init__(self, db_path: str = "leaderboard.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize leaderboard database."""
        conn = sqlite3.connect(self.db_path)
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS leaderboard_entries (
                entry_id TEXT PRIMARY KEY,
                server_name TEXT,
                test_type TEXT,
                workload_name TEXT,
                score REAL,
                throughput REAL,
                p95_latency REAL,
                consistency REAL,
                error_rate REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS server_stats (
                server_name TEXT PRIMARY KEY,
                total_tests INTEGER,
                avg_score REAL,
                best_score REAL,
                worst_score REAL,
                avg_throughput REAL,
                avg_p95_latency REAL,
                avg_consistency REAL,
                last_updated DATETIME
            )
        ''')
        
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_server_score 
            ON leaderboard_entries(server_name, score DESC)
        ''')
        
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_workload_score 
            ON leaderboard_entries(workload_name, score DESC)
        ''')
        
        conn.commit()
        conn.close()
    
    def add_benchmark_result(
        self,
        server_name: str,
        workload_name: str,
        benchmark_results: Dict[str, Any]
    ) -> float:
        """Add a benchmark result to the leaderboard and return the score."""
        
        # Calculate score based on multiple metrics
        score = self.calculate_score(benchmark_results)
        
        # Extract key metrics
        throughput = benchmark_results.get("operations_per_second", 0)
        p95_latency = benchmark_results.get("latencies", {}).get("p95", 0)
        consistency = benchmark_results.get("latencies", {}).get("consistency", 0)
        error_rate = benchmark_results.get("error_rate", 0)
        
        # Store entry
        conn = sqlite3.connect(self.db_path)
        
        entry_id = f"{server_name}_{workload_name}_{int(datetime.now().timestamp())}"
        
        conn.execute('''
            INSERT INTO leaderboard_entries 
            (entry_id, server_name, test_type, workload_name, score, 
             throughput, p95_latency, consistency, error_rate, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry_id,
            server_name,
            "benchmark",
            workload_name,
            score,
            throughput,
            p95_latency,
            consistency,
            error_rate,
            json.dumps(benchmark_results)
        ))
        
        conn.commit()
        conn.close()
        
        # Update server stats
        self.update_server_stats(server_name)
        
        return score
    
    def calculate_score(self, results: Dict[str, Any]) -> float:
        """Calculate a composite score from benchmark results."""
        
        # Scoring components (all normalized to 0-100)
        components = []
        
        # Throughput score (0-1000 ops/sec = 0-100 score)
        throughput = results.get("operations_per_second", 0)
        throughput_score = min(100, throughput / 10)
        components.append(("throughput", throughput_score, 0.3))
        
        # Latency score (lower is better, 0-100ms = 100-0 score)
        p95_latency = results.get("latencies", {}).get("p95", 100)
        latency_score = max(0, 100 - p95_latency)
        components.append(("latency", latency_score, 0.3))
        
        # Consistency score (already 0-100)
        consistency = results.get("latencies", {}).get("consistency", 0)
        components.append(("consistency", consistency, 0.2))
        
        # Error rate penalty (0% = 100, 10% = 0)
        error_rate = results.get("error_rate", 0)
        error_score = max(0, 100 - (error_rate * 1000))
        components.append(("reliability", error_score, 0.2))
        
        # Calculate weighted score
        total_score = sum(score * weight for _, score, weight in components)
        
        return round(total_score, 2)
    
    def update_server_stats(self, server_name: str):
        """Update aggregate statistics for a server."""
        
        conn = sqlite3.connect(self.db_path)
        
        # Get all entries for this server
        cursor = conn.execute('''
            SELECT score, throughput, p95_latency, consistency
            FROM leaderboard_entries
            WHERE server_name = ?
            ORDER BY timestamp DESC
            LIMIT 100
        ''', (server_name,))
        
        entries = cursor.fetchall()
        
        if entries:
            scores = [e[0] for e in entries]
            throughputs = [e[1] for e in entries]
            latencies = [e[2] for e in entries]
            consistencies = [e[3] for e in entries]
            
            stats = {
                "total_tests": len(entries),
                "avg_score": statistics.mean(scores),
                "best_score": max(scores),
                "worst_score": min(scores),
                "avg_throughput": statistics.mean(throughputs),
                "avg_p95_latency": statistics.mean(latencies),
                "avg_consistency": statistics.mean(consistencies),
                "last_updated": datetime.now()
            }
            
            # Update or insert
            conn.execute('''
                INSERT OR REPLACE INTO server_stats 
                (server_name, total_tests, avg_score, best_score, worst_score,
                 avg_throughput, avg_p95_latency, avg_consistency, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                server_name,
                stats["total_tests"],
                stats["avg_score"],
                stats["best_score"],
                stats["worst_score"],
                stats["avg_throughput"],
                stats["avg_p95_latency"],
                stats["avg_consistency"],
                stats["last_updated"]
            ))
            
            conn.commit()
        
        conn.close()
    
    def get_leaderboard(
        self,
        workload: Optional[str] = None,
        time_range: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get leaderboard entries."""
        
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT server_name, workload_name, score, throughput, 
                   p95_latency, consistency, error_rate, timestamp
            FROM leaderboard_entries
        '''
        
        conditions = []
        params = []
        
        if workload:
            conditions.append("workload_name = ?")
            params.append(workload)
        
        if time_range:
            cutoff = datetime.now() - timedelta(days=time_range)
            conditions.append("timestamp > ?")
            params.append(cutoff)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY score DESC LIMIT ?"
        params.append(limit)
        
        cursor = conn.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "server": row[0],
                "workload": row[1],
                "score": row[2],
                "throughput": row[3],
                "p95_latency": row[4],
                "consistency": row[5],
                "error_rate": row[6],
                "timestamp": row[7]
            })
        
        conn.close()
        
        return results
    
    def get_server_rankings(self) -> List[Tuple[str, float, int]]:
        """Get overall server rankings based on average scores."""
        
        conn = sqlite3.connect(self.db_path)
        
        cursor = conn.execute('''
            SELECT server_name, avg_score, total_tests
            FROM server_stats
            ORDER BY avg_score DESC
        ''')
        
        rankings = cursor.fetchall()
        conn.close()
        
        return rankings
    
    def get_workload_bests(self) -> Dict[str, str]:
        """Get best server for each workload."""
        
        conn = sqlite3.connect(self.db_path)
        
        cursor = conn.execute('''
            SELECT workload_name, server_name, MAX(score)
            FROM leaderboard_entries
            GROUP BY workload_name
        ''')
        
        bests = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        
        return bests
    
    def generate_html_report(self, output_path: str = "leaderboard.html") -> str:
        """Generate HTML leaderboard report."""
        
        # Get data
        overall_rankings = self.get_server_rankings()
        recent_entries = self.get_leaderboard(limit=20)
        workload_bests = self.get_workload_bests()
        
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>MCP Server Performance Leaderboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        h1 {
            color: #667eea;
            text-align: center;
            margin-bottom: 30px;
        }
        h2 {
            color: #764ba2;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px;
            text-align: left;
        }
        td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .rank-1 { background-color: #ffd700; font-weight: bold; }
        .rank-2 { background-color: #c0c0c0; }
        .rank-3 { background-color: #cd7f32; }
        .metric {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            margin: 2px;
            font-size: 12px;
        }
        .good { background-color: #4caf50; color: white; }
        .average { background-color: #ff9800; color: white; }
        .poor { background-color: #f44336; color: white; }
        .timestamp {
            color: #999;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏆 MCP Server Performance Leaderboard</h1>
        
        <h2>Overall Rankings</h2>
        <table>
            <tr>
                <th>Rank</th>
                <th>Server</th>
                <th>Average Score</th>
                <th>Tests Run</th>
            </tr>
"""
        
        for i, (server, avg_score, tests) in enumerate(overall_rankings, 1):
            rank_class = f"rank-{i}" if i <= 3 else ""
            html += f"""
            <tr class="{rank_class}">
                <td>#{i}</td>
                <td>{server}</td>
                <td>{avg_score:.1f}/100</td>
                <td>{tests}</td>
            </tr>
"""
        
        html += """
        </table>
        
        <h2>Best Performers by Workload</h2>
        <table>
            <tr>
                <th>Workload</th>
                <th>Best Server</th>
            </tr>
"""
        
        for workload, server in workload_bests.items():
            html += f"""
            <tr>
                <td>{workload}</td>
                <td>🥇 {server}</td>
            </tr>
"""
        
        html += """
        </table>
        
        <h2>Recent Benchmark Results</h2>
        <table>
            <tr>
                <th>Server</th>
                <th>Workload</th>
                <th>Score</th>
                <th>Throughput</th>
                <th>P95 Latency</th>
                <th>Consistency</th>
                <th>Timestamp</th>
            </tr>
"""
        
        for entry in recent_entries:
            # Color code metrics
            throughput_class = "good" if entry["throughput"] > 500 else "average" if entry["throughput"] > 100 else "poor"
            latency_class = "good" if entry["p95_latency"] < 10 else "average" if entry["p95_latency"] < 50 else "poor"
            consistency_class = "good" if entry["consistency"] > 70 else "average" if entry["consistency"] > 40 else "poor"
            
            timestamp = datetime.fromisoformat(entry["timestamp"]).strftime("%Y-%m-%d %H:%M")
            
            html += f"""
            <tr>
                <td>{entry['server']}</td>
                <td>{entry['workload']}</td>
                <td><strong>{entry['score']:.1f}</strong></td>
                <td><span class="metric {throughput_class}">{entry['throughput']:.0f} ops/s</span></td>
                <td><span class="metric {latency_class}">{entry['p95_latency']:.1f}ms</span></td>
                <td><span class="metric {consistency_class}">{entry['consistency']:.0f}%</span></td>
                <td class="timestamp">{timestamp}</td>
            </tr>
"""
        
        html += f"""
        </table>
        
        <div style="text-align: center; margin-top: 30px; color: #999;">
            Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>
</body>
</html>
"""
        
        with open(output_path, "w") as f:
            f.write(html)
        
        return output_path
    
    def print_leaderboard(self):
        """Print leaderboard to console."""
        
        print("\n" + "=" * 60)
        print("MCP SERVER LEADERBOARD")
        print("=" * 60)
        
        # Overall rankings
        rankings = self.get_server_rankings()
        
        if rankings:
            print("\nOVERALL RANKINGS:")
            print("-" * 40)
            for i, (server, score, tests) in enumerate(rankings, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
                print(f"{medal} #{i}. {server:20} Score: {score:6.1f}  Tests: {tests:3}")
        
        # Workload bests
        bests = self.get_workload_bests()
        
        if bests:
            print("\nBEST BY WORKLOAD:")
            print("-" * 40)
            for workload, server in bests.items():
                print(f"  {workload:20} → {server}")
        
        # Recent top scores
        recent = self.get_leaderboard(limit=5)
        
        if recent:
            print("\nRECENT TOP SCORES:")
            print("-" * 40)
            for entry in recent:
                print(f"  {entry['server']:15} {entry['workload']:20} Score: {entry['score']:.1f}")
        
        print("=" * 60)


async def main():
    """Test leaderboard functionality."""
    import asyncio
    
    # Import from same directory when run as main
    if __name__ == "__main__":
        from benchmark_runner import BenchmarkRunner
        from workloads import StandardWorkloads
    else:
        from .benchmark_runner import BenchmarkRunner
        from .workloads import StandardWorkloads
    
    # Initialize
    leaderboard = Leaderboard()
    runner = BenchmarkRunner()
    
    # Run a quick benchmark
    print("Running quick benchmark for leaderboard test...")
    workload = StandardWorkloads.get_quick_benchmarks()["quick_mixed"]
    
    server_config = {"name": "filesystem", "type": "filesystem", "path": "/private/tmp"}
    
    results = await runner.run_benchmark(server_config, workload)
    
    # Add to leaderboard
    score = leaderboard.add_benchmark_result(
        server_config["name"],
        workload.name,
        results
    )
    
    print(f"\nBenchmark score: {score:.1f}/100")
    
    # Display leaderboard
    leaderboard.print_leaderboard()
    
    # Generate HTML report
    html_path = leaderboard.generate_html_report()
    print(f"\nHTML report generated: {html_path}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())