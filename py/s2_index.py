# s2_index.py
# created by:
#   @author: vlv-squid
#   @date: 2025-07-23
#

import s2sphere
from index_base import SpatialIndex
import pickle
import os
import time
from collections import defaultdict
from osgeo import ogr


class S2SpatialIndex(SpatialIndex):

    def __init__(self,
                 data_path,
                 index_file='./index_py/s2.pkl',
                 resolution=15):
        super().__init__(data_path, index_file, resolution)
        self.s2_index = defaultdict(list)
        self.feature_bounds = {}  # 存储要素的外包矩形用于精确验证
        self.feature_count = 0  # 要素总数

        ogr.RegisterAll()

        if os.path.exists(index_file):
            print("加载已有的 S2 索引...")
            self.load_index()
        else:
            print("S2 索引文件不存在，请调用 build_index() 构建索引")

    def build_index(self):
        """构建或重建 S2 空间索引"""
        start_time = time.time()

        datasource = ogr.Open(self.data_path)
        layer = datasource.GetLayer()
        self.feature_count = layer.GetFeatureCount()
        print(f"开始构建 S2 索引，共 {self.feature_count} 个要素...")

        self.s2_index.clear()
        feature_bounds = []

        for feature in layer:
            fid = feature.GetFID()
            geom = feature.GetGeometryRef()
            if not geom:
                continue

            # 获取外包矩形
            env = geom.GetEnvelope()
            min_lon, max_lon, min_lat, max_lat = env
            bounds = (min_lon, min_lat, max_lon, max_lat)
            self.feature_bounds[fid] = bounds
            feature_bounds.append((fid, bounds))

            # 构建 S2 单元格
            p1 = s2sphere.LatLng.from_degrees(min_lat, min_lon)
            p2 = s2sphere.LatLng.from_degrees(max_lat, max_lon)
            rect = s2sphere.LatLngRect.from_point_pair(p1, p2)

            coverer = s2sphere.RegionCoverer()
            coverer.min_level = self.resolution
            coverer.max_level = self.resolution

            cell_ids = coverer.get_covering(rect)
            for cell in cell_ids:
                self.s2_index[cell.id()].append(fid)

        # 保存 S2 索引
        self.save_index()

        print(f"索引构建完成! 耗时: {time.time() - start_time:.2f}秒")
        print(f"S2索引条目: {len(self.s2_index)}, R树条目: {len(feature_bounds)}")

    def query_by_bbox(self, bbox):
        """基于 BBox 查询要素"""
        start_time = time.time()
        min_lon, min_lat, max_lon, max_lat = bbox

        # 构建查询区域的 S2 单元格
        p1 = s2sphere.LatLng.from_degrees(min_lat, min_lon)
        p2 = s2sphere.LatLng.from_degrees(max_lat, max_lon)
        query_rect = s2sphere.LatLngRect.from_point_pair(p1, p2)

        coverer = s2sphere.RegionCoverer()
        coverer.min_level = self.resolution
        query_cells = coverer.get_covering(query_rect)

        # 获取候选要素
        candidate_fids = set()
        for cell in query_cells:
            candidate_fids.update(self.s2_index.get(cell.id(), []))

        candidate_fids = list(candidate_fids)

        results = candidate_fids

        duration = (time.time() - start_time) * 1000
        print(f"查询完成! 耗时: {duration:.2f}ms")  # 占位，实际由测试类统计
        print(f"候选要素: {len(candidate_fids)}")
        return results

    def load_index(self):
        """从pickle文件加载S2索引"""
        with open(self.index_file, 'rb') as f:
            loaded_data = pickle.load(f)
            if isinstance(loaded_data, dict):
                self.s2_index = loaded_data
            else:
                raise ValueError("加载的S2索引格式不正确")

        print("S2索引加载完成")

    def save_index(self):
        """将S2索引保存为pickle文件"""
        os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
        with open(self.index_file, 'wb') as f:
            pickle.dump(dict(self.s2_index), f)

        print("S2索引保存完成")
