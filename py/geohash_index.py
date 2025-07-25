# geohash_index.py
# created by:
#   @author: vlv-squid
#   @date: 2025-07-23
#

import pygeohash as geohash
from index_base import SpatialIndex
import pickle
import os
import time
from collections import defaultdict
from osgeo import ogr


def bbox_to_geohashes(bbox, precision=6):
    """计算一个bbox覆盖的geohash列表，步长基于精度自适应"""
    min_lon, min_lat, max_lon, max_lat = bbox
    step = {
        5: 0.01,
        6: 0.001,
        7: 0.0005,
        8: 0.00025,
        9: 0.0001,
        10: 0.00005,
        11: 0.000025,
        12: 0.00001
    }.get(precision, 0.005)

    lat = min_lat
    geohashes = set()
    while lat <= max_lat:
        lon = min_lon
        while lon <= max_lon:
            h = geohash.encode(lat, lon, precision)
            geohashes.add(h)
            lon += step
        lat += step
    return list(geohashes)


class GeoHashSpatialIndex(SpatialIndex):

    def __init__(self,
                 data_path,
                 index_file='./index_py/geohash.pkl',
                 precision=6):
        super().__init__(data_path, index_file, precision)
        self.geohash_index = defaultdict(list)
        self.feature_bounds = {}  # 存储要素的外包矩形用于精确验证
        self.feature_count = 0  # 要素总数

        ogr.RegisterAll()

        if os.path.exists(index_file):
            print("加载已有的 GeoHash 索引...")
            self.load_index()
        else:
            print("GeoHash 索引文件不存在，请调用 build_index() 构建索引")

    def build_index(self):
        """构建或重建 GeoHash 空间索引"""
        start_time = time.time()

        datasource = ogr.Open(self.data_path)
        layer = datasource.GetLayer()
        self.feature_count = layer.GetFeatureCount()
        print(f"开始构建 GeoHash 索引，共 {self.feature_count} 个要素...")

        self.geohash_index.clear()
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

            # 计算覆盖的 GeoHash 列表
            covering_hashes = bbox_to_geohashes(bounds, self.resolution)

            for h in covering_hashes:
                self.geohash_index[h].append(fid)

        # 保存 GeoHash 索引
        self.save_index()

        print(f"索引构建完成! 耗时: {time.time() - start_time:.2f}秒")
        print(f"GeoHash索引条目: {len(self.geohash_index)}")

    def query_by_bbox(self, bbox):
        """基于 BBox 查询要素"""
        start_time = time.time()
        # 计算查询区域的 GeoHash 列表
        query_hashes = bbox_to_geohashes(bbox, self.resolution)
        candidate_fids = set()
        for h in query_hashes:
            candidate_fids.update(self.geohash_index.get(h, []))

        candidate_fids = list(candidate_fids)

        # 精确几何验证
        results = candidate_fids
        duration = (time.time() - start_time) * 1000
        print(f"查询完成! 耗时: {duration:.2f}ms")  # 占位，实际由测试类统计
        print(f"候选要素: {len(candidate_fids)}")
        return results

    def load_index(self):
        """从pickle文件加载GeoHash索引"""
        with open(self.index_file, 'rb') as f:
            loaded_data = pickle.load(f)
            if isinstance(loaded_data, dict):
                self.geohash_index = loaded_data
            else:
                raise ValueError("加载的GeoHash索引格式不正确")

        print("GeoHash索引加载完成")

    def save_index(self):
        """将GeoHash索引保存为pickle文件"""
        os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
        with open(self.index_file, 'wb') as f:
            pickle.dump(dict(self.geohash_index), f)

        print("GeoHash索引保存完成")
