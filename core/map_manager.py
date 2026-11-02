import random
import os
import json
import logging
from typing import Dict, List, Optional, Tuple, Set

logger = logging.getLogger("pixelmania.map_manager")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIED_PIXELS_FILE = os.path.join(BASE_DIR, "mined_pixels.json")

class MapManager:
    def __init__(self):
        self.tried_coordinates: Set[Tuple[int, int]] = set()
        self.active_chunks: List[dict] = []
        self.season_id: Optional[str] = None
        self._load_tried()

    def _load_tried(self):
        if os.path.exists(TRIED_PIXELS_FILE):
            try:
                with open(TRIED_PIXELS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.tried_coordinates = {tuple(pt) for pt in data}
            except Exception as e:
                logger.error(f"Error loading mined_pixels.json: {e}")

    def save_tried(self):
        try:
            with open(TRIED_PIXELS_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self.tried_coordinates), f)
        except Exception as e:
            logger.error(f"Error saving mined_pixels.json: {e}")

    def update_map(self, season_id: str, chunks: List[dict]):
        self.season_id = season_id
        self.active_chunks = [c for c in chunks if c.get("availableCount", 0) > 0]

    def mark_coordinate(self, x: int, y: int):
        self.tried_coordinates.add((x, y))
        if len(self.tried_coordinates) % 10 == 0:
            self.save_tried()

    def pick_candidate_pixel(self) -> Optional[Tuple[int, int]]:
        """
        Picks an unmined (x, y) anchor based on active chunk list.
        """
        if not self.active_chunks:
            # Fallback to random coordinate in 4000x2500 map
            for _ in range(50):
                x = random.randint(10, 3990)
                y = random.randint(10, 2490)
                if (x, y) not in self.tried_coordinates:
                    return (x, y)
            return (random.randint(10, 3990), random.randint(10, 2490))

        # Sample from chunks with higher available counts
        weights = [max(1, c.get("availableCount", 1)) for c in self.active_chunks]
        selected_chunk = random.choices(self.active_chunks, weights=weights, k=1)[0]
        cid = selected_chunk["chunkId"]

        # Client formula vp(chunkId)
        base_x = (cid % 63) * 64
        base_y = (cid // 63) * 64
        width = min(64, 4000 - base_x)
        height = min(64, 2500 - base_y)

        # Try to find an untried coordinate inside this chunk
        for _ in range(40):
            dx = random.randint(0, width - 1)
            dy = random.randint(0, height - 1)
            pt = (base_x + dx, base_y + dy)
            if pt not in self.tried_coordinates:
                return pt

        # If all 40 random attempts collided, return any valid point in the chunk
        return (base_x + random.randint(0, width - 1), base_y + random.randint(0, height - 1))

# Global map manager singleton
map_mgr = MapManager()
