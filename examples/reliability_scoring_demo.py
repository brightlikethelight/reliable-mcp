#!/usr/bin/env python3
"""
Comprehensive demo of the Reliability Scoring Engine.

This demo showcases:
1. Scoring individual MCP agents
2. Comparing multiple agents
3. Generating visual reports
4. ML-based insights and predictions
5. Historical trend analysis
"""

import asyncio
import random
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_reliability_lab.scoring import (
    ReliabilityScoringEngine,
    ScoringConfig,
    ReliabilityVisualizer
)


def generate_mock_test_results(num_tests: int = 20, success_rate: float = 0.85):
    """Generate mock test results for demo."""
    results = []
    for i in range(num_tests):
        success = random.random() < success_rate
        results.append({
            'test_id': f'test_{i}',
            'status': 'completed' if success else 'failed',
            'score': random.uniform(70, 100) if success else random.uniform(0, 60),
            'duration_ms': random.uniform(50, 500)
        })
    return results


def generate_mock_performance_metrics():
    """Generate mock performance metrics."""
    response_times = [random.uniform(0.05, 0.5) for _ in range(100)]
    return {
        'response_times': response_times,
        'duration_seconds': sum(response_times)
    }


def generate_mock_fault_tests(num_faults: int = 10, recovery_rate: float = 0.8):
    """Generate mock fault injection test results."""
    results = []
    for i in range(num_faults):
        recovered = random.random() < recovery_rate
        results.append({
            'fault_id': f'fault_{i}',
            'recovered': recovered,
            'recovery_time_ms': random.uniform(100, 5000) if recovered else 0,
            'retries': [True] * random.randint(1, 3) if recovered else []
        })
    return results


def generate_mock_resource_metrics():
    """Generate mock resource usage metrics."""
    return {
        'cpu_samples': [random.uniform(10, 60) for _ in range(50)],
        'memory_samples': [random.uniform(100, 500) for _ in range(50)],
        'io_operations': random.randint(1000, 10000),
        'network_bytes': random.randint(100000, 1000000)
    }


def generate_mock_consistency_results(num_runs: int = 5):
    """Generate mock consistency test results."""
    base_score = random.uniform(70, 90)
    results = []
    for i in range(num_runs):
        # Add some variance
        score = base_score + random.uniform(-5, 5)
        results.append({
            'run_id': f'run_{i}',
            'score': score,
            'duration_ms': random.uniform(100, 200),
            'output_hash': 'hash_common' if random.random() < 0.8 else f'hash_{i}'
        })
    return results


async def demo_basic_scoring():
    """Demonstrate basic agent scoring."""
    print("\n" + "="*60)
    print("DEMO 1: Basic Agent Scoring")
    print("="*60)
    
    # Initialize scoring engine
    config = ScoringConfig(
        confidence_level=0.95,
        enable_ml_insights=True,
        auto_generate_reports=True,
        report_format="html"
    )
    engine = ReliabilityScoringEngine(config)
    
    # Generate mock data for an agent
    test_results = generate_mock_test_results(30, success_rate=0.88)
    performance_metrics = generate_mock_performance_metrics()
    fault_tests = generate_mock_fault_tests(15, recovery_rate=0.85)
    resource_metrics = generate_mock_resource_metrics()
    consistency_results = generate_mock_consistency_results(5)
    
    # Score the agent
    score = await engine.score_agent(
        agent_id="demo_agent_v1",
        test_results=test_results,
        performance_metrics=performance_metrics,
        fault_test_results=fault_tests,
        resource_metrics=resource_metrics,
        multiple_run_results=consistency_results,
        agent_version="1.0.0",
        test_suite_id="comprehensive_suite"
    )
    
    # Display results
    print(f"\n📊 Agent: {score.agent_id}")
    print(f"   Version: {score.agent_version}")
    print(f"   Test Suite: {score.test_suite_id}")
    print(f"\n🎯 Overall Score: {score.composite_score:.1f} (Grade: {score.reliability_grade})")
    print(f"   Production Ready: {'✅ Yes' if score.is_production_ready else '❌ No'}")
    print(f"   Confidence Interval: {score.confidence_interval[0]:.1f}-{score.confidence_interval[1]:.1f}")
    
    print("\n📈 Dimension Breakdown:")
    for name, dim in score.dimensions.dimensions_dict.items():
        status = "✅" if dim.normalized_score >= 70 else "⚠️" if dim.normalized_score >= 50 else "❌"
        print(f"   {status} {name.replace('_', ' ').title()}: {dim.normalized_score:.1f} (weight: {dim.weight*100:.0f}%)")
    
    # Identify strengths and weaknesses
    weakest_dim, weakest_score = score.dimensions.get_weakest_dimension()
    strongest_dim, strongest_score = score.dimensions.get_strongest_dimension()
    
    print(f"\n💪 Strongest: {strongest_dim.replace('_', ' ').title()} ({strongest_score.normalized_score:.1f})")
    print(f"😰 Weakest: {weakest_dim.replace('_', ' ').title()} ({weakest_score.normalized_score:.1f})")
    
    # Show ML insights if available
    if 'ml_insights' in score.metadata:
        insights = score.metadata['ml_insights']
        print("\n🤖 ML Insights:")
        
        if insights.get('anomalies', {}).get('is_anomaly'):
            print(f"   ⚠️ Anomaly detected: {insights['anomalies']['interpretation']}")
        
        if 'failure_risk' in insights.get('predictions', {}):
            risk = insights['predictions']['failure_risk']
            risk_icon = "🔴" if risk['risk_level'] == 'high' else "🟡" if risk['risk_level'] == 'medium' else "🟢"
            print(f"   {risk_icon} Failure Risk: {risk['risk_level'].upper()} ({risk['probability']*100:.1f}%)")
        
        if insights.get('recommendations'):
            print("\n💡 Recommendations:")
            for rec in insights['recommendations'][:3]:
                print(f"   • {rec}")
    
    return score


async def demo_agent_comparison():
    """Demonstrate comparing multiple agents."""
    print("\n" + "="*60)
    print("DEMO 2: Multi-Agent Comparison")
    print("="*60)
    
    engine = ReliabilityScoringEngine()
    
    # Generate scores for multiple agents with different characteristics
    agents_config = [
        ("stable_agent", 0.90, 0.85, "Production-grade stable agent"),
        ("fast_agent", 0.75, 0.95, "High-performance but less reliable"),
        ("resilient_agent", 0.80, 0.95, "Excellent fault recovery"),
        ("efficient_agent", 0.70, 0.70, "Resource-optimized agent")
    ]
    
    scores = []
    for agent_id, success_rate, recovery_rate, description in agents_config:
        print(f"\n📦 Scoring {agent_id}: {description}")
        
        score = await engine.score_agent(
            agent_id=agent_id,
            test_results=generate_mock_test_results(20, success_rate),
            performance_metrics=generate_mock_performance_metrics(),
            fault_test_results=generate_mock_fault_tests(10, recovery_rate),
            resource_metrics=generate_mock_resource_metrics(),
            multiple_run_results=generate_mock_consistency_results(3),
            agent_version="1.0.0"
        )
        scores.append(score)
        print(f"   Score: {score.composite_score:.1f} (Grade: {score.reliability_grade})")
    
    # Compare agents
    comparison = await engine.compare_agents(scores)
    
    print("\n📊 Comparison Results:")
    print(f"   Best Overall: {comparison['best_overall'].agent_id} ({comparison['best_overall'].composite_score:.1f})")
    
    print("\n🏆 Dimension Leaders:")
    for dim, leader in comparison['dimension_leaders'].items():
        print(f"   {dim.replace('_', ' ').title()}: {leader['agent_id']} ({leader['score']:.1f})")
    
    print("\n📈 Statistical Summary:")
    stats = comparison['statistical_comparison']
    print(f"   Mean Score: {stats['mean']:.1f}")
    print(f"   Std Deviation: {stats['std_dev']:.1f}")
    print(f"   Significant Difference: {'Yes' if stats.get('significant_difference') else 'No'}")
    
    return scores


async def demo_visualizations(scores):
    """Demonstrate visualization generation."""
    print("\n" + "="*60)
    print("DEMO 3: Visualization Generation")
    print("="*60)
    
    visualizer = ReliabilityVisualizer()
    
    # Create reliability dashboard for the first agent
    score = scores[0] if scores else None
    if score:
        print(f"\n📊 Generating dashboard for {score.agent_id}...")
        
        # Prepare visualization data
        viz_data = {
            'composite_score': score.composite_score,
            'dimensions': score.dimensions.dimensions_dict,
            'score_history': [random.uniform(60, 95) for _ in range(30)],
            'performance_metrics': {
                'timestamps': [datetime.now() - timedelta(minutes=i) for i in range(20)],
                'response_times': [random.uniform(50, 200) for _ in range(20)]
            },
            'historical_scores': {
                'dates': [datetime.now() - timedelta(days=i) for i in range(30)],
                'scores': [random.uniform(70, 90) for _ in range(30)]
            }
        }
        
        # Create dashboard
        dashboard = visualizer.create_reliability_dashboard(viz_data, include_trends=True)
        
        # Save to file
        output_file = "reliability_dashboard.html"
        visualizer.save_figure(dashboard, output_file, format="html")
        print(f"   ✅ Dashboard saved to {output_file}")
        
        # Create dimension comparison chart
        print("\n📊 Generating dimension charts...")
        
        for chart_type in ["bar", "radar", "sunburst"]:
            fig = visualizer.create_dimension_chart(
                score.dimensions.dimensions_dict,
                chart_type=chart_type
            )
            output_file = f"dimensions_{chart_type}.html"
            visualizer.save_figure(fig, output_file, format="html")
            print(f"   ✅ {chart_type.title()} chart saved to {output_file}")
        
        # Create comparison chart for all agents
        if len(scores) > 1:
            print("\n📊 Generating agent comparison chart...")
            
            agents_data = [
                {
                    'agent_id': s.agent_id,
                    'correctness': s.dimensions.correctness.normalized_score,
                    'performance': s.dimensions.performance.normalized_score,
                    'resilience': s.dimensions.resilience.normalized_score,
                    'resource_efficiency': s.dimensions.resource_efficiency.normalized_score,
                    'consistency': s.dimensions.consistency.normalized_score
                }
                for s in scores
            ]
            
            comparison_fig = visualizer.create_comparison_chart(agents_data)
            visualizer.save_figure(comparison_fig, "agent_comparison.html", format="html")
            print(f"   ✅ Comparison chart saved to agent_comparison.html")


async def demo_ml_predictions():
    """Demonstrate ML-based predictions and insights."""
    print("\n" + "="*60)
    print("DEMO 4: ML-Based Predictions")
    print("="*60)
    
    engine = ReliabilityScoringEngine(
        ScoringConfig(enable_ml_insights=True)
    )
    
    # Generate historical data for training
    print("\n🤖 Training ML models on historical data...")
    historical_scores = []
    
    for i in range(50):
        score_value = 75 + random.uniform(-15, 15)
        historical_scores.append({
            'composite_score': score_value,
            'correctness': score_value + random.uniform(-5, 5),
            'performance': score_value + random.uniform(-10, 10),
            'resilience': score_value + random.uniform(-8, 8),
            'resource_efficiency': score_value + random.uniform(-7, 7),
            'consistency': score_value + random.uniform(-6, 6),
            'sample_size': random.randint(10, 50),
            'test_duration_seconds': random.uniform(10, 100)
        })
    
    # Train models
    if engine.ml_insights:
        await engine.ml_insights.train_models(historical_scores)
        print("   ✅ Models trained successfully")
        
        # Make predictions for a new agent
        print("\n🔮 Making predictions for new agent...")
        
        new_score = await engine.score_agent(
            agent_id="prediction_test_agent",
            test_results=generate_mock_test_results(15, success_rate=0.65),  # Lower success rate
            performance_metrics=generate_mock_performance_metrics(),
            fault_test_results=generate_mock_fault_tests(8, recovery_rate=0.60),  # Lower recovery
            resource_metrics=generate_mock_resource_metrics()
        )
        
        # Get failure risk prediction
        risk_prediction = await engine.predict_failure_risk(
            agent_id="prediction_test_agent",
            lookahead_hours=24
        )
        
        if 'error' not in risk_prediction:
            print(f"\n⚠️ Failure Risk Prediction (next 24 hours):")
            print(f"   Risk Level: {risk_prediction.get('risk_level', 'Unknown').upper()}")
            print(f"   Probability: {risk_prediction.get('probability', 0)*100:.1f}%")
            print(f"   Confidence: {risk_prediction.get('confidence_window', 'low')}")
            
            if risk_prediction.get('trend_adjustment'):
                print(f"   Trend Impact: {risk_prediction['trend_adjustment']}")
        
        # Find optimal configuration
        print("\n🔧 Finding optimal configuration...")
        
        test_configs = []
        for i in range(10):
            config_results = {
                'configuration': {
                    'timeout': random.choice([30, 60, 90]),
                    'retries': random.choice([1, 3, 5]),
                    'cache': random.choice([True, False])
                },
                'composite_score': random.uniform(60, 90)
            }
            test_configs.append(config_results)
        
        optimal = await engine.ml_insights.find_optimal_configuration(test_configs)
        
        if 'error' not in optimal:
            print(f"   Best Configuration: {optimal['optimal_configuration']}")
            print(f"   Expected Score: {optimal['expected_score']:.1f}")
            print(f"   Improvement Potential: +{optimal['improvement_potential']:.1f}")


async def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("MCP RELIABILITY SCORING ENGINE - COMPREHENSIVE DEMO")
    print("="*60)
    
    try:
        # Run basic scoring demo
        score = await demo_basic_scoring()
        
        # Run comparison demo
        scores = await demo_agent_comparison()
        
        # Run visualization demo
        await demo_visualizations(scores)
        
        # Run ML predictions demo
        await demo_ml_predictions()
        
        print("\n" + "="*60)
        print("✅ ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nGenerated files:")
        print("  • reliability_dashboard.html - Interactive dashboard")
        print("  • dimensions_*.html - Dimension visualizations")
        print("  • agent_comparison.html - Multi-agent comparison")
        print("  • reports/ - Generated reliability reports")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())