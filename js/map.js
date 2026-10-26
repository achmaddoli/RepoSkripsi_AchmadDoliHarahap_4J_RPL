/**
 * GeoKurir Malang - Interactive Map Controller
 * Integrates Leaflet with Convex Hull overlays and Wireframe-faithful Styling
 * Includes automatic SVG/Canvas fallback for offline rendering
 */

class GeoMapManager {
  constructor() {
    this.maps = {};
    this.layers = {};
  }

  /**
   * Initialize a map instance on a given container element ID
   */
  initMap(containerId, options = {}) {
    const el = document.getElementById(containerId);
    if (!el) return null;

    // Check if Leaflet instance already exists
    if (this.maps[containerId]) {
      try {
        if (typeof this.maps[containerId].remove === 'function') {
          this.maps[containerId].remove();
        }
      } catch (e) {}
      delete this.maps[containerId];
    }

    const defaultLat = KCU_ORIGIN.lat;
    const defaultLng = KCU_ORIGIN.lng;
    const defaultZoom = options.zoom || 12;

    if (typeof L !== 'undefined') {
      try {
        // Clear any previous fallback canvas or svg
        el.innerHTML = '';

        const map = L.map(containerId, {
          zoomControl: true,
          attributionControl: false
        }).setView([defaultLat, defaultLng], defaultZoom);

        // Deteksi Google Maps API Key dari environment .env (di-inject via Flask)
        const gKey = (typeof window !== 'undefined' && window.GOOGLE_MAPS_API_KEY) ? window.GOOGLE_MAPS_API_KEY.trim() : '';

        if (gKey) {
          // Render peta menggunakan Tile resmi Google Maps (Roadmap)
          L.tileLayer(`https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}&key=${gKey}`, {
            maxZoom: 20,
            subdomains: ['0', '1', '2', '3'],
            attribution: '&copy; Google Maps'
          }).addTo(map);
        } else {
          // Fallback elegan: CartoDB Positron / OSM tiles
          L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 19,
            subdomains: 'abcd',
            attribution: '&copy; CartoDB &copy; OpenStreetMap'
          }).addTo(map);
        }

        this.maps[containerId] = map;
        this.layers[containerId] = L.layerGroup().addTo(map);

        setTimeout(() => map.invalidateSize(), 200);
        return map;
      } catch (e) {
        console.warn('Leaflet initialization fallback to SVG/Canvas:', e);
      }
    }

    // Mark as fallback container
    this.maps[containerId] = { isFallback: true, container: el };
    return this.maps[containerId];
  }

  /**
   * Render clusters, convex hulls, points, and origin hub marker
   */
  renderClustering(containerId, points, mode = 'kmeans') {
    const map = this.maps[containerId];
    if (!map) return;

    if (!points || points.length === 0) {
      this.renderEmptyMap(containerId);
      return;
    }

    if (!map.isFallback && typeof L !== 'undefined') {
      this.renderLeafletClustering(containerId, points, mode);
    } else {
      this.renderFallbackClustering(containerId, points, mode);
    }
  }

  /**
   * Render empty state map centered on KCU Pos Malang
   */
  renderEmptyMap(containerId) {
    const map = this.maps[containerId];
    if (!map) return;

    if (!map.isFallback && typeof L !== 'undefined') {
      const layerGroup = this.layers[containerId];
      if (layerGroup) layerGroup.clearLayers();

      const kcuIcon = L.divIcon({
        className: 'kcu-marker-icon',
        html: `
          <div style="
            background: #1c2d5a;
            color: white;
            width: 34px;
            height: 34px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(28,45,90,0.35);
            border: 2px solid #ef4123;
          ">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              <polyline points="9 22 9 12 15 12 15 22"></polyline>
            </svg>
          </div>
        `,
        iconSize: [34, 34],
        iconAnchor: [17, 17]
      });

      const kcuMarker = L.marker([KCU_ORIGIN.lat, KCU_ORIGIN.lng], { icon: kcuIcon })
        .bindPopup(`
          <div style="font-family: inherit; font-size: 13px; line-height: 1.5;">
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
              <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #ef4123;"></span>
              <strong style="color: #1c2d5a; font-size: 14px;">${KCU_ORIGIN.name}</strong>
            </div>
            <span style="color: #64748b; font-size: 12px;">Hub Distribusi Malang (Siap menerima dataset)</span>
          </div>
        `);

      if (layerGroup) layerGroup.addLayer(kcuMarker);
      map.setView([KCU_ORIGIN.lat, KCU_ORIGIN.lng], 13);
    }
  }

  /**
   * Render with Leaflet
   */
  renderLeafletClustering(containerId, points, mode) {
    const map = this.maps[containerId];
    const layerGroup = this.layers[containerId];
    layerGroup.clearLayers();

    const clusterKey = mode === 'kmeans' ? 'c_init' : 'c_final';
    const clusterGroups = {};

    points.forEach(pt => {
  const cId = Number(pt[clusterKey]);

  // Hanya kelompokkan titik yang sudah memiliki nomor cluster valid
  if (!Number.isInteger(cId) || cId <= 0) return;

  if (!clusterGroups[cId]) clusterGroups[cId] = [];
  clusterGroups[cId].push(pt);
});

    const bounds = [];

    // 1. KCU Pos Malang Hub Marker (POS IND Branded)
    const kcuIcon = L.divIcon({
      className: 'kcu-marker-icon',
      html: `
        <div style="
          background: #1c2d5a;
          color: white;
          width: 34px;
          height: 34px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 12px rgba(28,45,90,0.35);
          border: 2px solid #ef4123;
        ">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
            <polyline points="9 22 9 12 15 12 15 22"></polyline>
          </svg>
        </div>
      `,
      iconSize: [34, 34],
      iconAnchor: [17, 17]
    });

    const kcuMarker = L.marker([KCU_ORIGIN.lat, KCU_ORIGIN.lng], { icon: kcuIcon })
      .bindPopup(`
        <div style="font-family: inherit; font-size: 13px; line-height: 1.5;">
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
            <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #ef4123;"></span>
            <strong style="color: #1c2d5a; font-size: 14px;">${KCU_ORIGIN.name}</strong>
          </div>
          <span style="color: #64748b; font-size: 12px;">Hub Pusat Distribusi & Titik Acuan</span><br>
          <div style="margin-top: 8px; font-size: 11.5px; background: #edf3fb; color: #1c2d5a; padding: 6px 10px; border-radius: 4px; border: 1px solid #d5e2f5;">
            <strong>Latitude:</strong> ${KCU_ORIGIN.lat}<br>
            <strong>Longitude:</strong> ${KCU_ORIGIN.lng}
          </div>
        </div>
      `);
    layerGroup.addLayer(kcuMarker);
    bounds.push([KCU_ORIGIN.lat, KCU_ORIGIN.lng]);

    // 2. Draw Convex Hulls and Labels
Object.keys(clusterGroups).forEach(clusterId => {
  const cMeta = getClusterMetadata(clusterId);
  if (!cMeta) return;

  const pts = clusterGroups[clusterId];
  if (pts.length === 0) return;

      
      const hullCoords = GeoUtils.convexHull(pts);

      if (hullCoords.length > 0) {
        const hullStyle = {
          color: '#374151',
          weight: 2,
          dashArray: '3, 4',
          fillColor: cMeta.color,
          fillOpacity: 0.16
        };

        let hullLayer;

        if (hullCoords.length === 1) {
          hullLayer = L.circleMarker(hullCoords[0], {
            radius: 8,
            color: '#374151',
            weight: 2,
            fillColor: cMeta.color,
            fillOpacity: 0.16
          });
        } else if (hullCoords.length === 2) {
          hullLayer = L.polyline(hullCoords, hullStyle);
        } else {
          hullLayer = L.polygon(hullCoords, hullStyle);
        }

        hullLayer.bindTooltip(
          `${cMeta.name} (Batas Convex Hull)`,
          { sticky: true }
        );

        layerGroup.addLayer(hullLayer);

        const centroid = GeoUtils.calculateCentroid(pts);
        const labelIcon = L.divIcon({
          className: 'cluster-label-badge',
          html: `
            <div style="
              background: rgba(255, 255, 255, 0.95);
              border: 1px solid #d1d5db;
              border-radius: 20px;
              padding: 2px 10px;
              font-size: 11px;
              font-weight: 700;
              color: #1f2937;
              white-space: nowrap;
              box-shadow: 0 2px 5px rgba(0,0,0,0.1);
              display: inline-flex;
              align-items: center;
              gap: 4px;
            ">
              <span style="width: 8px; height: 8px; border-radius: 50%; background: ${cMeta.color};"></span>
              ${cMeta.name}
            </div>
          `,
          iconAnchor: [38, 12]
        });

        layerGroup.addLayer(L.marker([centroid.lat, centroid.lng], { icon: labelIcon }));
      }
    });

    // 3. Draw Points
points.forEach(pt => {
  const cId = Number(pt[clusterKey]);
  const hasCluster = Number.isInteger(cId) && cId > 0;
  const cMeta = hasCluster ? getClusterMetadata(cId) : null;

      const circleMarker = L.circleMarker([pt.lat, pt.lng], {
        radius: 5,
        fillColor: cMeta ? cMeta.color : '#1c2d5a',
        color: '#111827',
        weight: 1,
        opacity: 0.9,
        fillOpacity: 0.85
      }).bindPopup(`
        <div style="font-family: inherit; font-size: 12px; line-height: 1.4;">
          <strong style="color: #111827;">${pt.resi} (${pt.id})</strong><br>
          <span style="color: #4b5563;">${pt.alamat}</span><br>
          <div style="margin-top: 6px; display: flex; gap: 6px;">
            ${hasCluster ? `
  <span style="background: ${cMeta.fillColor}; color: ${cMeta.color}; font-weight: 600; padding: 2px 6px; border-radius: 4px; font-size: 11px;">
    ${cMeta.name}
  </span>
` : `
  <span style="color: #64748b; font-size: 11px;">
    Belum dilakukan clustering
  </span>
`}

${hasCluster && pt.status === 'Berpindah'
  ? '<span style="background: #fef3c7; color: #b45309; font-weight: 600; padding: 2px 6px; border-radius: 4px; font-size: 11px;">Direassignment</span>'
  : ''}
          </div>
        </div>
      `);

      layerGroup.addLayer(circleMarker);
      bounds.push([pt.lat, pt.lng]);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [35, 35], maxZoom: 14 });
    }
  }

  /**
   * Offline SVG / Canvas Fallback Renderer
   */
  renderFallbackClustering(containerId, points, mode) {
    const el = document.getElementById(containerId);
    if (!el) return;

    const width = el.clientWidth || 500;
    const height = el.clientHeight || 360;

    let minLat = KCU_ORIGIN.lat, maxLat = KCU_ORIGIN.lat;
    let minLng = KCU_ORIGIN.lng, maxLng = KCU_ORIGIN.lng;

    points.forEach(p => {
      if (p.lat < minLat) minLat = p.lat;
      if (p.lat > maxLat) maxLat = p.lat;
      if (p.lng < minLng) minLng = p.lng;
      if (p.lng > maxLng) maxLng = p.lng;
    });

    const padding = 45;
    const toX = (lng) => padding + ((lng - minLng) / (maxLng - minLng || 0.01)) * (width - 2 * padding);
    const toY = (lat) => height - (padding + ((lat - minLat) / (maxLat - minLat || 0.01)) * (height - 2 * padding));

    const clusterKey = mode === 'kmeans' ? 'c_init' : 'c_final';
    const clusterGroups = {};
    points.forEach(pt => {
  const cId = Number(pt[clusterKey]);

  // Hanya kelompokkan titik yang sudah memiliki nomor cluster valid
  if (!Number.isInteger(cId) || cId <= 0) return;

  if (!clusterGroups[cId]) clusterGroups[cId] = [];
  clusterGroups[cId].push(pt);
});

    let svgContent = `
      <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg" style="background: #f8fafc; font-family: inherit;">
        <defs>
          <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
            <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#e2e8f0" stroke-width="0.7"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
    `;

    
    Object.keys(clusterGroups).forEach(clusterId => {
  const cMeta = getClusterMetadata(clusterId);
  if (!cMeta) return;

  const pts = clusterGroups[clusterId];
  if (pts.length === 0) return;

      const hullCoords = GeoUtils.convexHull(pts);
      if (hullCoords.length === 0) return;

      const toSvgPoint = coord => ({
        x: toX(coord[1]),
        y: toY(coord[0])
      });

      if (hullCoords.length === 1) {
        // Satu titik: tampilkan lingkaran batas
        const p = toSvgPoint(hullCoords[0]);

        svgContent += `
          <circle
            cx="${p.x.toFixed(1)}"
            cy="${p.y.toFixed(1)}"
            r="8"
            fill="${cMeta.color}"
            fill-opacity="0.16"
            stroke="#374151"
            stroke-width="2"
          />
        `;

      } else if (hullCoords.length === 2) {
        // Dua titik atau kolinear: tampilkan garis
        const p1 = toSvgPoint(hullCoords[0]);
        const p2 = toSvgPoint(hullCoords[1]);

        svgContent += `
          <line
            x1="${p1.x.toFixed(1)}"
            y1="${p1.y.toFixed(1)}"
            x2="${p2.x.toFixed(1)}"
            y2="${p2.y.toFixed(1)}"
            stroke="#374151"
            stroke-width="1.8"
            stroke-dasharray="4,4"
          />
        `;

      } else {
        // Tiga titik atau lebih: polygon tertutup
        const pathData = hullCoords.map((coord, idx) => {
          const p = toSvgPoint(coord);
          return `${idx === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
        }).join(' ') + ' Z';

        svgContent += `
          <path
            d="${pathData}"
            fill="${cMeta.fillColor}"
            stroke="#374151"
            stroke-width="1.8"
            stroke-dasharray="4,4"
          />
        `;
      }

      // Label cluster tetap ditampilkan
      const center = GeoUtils.calculateCentroid(pts);
      const cx = toX(center.lng);
      const cy = toY(center.lat);

      svgContent += `
        <rect x="${cx - 32}" y="${cy - 10}"
              width="64" height="20" rx="10"
              fill="#ffffff" stroke="#cbd5e1"
              filter="drop-shadow(0 2px 4px rgba(0,0,0,0.1))" />
        <circle cx="${cx - 20}" cy="${cy}" r="4"
                fill="${cMeta.color}" />
        <text x="${cx - 10}" y="${cy + 4}"
              font-size="10" font-weight="700"
              fill="#1f2937">${cMeta.name}</text>
      `;
    });

    points.forEach(pt => {
  const cId = Number(pt[clusterKey]);
  const hasCluster = Number.isInteger(cId) && cId > 0;
  const cMeta = hasCluster ? getClusterMetadata(cId) : null;
  const pointColor = cMeta ? cMeta.color : '#1c2d5a';

  const px = toX(pt.lng);
  const py = toY(pt.lat);

  svgContent += `
    <circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="4.5" fill="${pointColor}" stroke="#111827" stroke-width="1">
      <title>${pt.resi}: ${pt.alamat}</title>
    </circle>
  `;
});

    const kx = toX(KCU_ORIGIN.lng);
    const ky = toY(KCU_ORIGIN.lat);

    svgContent += `
      <g transform="translate(${kx - 14}, ${ky - 14})">
        <rect width="28" height="28" rx="6" fill="#1c2d5a" stroke="#ef4123" stroke-width="2" />
        <path d="M5 11 L14 4 L23 11 V22 H7 Z" fill="none" stroke="#ffffff" stroke-width="2" />
        <circle cx="14" cy="18" r="2" fill="#ef4123" />
        <title>${KCU_ORIGIN.name} (Origin Hub)</title>
      </g>
    `;

    svgContent += '</svg>';
    el.innerHTML = svgContent;
  }
}

const mapManager = new GeoMapManager();
