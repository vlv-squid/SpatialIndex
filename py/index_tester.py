# index_tester.py
# created by:
#   @author: vlv-squid
#   @date: 2025-07-23
#

import time
from visualization import Visualizer


class IndexTester:

    def __init__(self, data_path, bbox):
        self.data_path = data_path
        self.bbox = bbox

    def run_performance_test(self, indexers, visualize=False):
        print("\n===== 性能测试开始 =====")

        for name, indexer in indexers.items():
            print(f"\n[测试] {name}:")
            start_time = time.time()
            results = indexer.query_by_bbox(self.bbox)
            duration = (time.time() - start_time) * 1000
            print(f"总耗时: {duration:.2f}ms, 结果数: {len(results)}")
            if visualize:
                Visualizer.visualize_results(self.data_path, results,
                                             self.bbox, name)

        print("===== 性能测试结束 =====")
