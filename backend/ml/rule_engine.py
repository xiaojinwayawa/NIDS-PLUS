"""
Rule Engine Module
Post-inference rule-based correction for attack type classification.
Applies expert rules to correct model predictions when the model's
attack type classification is inaccurate but binary detection (attack vs normal) is correct.

Designed for CIC-IDS2017 dataset with configurable JSON rules.
"""
import json
import os
import threading
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

from logging_config import app_logger as logger


CIC_IDS2017_FEATURE_NAMES = [
    'Destination Port', 'Flow Duration', 'Total Fwd Packets', 'Total Backward Packets',
    'Total Length of Fwd Packets', 'Total Length of Bwd Packets', 'Fwd Packet Length Max',
    'Fwd Packet Length Min', 'Fwd Packet Length Mean', 'Fwd Packet Length Std',
    'Bwd Packet Length Max', 'Bwd Packet Length Min', 'Bwd Packet Length Mean',
    'Bwd Packet Length Std', 'Flow Bytes/s', 'Flow Packets/s', 'Flow IAT Mean',
    'Flow IAT Std', 'Flow IAT Max', 'Flow IAT Min', 'Fwd IAT Total', 'Fwd IAT Mean',
    'Fwd IAT Std', 'Fwd IAT Max', 'Fwd IAT Min', 'Bwd IAT Total', 'Bwd IAT Mean',
    'Bwd IAT Std', 'Bwd IAT Max', 'Bwd IAT Min', 'Fwd PSH Flags', 'Bwd PSH Flags',
    'Fwd URG Flags', 'Bwd URG Flags', 'Fwd Header Length', 'Bwd Header Length',
    'Fwd Packets/s', 'Bwd Packets/s', 'Min Packet Length', 'Max Packet Length',
    'Packet Length Mean', 'Packet Length Std', 'Packet Length Variance',
    'FIN Flag Count', 'SYN Flag Count', 'RST Flag Count', 'PSH Flag Count',
    'ACK Flag Count', 'URG Flag Count', 'CWE Flag Count', 'ECE Flag Count',
    'Down/Up Ratio', 'Average Packet Size', 'Avg Fwd Segment Size',
    'Avg Bwd Segment Size', 'Fwd Header Length.1', 'Fwd Avg Bytes/Bulk',
    'Fwd Avg Packets/Bulk', 'Fwd Avg Bulk Rate', 'Bwd Avg Bytes/Bulk',
    'Bwd Avg Packets/Bulk', 'Bwd Avg Bulk Rate', 'Subflow Fwd Packets',
    'Subflow Fwd Bytes', 'Subflow Bwd Packets', 'Subflow Bwd Bytes',
    'Init_Win_bytes_forward', 'Init_Win_bytes_backward', 'act_data_pkt_fwd',
    'min_seg_size_forward', 'Active Mean', 'Active Std', 'Active Max', 'Active Min',
    'Idle Mean', 'Idle Std', 'Idle Max', 'Idle Min'
]


class RuleEngine:
    """
    Rule-based post-inference correction engine.
    
    After the ML model predicts an attack type, this engine can apply
    expert-defined rules to correct the classification based on flow features.
    This is particularly useful when the model correctly identifies an attack
    but misclassifies the specific attack type.
    """

    def __init__(self, rules_path: str = None):
        self.enabled = False
        self.rules: List[Dict[str, Any]] = []
        self.feature_name_to_idx: Dict[str, int] = {}
        self._lock = threading.RLock()

        for idx, name in enumerate(CIC_IDS2017_FEATURE_NAMES):
            self.feature_name_to_idx[name] = idx

        if rules_path and os.path.exists(rules_path):
            self.load_rules(rules_path)
        else:
            self._load_default_rules()

    def load_rules(self, rules_path: str) -> bool:
        """Load rules from a JSON configuration file."""
        try:
            with open(rules_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.rules = config.get("rules", [])
            self._sort_rules_by_priority()
            logger.info(f"Loaded {len(self.rules)} correction rules from {rules_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load rules from {rules_path}: {e}")
            return False

    def _load_default_rules(self):
        """Load built-in default rules for CIC-IDS2017."""
        self.rules = [
            {
                "id": "RULE_DDOS_001",
                "name": "DDoS Flood Detection",
                "description": "High packet rate DDoS attack targeting web ports",
                "priority": 1,
                "conditions": {
                    "Destination Port": {"in": [80, 443, 8080, 8000]},
                    "Flow Packets/s": {"min": 1000},
                    "Total Fwd Packets": {"min": 50},
                    "Total Backward Packets": {"max": 10}
                },
                "correction": "DDoS"
            },
            {
                "id": "RULE_DDOS_002",
                "name": "DDoS Detection (High Bytes)",
                "description": "DDoS with extremely high byte rate",
                "priority": 1,
                "conditions": {
                    "Destination Port": {"in": [80, 443, 8080]},
                    "Flow Bytes/s": {"min": 500000},
                    "Total Fwd Packets": {"min": 30},
                    "Total Backward Packets": {"max": 15}
                },
                "correction": "DDoS"
            },
            {
                "id": "RULE_PORTSCAN_001",
                "name": "Port Scan Detection",
                "description": "Short-duration SYN-heavy flows indicating port scanning",
                "priority": 2,
                "conditions": {
                    "SYN Flag Count": {"min": 3},
                    "Total Fwd Packets": {"min": 5, "max": 80},
                    "Flow Duration": {"max": 5000000}
                },
                "correction": "PortScan"
            },
            {
                "id": "RULE_PORTSCAN_002",
                "name": "Port Scan (Single Packet Probes)",
                "description": "Very short flows with minimal data transfer",
                "priority": 2,
                "conditions": {
                    "Total Fwd Packets": {"min": 1, "max": 3},
                    "Total Backward Packets": {"max": 1},
                    "Flow Duration": {"max": 100000},
                    "Total Length of Fwd Packets": {"max": 100}
                },
                "correction": "PortScan"
            },
            {
                "id": "RULE_DOS_HULK_001",
                "name": "DoS Hulk Detection",
                "description": "HTTP flood attack with PSH flags",
                "priority": 2,
                "conditions": {
                    "Destination Port": {"in": [80, 443]},
                    "Flow Packets/s": {"min": 100, "max": 1000},
                    "Fwd PSH Flags": {"min": 1},
                    "Fwd Packet Length Mean": {"max": 500}
                },
                "correction": "DoS Hulk"
            },
            {
                "id": "RULE_DOS_SLOWHTTP_001",
                "name": "DoS Slow HTTP Detection",
                "description": "Slow HTTP attack with long duration and low packet count",
                "priority": 2,
                "conditions": {
                    "Destination Port": {"in": [80, 443]},
                    "Flow Duration": {"min": 1000000},
                    "Total Fwd Packets": {"max": 20},
                    "Fwd Packet Length Mean": {"max": 200}
                },
                "correction": "DoS Slowhttptest"
            },
            {
                "id": "RULE_DOS_GOLDENEYE_001",
                "name": "DoS GoldenEye Detection",
                "description": "HTTP Keep-Alive abuse attack",
                "priority": 2,
                "conditions": {
                    "Destination Port": {"in": [80, 443]},
                    "Flow Packets/s": {"min": 50, "max": 500},
                    "Fwd PSH Flags": {"min": 1},
                    "Flow Duration": {"min": 500000}
                },
                "correction": "DoS GoldenEye"
            },
            {
                "id": "RULE_DOS_SLOWLORIS_001",
                "name": "DoS Slowloris Detection",
                "description": "Slowloris-style attack with many concurrent connections",
                "priority": 2,
                "conditions": {
                    "Destination Port": {"in": [80, 443]},
                    "Flow Duration": {"min": 5000000},
                    "Total Fwd Packets": {"min": 5, "max": 50},
                    "Flow Packets/s": {"max": 50}
                },
                "correction": "DoS Slowloris"
            },
            {
                "id": "RULE_WEBATTACK_001",
                "name": "Web Attack Detection",
                "description": "Suspicious traffic on HTTP/HTTPS ports",
                "priority": 3,
                "conditions": {
                    "Destination Port": {"in": [80, 443, 8080, 8000, 8443]},
                    "Total Fwd Packets": {"min": 3},
                    "Fwd Packet Length Max": {"min": 100}
                },
                "correction": "Web Attack"
            },
            {
                "id": "RULE_FTP_PATATOR_001",
                "name": "FTP Brute Force Detection",
                "description": "Frequent connection attempts on FTP port",
                "priority": 3,
                "conditions": {
                    "Destination Port": {"in": [21, 20]},
                    "Total Fwd Packets": {"min": 5, "max": 100},
                    "Flow Duration": {"max": 3000000}
                },
                "correction": "FTP-Patator"
            },
            {
                "id": "RULE_SSH_PATATOR_001",
                "name": "SSH Brute Force Detection",
                "description": "Frequent connection attempts on SSH port",
                "priority": 3,
                "conditions": {
                    "Destination Port": 22,
                    "Total Fwd Packets": {"min": 5, "max": 100},
                    "Flow Duration": {"max": 3000000}
                },
                "correction": "SSH-Patator"
            },
            {
                "id": "RULE_BOTNET_001",
                "name": "Botnet Detection",
                "description": "Periodic communication on non-standard ports",
                "priority": 4,
                "conditions": {
                    "Destination Port": {"not_in": [80, 443, 22, 21, 53, 123]},
                    "Fwd IAT Mean": {"min": 10000, "max": 300000},
                    "Total Fwd Packets": {"min": 5}
                },
                "correction": "Botnet"
            }
        ]
        self._sort_rules_by_priority()
        logger.info(f"Loaded {len(self.rules)} default correction rules")

    def _sort_rules_by_priority(self):
        """Sort rules by priority (lower number = higher priority)."""
        self.rules.sort(key=lambda r: r.get("priority", 99))

    def set_enabled(self, enabled: bool):
        """Enable or disable rule correction."""
        with self._lock:
            self.enabled = enabled
            logger.info(f"Rule correction {'enabled' if enabled else 'disabled'}")

    def is_enabled(self) -> bool:
        """Check if rule correction is enabled."""
        return self.enabled

    def correct(
        self,
        features: np.ndarray,
        original_attack_type: str,
        flow_info: Dict[str, Any] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Apply rule correction to a single flow's prediction.

        Args:
            features: Feature vector (1D numpy array, 78 features for CIC-IDS2017)
            original_attack_type: The model's predicted attack type
            flow_info: Optional dict with additional flow metadata
                       (src_ip, dst_ip, src_port, dst_port, protocol, etc.)

        Returns:
            Tuple of (corrected_attack_type, applied_rule_id or None)
        """
        if not self.enabled:
            return original_attack_type, None

        if original_attack_type.lower() in ("normal", "benign"):
            return original_attack_type, None

        with self._lock:
            feature_dict = self._build_feature_dict(features, flow_info)

            for rule in self.rules:
                if self._match_rule(rule, feature_dict):
                    corrected = rule["correction"]
                    rule_id = rule["id"]
                    logger.info(
                        f"Rule correction applied: {rule_id} '{rule['name']}' "
                        f"changed '{original_attack_type}' -> '{corrected}'"
                    )
                    return corrected, rule_id

        return original_attack_type, None

    def correct_batch(
        self,
        features_batch: np.ndarray,
        original_attack_types: List[str],
        flow_infos: List[Dict[str, Any]] = None
    ) -> Tuple[List[str], List[Optional[str]]]:
        """
        Apply rule correction to a batch of predictions.

        Args:
            features_batch: Feature matrix (N x 78)
            original_attack_types: List of model-predicted attack types
            flow_infos: Optional list of flow metadata dicts

        Returns:
            Tuple of (corrected_attack_types, applied_rule_ids)
        """
        if not self.enabled:
            return original_attack_types, [None] * len(original_attack_types)

        corrected_types = []
        applied_rules = []

        for i in range(len(original_attack_types)):
            features = features_batch[i] if features_batch.ndim > 1 else features_batch
            flow_info = flow_infos[i] if flow_infos else None

            corrected, rule_id = self.correct(features, original_attack_types[i], flow_info)
            corrected_types.append(corrected)
            applied_rules.append(rule_id)

        corrections_count = sum(1 for r in applied_rules if r is not None)
        if corrections_count > 0:
            logger.info(
                f"Rule correction batch: {corrections_count}/{len(original_attack_types)} "
                f"predictions corrected"
            )

        return corrected_types, applied_rules

    def _build_feature_dict(
        self,
        features: np.ndarray,
        flow_info: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Build a feature name -> value dictionary from the feature vector."""
        feature_dict = {}

        for name, idx in self.feature_name_to_idx.items():
            if idx < len(features):
                try:
                    val = float(features[idx])
                    if np.isnan(val) or np.isinf(val):
                        val = 0.0
                    feature_dict[name] = val
                except (ValueError, TypeError):
                    feature_dict[name] = 0.0

        if flow_info:
            for key in ["dst_port", "src_port", "protocol"]:
                if key in flow_info:
                    feature_dict[f"_flow_{key}"] = flow_info[key]

        return feature_dict

    def _match_rule(self, rule: Dict[str, Any], feature_dict: Dict[str, Any]) -> bool:
        """Check if all conditions in a rule are satisfied."""
        conditions = rule.get("conditions", {})
        if not conditions:
            return False

        for feature_name, condition in conditions.items():
            value = feature_dict.get(feature_name)
            if value is None:
                alt_key = f"_flow_{feature_name.lower().replace(' ', '_')}"
                value = feature_dict.get(alt_key)
                if value is None:
                    return False

            if not self._check_condition(value, condition):
                return False

        return True

    def _check_condition(self, value: Any, condition: Any) -> bool:
        """Check a single condition against a feature value."""
        if isinstance(condition, (int, float)):
            return value == condition

        if not isinstance(condition, dict):
            return value == condition

        if "min" in condition and "max" in condition:
            return condition["min"] <= value <= condition["max"]
        elif "min" in condition:
            return value >= condition["min"]
        elif "max" in condition:
            return value <= condition["max"]
        elif "in" in condition:
            return value in condition["in"]
        elif "not_in" in condition:
            return value not in condition["not_in"]
        elif "eq" in condition:
            return value == condition["eq"]
        elif "neq" in condition:
            return value != condition["neq"]

        return False

    def get_rules_info(self) -> Dict[str, Any]:
        """Get information about loaded rules."""
        return {
            "enabled": self.enabled,
            "total_rules": len(self.rules),
            "rules": [
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "description": r.get("description"),
                    "priority": r.get("priority"),
                    "correction": r.get("correction")
                }
                for r in self.rules
            ]
        }
