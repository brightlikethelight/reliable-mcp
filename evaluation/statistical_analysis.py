"""Statistical analysis framework for reliability metrics using scipy."""

import logging
import warnings
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import normaltest, shapiro, anderson, kstest
from scipy.signal import find_peaks
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score

from .reliability_scoring import ReliabilityScore, DimensionScore, ScoringDimension

logger = logging.getLogger(__name__)

# Suppress scipy warnings for cleaner output
warnings.filterwarnings('ignore', category=RuntimeWarning)


class DistributionType(Enum):
    """Statistical distribution types."""
    NORMAL = "normal"
    EXPONENTIAL = "exponential"
    UNIFORM = "uniform"
    BETA = "beta"
    GAMMA = "gamma"
    UNKNOWN = "unknown"


class TrendType(Enum):
    """Trend analysis types."""
    IMPROVING = "improving"
    DEGRADING = "degrading"
    STABLE = "stable"
    VOLATILE = "volatile"
    CYCLICAL = "cyclical"


@dataclass
class StatisticalSummary:
    """Statistical summary of a metric series."""
    
    # Basic statistics
    count: int
    mean: float
    median: float
    std: float
    variance: float
    min_value: float
    max_value: float
    
    # Distribution analysis
    skewness: float
    kurtosis: float
    distribution_type: DistributionType
    distribution_params: Dict[str, float]
    normality_p_value: float
    
    # Percentiles
    q25: float
    q75: float
    q90: float
    q95: float
    iqr: float
    
    # Outlier analysis
    outlier_count: int
    outlier_percentage: float
    outliers_lower: List[float]
    outliers_upper: List[float]


@dataclass
class ConfidenceInterval:
    """Statistical confidence interval."""
    
    confidence_level: float
    lower_bound: float
    upper_bound: float
    margin_of_error: float
    sample_size: int
    method: str  # t-distribution, bootstrap, etc.


@dataclass
class TrendAnalysis:
    """Comprehensive trend analysis results."""
    
    trend_type: TrendType
    slope: float
    intercept: float
    r_squared: float
    p_value: float
    confidence_interval: ConfidenceInterval
    
    # Advanced metrics
    trend_strength: float  # 0-1 scale
    change_points: List[int]  # Indices where trend changes
    seasonal_components: Optional[Dict[str, float]]
    volatility: float
    persistence: float  # How consistent the trend is


@dataclass 
class SignificanceTest:
    """Statistical significance test results."""
    
    test_name: str
    statistic: float
    p_value: float
    is_significant: bool
    alpha: float
    effect_size: Optional[float]
    power: Optional[float]
    interpretation: str


class StatisticalAnalyzer:
    """Comprehensive statistical analysis engine for reliability metrics."""
    
    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def analyze_series(self, data: List[float], timestamps: Optional[List[datetime]] = None) -> StatisticalSummary:
        """Perform comprehensive statistical analysis of a data series."""
        
        if not data or len(data) < 2:
            return self._empty_summary()
        
        data_array = np.array(data, dtype=float)
        
        # Remove any NaN or infinite values
        clean_data = data_array[np.isfinite(data_array)]
        
        if len(clean_data) < 2:
            return self._empty_summary()
        
        # Basic statistics
        count = len(clean_data)
        mean = np.mean(clean_data)
        median = np.median(clean_data)
        std = np.std(clean_data, ddof=1) if count > 1 else 0
        variance = np.var(clean_data, ddof=1) if count > 1 else 0
        
        # Percentiles
        percentiles = np.percentile(clean_data, [25, 75, 90, 95])
        q25, q75, q90, q95 = percentiles
        iqr = q75 - q25
        
        # Distribution analysis
        skewness = stats.skew(clean_data)
        kurtosis = stats.kurtosis(clean_data)
        
        # Test for normality
        normality_p = self._test_normality(clean_data)
        
        # Identify distribution type
        dist_type, dist_params = self._identify_distribution(clean_data)
        
        # Outlier analysis
        outliers_lower, outliers_upper, outlier_count = self._detect_outliers(clean_data, q25, q75, iqr)
        
        return StatisticalSummary(
            count=count,
            mean=mean,
            median=median,
            std=std,
            variance=variance,
            min_value=float(np.min(clean_data)),
            max_value=float(np.max(clean_data)),
            skewness=skewness,
            kurtosis=kurtosis,
            distribution_type=dist_type,
            distribution_params=dist_params,
            normality_p_value=normality_p,
            q25=q25,
            q75=q75,
            q90=q90,
            q95=q95,
            iqr=iqr,
            outlier_count=outlier_count,
            outlier_percentage=(outlier_count / count) * 100,
            outliers_lower=outliers_lower,
            outliers_upper=outliers_upper
        )
    
    def calculate_confidence_interval(
        self,
        data: List[float],
        confidence_level: Optional[float] = None,
        method: str = "t_distribution"
    ) -> ConfidenceInterval:
        """Calculate confidence interval for the mean."""
        
        conf_level = confidence_level or self.confidence_level
        alpha = 1 - conf_level
        
        data_array = np.array(data, dtype=float)
        clean_data = data_array[np.isfinite(data_array)]
        
        if len(clean_data) < 2:
            return ConfidenceInterval(
                confidence_level=conf_level,
                lower_bound=0.0,
                upper_bound=0.0,
                margin_of_error=0.0,
                sample_size=len(clean_data),
                method=method
            )
        
        sample_size = len(clean_data)
        mean = np.mean(clean_data)
        std_err = stats.sem(clean_data)
        
        if method == "t_distribution":
            # Student's t-distribution (preferred for small samples)
            t_stat = stats.t.ppf(1 - alpha/2, df=sample_size - 1)
            margin_error = t_stat * std_err
            
        elif method == "bootstrap":
            # Bootstrap confidence interval
            bootstrap_means = []
            n_bootstrap = 1000
            
            for _ in range(n_bootstrap):
                bootstrap_sample = np.random.choice(clean_data, size=sample_size, replace=True)
                bootstrap_means.append(np.mean(bootstrap_sample))
            
            lower_percentile = (alpha/2) * 100
            upper_percentile = (1 - alpha/2) * 100
            
            lower_bound = np.percentile(bootstrap_means, lower_percentile)
            upper_bound = np.percentile(bootstrap_means, upper_percentile)
            margin_error = max(mean - lower_bound, upper_bound - mean)
            
            return ConfidenceInterval(
                confidence_level=conf_level,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                margin_of_error=margin_error,
                sample_size=sample_size,
                method=method
            )
        
        else:  # normal distribution
            z_stat = stats.norm.ppf(1 - alpha/2)
            margin_error = z_stat * std_err
        
        lower_bound = mean - margin_error
        upper_bound = mean + margin_error
        
        return ConfidenceInterval(
            confidence_level=conf_level,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            margin_of_error=margin_error,
            sample_size=sample_size,
            method=method
        )
    
    def analyze_trend(
        self,
        data: List[float],
        timestamps: Optional[List[datetime]] = None
    ) -> TrendAnalysis:
        """Perform comprehensive trend analysis."""
        
        if not data or len(data) < 3:
            return self._empty_trend_analysis()
        
        data_array = np.array(data, dtype=float)
        clean_indices = np.isfinite(data_array)
        clean_data = data_array[clean_indices]
        
        if len(clean_data) < 3:
            return self._empty_trend_analysis()
        
        # Create time index
        if timestamps:
            clean_timestamps = np.array(timestamps)[clean_indices]
            # Convert to numeric (days since first timestamp)
            time_deltas = [(ts - clean_timestamps[0]).total_seconds() / 86400 for ts in clean_timestamps]
            x = np.array(time_deltas)
        else:
            x = np.arange(len(clean_data))
        
        # Linear regression for trend
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, clean_data)
        r_squared = r_value ** 2
        
        # Confidence interval for slope
        n = len(clean_data)
        t_stat = stats.t.ppf(1 - self.alpha/2, df=n-2)
        margin_error = t_stat * std_err
        
        slope_ci = ConfidenceInterval(
            confidence_level=self.confidence_level,
            lower_bound=slope - margin_error,
            upper_bound=slope + margin_error,
            margin_of_error=margin_error,
            sample_size=n,
            method="linear_regression"
        )
        
        # Determine trend type
        trend_type = self._classify_trend(slope, p_value, r_squared, clean_data)
        
        # Calculate trend strength (normalized R-squared)
        trend_strength = min(1.0, r_squared)
        
        # Detect change points
        change_points = self._detect_change_points(clean_data)
        
        # Calculate volatility (coefficient of variation of residuals)
        predicted = slope * x + intercept
        residuals = clean_data - predicted
        volatility = np.std(residuals) / np.mean(clean_data) if np.mean(clean_data) != 0 else 0
        
        # Calculate persistence (autocorrelation at lag 1)
        persistence = self._calculate_persistence(clean_data)
        
        return TrendAnalysis(
            trend_type=trend_type,
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            p_value=p_value,
            confidence_interval=slope_ci,
            trend_strength=trend_strength,
            change_points=change_points,
            seasonal_components=None,  # Could be extended for seasonal analysis
            volatility=volatility,
            persistence=persistence
        )
    
    def compare_distributions(
        self,
        data1: List[float],
        data2: List[float],
        test_type: str = "auto"
    ) -> SignificanceTest:
        """Compare two distributions using appropriate statistical tests."""
        
        data1_clean = np.array(data1)[np.isfinite(data1)]
        data2_clean = np.array(data2)[np.isfinite(data2)]
        
        if len(data1_clean) < 2 or len(data2_clean) < 2:
            return SignificanceTest(
                test_name="insufficient_data",
                statistic=0.0,
                p_value=1.0,
                is_significant=False,
                alpha=self.alpha,
                effect_size=None,
                power=None,
                interpretation="Insufficient data for comparison"
            )
        
        # Choose appropriate test
        if test_type == "auto":
            # Check normality of both distributions
            normal1 = self._test_normality(data1_clean) > 0.05
            normal2 = self._test_normality(data2_clean) > 0.05
            
            if normal1 and normal2:
                test_type = "t_test"
            else:
                test_type = "mann_whitney"
        
        if test_type == "t_test":
            # Independent t-test
            statistic, p_value = stats.ttest_ind(data1_clean, data2_clean)
            test_name = "Independent t-test"
            
            # Effect size (Cohen's d)
            pooled_std = np.sqrt(((len(data1_clean) - 1) * np.var(data1_clean, ddof=1) + 
                                 (len(data2_clean) - 1) * np.var(data2_clean, ddof=1)) / 
                                (len(data1_clean) + len(data2_clean) - 2))
            effect_size = (np.mean(data1_clean) - np.mean(data2_clean)) / pooled_std if pooled_std > 0 else 0
            
        elif test_type == "mann_whitney":
            # Mann-Whitney U test (non-parametric)
            statistic, p_value = stats.mannwhitneyu(data1_clean, data2_clean, alternative='two-sided')
            test_name = "Mann-Whitney U test"
            
            # Effect size (rank-biserial correlation)
            n1, n2 = len(data1_clean), len(data2_clean)
            effect_size = (2 * statistic / (n1 * n2)) - 1
            
        elif test_type == "ks_test":
            # Kolmogorov-Smirnov test
            statistic, p_value = stats.ks_2samp(data1_clean, data2_clean)
            test_name = "Kolmogorov-Smirnov test"
            effect_size = statistic  # KS statistic itself is an effect size measure
            
        else:
            raise ValueError(f"Unknown test type: {test_type}")
        
        # Interpret results
        is_significant = p_value < self.alpha
        
        if is_significant:
            if abs(effect_size) < 0.2:
                interpretation = "Statistically significant but small effect size"
            elif abs(effect_size) < 0.5:
                interpretation = "Statistically significant with medium effect size"
            else:
                interpretation = "Statistically significant with large effect size"
        else:
            interpretation = "No statistically significant difference"
        
        return SignificanceTest(
            test_name=test_name,
            statistic=statistic,
            p_value=p_value,
            is_significant=is_significant,
            alpha=self.alpha,
            effect_size=effect_size,
            power=None,  # Power analysis would require additional computation
            interpretation=interpretation
        )
    
    def detect_anomalies(
        self,
        data: List[float],
        method: str = "iqr",
        sensitivity: float = 1.5
    ) -> Tuple[List[int], List[float]]:
        """Detect anomalies in the data series."""
        
        data_array = np.array(data, dtype=float)
        clean_indices = np.isfinite(data_array)
        clean_data = data_array[clean_indices]
        
        if len(clean_data) < 4:
            return [], []
        
        anomaly_indices = []
        anomaly_values = []
        
        if method == "iqr":
            # Interquartile Range method
            q1, q3 = np.percentile(clean_data, [25, 75])
            iqr = q3 - q1
            lower_bound = q1 - sensitivity * iqr
            upper_bound = q3 + sensitivity * iqr
            
            for i, value in enumerate(data):
                if np.isfinite(value) and (value < lower_bound or value > upper_bound):
                    anomaly_indices.append(i)
                    anomaly_values.append(value)
        
        elif method == "zscore":
            # Z-score method
            mean = np.mean(clean_data)
            std = np.std(clean_data, ddof=1)
            
            if std > 0:
                for i, value in enumerate(data):
                    if np.isfinite(value):
                        z_score = abs((value - mean) / std)
                        if z_score > sensitivity:
                            anomaly_indices.append(i)
                            anomaly_values.append(value)
        
        elif method == "modified_zscore":
            # Modified Z-score using median and MAD
            median = np.median(clean_data)
            mad = np.median(np.abs(clean_data - median))
            
            if mad > 0:
                for i, value in enumerate(data):
                    if np.isfinite(value):
                        modified_z = 0.6745 * (value - median) / mad
                        if abs(modified_z) > sensitivity:
                            anomaly_indices.append(i)
                            anomaly_values.append(value)
        
        return anomaly_indices, anomaly_values
    
    def calculate_statistical_control_limits(
        self,
        data: List[float],
        control_type: str = "3sigma"
    ) -> Dict[str, float]:
        """Calculate statistical control limits for process control."""
        
        data_array = np.array(data, dtype=float)
        clean_data = data_array[np.isfinite(data_array)]
        
        if len(clean_data) < 3:
            return {"mean": 0, "lcl": 0, "ucl": 0, "warning_lcl": 0, "warning_ucl": 0}
        
        mean = np.mean(clean_data)
        std = np.std(clean_data, ddof=1)
        
        if control_type == "3sigma":
            # 3-sigma control limits (99.7% of data should fall within)
            ucl = mean + 3 * std
            lcl = mean - 3 * std
            warning_ucl = mean + 2 * std
            warning_lcl = mean - 2 * std
            
        elif control_type == "2sigma":
            # 2-sigma control limits (95% of data should fall within)
            ucl = mean + 2 * std
            lcl = mean - 2 * std
            warning_ucl = mean + 1.5 * std
            warning_lcl = mean - 1.5 * std
            
        else:
            raise ValueError(f"Unknown control type: {control_type}")
        
        return {
            "mean": mean,
            "std": std,
            "ucl": ucl,
            "lcl": lcl,
            "warning_ucl": warning_ucl,
            "warning_lcl": warning_lcl
        }
    
    def _test_normality(self, data: np.ndarray) -> float:
        """Test for normality using multiple tests."""
        
        if len(data) < 3:
            return 0.0
        
        # Use Shapiro-Wilk for small samples (< 50), Anderson-Darling for larger
        if len(data) <= 50:
            try:
                _, p_value = shapiro(data)
                return p_value
            except:
                return 0.0
        else:
            try:
                # Anderson-Darling test
                result = anderson(data, dist='norm')
                # Convert to approximate p-value
                critical_value = result.critical_values[2]  # 5% significance level
                if result.statistic < critical_value:
                    return 0.1  # Approximate p-value > 0.05
                else:
                    return 0.01  # Approximate p-value < 0.05
            except:
                return 0.0
    
    def _identify_distribution(self, data: np.ndarray) -> Tuple[DistributionType, Dict[str, float]]:
        """Identify the best-fitting distribution."""
        
        if len(data) < 10:
            return DistributionType.UNKNOWN, {}
        
        # Test common distributions
        distributions = [
            (stats.norm, DistributionType.NORMAL),
            (stats.expon, DistributionType.EXPONENTIAL),
            (stats.uniform, DistributionType.UNIFORM),
            (stats.beta, DistributionType.BETA),
            (stats.gamma, DistributionType.GAMMA)
        ]
        
        best_dist = DistributionType.UNKNOWN
        best_params = {}
        best_p_value = 0
        
        for dist, dist_type in distributions:
            try:
                # Fit distribution
                params = dist.fit(data)
                
                # Kolmogorov-Smirnov test
                ks_stat, p_value = kstest(data, lambda x: dist.cdf(x, *params))
                
                if p_value > best_p_value:
                    best_p_value = p_value
                    best_dist = dist_type
                    
                    # Store parameters with meaningful names
                    if dist_type == DistributionType.NORMAL:
                        best_params = {"mean": params[0], "std": params[1]}
                    elif dist_type == DistributionType.EXPONENTIAL:
                        best_params = {"scale": params[1]}
                    elif dist_type == DistributionType.UNIFORM:
                        best_params = {"low": params[0], "high": params[0] + params[1]}
                    elif dist_type == DistributionType.BETA:
                        best_params = {"alpha": params[0], "beta": params[1]}
                    elif dist_type == DistributionType.GAMMA:
                        best_params = {"shape": params[0], "scale": params[2]}
                        
            except Exception:
                continue
        
        return best_dist, best_params
    
    def _detect_outliers(
        self, 
        data: np.ndarray, 
        q25: float, 
        q75: float, 
        iqr: float
    ) -> Tuple[List[float], List[float], int]:
        """Detect outliers using IQR method."""
        
        lower_bound = q25 - 1.5 * iqr
        upper_bound = q75 + 1.5 * iqr
        
        outliers_lower = [x for x in data if x < lower_bound]
        outliers_upper = [x for x in data if x > upper_bound]
        outlier_count = len(outliers_lower) + len(outliers_upper)
        
        return outliers_lower, outliers_upper, outlier_count
    
    def _classify_trend(
        self, 
        slope: float, 
        p_value: float, 
        r_squared: float, 
        data: np.ndarray
    ) -> TrendType:
        """Classify the type of trend."""
        
        # Check if trend is statistically significant
        if p_value > 0.05 or r_squared < 0.1:
            # No significant trend, check for volatility
            cv = np.std(data) / np.mean(data) if np.mean(data) != 0 else 0
            if cv > 0.3:  # High coefficient of variation
                return TrendType.VOLATILE
            else:
                return TrendType.STABLE
        
        # Significant trend
        if slope > 0:
            return TrendType.IMPROVING
        else:
            return TrendType.DEGRADING
    
    def _detect_change_points(self, data: np.ndarray, min_size: int = 5) -> List[int]:
        """Detect change points in the data series."""
        
        if len(data) < 2 * min_size:
            return []
        
        change_points = []
        
        # Simple change point detection using sliding window variance
        window_size = max(min_size, len(data) // 10)
        
        for i in range(window_size, len(data) - window_size):
            # Calculate variance before and after potential change point
            before_var = np.var(data[i-window_size:i])
            after_var = np.var(data[i:i+window_size])
            
            # If variance changes significantly, mark as change point
            if before_var > 0 and after_var > 0:
                var_ratio = max(before_var, after_var) / min(before_var, after_var)
                if var_ratio > 2.0:  # Threshold for significant variance change
                    change_points.append(i)
        
        return change_points
    
    def _calculate_persistence(self, data: np.ndarray) -> float:
        """Calculate persistence (autocorrelation at lag 1)."""
        
        if len(data) < 3:
            return 0.0
        
        # Calculate lag-1 autocorrelation
        try:
            correlation = np.corrcoef(data[:-1], data[1:])[0, 1]
            return correlation if not np.isnan(correlation) else 0.0
        except Exception:
            return 0.0
    
    def _empty_summary(self) -> StatisticalSummary:
        """Return empty statistical summary."""
        return StatisticalSummary(
            count=0, mean=0.0, median=0.0, std=0.0, variance=0.0,
            min_value=0.0, max_value=0.0, skewness=0.0, kurtosis=0.0,
            distribution_type=DistributionType.UNKNOWN, distribution_params={},
            normality_p_value=0.0, q25=0.0, q75=0.0, q90=0.0, q95=0.0,
            iqr=0.0, outlier_count=0, outlier_percentage=0.0,
            outliers_lower=[], outliers_upper=[]
        )
    
    def _empty_trend_analysis(self) -> TrendAnalysis:
        """Return empty trend analysis."""
        return TrendAnalysis(
            trend_type=TrendType.STABLE, slope=0.0, intercept=0.0,
            r_squared=0.0, p_value=1.0,
            confidence_interval=ConfidenceInterval(
                confidence_level=self.confidence_level,
                lower_bound=0.0, upper_bound=0.0, margin_of_error=0.0,
                sample_size=0, method="none"
            ),
            trend_strength=0.0, change_points=[], seasonal_components=None,
            volatility=0.0, persistence=0.0
        )


class ReliabilityStatistics:
    """Specialized statistical analysis for reliability scores."""
    
    def __init__(self):
        self.analyzer = StatisticalAnalyzer()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def analyze_dimension_performance(
        self,
        scores: List[ReliabilityScore],
        dimension: ScoringDimension
    ) -> Dict[str, Any]:
        """Analyze performance of a specific dimension over time."""
        
        # Extract dimension scores
        dimension_values = []
        timestamps = []
        
        for score in scores:
            if dimension in score.dimension_scores:
                dimension_values.append(score.dimension_scores[dimension].raw_score)
                timestamps.append(score.timestamp)
        
        if len(dimension_values) < 2:
            return {"error": "Insufficient data for analysis"}
        
        # Perform statistical analysis
        summary = self.analyzer.analyze_series(dimension_values, timestamps)
        trend = self.analyzer.analyze_trend(dimension_values, timestamps)
        confidence_interval = self.analyzer.calculate_confidence_interval(dimension_values)
        control_limits = self.analyzer.calculate_statistical_control_limits(dimension_values)
        
        # Detect anomalies
        anomaly_indices, anomaly_values = self.analyzer.detect_anomalies(dimension_values)
        
        return {
            "dimension": dimension.value,
            "statistical_summary": summary,
            "trend_analysis": trend,
            "confidence_interval": confidence_interval,
            "control_limits": control_limits,
            "anomalies": {
                "count": len(anomaly_indices),
                "indices": anomaly_indices,
                "values": anomaly_values,
                "percentage": (len(anomaly_indices) / len(dimension_values)) * 100
            }
        }
    
    def compare_agents(
        self,
        agent1_scores: List[ReliabilityScore],
        agent2_scores: List[ReliabilityScore],
        dimension: Optional[ScoringDimension] = None
    ) -> Dict[str, Any]:
        """Compare reliability performance between two agents."""
        
        if dimension:
            # Compare specific dimension
            agent1_values = [s.dimension_scores[dimension].raw_score 
                           for s in agent1_scores if dimension in s.dimension_scores]
            agent2_values = [s.dimension_scores[dimension].raw_score 
                           for s in agent2_scores if dimension in s.dimension_scores]
            metric_name = f"{dimension.value}_score"
        else:
            # Compare composite scores
            agent1_values = [s.composite_score for s in agent1_scores]
            agent2_values = [s.composite_score for s in agent2_scores]
            metric_name = "composite_score"
        
        if len(agent1_values) < 2 or len(agent2_values) < 2:
            return {"error": "Insufficient data for comparison"}
        
        # Statistical comparison
        significance_test = self.analyzer.compare_distributions(agent1_values, agent2_values)
        
        # Individual summaries
        agent1_summary = self.analyzer.analyze_series(agent1_values)
        agent2_summary = self.analyzer.analyze_series(agent2_values)
        
        return {
            "metric": metric_name,
            "agent1_summary": agent1_summary,
            "agent2_summary": agent2_summary,
            "significance_test": significance_test,
            "practical_difference": {
                "mean_difference": agent1_summary.mean - agent2_summary.mean,
                "relative_difference": ((agent1_summary.mean - agent2_summary.mean) / 
                                      agent2_summary.mean * 100) if agent2_summary.mean != 0 else 0,
                "better_agent": 1 if agent1_summary.mean > agent2_summary.mean else 2
            }
        }


# Export key classes
__all__ = [
    'DistributionType', 'TrendType', 'StatisticalSummary', 'ConfidenceInterval',
    'TrendAnalysis', 'SignificanceTest', 'StatisticalAnalyzer', 'ReliabilityStatistics'
]