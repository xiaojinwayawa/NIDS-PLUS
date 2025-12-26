"""
False Positive Management Module
Implements feedback-driven false positive governance for continuous improvement.

补充需求 D：可解释性闭环（解释驱动的误报治理）
"""
import os
import json
import time
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

from logging_config import app_logger as logger


@dataclass
class FalsePositiveFeedback:
    """Record of a false positive feedback"""
    alert_id: int
    timestamp: datetime
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    attack_type: str
    confidence: float
    features: Dict[str, float]  # Feature values at detection time
    shap_values: Dict[str, float]  # SHAP explanation
    marked_by: int  # User ID
    reason: str = ""  # Optional reason from user


@dataclass
class GovernanceRule:
    """A rule for false positive governance"""
    rule_id: str
    rule_type: str  # 'threshold', 'whitelist', 'feature_rule'
    created_at: datetime
    is_active: bool = True
    
    # For threshold rules
    threshold_adjustment: float = 0.0
    
    # For whitelist rules
    whitelist_ips: List[str] = field(default_factory=list)
    whitelist_ports: List[int] = field(default_factory=list)
    
    # For feature rules
    feature_name: str = ""
    feature_condition: str = ""  # 'lt', 'gt', 'eq'
    feature_value: float = 0.0
    
    # Metrics
    fp_prevented: int = 0
    fn_caused: int = 0


@dataclass
class GovernanceMetrics:
    """Metrics for governance effectiveness"""
    period_start: datetime
    period_end: datetime
    total_alerts: int = 0
    false_positives: int = 0
    true_positives: int = 0
    false_negatives: int = 0
    fpr_before: float = 0.0  # False positive rate before governance
    fpr_after: float = 0.0   # False positive rate after governance
    fnr_before: float = 0.0  # False negative rate before
    fnr_after: float = 0.0   # False negative rate after


class FalsePositiveManager:
    """
    Manages false positive feedback and governance strategies.
    Implements a closed-loop system for continuous FP reduction.
    """
    
    def __init__(self, data_dir: str = None):
        # Get project root
        if data_dir is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(backend_dir)
            data_dir = os.path.join(project_root, "data", "fp_governance")
        
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        # Storage
        self.feedbacks: List[FalsePositiveFeedback] = []
        self.rules: Dict[str, GovernanceRule] = {}
        self.metrics_history: List[GovernanceMetrics] = []
        
        # Configuration
        self.min_feedbacks_for_rule = 5  # Minimum FP feedbacks to generate a rule
        self.confidence_threshold = 0.5  # Default detection threshold
        self.threshold_adjustment_step = 0.05
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Load existing data
        self._load_data()
    
    def _load_data(self):
        """Load existing feedbacks and rules from disk"""
        try:
            # Load feedbacks
            feedbacks_path = os.path.join(self.data_dir, "feedbacks.json")
            if os.path.exists(feedbacks_path):
                with open(feedbacks_path, 'r') as f:
                    data = json.load(f)
                    for item in data:
                        item['timestamp'] = datetime.fromisoformat(item['timestamp'])
                        self.feedbacks.append(FalsePositiveFeedback(**item))
            
            # Load rules
            rules_path = os.path.join(self.data_dir, "rules.json")
            if os.path.exists(rules_path):
                with open(rules_path, 'r') as f:
                    data = json.load(f)
                    for rule_id, rule_data in data.items():
                        rule_data['created_at'] = datetime.fromisoformat(rule_data['created_at'])
                        self.rules[rule_id] = GovernanceRule(**rule_data)
            
            logger.info(f"Loaded {len(self.feedbacks)} feedbacks and {len(self.rules)} rules")
            
        except Exception as e:
            logger.error(f"Error loading FP governance data: {e}")
    
    def _save_data(self):
        """Save feedbacks and rules to disk"""
        try:
            # Save feedbacks
            feedbacks_path = os.path.join(self.data_dir, "feedbacks.json")
            feedbacks_data = []
            for fb in self.feedbacks:
                fb_dict = asdict(fb)
                fb_dict['timestamp'] = fb.timestamp.isoformat()
                feedbacks_data.append(fb_dict)
            
            with open(feedbacks_path, 'w') as f:
                json.dump(feedbacks_data, f, indent=2)
            
            # Save rules
            rules_path = os.path.join(self.data_dir, "rules.json")
            rules_data = {}
            for rule_id, rule in self.rules.items():
                rule_dict = asdict(rule)
                rule_dict['created_at'] = rule.created_at.isoformat()
                rules_data[rule_id] = rule_dict
            
            with open(rules_path, 'w') as f:
                json.dump(rules_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving FP governance data: {e}")
    
    def record_feedback(self, 
                       alert_id: int,
                       src_ip: str,
                       dst_ip: str,
                       src_port: int,
                       dst_port: int,
                       protocol: str,
                       attack_type: str,
                       confidence: float,
                       features: Dict[str, float],
                       shap_values: Dict[str, float],
                       marked_by: int,
                       reason: str = "") -> FalsePositiveFeedback:
        """
        Record a false positive feedback from user.
        
        Returns:
            The created feedback record
        """
        with self.lock:
            feedback = FalsePositiveFeedback(
                alert_id=alert_id,
                timestamp=datetime.now(),
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=src_port,
                dst_port=dst_port,
                protocol=protocol,
                attack_type=attack_type,
                confidence=confidence,
                features=features,
                shap_values=shap_values,
                marked_by=marked_by,
                reason=reason
            )
            
            self.feedbacks.append(feedback)
            self._save_data()
            
            logger.info(f"Recorded FP feedback for alert {alert_id}")
            
            # Check if we should generate new rules
            self._check_and_generate_rules()
            
            return feedback

    def _check_and_generate_rules(self):
        """Check if we have enough feedback to generate governance rules"""
        if len(self.feedbacks) < self.min_feedbacks_for_rule:
            return
        
        # Analyze recent feedbacks
        recent_feedbacks = [fb for fb in self.feedbacks 
                          if fb.timestamp > datetime.now() - timedelta(days=7)]
        
        if len(recent_feedbacks) < self.min_feedbacks_for_rule:
            return
        
        # Generate suggestions
        suggestions = self.generate_governance_suggestions()
        
        # Auto-apply high-confidence suggestions
        for suggestion in suggestions:
            if suggestion.get("confidence", 0) > 0.8:
                self._apply_suggestion(suggestion)
    
    def generate_governance_suggestions(self) -> List[Dict[str, Any]]:
        """
        Analyze false positive patterns and generate governance suggestions.
        
        Returns:
            List of suggestion dictionaries
        """
        suggestions = []
        
        if len(self.feedbacks) < self.min_feedbacks_for_rule:
            return suggestions
        
        # Analyze IP patterns
        ip_suggestions = self._analyze_ip_patterns()
        suggestions.extend(ip_suggestions)
        
        # Analyze port patterns
        port_suggestions = self._analyze_port_patterns()
        suggestions.extend(port_suggestions)
        
        # Analyze feature patterns using SHAP
        feature_suggestions = self._analyze_feature_patterns()
        suggestions.extend(feature_suggestions)
        
        # Analyze threshold
        threshold_suggestion = self._analyze_threshold()
        if threshold_suggestion:
            suggestions.append(threshold_suggestion)
        
        return suggestions
    
    def _analyze_ip_patterns(self) -> List[Dict[str, Any]]:
        """Analyze IP-based false positive patterns"""
        suggestions = []
        
        # Count FPs by source IP
        src_ip_counts = defaultdict(int)
        for fb in self.feedbacks:
            src_ip_counts[fb.src_ip] += 1
        
        # Find IPs with high FP counts
        for ip, count in src_ip_counts.items():
            if count >= self.min_feedbacks_for_rule:
                suggestions.append({
                    "type": "whitelist_ip",
                    "ip": ip,
                    "count": count,
                    "confidence": min(count / 10, 1.0),
                    "description": f"IP {ip} has {count} false positives. Consider whitelisting."
                })
        
        return suggestions
    
    def _analyze_port_patterns(self) -> List[Dict[str, Any]]:
        """Analyze port-based false positive patterns"""
        suggestions = []
        
        # Count FPs by destination port
        port_counts = defaultdict(int)
        for fb in self.feedbacks:
            port_counts[fb.dst_port] += 1
        
        # Find ports with high FP counts
        for port, count in port_counts.items():
            if count >= self.min_feedbacks_for_rule and port > 0:
                suggestions.append({
                    "type": "whitelist_port",
                    "port": port,
                    "count": count,
                    "confidence": min(count / 10, 1.0),
                    "description": f"Port {port} has {count} false positives. Consider whitelisting."
                })
        
        return suggestions
    
    def _analyze_feature_patterns(self) -> List[Dict[str, Any]]:
        """Analyze feature-based patterns using SHAP values"""
        suggestions = []
        
        if not self.feedbacks:
            return suggestions
        
        # Aggregate SHAP values across feedbacks
        feature_shap_sums = defaultdict(float)
        feature_counts = defaultdict(int)
        
        for fb in self.feedbacks:
            for feature, shap_val in fb.shap_values.items():
                feature_shap_sums[feature] += abs(shap_val)
                feature_counts[feature] += 1
        
        # Find features that consistently contribute to FPs
        for feature, total_shap in feature_shap_sums.items():
            count = feature_counts[feature]
            avg_shap = total_shap / count if count > 0 else 0
            
            if avg_shap > 0.1 and count >= self.min_feedbacks_for_rule:
                # Get average feature value for FPs
                feature_values = [fb.features.get(feature, 0) for fb in self.feedbacks 
                                 if feature in fb.features]
                avg_value = np.mean(feature_values) if feature_values else 0
                
                suggestions.append({
                    "type": "feature_rule",
                    "feature": feature,
                    "avg_shap": avg_shap,
                    "avg_value": avg_value,
                    "count": count,
                    "confidence": min(avg_shap * count / 10, 1.0),
                    "description": f"Feature '{feature}' contributes significantly to FPs (avg SHAP: {avg_shap:.3f})"
                })
        
        return suggestions
    
    def _analyze_threshold(self) -> Optional[Dict[str, Any]]:
        """Analyze if threshold adjustment would help"""
        if len(self.feedbacks) < self.min_feedbacks_for_rule:
            return None
        
        # Get confidence values of FPs
        fp_confidences = [fb.confidence for fb in self.feedbacks]
        avg_confidence = np.mean(fp_confidences)
        
        # If many FPs are just above threshold, suggest raising it
        near_threshold = sum(1 for c in fp_confidences if c < self.confidence_threshold + 0.1)
        
        if near_threshold > len(fp_confidences) * 0.5:
            new_threshold = self.confidence_threshold + self.threshold_adjustment_step
            return {
                "type": "threshold",
                "current_threshold": self.confidence_threshold,
                "suggested_threshold": new_threshold,
                "near_threshold_count": near_threshold,
                "confidence": near_threshold / len(fp_confidences),
                "description": f"Many FPs ({near_threshold}) are near threshold. Consider raising to {new_threshold:.2f}"
            }
        
        return None
    
    def _apply_suggestion(self, suggestion: Dict[str, Any]):
        """Apply a governance suggestion as a rule"""
        rule_id = f"auto_{suggestion['type']}_{int(time.time())}"
        
        if suggestion["type"] == "whitelist_ip":
            rule = GovernanceRule(
                rule_id=rule_id,
                rule_type="whitelist",
                created_at=datetime.now(),
                whitelist_ips=[suggestion["ip"]]
            )
        elif suggestion["type"] == "whitelist_port":
            rule = GovernanceRule(
                rule_id=rule_id,
                rule_type="whitelist",
                created_at=datetime.now(),
                whitelist_ports=[suggestion["port"]]
            )
        elif suggestion["type"] == "threshold":
            rule = GovernanceRule(
                rule_id=rule_id,
                rule_type="threshold",
                created_at=datetime.now(),
                threshold_adjustment=suggestion["suggested_threshold"] - suggestion["current_threshold"]
            )
            self.confidence_threshold = suggestion["suggested_threshold"]
        elif suggestion["type"] == "feature_rule":
            rule = GovernanceRule(
                rule_id=rule_id,
                rule_type="feature_rule",
                created_at=datetime.now(),
                feature_name=suggestion["feature"],
                feature_condition="lt",
                feature_value=suggestion["avg_value"]
            )
        else:
            return
        
        self.rules[rule_id] = rule
        self._save_data()
        logger.info(f"Applied governance rule: {rule_id}")

    def apply_governance(self, 
                        src_ip: str, 
                        dst_ip: str,
                        src_port: int,
                        dst_port: int,
                        confidence: float,
                        features: Dict[str, float] = None) -> Tuple[bool, float, str]:
        """
        Apply governance rules to a detection result.
        
        Args:
            src_ip: Source IP
            dst_ip: Destination IP
            src_port: Source port
            dst_port: Destination port
            confidence: Detection confidence
            features: Feature values (optional)
            
        Returns:
            Tuple of (should_alert, adjusted_confidence, reason)
        """
        with self.lock:
            adjusted_confidence = confidence
            
            for rule_id, rule in self.rules.items():
                if not rule.is_active:
                    continue
                
                # Check whitelist rules
                if rule.rule_type == "whitelist":
                    if src_ip in rule.whitelist_ips or dst_ip in rule.whitelist_ips:
                        rule.fp_prevented += 1
                        return False, 0.0, f"IP whitelisted by rule {rule_id}"
                    
                    if src_port in rule.whitelist_ports or dst_port in rule.whitelist_ports:
                        rule.fp_prevented += 1
                        return False, 0.0, f"Port whitelisted by rule {rule_id}"
                
                # Check threshold rules
                elif rule.rule_type == "threshold":
                    adjusted_confidence = confidence - rule.threshold_adjustment
                
                # Check feature rules
                elif rule.rule_type == "feature_rule" and features:
                    feature_val = features.get(rule.feature_name, 0)
                    
                    if rule.feature_condition == "lt" and feature_val < rule.feature_value:
                        rule.fp_prevented += 1
                        return False, 0.0, f"Feature rule {rule_id} matched"
                    elif rule.feature_condition == "gt" and feature_val > rule.feature_value:
                        rule.fp_prevented += 1
                        return False, 0.0, f"Feature rule {rule_id} matched"
            
            # Apply adjusted threshold
            should_alert = adjusted_confidence > self.confidence_threshold
            
            return should_alert, adjusted_confidence, ""
    
    def add_rule(self, rule: GovernanceRule) -> str:
        """Add a manual governance rule"""
        with self.lock:
            self.rules[rule.rule_id] = rule
            self._save_data()
            logger.info(f"Added governance rule: {rule.rule_id}")
            return rule.rule_id
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a governance rule"""
        with self.lock:
            if rule_id in self.rules:
                del self.rules[rule_id]
                self._save_data()
                logger.info(f"Removed governance rule: {rule_id}")
                return True
            return False
    
    def toggle_rule(self, rule_id: str, is_active: bool) -> bool:
        """Enable or disable a rule"""
        with self.lock:
            if rule_id in self.rules:
                self.rules[rule_id].is_active = is_active
                self._save_data()
                return True
            return False
    
    def rollback_rule(self, rule_id: str) -> bool:
        """Rollback (remove) a rule and restore previous state"""
        return self.remove_rule(rule_id)
    
    def get_metrics_comparison(self, 
                              days_before: int = 7,
                              days_after: int = 7) -> Dict[str, Any]:
        """
        Get before/after comparison of FP/FN rates.
        
        Args:
            days_before: Days to look back before rules
            days_after: Days to look at after rules
            
        Returns:
            Comparison metrics
        """
        now = datetime.now()
        
        # Get feedbacks before and after rules were applied
        rule_dates = [r.created_at for r in self.rules.values()]
        if not rule_dates:
            return {"message": "No rules applied yet"}
        
        earliest_rule = min(rule_dates)
        
        feedbacks_before = [fb for fb in self.feedbacks 
                          if fb.timestamp < earliest_rule]
        feedbacks_after = [fb for fb in self.feedbacks 
                         if fb.timestamp >= earliest_rule]
        
        # Calculate metrics
        fp_count_before = len(feedbacks_before)
        fp_count_after = len(feedbacks_after)
        
        # Get rule effectiveness
        total_prevented = sum(r.fp_prevented for r in self.rules.values())
        total_fn_caused = sum(r.fn_caused for r in self.rules.values())
        
        return {
            "period_before": {
                "start": (earliest_rule - timedelta(days=days_before)).isoformat(),
                "end": earliest_rule.isoformat(),
                "false_positives": fp_count_before
            },
            "period_after": {
                "start": earliest_rule.isoformat(),
                "end": now.isoformat(),
                "false_positives": fp_count_after,
                "fp_prevented_by_rules": total_prevented,
                "fn_caused_by_rules": total_fn_caused
            },
            "improvement": {
                "fp_reduction": fp_count_before - fp_count_after if fp_count_before > 0 else 0,
                "fp_reduction_percent": ((fp_count_before - fp_count_after) / fp_count_before * 100) 
                                       if fp_count_before > 0 else 0
            },
            "active_rules": len([r for r in self.rules.values() if r.is_active]),
            "total_rules": len(self.rules)
        }
    
    def get_all_rules(self) -> List[Dict[str, Any]]:
        """Get all governance rules"""
        with self.lock:
            rules_list = []
            for rule_id, rule in self.rules.items():
                rule_dict = asdict(rule)
                rule_dict['created_at'] = rule.created_at.isoformat()
                rules_list.append(rule_dict)
            return rules_list
    
    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get summary of false positive feedbacks"""
        with self.lock:
            if not self.feedbacks:
                return {"total": 0, "by_attack_type": {}, "by_ip": {}}
            
            # Group by attack type
            by_attack_type = defaultdict(int)
            for fb in self.feedbacks:
                by_attack_type[fb.attack_type] += 1
            
            # Group by source IP
            by_ip = defaultdict(int)
            for fb in self.feedbacks:
                by_ip[fb.src_ip] += 1
            
            # Top IPs
            top_ips = sorted(by_ip.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "total": len(self.feedbacks),
                "by_attack_type": dict(by_attack_type),
                "top_source_ips": dict(top_ips),
                "recent_count": len([fb for fb in self.feedbacks 
                                    if fb.timestamp > datetime.now() - timedelta(days=7)])
            }
