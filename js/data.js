/**
 * GeoKurir Malang - Data Store
 * Metadata konfigurasi dan wadah penyimpanan dataset dinamis
 */

const KCU_ORIGIN = {
  "name": "PT Pos Indonesia KCU Malang",
  "lat": -7.9835954,
  "lng": 112.6303597,
  "address": "Jl. Merdeka Selatan No.5, Kauman, Kec. Klojen, Kota Malang"
};

const CLUSTER_METADATA = [
  {
    "id": 1,
    "name": "Cluster 1",
    "color": "#1c2d5a",
    "fillColor": "rgba(28, 45, 90, 0.18)"
  },
  {
    "id": 2,
    "name": "Cluster 2",
    "color": "#ef4123",
    "fillColor": "rgba(239, 65, 35, 0.18)"
  },
  {
    "id": 3,
    "name": "Cluster 3",
    "color": "#0284c7",
    "fillColor": "rgba(2, 132, 199, 0.18)"
  },
  {
    "id": 4,
    "name": "Cluster 4",
    "color": "#059669",
    "fillColor": "rgba(5, 150, 105, 0.18)"
  },
  {
    "id": 5,
    "name": "Cluster 5",
    "color": "#7c3aed",
    "fillColor": "rgba(124, 58, 237, 0.18)"
  }
];

/**
 * Mengambil metadata cluster berdasarkan ID.
 * Cluster 1–5 mempertahankan warna asli.
 * Cluster berikutnya mendapatkan warna secara dinamis.
 */
function getClusterMetadata(clusterId) {
  const id = Number(clusterId);

  if (!Number.isInteger(id) || id < 1) {
    return null;
  }

  const existing = CLUSTER_METADATA.find(c => c.id === id);
  if (existing) return existing;

  // Golden angle untuk distribusi hue cluster tambahan
  const hue = (210 + (id - 6) * 137.508) % 360;
  const color = `hsl(${hue.toFixed(2)}, 70%, 40%)`;

  return {
    id,
    name: `Cluster ${id}`,
    color,
    fillColor: `hsla(${hue.toFixed(2)}, 70%, 40%, 0.18)`
  };
}
// Wadah dataset dinamis yang diisi dari database PostgreSQL / hasil upload pengguna
const DATASETS = {};
