"""TimescaleDB storage layer for reliability metrics and time-series data."""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import asdict
import uuid

import asyncpg
import pandas as pd
import numpy as np
from contextlib import asynccontextmanager

from .reliability_scoring import (
    ReliabilityScore, DimensionScore, ScoringDimension, 
    BaselineMetrics, SeverityLevel
)

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Configuration for TimescaleDB connection."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "mcp_reliability",
        username: str = "postgres",
        password: str = "postgres",
        pool_size: int = 10,
        max_connections: int = 20,
        ssl_mode: str = "prefer"
    ):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.pool_size = pool_size
        self.max_connections = max_connections
        self.ssl_mode = ssl_mode
    
    @property
    def dsn(self) -> str:
        """Get PostgreSQL DSN."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?sslmode={self.ssl_mode}"
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create config from environment variables."""
        import os
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "mcp_reliability"),
            username=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_connections=int(os.getenv("DB_MAX_CONNECTIONS", "20")),
            ssl_mode=os.getenv("DB_SSL_MODE", "prefer")
        )


class ReliabilityStore:
    """TimescaleDB-backed storage for reliability metrics."""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig.from_env()
        self.pool: Optional[asyncpg.Pool] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self._initialized = False
    
    async def initialize(self):
        """Initialize database connection pool and create tables."""
        if self._initialized:
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                dsn=self.config.dsn,
                min_size=1,
                max_size=self.config.max_connections,
                command_timeout=60
            )
            
            await self._create_tables()
            self._initialized = True
            self.logger.info("Database connection pool initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            self.logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool."""
        if not self.pool:
            await self.initialize()
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def _create_tables(self):
        """Create TimescaleDB tables for reliability data."""
        
        async with self.get_connection() as conn:
            # Enable TimescaleDB extension
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
            except Exception as e:
                self.logger.warning(f"Could not enable TimescaleDB extension: {e}")
            
            # Create reliability scores table (main hypertable)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reliability_scores (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    agent_id TEXT NOT NULL,
                    evaluation_id TEXT,
                    composite_score DECIMAL(5,2) NOT NULL,
                    overall_confidence DECIMAL(4,3) NOT NULL,
                    confidence_interval_lower DECIMAL(5,2),
                    confidence_interval_upper DECIMAL(5,2),
                    sample_size INTEGER,
                    trend_direction TEXT,
                    trend_strength DECIMAL(4,3),
                    volatility DECIMAL(6,4),
                    baseline_score DECIMAL(5,2),
                    percentile_rank DECIMAL(5,2),
                    days_since_baseline INTEGER,
                    failure_risk DECIMAL(4,3),
                    failure_prediction_horizon INTERVAL,
                    data_quality_score DECIMAL(4,3) DEFAULT 1.0,
                    completeness_score DECIMAL(4,3) DEFAULT 1.0,
                    duration INTERVAL,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            
            # Convert to hypertable if TimescaleDB is available
            try:
                await conn.execute("""
                    SELECT create_hypertable('reliability_scores', 'timestamp',
                        if_not_exists => TRUE,
                        chunk_time_interval => INTERVAL '1 day'
                    );
                """)
                self.logger.info("Created hypertable for reliability_scores")
            except Exception as e:
                self.logger.warning(f"Could not create hypertable: {e}")
            
            # Create dimension scores table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dimension_scores (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    reliability_score_id UUID NOT NULL REFERENCES reliability_scores(id) ON DELETE CASCADE,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    agent_id TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    raw_score DECIMAL(5,2) NOT NULL,
                    weighted_score DECIMAL(6,3) NOT NULL,
                    confidence DECIMAL(4,3) NOT NULL,
                    data_points INTEGER,
                    baseline_deviation DECIMAL(8,4),
                    percentile_rank DECIMAL(5,2),
                    z_score DECIMAL(8,4),
                    trend_slope DECIMAL(10,6),
                    metrics JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            
            # Create baseline metrics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS baseline_metrics (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_id TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    baseline_score DECIMAL(5,2) NOT NULL,
                    baseline_std DECIMAL(6,3) NOT NULL,
                    sample_count INTEGER NOT NULL,
                    calculation_date TIMESTAMPTZ NOT NULL,
                    lower_control_limit DECIMAL(5,2),
                    upper_control_limit DECIMAL(5,2),
                    warning_lower_limit DECIMAL(5,2),
                    warning_upper_limit DECIMAL(5,2),
                    min_score DECIMAL(5,2),
                    max_score DECIMAL(5,2),
                    median_score DECIMAL(5,2),
                    percentiles JSONB DEFAULT '{}'::jsonb,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(agent_id, dimension, calculation_date)
                );
            """)
            
            # Create aggregated metrics table for faster queries
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS aggregated_metrics (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    timestamp TIMESTAMPTZ NOT NULL,
                    agent_id TEXT NOT NULL,
                    aggregation_period TEXT NOT NULL, -- 'hourly', 'daily', 'weekly'
                    composite_score_avg DECIMAL(5,2),
                    composite_score_min DECIMAL(5,2),
                    composite_score_max DECIMAL(5,2),
                    composite_score_std DECIMAL(6,3),
                    sample_count INTEGER,
                    failure_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    dimension_averages JSONB DEFAULT '{}'::jsonb,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(agent_id, aggregation_period, timestamp)
                );
            """)
            
            # Create alerts table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reliability_alerts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    agent_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    dimension TEXT,
                    current_score DECIMAL(5,2),
                    threshold_score DECIMAL(5,2),
                    message TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    resolved_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            
            # Create indices for better performance
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reliability_scores_agent_timestamp 
                ON reliability_scores(agent_id, timestamp DESC);
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reliability_scores_composite_score 
                ON reliability_scores(composite_score);
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_dimension_scores_agent_dimension_timestamp 
                ON dimension_scores(agent_id, dimension, timestamp DESC);
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_baseline_metrics_agent_active 
                ON baseline_metrics(agent_id, is_active) WHERE is_active = TRUE;
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_aggregated_metrics_agent_period_timestamp 
                ON aggregated_metrics(agent_id, aggregation_period, timestamp DESC);
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_agent_timestamp 
                ON reliability_alerts(agent_id, timestamp DESC);
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_unresolved 
                ON reliability_alerts(agent_id, severity) WHERE resolved_at IS NULL;
            """)
            
            self.logger.info("Database tables and indices created successfully")
    
    async def store_reliability_score(self, score: ReliabilityScore) -> str:
        """Store a reliability score with all dimension scores."""
        
        async with self.get_connection() as conn:
            async with conn.transaction():
                # Insert main reliability score
                score_id = str(uuid.uuid4())
                
                await conn.execute("""
                    INSERT INTO reliability_scores (
                        id, timestamp, agent_id, evaluation_id, composite_score,
                        overall_confidence, confidence_interval_lower, confidence_interval_upper,
                        sample_size, trend_direction, trend_strength, volatility,
                        baseline_score, percentile_rank, days_since_baseline,
                        failure_risk, failure_prediction_horizon, data_quality_score,
                        completeness_score, duration, metadata
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, 
                        $14, $15, $16, $17, $18, $19, $20, $21
                    )
                """, 
                    score_id,
                    score.timestamp,
                    score.agent_id,
                    score.evaluation_id,
                    float(score.composite_score),
                    float(score.overall_confidence),
                    float(score.confidence_interval[0]) if score.confidence_interval else None,
                    float(score.confidence_interval[1]) if score.confidence_interval else None,
                    score.sample_size,
                    score.trend_direction,
                    float(score.trend_strength),
                    float(score.volatility),
                    float(score.baseline_score) if score.baseline_score else None,
                    float(score.percentile_rank) if score.percentile_rank else None,
                    score.days_since_baseline,
                    float(score.failure_risk),
                    score.failure_prediction_horizon,
                    float(score.data_quality_score),
                    float(score.completeness_score),
                    score.duration,
                    json.dumps({})  # Additional metadata can be added here
                )
                
                # Insert dimension scores
                for dimension, dim_score in score.dimension_scores.items():
                    await conn.execute("""
                        INSERT INTO dimension_scores (
                            reliability_score_id, timestamp, agent_id, dimension,
                            raw_score, weighted_score, confidence, data_points,
                            baseline_deviation, percentile_rank, z_score, trend_slope,
                            metrics
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    """,
                        score_id,
                        dim_score.timestamp,
                        score.agent_id,
                        dimension.value,
                        float(dim_score.raw_score),
                        float(dim_score.weighted_score),
                        float(dim_score.confidence),
                        dim_score.data_points,
                        float(dim_score.baseline_deviation),
                        float(dim_score.percentile_rank) if dim_score.percentile_rank else None,
                        float(dim_score.z_score) if dim_score.z_score else None,
                        float(dim_score.trend_slope) if dim_score.trend_slope else None,
                        json.dumps(dim_score.metrics)
                    )
                
                self.logger.debug(f"Stored reliability score {score_id} for agent {score.agent_id}")
                return score_id
    
    async def get_reliability_scores(
        self,
        agent_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get reliability scores for an agent within a time range."""
        
        query = """
            SELECT rs.*, 
                   array_agg(
                       json_build_object(
                           'dimension', ds.dimension,
                           'raw_score', ds.raw_score,
                           'weighted_score', ds.weighted_score,
                           'confidence', ds.confidence,
                           'data_points', ds.data_points,
                           'baseline_deviation', ds.baseline_deviation,
                           'percentile_rank', ds.percentile_rank,
                           'z_score', ds.z_score,
                           'trend_slope', ds.trend_slope,
                           'metrics', ds.metrics
                       )
                   ) as dimension_scores
            FROM reliability_scores rs
            LEFT JOIN dimension_scores ds ON rs.id = ds.reliability_score_id
            WHERE rs.agent_id = $1
        """
        
        params = [agent_id]
        param_count = 1
        
        if start_time:
            param_count += 1
            query += f" AND rs.timestamp >= ${param_count}"
            params.append(start_time)
        
        if end_time:
            param_count += 1
            query += f" AND rs.timestamp <= ${param_count}"
            params.append(end_time)
        
        query += " GROUP BY rs.id ORDER BY rs.timestamp DESC"
        
        if limit:
            param_count += 1
            query += f" LIMIT ${param_count}"
            params.append(limit)
        
        async with self.get_connection() as conn:
            rows = await conn.fetch(query, *params)
            
            results = []
            for row in rows:
                result = dict(row)
                # Parse dimension scores
                if result['dimension_scores']:
                    dim_scores = {}
                    for ds in result['dimension_scores']:
                        if ds:  # Handle null entries
                            dim_scores[ds['dimension']] = ds
                    result['dimension_scores'] = dim_scores
                else:
                    result['dimension_scores'] = {}
                
                results.append(result)
            
            return results
    
    async def get_time_series_data(
        self,
        agent_id: str,
        metric: str,
        start_time: datetime,
        end_time: datetime,
        aggregation: str = "1h"  # PostgreSQL interval format
    ) -> pd.DataFrame:
        """Get time series data for a specific metric."""
        
        if metric == "composite_score":
            query = f"""
                SELECT 
                    time_bucket('{aggregation}', timestamp) as bucket,
                    AVG(composite_score) as avg_value,
                    MIN(composite_score) as min_value,
                    MAX(composite_score) as max_value,
                    COUNT(*) as sample_count
                FROM reliability_scores
                WHERE agent_id = $1 AND timestamp BETWEEN $2 AND $3
                GROUP BY bucket
                ORDER BY bucket
            """
        else:
            # Dimension-specific queries
            dimension = metric.replace("_score", "")
            query = f"""
                SELECT 
                    time_bucket('{aggregation}', timestamp) as bucket,
                    AVG(raw_score) as avg_value,
                    MIN(raw_score) as min_value,
                    MAX(raw_score) as max_value,
                    COUNT(*) as sample_count
                FROM dimension_scores
                WHERE agent_id = $1 AND dimension = $2 AND timestamp BETWEEN $3 AND $4
                GROUP BY bucket
                ORDER BY bucket
            """
            params = [agent_id, dimension, start_time, end_time]
        
        if metric == "composite_score":
            params = [agent_id, start_time, end_time]
        
        async with self.get_connection() as conn:
            rows = await conn.fetch(query, *params)
            
            # Convert to pandas DataFrame
            data = [dict(row) for row in rows]
            df = pd.DataFrame(data)
            
            if not df.empty:
                df['bucket'] = pd.to_datetime(df['bucket'])
                df.set_index('bucket', inplace=True)
            
            return df
    
    async def store_baseline_metrics(self, baseline: BaselineMetrics, agent_id: str):
        """Store baseline metrics for an agent and dimension."""
        
        async with self.get_connection() as conn:
            # Deactivate previous baselines for this agent/dimension
            await conn.execute("""
                UPDATE baseline_metrics 
                SET is_active = FALSE 
                WHERE agent_id = $1 AND dimension = $2
            """, agent_id, baseline.dimension.value)
            
            # Insert new baseline
            await conn.execute("""
                INSERT INTO baseline_metrics (
                    agent_id, dimension, baseline_score, baseline_std, sample_count,
                    calculation_date, lower_control_limit, upper_control_limit,
                    warning_lower_limit, warning_upper_limit, min_score, max_score,
                    median_score, percentiles, is_active
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (agent_id, dimension, calculation_date) 
                DO UPDATE SET 
                    baseline_score = $3, baseline_std = $4, sample_count = $5,
                    lower_control_limit = $7, upper_control_limit = $8,
                    warning_lower_limit = $9, warning_upper_limit = $10,
                    min_score = $11, max_score = $12, median_score = $13,
                    percentiles = $14, is_active = $15
            """,
                agent_id,
                baseline.dimension.value,
                float(baseline.baseline_score),
                float(baseline.baseline_std),
                baseline.sample_count,
                baseline.calculation_date,
                float(baseline.lower_control_limit),
                float(baseline.upper_control_limit),
                float(baseline.warning_lower_limit),
                float(baseline.warning_upper_limit),
                float(baseline.min_score),
                float(baseline.max_score),
                float(baseline.median_score),
                json.dumps(baseline.percentiles),
                True
            )
    
    async def get_active_baselines(self, agent_id: str) -> Dict[ScoringDimension, BaselineMetrics]:
        """Get active baseline metrics for an agent."""
        
        async with self.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT * FROM baseline_metrics 
                WHERE agent_id = $1 AND is_active = TRUE
                ORDER BY calculation_date DESC
            """, agent_id)
            
            baselines = {}
            for row in rows:
                dimension = ScoringDimension(row['dimension'])
                baselines[dimension] = BaselineMetrics(
                    dimension=dimension,
                    baseline_score=float(row['baseline_score']),
                    baseline_std=float(row['baseline_std']),
                    sample_count=row['sample_count'],
                    calculation_date=row['calculation_date'],
                    lower_control_limit=float(row['lower_control_limit']),
                    upper_control_limit=float(row['upper_control_limit']),
                    warning_lower_limit=float(row['warning_lower_limit']),
                    warning_upper_limit=float(row['warning_upper_limit']),
                    min_score=float(row['min_score']),
                    max_score=float(row['max_score']),
                    median_score=float(row['median_score']),
                    percentiles=json.loads(row['percentiles'])
                )
            
            return baselines
    
    async def store_alert(
        self,
        agent_id: str,
        alert_type: str,
        severity: SeverityLevel,
        message: str,
        dimension: Optional[ScoringDimension] = None,
        current_score: Optional[float] = None,
        threshold_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a reliability alert."""
        
        async with self.get_connection() as conn:
            alert_id = str(uuid.uuid4())
            
            await conn.execute("""
                INSERT INTO reliability_alerts (
                    id, agent_id, alert_type, severity, dimension,
                    current_score, threshold_score, message, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                alert_id,
                agent_id,
                alert_type,
                severity.value,
                dimension.value if dimension else None,
                float(current_score) if current_score else None,
                float(threshold_score) if threshold_score else None,
                message,
                json.dumps(metadata or {})
            )
            
            return alert_id
    
    async def resolve_alert(self, alert_id: str):
        """Mark an alert as resolved."""
        
        async with self.get_connection() as conn:
            await conn.execute("""
                UPDATE reliability_alerts 
                SET resolved_at = NOW() 
                WHERE id = $1
            """, alert_id)
    
    async def get_active_alerts(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get active (unresolved) alerts for an agent."""
        
        async with self.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT * FROM reliability_alerts 
                WHERE agent_id = $1 AND resolved_at IS NULL
                ORDER BY timestamp DESC
            """, agent_id)
            
            return [dict(row) for row in rows]
    
    async def calculate_aggregated_metrics(
        self,
        agent_id: str,
        start_time: datetime,
        end_time: datetime,
        period: str = "daily"
    ):
        """Calculate and store aggregated metrics for faster queries."""
        
        # Determine time bucket interval
        interval_map = {
            "hourly": "1 hour",
            "daily": "1 day", 
            "weekly": "1 week"
        }
        interval = interval_map.get(period, "1 day")
        
        async with self.get_connection() as conn:
            # Calculate aggregated reliability scores
            await conn.execute(f"""
                INSERT INTO aggregated_metrics (
                    timestamp, agent_id, aggregation_period,
                    composite_score_avg, composite_score_min, composite_score_max,
                    composite_score_std, sample_count, failure_count, success_count,
                    dimension_averages
                )
                SELECT 
                    time_bucket('{interval}', timestamp) as bucket,
                    agent_id,
                    $1 as period,
                    AVG(composite_score),
                    MIN(composite_score),
                    MAX(composite_score),
                    STDDEV(composite_score),
                    COUNT(*),
                    COUNT(*) FILTER (WHERE composite_score < 60) as failures,
                    COUNT(*) FILTER (WHERE composite_score >= 60) as successes,
                    json_object_agg(
                        'composite', 
                        json_build_object(
                            'avg', AVG(composite_score),
                            'min', MIN(composite_score),
                            'max', MAX(composite_score)
                        )
                    ) as dimension_avgs
                FROM reliability_scores 
                WHERE agent_id = $2 
                  AND timestamp BETWEEN $3 AND $4
                GROUP BY bucket, agent_id
                ON CONFLICT (agent_id, aggregation_period, timestamp) 
                DO UPDATE SET 
                    composite_score_avg = EXCLUDED.composite_score_avg,
                    composite_score_min = EXCLUDED.composite_score_min,
                    composite_score_max = EXCLUDED.composite_score_max,
                    composite_score_std = EXCLUDED.composite_score_std,
                    sample_count = EXCLUDED.sample_count,
                    failure_count = EXCLUDED.failure_count,
                    success_count = EXCLUDED.success_count,
                    dimension_averages = EXCLUDED.dimension_averages
            """, period, agent_id, start_time, end_time)
    
    async def get_agent_summary(self, agent_id: str) -> Dict[str, Any]:
        """Get comprehensive summary statistics for an agent."""
        
        async with self.get_connection() as conn:
            # Get latest score
            latest_score = await conn.fetchrow("""
                SELECT composite_score, timestamp, trend_direction, failure_risk
                FROM reliability_scores 
                WHERE agent_id = $1 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, agent_id)
            
            # Get historical statistics
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_evaluations,
                    AVG(composite_score) as avg_score,
                    MIN(composite_score) as min_score,
                    MAX(composite_score) as max_score,
                    STDDEV(composite_score) as score_std,
                    COUNT(*) FILTER (WHERE composite_score < 60) as failure_count,
                    COUNT(*) FILTER (WHERE composite_score >= 90) as excellent_count,
                    COUNT(DISTINCT DATE(timestamp)) as active_days
                FROM reliability_scores 
                WHERE agent_id = $1
            """, agent_id)
            
            # Get active alerts count
            alert_counts = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_active_alerts,
                    COUNT(*) FILTER (WHERE severity = 'critical') as critical_alerts,
                    COUNT(*) FILTER (WHERE severity = 'high') as high_alerts
                FROM reliability_alerts 
                WHERE agent_id = $1 AND resolved_at IS NULL
            """, agent_id)
            
            return {
                "agent_id": agent_id,
                "latest_score": dict(latest_score) if latest_score else None,
                "statistics": dict(stats) if stats else None,
                "alerts": dict(alert_counts) if alert_counts else None,
                "summary_generated_at": datetime.utcnow()
            }


# Export main classes
__all__ = ['DatabaseConfig', 'ReliabilityStore']