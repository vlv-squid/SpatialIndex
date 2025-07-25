#
# created by:
#   @author: vlv-squid
#   @date: 2025-07-22
#

import os
import time
import pickle
from collections import defaultdict
from osgeo import ogr
import pygeohash as geohash
import matplotlib.pyplot as plt
from rtree import index


def bbox_to_geohashes(bbox, precision=6):
    min_lon, min_lat, max_lon, max_lat = bbox
    """计算一个bbox覆盖的geohash列表，步长基于精度自适应"""
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


class GeoHashSpatialIndexBased:

    def __init__(self,
                 data_path,
                 geohash_index_file='./index_py/geohash_index.pkl',
                 rtree_index_file='./index_py/rtree_index.pkl',
                 precision=6):
        self.data_path = data_path
        self.geohash_index_file = geohash_index_file
        self.rtree_index_file = rtree_index_file
        self.precision = precision  # GeoHash 精度级别
        self.feature_bounds = {}
        self.feature_count = 0
        self.geohash_index = defaultdict(list)  # 内存中的 GeoHash 索引
        self.rtree_idx = None

        ogr.RegisterAll()

        # 加载已有的索引文件（如果存在）
        if os.path.exists(self.geohash_index_file):
            print("加载已有的 GeoHash 索引...")
            self.load_geohash_index()
        else:
            print("GeoHash 索引文件不存在，请调用 build_index() 构建索引")

        if os.path.exists(rtree_index_file):
            print("从pkl加载R树索引...")
            self.load_rtree_index()
        else:
            print("R 树索引文件不存在，请调用 build_index() 构建索引")

    def load_geohash_index(self):
        """从文件加载 GeoHash 索引"""
        with open(self.geohash_index_file, 'rb') as f:
            self.geohash_index = pickle.load(f)
        print(f"加载的 GeoHash 索引条目数: {len(self.geohash_index)}")

    def save_geohash_index(self):
        """将 GeoHash 索引保存到文件"""
        os.makedirs(os.path.dirname(self.geohash_index_file), exist_ok=True)
        with open(self.geohash_index_file, 'wb') as f:
            pickle.dump(self.geohash_index, f)

    def save_rtree_index(self):
        """将R树索引保存为pickle文件"""
        if self.rtree_idx is None:
            print("没有可用的R树索引")
            return

        # 收集所有条目
        all_entries = []
        for fid in self.rtree_idx.intersection(self.rtree_idx.get_bounds()):
            bounds = self.rtree_idx.get_bounds([fid])
            all_entries.append((fid, bounds))

        # 保存到 .pkl 文件
        os.makedirs(os.path.dirname(self.rtree_index_file), exist_ok=True)
        with open(self.rtree_index_file, 'wb') as f:
            pickle.dump(all_entries, f)

    def load_rtree_index(self):
        """从pickle文件加载R树索引"""
        pkl_file = self.rtree_index_file
        if not os.path.exists(pkl_file):
            print("R树索引pkl文件不存在")
            return None

        with open(pkl_file, 'rb') as f:
            all_entries = pickle.load(f)

        # 创建新的R树索引
        rtree_properties = index.Property()
        rtree_properties.dimension = 2
        self.rtree_idx = index.Index(properties=rtree_properties)

        # 重新插入所有条目
        for fid, bounds in all_entries:
            self.rtree_idx.insert(fid, bounds)

    def build_index(self):
        """构建或重建空间索引"""
        start_time = time.time()

        # 打开 GIS 数据源
        datasource = ogr.Open(self.data_path)
        if not datasource:
            raise ValueError(f"无法打开数据源: {self.data_path}")
        layer = datasource.GetLayer()
        self.feature_count = layer.GetFeatureCount()
        print(f"开始构建索引，共 {self.feature_count} 个要素...")

        # 初始化 R 树索引（仅内存中）
        rtree_properties = index.Property()
        rtree_properties.dimension = 2
        self.rtree_idx = index.Index(properties=rtree_properties)

        # 构建索引
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

            # 替换原来的单点索引逻辑
            covering_hashes = bbox_to_geohashes(bounds, self.precision)

            for h in covering_hashes:
                self.geohash_index[h].append(fid)

        # 保存 GeoHash 索引到文件
        self.save_geohash_index()

        # 构建 R 树索引
        for fid, bounds in feature_bounds:
            minx, miny, maxx, maxy = bounds
            self.rtree_idx.insert(fid, (minx, miny, maxx, maxy))

        # 保存 rtree 索引到文件
        self.save_rtree_index()

        print(f"索引构建完成! 耗时: {time.time() - start_time:.2f}秒")
        print(
            f"GeoHash索引条目: {len(self.geohash_index)}, R树条目: {len(feature_bounds)}"
        )

    def query_by_bbox(self, bbox, use_rtree=True, exact_check=True):
        min_lon, min_lat, max_lon, max_lat = bbox
        start_time = time.time()

        # 替换原来的单点查询逻辑
        query_hashes = bbox_to_geohashes(bbox, self.precision)
        candidate_fids = set()
        for h in query_hashes:
            candidate_fids.update(self.geohash_index.get(h, []))

        # 使用 R 树优化
        if use_rtree and self.rtree_idx:
            filtered = list(self.rtree_idx.intersection(bbox))
            candidate_fids = list(set(candidate_fids) & set(filtered))

        # 精确几何验证
        results = []
        if exact_check:
            for fid in candidate_fids:
                f_minx, f_miny, f_maxx, f_maxy = self.feature_bounds[fid]
                if not (f_maxx < min_lon or f_minx > max_lon
                        or f_maxy < min_lat or f_miny > max_lat):
                    results.append(fid)
        else:
            results = candidate_fids

        print(f"查询完成! 耗时: {(time.time() - start_time)*1000:.2f}ms")
        print(f"候选要素: {len(candidate_fids)}, 结果要素: {len(results)}")
        return results


def visualize_results(data_path, results, bbox, query_name):
    """可视化查询结果"""
    datasource = ogr.Open(data_path)

    fig, ax = plt.subplots(figsize=(12, 8))

    # 绘制BBox
    min_lon, min_lat, max_lon, max_lat = bbox
    rect = plt.Rectangle((min_lon, min_lat),
                         max_lon - min_lon,
                         max_lat - min_lat,
                         fill=False,
                         color='red',
                         linewidth=2)
    ax.add_patch(rect)

    colors = ['blue', 'green', 'purple']
    layer = datasource.GetLayer()
    for feature in layer:
        geom = feature.GetGeometryRef()
        if geom is None:
            continue
        if geom.GetGeometryType() == ogr.wkbPoint:
            x, y = geom.GetX(), geom.GetY()
            ax.plot(x, y, 'o', color='gray', markersize=2, alpha=0.3)
        elif geom.GetGeometryType() in [
                ogr.wkbLineString, ogr.wkbMultiLineString
        ]:
            coords = [(g.GetX(), g.GetY()) for g in geom]
            xs, ys = zip(*coords) if coords else ([], [])
            ax.plot(xs, ys, color='gray', linewidth=0.5, alpha=0.3)
        elif geom.GetGeometryType() in [ogr.wkbPolygon, ogr.wkbMultiPolygon]:
            ring = geom.GetGeometryRef(
                0) if geom.GetGeometryCount() > 0 else None
            if ring:
                coords = [(ring.GetX(j), ring.GetY(j))
                          for j in range(ring.GetPointCount())]
                xs, ys = zip(*coords)
                ax.fill(xs, ys, color='lightgray', alpha=0.1)

    # 高亮显示结果要素
    for fid in results:
        feature = layer.GetFeature(fid)
        geom = feature.GetGeometryRef()
        if geom is None:
            continue
        if geom.GetGeometryType() == ogr.wkbPoint:
            ax.plot(geom.GetX(), geom.GetY(), 'ro', markersize=6)
        elif geom.GetGeometryType() in [
                ogr.wkbLineString, ogr.wkbMultiLineString
        ]:
            coords = [(g.GetX(), g.GetY()) for g in geom]
            xs, ys = zip(*coords) if coords else ([], [])
            ax.plot(xs, ys, 'r-', linewidth=2)
        elif geom.GetGeometryType() in [ogr.wkbPolygon, ogr.wkbMultiPolygon]:
            ring = geom.GetGeometryRef(0)
            coords = [(ring.GetX(j), ring.GetY(j))
                      for j in range(ring.GetPointCount())]
            xs, ys = zip(*coords)
            ax.fill(xs, ys, color='red', alpha=0.4)

    ax.set_title(f"Spatial Query Results ({len(results)} features)")
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.grid(True)
    plt.tight_layout()
    outpath = os.path.join("./png", query_name + ".png")
    plt.savefig(outpath)
    print("可视化结果已保存为" + query_name + ".png")


def run_performance_test(data_path, bbox, indexer):
    """运行性能测试"""
    print("\n===== 性能测试开始 =====")

    # 测试1: 纯GDAL顺序扫描
    print("\n[测试1] 纯GDAL顺序扫描:")
    start_time = time.time()
    datasource = ogr.Open(data_path)
    results = []
    layer = datasource.GetLayer()
    min_lon, min_lat, max_lon, max_lat = bbox
    layer.SetSpatialFilterRect(min_lon, min_lat, max_lon, max_lat)
    results.extend([feat.GetFID() for feat in layer])
    print(f"耗时: {(time.time() - start_time)*1000:.2f}ms, 结果数: {len(results)}")
    query_name = "纯GDAL顺序扫描索引"
    visualize_results(data_path, results, sample_bbox, query_name)

    # 测试2: 纯geohash索引 (无精确验证)
    print("\n[测试2] 纯geohash索引 (无精确验证):")
    start_time = time.time()
    results = indexer.query_by_bbox(bbox, use_rtree=False, exact_check=False)
    print(f"总耗时: {(time.time() - start_time)*1000:.2f}ms")
    query_name = "纯geohash索引"
    visualize_results(data_path, results, sample_bbox, query_name)

    # 测试3: geohash索引 + 矩形精确验证
    print("\n[测试3] geohash + 矩形精确验证:")
    start_time = time.time()
    results = indexer.query_by_bbox(bbox, use_rtree=False, exact_check=True)
    print(f"总耗时: {(time.time() - start_time)*1000:.2f}ms")
    query_name = "geohash + 矩形索引"
    visualize_results(data_path, results, sample_bbox, query_name)

    # 测试4: geohash索引 + R树验证
    print("\n[测试4] geohash + R树验证:")
    start_time = time.time()
    results = indexer.query_by_bbox(bbox, use_rtree=True, exact_check=False)
    print(f"总耗时: {(time.time() - start_time)*1000:.2f}ms")
    query_name = "geohash + R树索引"
    visualize_results(data_path, results, sample_bbox, query_name)

    # 测试5: geohash索引 + R树优化 + 矩形精确验证
    print("\n[测试5] geohash + R树 + 矩形精确验证:")
    start_time = time.time()
    results = indexer.query_by_bbox(bbox, use_rtree=True, exact_check=True)
    print(f"总耗时: {(time.time() - start_time)*1000:.2f}ms")
    query_name = "geohash + R树 + 矩形索引"
    visualize_results(data_path, results, sample_bbox, query_name)

    print("===== 性能测试结束 =====")


if __name__ == "__main__":
    test_data = "./data/test.shp"
    sample_bbox = (103.2504, 26.4297, 103.3028, 26.4747)

    indexer = GeoHashSpatialIndexBased(test_data, precision=7)
    indexer.build_index()
    run_performance_test(test_data, sample_bbox, indexer)
