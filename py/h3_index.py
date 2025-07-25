# h3_index.py
# created by:
#   @author: vlv-squid
#   @date: 2025-07-23
#

from h3 import geo_to_cells
from index_base import SpatialIndex
import pickle
import os
import time
from collections import defaultdict
from shapely.geometry import box
from osgeo import ogr


class H3SpatialIndex(SpatialIndex):

    def __init__(self,
                 data_path,
                 index_file='./index_py/h3.pkl',
                 resolution=9):
        super().__init__(data_path, index_file, resolution)
        self.h3_index = defaultdict(list)
        self.feature_bounds = {}  # 存储要素的外包矩形用于精确验证
        self.feature_count = 0  # 要素总数

        ogr.RegisterAll()

        if os.path.exists(index_file):
            print("加载已有的 H3 索引...")
            self.load_index()
        else:
            print("H3 索引文件不存在，请调用 build_index() 构建索引")

    def build_index(self):
        """构建或重建 H3 空间索引"""
        start_time = time.time()

        datasource = ogr.Open(self.data_path)
        layer = datasource.GetLayer()
        self.feature_count = layer.GetFeatureCount()
        print(f"开始构建 H3 索引，共 {self.feature_count} 个要素...")

        self.h3_index.clear()
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

            # 构建查询区域（使用外包矩形）
            polygon = box(min_lon, min_lat, max_lon, max_lat)

            # 获取覆盖这个区域的 H3 单元格
            coverer = geo_to_cells(polygon, self.resolution)

            for cell in coverer:
                self.h3_index[cell].append(fid)

        # 保存 H3 索引
        self.save_index()

        print(f"索引构建完成! 耗时: {time.time() - start_time:.2f}秒")
        print(f"H3索引条目: {len(self.h3_index)}")

    def query_by_bbox(self, bbox):
        """基于 BBox 查询要素"""
        start_time = time.time()
        min_lon, min_lat, max_lon, max_lat = bbox

        # 构建查询区域的 H3 单元格
        polygon = box(min_lon, min_lat, max_lon, max_lat)
        coverer = geo_to_cells(polygon, self.resolution)
        candidate_fids = set()
        for cell in coverer:
            candidate_fids.update(self.h3_index.get(cell, []))

        candidate_fids = list(candidate_fids)

        results = candidate_fids

        duration = (time.time() - start_time) * 1000
        print(f"查询完成! 耗时: {duration:.2f}ms")  # 占位，实际由测试类统计
        print(f"候选要素: {len(candidate_fids)}")
        return results

    def load_index(self):
        """从pickle文件加载H3索引"""
        with open(self.index_file, 'rb') as f:
            loaded_data = pickle.load(f)
            if isinstance(loaded_data, dict):
                self.h3_index = loaded_data
            else:
                raise ValueError("加载的H3索引格式不正确")

        print("H3索引加载完成")

    def save_index(self):
        """将H3索引保存为pickle文件"""
        os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
        with open(self.index_file, 'wb') as f:
            pickle.dump(dict(self.h3_index), f)

        print("H3索引保存完成")
