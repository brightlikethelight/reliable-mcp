"""Comprehensive reliability scoring engine for MCP agents."""

import time
import json
import logging
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
import statistics
from collections import defaultdict, deque

import numpy as np
from scipy import stats
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

from .metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


class ScoringDimension(Enum):
    """Reliability scoring dimensions."""
    CORRECTNESS = "correctness"
    PERFORMANCE = "performance" 
    RESILIENCE = "resilience"
    CONSISTENCY = "consistency"
    RESOURCE_USAGE = "resource_usage"


class SeverityLevel(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ScoringWeights:
    """Configurable weights for scoring dimensions."""
    correctness: float = 0.40  # 40%
    performance: float = 0.20  # 20%
    resilience: float = 0.20   # 20%
    consistency: float = 0.10  # 10%
    resource_usage: float = 0.10  # 10%
    
    def __post_init__(self):
        """Validate weights sum to 1.0."""
        total = self.correctness + self.performance + self.resilience + self.consistency + self.resource_usage
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")
    
    def normalize(self):
        """Normalize weights to sum to 1.0."""
        total = self.correctness + self.performance + self.resilience + self.consistency + self.resource_usage
        self.correctness /= total
        self.performance /= total
        self.resilience /= total
        self.consistency /= total
        self.resource_usage /= total


@dataclass 
class DimensionScore:
    """Score for a single reliability dimension."""
    dimension: ScoringDimension
    raw_score: float  # 0-100 raw score
    weighted_score: float  # Raw score * weight
    confidence: float  # Statistical confidence (0-1)
    data_points: int  # Number of data points used
    baseline_deviation: float  # Deviation from baseline
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Detailed metrics for this dimension
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Statistical information
    percentile_rank: Optional[float] = None
    z_score: Optional[float] = None
    trend_slope: Optional[float] = None


@dataclass
class ReliabilityScore:
    """Comprehensive reliability score for an MCP agent."""
    
    # Core scores
    composite_score: float  # 0-100 weighted composite score
    dimension_scores: Dict[ScoringDimension, DimensionScore] = field(default_factory=dict)
    
    # Metadata
    agent_id: str = ""
    evaluation_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration: timedelta = field(default_factory=lambda: timedelta(0))
    
    # Statistical confidence
    overall_confidence: float = 0.0
    confidence_interval: Tuple[float, float] = (0.0, 0.0)
    sample_size: int = 0
    
    # Trend analysis
    trend_direction: str = "stable"  # improving, degrading, stable
    trend_strength: float = 0.0  # 0-1 strength of trend
    volatility: float = 0.0  # Score volatility measure
    
    # Historical context
    baseline_score: Optional[float] = None
    percentile_rank: Optional[float] = None  # Percentile among historical scores
    days_since_baseline: Optional[int] = None
    
    # Failure prediction
    failure_risk: float = 0.0  # 0-1 probability of failure
    failure_prediction_horizon: Optional[timedelta] = None
    
    # Quality indicators
    data_quality_score: float = 1.0  # Quality of underlying data
    completeness_score: float = 1.0  # Data completeness percentage
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        # Convert enums and datetime objects
        result['dimension_scores'] = {
            dim.value: asdict(score) for dim, score in self.dimension_scores.items()
        }
        result['timestamp'] = self.timestamp.isoformat()
        result['duration'] = str(self.duration)
        return result
    
    def get_grade(self) -> str:
        """Get letter grade for composite score."""
        if self.composite_score >= 90:
            return "A"
        elif self.composite_score >= 80:
            return "B"
        elif self.composite_score >= 70:
            return "C"
        elif self.composite_score >= 60:
            return "D"
        else:
            return "F"


@dataclass
class ScoringConfiguration:
    """Configuration for reliability scoring engine."""
    
    # Scoring weights
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    
    # Statistical parameters
    min_sample_size: int = 10
    confidence_level: float = 0.95
    baseline_window_days: int = 30
    trend_analysis_window: int = 50
    
    # Thresholds
    critical_threshold: float = 30.0  # Below this is critical
    warning_threshold: float = 70.0   # Below this is warning
    excellent_threshold: float = 90.0  # Above this is excellent
    
    # Anomaly detection parameters
    anomaly_sensitivity: float = 0.1  # Lower = more sensitive
    min_data_points_for_ml: int = 100
    
    # Performance parameters
    max_score_cache_size: int = 1000
    enable_real_time_scoring: bool = True
    scoring_frequency_seconds: int = 30
    
    # Data quality requirements
    min_data_quality_score: float = 0.7
    max_missing_data_percentage: float = 0.1


@dataclass
class BaselineMetrics:
    """Baseline metrics for comparison."""
    
    dimension: ScoringDimension
    baseline_score: float
    baseline_std: float
    sample_count: int
    calculation_date: datetime
    
    # Statistical bounds
    lower_control_limit: float
    upper_control_limit: float
    warning_lower_limit: float
    warning_upper_limit: float
    
    # Historical data summary
    min_score: float
    max_score: float
    median_score: float
    percentiles: Dict[int, float] = field(default_factory=dict)  # 25, 75, 90, 95
    
    def is_score_normal(self, score: float, sensitivity: float = 2.0) -> bool:
        """Check if score is within normal range."""
        z_score = abs((score - self.baseline_score) / max(self.baseline_std, 0.001))
        return z_score <= sensitivity
    
    def get_deviation_severity(self, score: float) -> SeverityLevel:
        """Get severity level for score deviation."""
        if score < self.lower_control_limit:
            return SeverityLevel.CRITICAL
        elif score < self.warning_lower_limit:
            return SeverityLevel.HIGH
        elif score > self.upper_control_limit:
            return SeverityLevel.MEDIUM  # Better than expected
        else:
            return SeverityLevel.INFO


class ScoringEngine:
    """Core reliability scoring engine."""
    
    def __init__(self, config: Optional[ScoringConfiguration] = None):
        self.config = config or ScoringConfiguration()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Internal state
        self._score_cache = deque(maxlen=self.config.max_score_cache_size)
        self._baseline_cache: Dict[ScoringDimension, BaselineMetrics] = {}
        self._anomaly_detector: Optional[IsolationForest] = None
        self._failure_predictor: Optional[RandomForestClassifier] = None
        self._scaler = StandardScaler()
        
        # Performance tracking
        self._scoring_times = deque(maxlen=100)
        self._last_baseline_update = datetime.utcnow() - timedelta(days=1)
    
    def calculate_dimension_score(
        self,
        dimension: ScoringDimension,
        metrics: PerformanceMetrics,
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> DimensionScore:
        """Calculate score for a specific dimension."""
        
        start_time = time.time()
        
        try:
            if dimension == ScoringDimension.CORRECTNESS:
                score = self._score_correctness(metrics)
            elif dimension == ScoringDimension.PERFORMANCE:
                score = self._score_performance(metrics)
            elif dimension == ScoringDimension.RESILIENCE:
                score = self._score_resilience(metrics)
            elif dimension == ScoringDimension.CONSISTENCY:
                score = self._score_consistency(metrics, historical_data)
            elif dimension == ScoringDimension.RESOURCE_USAGE:
                score = self._score_resource_usage(metrics)
            else:
                raise ValueError(f"Unknown dimension: {dimension}")
            
            # Get weight for dimension
            weight = getattr(self.config.weights, dimension.value)
            weighted_score = score * weight
            
            # Calculate statistical metrics
            confidence = self._calculate_confidence(metrics, historical_data)
            baseline_deviation = self._calculate_baseline_deviation(dimension, score)
            
            # Create dimension score
            dim_score = DimensionScore(
                dimension=dimension,
                raw_score=score,
                weighted_score=weighted_score,
                confidence=confidence,
                data_points=self._get_data_point_count(metrics),
                baseline_deviation=baseline_deviation,
                metrics=self._extract_dimension_metrics(dimension, metrics)
            )
            
            # Add statistical analysis if we have historical data
            if historical_data and len(historical_data) >= 5:
                self._add_statistical_analysis(dim_score, historical_data)
            
            execution_time = time.time() - start_time
            self.logger.debug(f"Calculated {dimension.value} score: {score:.2f} in {execution_time:.3f}s")
            
            return dim_score
            
        except Exception as e:
            self.logger.error(f"Error calculating {dimension.value} score: {e}")
            # Return default score
            return DimensionScore(
                dimension=dimension,
                raw_score=0.0,
                weighted_score=0.0,
                confidence=0.0,
                data_points=0,
                baseline_deviation=0.0
            )
    
    def calculate_composite_score(
        self,
        metrics: PerformanceMetrics,
        historical_data: Optional[List[Dict[str, Any]]] = None,
        agent_id: str = "",
        evaluation_id: str = ""
    ) -> ReliabilityScore:
        """Calculate comprehensive reliability score."""
        
        start_time = time.time()
        
        # Calculate dimension scores
        dimension_scores = {}
        weighted_sum = 0.0
        total_confidence = 0.0
        total_sample_size = 0
        
        for dimension in ScoringDimension:
            dim_score = self.calculate_dimension_score(dimension, metrics, historical_data)
            dimension_scores[dimension] = dim_score
            weighted_sum += dim_score.weighted_score
            total_confidence += dim_score.confidence
            total_sample_size += dim_score.data_points
        
        # Calculate overall confidence (average of dimension confidences)
        overall_confidence = total_confidence / len(ScoringDimension) if dimension_scores else 0.0
        
        # Create reliability score
        reliability_score = ReliabilityScore(
            composite_score=weighted_sum,
            dimension_scores=dimension_scores,
            agent_id=agent_id,
            evaluation_id=evaluation_id,
            duration=timedelta(seconds=time.time() - start_time),
            overall_confidence=overall_confidence,
            sample_size=total_sample_size
        )
        
        # Add statistical analysis
        self._add_composite_analysis(reliability_score, historical_data)
        
        # Predict failure risk if we have enough data
        if historical_data and len(historical_data) >= self.config.min_data_points_for_ml:
            reliability_score.failure_risk = self._predict_failure_risk(
                reliability_score, historical_data
            )
        
        # Cache the score
        self._score_cache.append(reliability_score)
        
        execution_time = time.time() - start_time
        self.logger.info(
            f"Calculated composite reliability score: {reliability_score.composite_score:.2f} "
            f"(grade: {reliability_score.get_grade()}) in {execution_time:.3f}s"
        )
        
        return reliability_score
    
    def _score_correctness(self, metrics: PerformanceMetrics) -> float:
        """Score correctness dimension (40% weight)."""
        
        components = []
        
        # Task completion rate (50% of correctness)
        if metrics.total_tasks > 0:
            completion_rate = metrics.completed_tasks / metrics.total_tasks
            components.append(('completion_rate', completion_rate * 100, 0.5))
        
        # Test pass rate (30% of correctness)
        if metrics.test_pass_rate > 0:
            components.append(('test_pass_rate', metrics.test_pass_rate * 100, 0.3))
        
        # Validation success rate (20% of correctness)
        if metrics.validation_success_rate > 0:
            components.append(('validation_success', metrics.validation_success_rate * 100, 0.2))
        
        # Calculate weighted score
        if not components:
            return 0.0
            
        total_score = sum(score * weight for _, score, weight in components)
        total_weight = sum(weight for _, _, weight in components)
        
        return min(100.0, total_score / total_weight if total_weight > 0 else 0.0)
    
    def _score_performance(self, metrics: PerformanceMetrics) -> float:
        """Score performance dimension (20% weight)."""
        
        components = []
        
        # Throughput score (40% of performance)
        if metrics.throughput > 0:
            # Score based on tasks per hour - higher is better
            # Use logarithmic scaling for throughput
            throughput_score = min(100, np.log10(metrics.throughput + 1) * 25)
            components.append(('throughput', throughput_score, 0.4))
        
        # Time efficiency (40% of performance)
        if metrics.average_time_per_task > 0:
            # Inverse relationship - faster is better
            # Assume 300s is baseline acceptable time
            time_score = min(100, (300 / metrics.average_time_per_task) * 100)
            components.append(('time_efficiency', time_score, 0.4))
        
        # Resource efficiency (20% of performance)
        if metrics.average_cpu_usage > 0 and metrics.average_memory_mb > 0:
            # Lower resource usage is better
            cpu_efficiency = max(0, 100 - metrics.average_cpu_usage)
            # Assume 1GB (1024MB) is reasonable baseline
            memory_efficiency = max(0, 100 - (metrics.average_memory_mb / 1024) * 50)
            resource_score = (cpu_efficiency + memory_efficiency) / 2
            components.append(('resource_efficiency', resource_score, 0.2))
        
        if not components:
            return 50.0  # Neutral score if no data
            
        total_score = sum(score * weight for _, score, weight in components)
        total_weight = sum(weight for _, _, weight in components)
        
        return min(100.0, total_score / total_weight if total_weight > 0 else 50.0)
    
    def _score_resilience(self, metrics: PerformanceMetrics) -> float:
        """Score resilience dimension (20% weight)."""
        
        components = []
        
        # Error recovery rate (40% of resilience)
        total_tasks = metrics.completed_tasks + metrics.failed_tasks + metrics.timeout_tasks
        if total_tasks > 0:
            # Success rate under stress
            success_rate = metrics.completed_tasks / total_tasks
            components.append(('error_recovery', success_rate * 100, 0.4))
        
        # Tool error handling (30% of resilience)
        if metrics.total_tool_calls > 0 and metrics.tool_error_rate >= 0:
            tool_resilience = (1 - metrics.tool_error_rate) * 100
            components.append(('tool_resilience', tool_resilience, 0.3))
        
        # Timeout handling (30% of resilience)
        if total_tasks > 0:
            timeout_resilience = (1 - metrics.timeout_tasks / total_tasks) * 100
            components.append(('timeout_resilience', timeout_resilience, 0.3))
        
        if not components:
            return 50.0
            
        total_score = sum(score * weight for _, score, weight in components)
        total_weight = sum(weight for _, _, weight in components)
        
        return min(100.0, total_score / total_weight if total_weight > 0 else 50.0)
    
    def _score_consistency(
        self,
        metrics: PerformanceMetrics,
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> float:
        """Score consistency dimension (10% weight)."""
        
        components = []
        
        # Time consistency (50% of consistency)
        if len(metrics.time_distribution) > 1:
            mean_time = statistics.mean(metrics.time_distribution)
            std_time = statistics.stdev(metrics.time_distribution)
            if mean_time > 0:
                cv = std_time / mean_time  # Coefficient of variation
                # Lower CV is more consistent
                time_consistency = max(0, 100 - (cv * 100))
                components.append(('time_consistency', time_consistency, 0.5))
        
        # Historical consistency (50% of consistency)
        if historical_data and len(historical_data) >= 5:
            historical_scores = [d.get('composite_score', 50) for d in historical_data[-10:]]
            if len(historical_scores) > 1:
                hist_mean = statistics.mean(historical_scores)
                hist_std = statistics.stdev(historical_scores)
                if hist_mean > 0:
                    hist_cv = hist_std / hist_mean
                    historical_consistency = max(0, 100 - (hist_cv * 100))
                    components.append(('historical_consistency', historical_consistency, 0.5))
        
        if not components:
            return 75.0  # Assume good consistency if no data to prove otherwise
            
        total_score = sum(score * weight for _, score, weight in components)
        total_weight = sum(weight for _, _, weight in components)
        
        return min(100.0, total_score / total_weight if total_weight > 0 else 75.0)
    
    def _score_resource_usage(self, metrics: PerformanceMetrics) -> float:
        """Score resource usage dimension (10% weight)."""
        
        components = []
        
        # CPU efficiency (40% of resource usage)
        if metrics.average_cpu_usage > 0:
            # Score inversely to CPU usage - lower is better
            cpu_score = max(0, 100 - metrics.average_cpu_usage)
            components.append(('cpu_efficiency', cpu_score, 0.4))
        
        # Memory efficiency (40% of resource usage)  
        if metrics.average_memory_mb > 0:
            # Assume 2GB (2048MB) is high usage, score inversely
            memory_score = max(0, 100 - (metrics.average_memory_mb / 2048) * 100)
            components.append(('memory_efficiency', memory_score, 0.4))
        
        # Token efficiency (20% of resource usage)
        if metrics.total_tokens_used > 0 and metrics.completed_tasks > 0:
            tokens_per_task = metrics.total_tokens_used / metrics.completed_tasks
            # Assume 10k tokens per task is reasonable baseline
            token_efficiency = max(0, 100 - (tokens_per_task / 10000) * 50)
            components.append(('token_efficiency', token_efficiency, 0.2))
        
        if not components:
            return 75.0  # Assume good efficiency if no data
            
        total_score = sum(score * weight for _, score, weight in components)
        total_weight = sum(weight for _, _, weight in components)
        
        return min(100.0, total_score / total_weight if total_weight > 0 else 75.0)
    
    def _calculate_confidence(
        self,
        metrics: PerformanceMetrics,
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> float:
        """Calculate statistical confidence in the score."""
        
        # Base confidence on sample size
        sample_size = max(
            metrics.total_tasks,
            len(metrics.time_distribution) if metrics.time_distribution else 0,
            len(metrics.resource_samples) if metrics.resource_samples else 0
        )
        
        # Confidence based on sample size (using statistical power analysis)
        if sample_size >= 100:
            base_confidence = 0.95
        elif sample_size >= 30:
            base_confidence = 0.80
        elif sample_size >= 10:
            base_confidence = 0.70
        elif sample_size >= 5:
            base_confidence = 0.60
        else:
            base_confidence = 0.30
        
        # Adjust confidence based on data quality
        if hasattr(metrics, 'data_quality_score'):
            base_confidence *= getattr(metrics, 'data_quality_score', 1.0)
        
        # Reduce confidence if we have very little historical context
        if not historical_data or len(historical_data) < 5:
            base_confidence *= 0.8
        
        return min(1.0, base_confidence)
    
    def _calculate_baseline_deviation(
        self,
        dimension: ScoringDimension,
        score: float
    ) -> float:
        """Calculate deviation from baseline for dimension."""
        
        baseline = self._baseline_cache.get(dimension)
        if not baseline:
            return 0.0
        
        if baseline.baseline_std == 0:
            return 0.0
            
        return (score - baseline.baseline_score) / baseline.baseline_std
    
    def _get_data_point_count(self, metrics: PerformanceMetrics) -> int:
        """Get total number of data points used in metrics."""
        return max(
            metrics.total_tasks,
            len(metrics.time_distribution) if metrics.time_distribution else 0,
            len(metrics.resource_samples) if metrics.resource_samples else 0
        )
    
    def _extract_dimension_metrics(
        self,
        dimension: ScoringDimension,
        metrics: PerformanceMetrics
    ) -> Dict[str, Any]:
        """Extract relevant metrics for a dimension."""
        
        if dimension == ScoringDimension.CORRECTNESS:
            return {
                'completion_rate': metrics.completed_tasks / max(metrics.total_tasks, 1),
                'test_pass_rate': metrics.test_pass_rate,
                'validation_success_rate': metrics.validation_success_rate
            }
        elif dimension == ScoringDimension.PERFORMANCE:
            return {
                'throughput': metrics.throughput,
                'average_time': metrics.average_time_per_task,
                'cpu_usage': metrics.average_cpu_usage,
                'memory_usage': metrics.average_memory_mb
            }
        elif dimension == ScoringDimension.RESILIENCE:
            return {
                'failed_tasks': metrics.failed_tasks,
                'timeout_tasks': metrics.timeout_tasks,
                'tool_error_rate': metrics.tool_error_rate
            }
        elif dimension == ScoringDimension.CONSISTENCY:
            return {
                'time_variance': statistics.variance(metrics.time_distribution) if len(metrics.time_distribution) > 1 else 0
            }
        elif dimension == ScoringDimension.RESOURCE_USAGE:
            return {
                'cpu_usage': metrics.average_cpu_usage,
                'memory_usage': metrics.average_memory_mb,
                'tokens_used': metrics.total_tokens_used
            }
        
        return {}
    
    def _add_statistical_analysis(
        self,
        dim_score: DimensionScore,
        historical_data: List[Dict[str, Any]]
    ):
        """Add statistical analysis to dimension score."""
        
        # Extract historical scores for this dimension
        historical_scores = []
        for data in historical_data:
            dim_scores = data.get('dimension_scores', {})
            if dim_score.dimension.value in dim_scores:
                historical_scores.append(dim_scores[dim_score.dimension.value]['raw_score'])
        
        if len(historical_scores) >= 5:
            # Calculate percentile rank
            dim_score.percentile_rank = stats.percentileofscore(
                historical_scores, dim_score.raw_score
            )
            
            # Calculate z-score
            mean_score = statistics.mean(historical_scores)
            std_score = statistics.stdev(historical_scores) if len(historical_scores) > 1 else 1.0
            dim_score.z_score = (dim_score.raw_score - mean_score) / max(std_score, 0.001)
            
            # Calculate trend slope using linear regression
            if len(historical_scores) >= 10:
                x = np.arange(len(historical_scores))
                slope, _, _, _, _ = stats.linregress(x, historical_scores)
                dim_score.trend_slope = slope
    
    def _add_composite_analysis(
        self,
        reliability_score: ReliabilityScore,
        historical_data: Optional[List[Dict[str, Any]]]
    ):
        """Add composite score analysis."""
        
        if not historical_data or len(historical_data) < 5:
            return
        
        # Extract historical composite scores
        historical_scores = [d.get('composite_score', 50) for d in historical_data]
        
        # Calculate confidence interval
        if len(historical_scores) >= 3:
            mean_score = statistics.mean(historical_scores)
            std_score = statistics.stdev(historical_scores) if len(historical_scores) > 1 else 5.0
            n = len(historical_scores)
            
            # 95% confidence interval
            margin = stats.t.ppf(0.975, n-1) * (std_score / np.sqrt(n)) if n > 1 else std_score
            reliability_score.confidence_interval = (
                max(0, mean_score - margin),
                min(100, mean_score + margin)
            )
        
        # Calculate percentile rank
        reliability_score.percentile_rank = stats.percentileofscore(
            historical_scores, reliability_score.composite_score
        )
        
        # Analyze trend
        if len(historical_scores) >= 10:
            x = np.arange(len(historical_scores))
            slope, _, r_value, _, _ = stats.linregress(x, historical_scores)
            
            reliability_score.trend_strength = abs(r_value)
            
            if slope > 0.5:
                reliability_score.trend_direction = "improving"
            elif slope < -0.5:
                reliability_score.trend_direction = "degrading"
            else:
                reliability_score.trend_direction = "stable"
        
        # Calculate volatility (coefficient of variation)
        if len(historical_scores) > 1:
            mean_score = statistics.mean(historical_scores)
            std_score = statistics.stdev(historical_scores)
            reliability_score.volatility = std_score / mean_score if mean_score > 0 else 0
    
    def _predict_failure_risk(
        self,
        reliability_score: ReliabilityScore,
        historical_data: List[Dict[str, Any]]
    ) -> float:
        """Predict failure risk using ML model."""
        
        try:
            # This is a simplified implementation
            # In production, you'd want a more sophisticated model
            
            # Extract features from historical data
            features = []
            labels = []
            
            for data in historical_data:
                score = data.get('composite_score', 50)
                # Simple binary classification: score < 60 is "failure"
                labels.append(1 if score < 60 else 0)
                
                # Extract features
                feature_vector = [
                    score,
                    data.get('overall_confidence', 0.5),
                    data.get('volatility', 0),
                ]
                
                # Add dimension scores as features
                dim_scores = data.get('dimension_scores', {})
                for dim in ScoringDimension:
                    dim_data = dim_scores.get(dim.value, {'raw_score': 50})
                    feature_vector.append(dim_data['raw_score'])
                
                features.append(feature_vector)
            
            if len(features) < 20:  # Not enough data for ML
                # Use simple heuristic
                if reliability_score.composite_score < 60:
                    return min(1.0, (60 - reliability_score.composite_score) / 60)
                else:
                    return 0.0
            
            # Train simple model
            X = np.array(features)
            y = np.array(labels)
            
            if len(np.unique(y)) < 2:  # No variation in labels
                return 0.0
                
            model = RandomForestClassifier(n_estimators=50, random_state=42)
            model.fit(X, y)
            
            # Predict for current score
            current_features = [
                reliability_score.composite_score,
                reliability_score.overall_confidence,
                reliability_score.volatility,
            ]
            
            for dim in ScoringDimension:
                dim_score = reliability_score.dimension_scores.get(dim, DimensionScore(dim, 50, 0, 0, 0, 0))
                current_features.append(dim_score.raw_score)
            
            prediction_proba = model.predict_proba([current_features])
            return float(prediction_proba[0][1])  # Probability of failure
            
        except Exception as e:
            self.logger.warning(f"Failed to predict failure risk: {e}")
            return 0.0


# Export key classes
__all__ = [
    'ScoringDimension', 'SeverityLevel', 'ScoringWeights', 'DimensionScore',
    'ReliabilityScore', 'ScoringConfiguration', 'BaselineMetrics', 'ScoringEngine'
]