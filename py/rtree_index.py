# rtree_index.py
# created by:
#   @author: vlv-squid
#   @date: 2025-07-23
#

from rtree import index
from index_base import SpatialIndex
import pickle
import os
import time
from osgeo import ogr


class RtreeIndex(SpatialIndex):

    def __init__(self,
                 data_path,
                 index_file='./index_py/rtree.pkl',
                 resolution=None):
        super().__init__(data_path, index_file, resolution)
        self.rtree_idx = None
        self.rtree_index_file = index_file
        self.feature_bounds = {}  # 存储要素的外包矩形用于精确验证
        self.feature_count = 0  # 要素总数

        ogr.RegisterAll()

        if os.path.exists(index_file):
            print("从pkl加载R树索引...")
            self.load_index()
        else:
            print("R 树索引文件不存在，请调用 build_index() 构建索引")

    def build_index(self):
        """构建或重建 R 树索引"""
        start_time = time.time()

        datasource = ogr.Open(self.data_path)
        layer = datasource.GetLayer()
        self.feature_count = layer.GetFeatureCount()
        print(f"开始构建 R 树索引，共 {self.feature_count} 个要素...")

        # 初始化 R 树索引（仅内存中）
        rtree_properties = index.Property()
        rtree_properties.dimension = 2
        self.rtree_idx = index.Index(properties=rtree_properties)

        self.feature_bounds = {}  # 清空旧的边界信息

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

        # 构建 R 树索引
        for fid, bounds in self.feature_bounds.items():
            minx, miny, maxx, maxy = bounds
            self.rtree_idx.insert(fid, (minx, miny, maxx, maxy))

        # 保存 R 树索引到文件
        self.save_index()

        print(f"索引构建完成! 耗时: {time.time() - start_time:.2f}秒")
        print(f"R树条目: {len(self.feature_bounds)}")

    def query_by_bbox(self, bbox):
        """基于 BBox 查询要素"""
        start_time = time.time()
        if not self.rtree_idx:
            raise RuntimeError("R树索引未加载，请先调用 build_index() 或 load_index()")

        # 使用 R 树查询
        candidate_fids = list(self.rtree_idx.intersection(bbox))

        results = candidate_fids

        duration = (time.time() - start_time) * 1000
        print(f"查询完成! 耗时: {duration:.2f}ms")  # 占位，实际由测试类统计
        print(f"候选要素: {len(candidate_fids)}")
        return results

    def load_index(self):
        """从pickle文件加载R树索引"""
        pkl_file = self.index_file
        if not os.path.exists(pkl_file):
            print("R树索引pkl文件不存在")
            return

        with open(pkl_file, 'rb') as f:
            loaded_data = pickle.load(f)
            all_entries = loaded_data['entries']
            self.feature_bounds = loaded_data.get('feature_bounds', {})

        # 创建新的R树索引
        rtree_properties = index.Property()
        rtree_properties.dimension = 2
        self.rtree_idx = index.Index(properties=rtree_properties)

        # 重新插入所有条目
        for fid, bounds in all_entries:
            self.rtree_idx.insert(fid, bounds)

        print("R树索引加载完成")

    def save_index(self):
        """将R树索引保存为pickle文件"""
        if self.rtree_idx is None:
            print("没有可用的R树索引")
            return

        # 收集所有条目
        all_entries = []
        for fid in self.feature_bounds.keys():
            bounds = self.feature_bounds[fid]
            all_entries.append((fid, bounds))

        # 保存到 .pkl 文件
        os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
        with open(self.index_file, 'wb') as f:
            pickle.dump(
                {
                    'entries': all_entries,
                    'feature_bounds': self.feature_bounds
                }, f)

        print("R树索引保存完成")
