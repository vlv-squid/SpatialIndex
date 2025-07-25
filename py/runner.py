# runner.py
# created by:
#   @author: vlv-squid
#   @date: 2025-07-23
#

from typing import Dict
from index_base import SpatialIndex
from index_tester import IndexTester
from rtree_index import RtreeIndex
from geohash_index import GeoHashSpatialIndex
from s2_index import S2SpatialIndex
from h3_index import H3SpatialIndex

import os

if __name__ == "__main__":
    # test_data = "./data/test.shp"
    # sample_bbox = (103.2504, 26.4297, 103.3028, 26.4747)

    test_data = "/home/chenming/Data/GIS_DATA/shapefile/dltb_532300_2020.shp"
    sample_bbox = (100.546875, 25.3125, 101.25, 26.015625)

    indexers: Dict[str, SpatialIndex] = {
        "Rtree": RtreeIndex(test_data),
        "GeoHash": GeoHashSpatialIndex(test_data, precision=7),
        "S2": S2SpatialIndex(test_data, resolution=15),
        # "H3": H3SpatialIndex(test_data, resolution=10),
    }

    # 检查并加载或构建索引
    for name, idx in indexers.items():
        if hasattr(idx, 'index_file') and os.path.exists(idx.index_file):
            print(f"Loading existing {name} index...")
            idx.load_index()
        else:
            print(f"Building {name} index...")
            idx.build_index()

    tester = IndexTester(test_data, sample_bbox)
    tester.run_performance_test(indexers, visualize=True)
