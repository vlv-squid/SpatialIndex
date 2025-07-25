# visualization.py
# created by:
#   @author: vlv-squid
#   @date: 2025-07-23
#

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from osgeo import ogr
import os


class Visualizer:

    @staticmethod
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
            elif geom.GetGeometryType() in [
                    ogr.wkbPolygon, ogr.wkbMultiPolygon
            ]:
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
            elif geom.GetGeometryType() in [
                    ogr.wkbPolygon, ogr.wkbMultiPolygon
            ]:
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
