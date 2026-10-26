/**
 * GeoKurir Malang - Clustering & Geometric Utilities
 * Implements Convex Hull (Monotone Chain), Centroid calculations, and Metric Evaluations
 */

const GeoUtils = {
  /**
   * Andrew's Monotone Chain 2D Convex Hull Algorithm
   * @param {Array<{lat: number, lng: number}>} points
   * @returns {Array<[number, number]>} Coordinates of Point, LineString, or closed Polygon
   */
  
  convexHull(points) {
    if (!Array.isArray(points) || points.length === 0) {
      return [];
    }

    // Normalisasi dan hapus koordinat duplikat
    const unique = [
      ...new Map(
        points
          .filter(p =>
            Number.isFinite(p.lat) &&
            Number.isFinite(p.lng)
          )
          .map(p => [`${p.lat},${p.lng}`, p])
      ).values()
    ];

    if (unique.length === 0) return [];

    if (unique.length === 1) {
      return [[unique[0].lat, unique[0].lng]];
    }

    const sorted = unique.sort(
      (a, b) => a.lng - b.lng || a.lat - b.lat
    );

    const cross = (o, a, b) =>
      (a.lng - o.lng) * (b.lat - o.lat) -
      (a.lat - o.lat) * (b.lng - o.lng);
      const EPS = 1e-12;

    const lower = [];
    for (const p of sorted) {
      while (
        lower.length >= 2 &&
        cross(
          lower[lower.length - 2],
          lower[lower.length - 1],
          p
        ) <= EPS
      ) {
        lower.pop();
      }
      lower.push(p);
    }

    const upper = [];
    for (let i = sorted.length - 1; i >= 0; i--) {
      const p = sorted[i];
      while (
        upper.length >= 2 &&
        cross(
          upper[upper.length - 2],
          upper[upper.length - 1],
          p
        ) <= EPS
      ) {
        upper.pop();
      }
      upper.push(p);
    }

    const hull = lower.slice(0, -1).concat(
      upper.slice(0, -1)
    );

    // Titik tunggal
    if (hull.length === 1) {
      return [[hull[0].lat, hull[0].lng]];
    }

    // Dua titik atau titik-titik kolinear
    if (hull.length === 2) {
      return hull.map(p => [p.lat, p.lng]);
    }

    // Polygon: tutup dengan koordinat pertama
    const result = hull.map(p => [p.lat, p.lng]);
    result.push([...result[0]]);

    return result;
  },


  /**
   * Calculate geometric center of points
   */
  calculateCentroid(points) {
    if (!points || points.length === 0) return { lat: -7.9835954, lng: 112.6303597 };
    let sumLat = 0;
    let sumLng = 0;
    points.forEach(p => {
      sumLat += (p.lat || p[0]);
      sumLng += (p.lng || p[1]);
    });
    return {
      lat: sumLat / points.length,
      lng: sumLng / points.length
    };
  },

  /**
   * Variance in cluster sizes (Z1 metric)
   * Z1 = (1 / K) * sum((n_k - mean_n)^2)
   */
  calculateZ1(counts) {
    if (!counts || counts.length === 0) return 0;
    const mean = counts.reduce((a, b) => a + b, 0) / counts.length;
    const variance = counts.reduce((acc, c) => acc + Math.pow(c - mean, 2), 0) / counts.length;
    return variance;
  },

  /**
   * Format numbers to Indonesian locale (dots for thousands, comma for decimal)
   */
  formatNumber(val, decimals = 0) {
    if (val === null || val === undefined || isNaN(val)) return '-';
    return Number(val).toLocaleString('id-ID', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }
};
