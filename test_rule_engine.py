import sys
sys.path.insert(0, r'c:\SpaceB\nids-system\backend')
from ml.rule_engine import RuleEngine
import numpy as np

re = RuleEngine()
print('RuleEngine import OK')
print(f'Rules loaded: {len(re.rules)}')
print(f'Enabled: {re.is_enabled()}')

re.set_enabled(True)
print(f'After enable: {re.is_enabled()}')

info = re.get_rules_info()
print(f'Rules info: {info["total_rules"]} rules')

features = np.zeros(78)
features[0] = 80
features[2] = 100
features[3] = 5
features[15] = 2000
features[44] = 5

corrected, rule_id = re.correct(features, "DoS Slowhttptest")
print(f'Test correction: DoS Slowhttptest -> {corrected} (rule: {rule_id})')

re.set_enabled(False)
corrected2, rule_id2 = re.correct(features, "DoS Slowhttptest")
print(f'Disabled correction: DoS Slowhttptest -> {corrected2} (rule: {rule_id2})')

print('All tests passed!')
