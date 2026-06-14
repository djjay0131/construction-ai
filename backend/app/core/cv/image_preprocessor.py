"""Image preprocessor for raster/scanned construction drawings.

Two responsibilities, kept narrow:

* Detect how skewed an input image is (Hough dominant-edge angle).
* Reject when over threshold, otherwise enhance contrast (CLAHE) and
  denoise (Gaussian) so downstream Hough line extraction has clean edges
  to work from.

Skewed drawings are **rejected**, never corrected. This matches the
project's standing policy from earlier specs — deskewing a "to-scale"
drawing distorts the measurements we want to extract from it.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class SkewRejected(RuntimeError):
    """Raised by :class:`ImagePreprocessor` when measured skew exceeds the
    configured threshold. The exception message always includes the
    measured angle so the operator can see how far off the input was.
    """


class ImagePreprocessor:
    """Preprocess a raster/scanned drawing: reject skewed, enhance the rest."""

    def __init__(self, skew_threshold_deg: float = 5.0) -> None:
        if skew_threshold_deg <= 0:
            raise ValueError(
                f"skew_threshold_deg must be positive; got {skew_threshold_deg}"
            )
        self.skew_threshold_deg = skew_threshold_deg

    def detect_skew(self, image: np.ndarray) -> float:
        """Return the dominant skew angle in degrees, signed.

        Algorithm:
            1. Convert to grayscale if 3-channel.
            2. Canny edge map (50, 150).
            3. ``cv2.HoughLines`` → list of (rho, theta) tuples.
            4. For each theta, compute deviation from the nearest axis
               (0 or pi/2). Take the median deviation. That's the skew
               angle in radians; convert to degrees and return.

        A near-blank image with no detected lines returns 0.0 (no
        deviation detectable). That's a defensible default: downstream
        wall extraction will fail later with a clear "no walls" error.
        """
        if image is None or getattr(image, "size", 0) == 0:
            raise ValueError("detect_skew received empty image")

        gray = (
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        )
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)

        if lines is None or len(lines) == 0:
            return 0.0

        deviations_deg: list[float] = []
        for rho_theta in lines:
            theta = float(rho_theta[0][1])
            # Map theta to its deviation from the nearest of {0, pi/2},
            # in the range (-45, 45] degrees.
            dev_rad = ((theta + np.pi / 4) % (np.pi / 2)) - np.pi / 4
            deviations_deg.append(float(np.degrees(dev_rad)))

        return float(np.median(deviations_deg))

    def run(self, image: np.ndarray) -> np.ndarray:
        """Detect skew → reject if over threshold → enhance + denoise.

        Returns a single-channel ``np.uint8`` array on success. Raises
        :class:`SkewRejected` when the measured skew exceeds the threshold.
        """
        skew = self.detect_skew(image)
        if abs(skew) > self.skew_threshold_deg:
            raise SkewRejected(
                f"Drawing appears skewed by {skew:.1f} degrees "
                f"(threshold {self.skew_threshold_deg:.1f}). "
                "Please provide a properly scanned image."
            )

        gray = (
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        )
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        denoised = cv2.GaussianBlur(enhanced, (3, 3), 0)
        return denoised
