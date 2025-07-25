# index_base.py
# created by:
#   @author: vlv-squid
#   @date: 2025-07-23
#

from abc import ABC, abstractmethod


class SpatialIndex(ABC):

    def __init__(self, data_path, index_file, resolution):
        self.data_path = data_path
        self.index_file = index_file
        self.resolution = resolution
        self.feature_bounds = {}
        self.feature_count = 0

    @abstractmethod
    def build_index(self):
        pass

    @abstractmethod
    def query_by_bbox(self, bbox):
        pass

    @abstractmethod
    def load_index(self):
        pass

    @abstractmethod
    def save_index(self):
        pass
