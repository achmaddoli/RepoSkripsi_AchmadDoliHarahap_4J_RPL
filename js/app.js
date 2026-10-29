/**
 * GeoKurir Malang - Main Application Logic & Interactivity
 * Integrated with Flask Backend & PostgreSQL Database
 * Gracefully falls back to client-side data when opened standalone (file://)
 */

document.addEventListener('DOMContentLoaded', () => {
  const isServerMode = window.location.protocol.startsWith('http');

  // Application State
  const state = {
    currentView: 'dashboard',
    activeDatasetKey: null, // Default null: tidak memuat data dummy statis
    zonaMode: 'kmeans', // 'kmeans' | 'hbcdp'
    tableSearchQuery: '',
    tableCurrentPage: 1,
    tablePageSize: 5,
    geocodingProgress: 0,
    currentDbDatasetId: null,
    datasets: [],
    deletingDatasetIds: new Set(),
    selectedDeleteDatasetIds: new Set(),
    loadingDeleteDatasets: false,
    deleteDatasetError: '',

// Status proses upload hingga clustering
uploadStatus: 'idle', // idle, uploading, geocoding, ready, error
readyDatasetId: null,
geocodedPointCount: 0,
isClustering: false
  };

  // DOM Elements
  const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
  const viewPages = document.querySelectorAll('.view-page');
  const processSelector = document.getElementById('select-process-dashboard');
  const mobileToggle = document.getElementById('mobile-toggle');
  const sidebar = document.getElementById('sidebar');
  const deleteDatasetsBody = document.getElementById('table-delete-datasets-body');
  const deleteDatasetStatus = document.getElementById('delete-dataset-status');
  const deleteDatasetSearch = document.getElementById('search-delete-dataset');
  const refreshDeleteDatasets = document.getElementById('btn-refresh-delete-datasets');
  const selectAllDeleteDatasets = document.getElementById('select-all-delete-datasets');
  const deleteSelectedDatasets = document.getElementById('btn-delete-selected-datasets');
  const deleteDatasetSelectionCount = document.getElementById('delete-dataset-selection-count');

  // Tab buttons for Hasil Pembagian Zona
  const tabKmeans = document.getElementById('tab-kmeans');
  const tabHbcdp = document.getElementById('tab-hbcdp');
  const zonaMapTitle = document.getElementById('zona-map-title');
  const zonaSummaryTitle = document.getElementById('zona-summary-title');

  // Table search & pagination
  const searchInput = document.getElementById('search-resi-alamat');
  const tableBody = document.getElementById('table-anggota-body');
  const paginationInfo = document.getElementById('pagination-info');
  const paginationControls = document.getElementById('pagination-controls');

  // File upload elements
  const dropzone = document.getElementById('upload-dropzone');
  const fileInput = document.getElementById('file-input');
  const btnSelectFile = document.getElementById('btn-select-file');
  const selectedFileCard = document.getElementById('selected-file-card');
  const selectedFileName = document.getElementById('selected-file-name');
  const selectedFileMeta = document.getElementById('selected-file-meta');
  const btnRemoveFile = document.getElementById('btn-remove-file');
  const btnStartClustering = document.getElementById('btn-start-clustering');
  const inputClusterK = document.getElementById('input-cluster-k');
  const clusteringBtnDefaultHtml = btnStartClustering
  ? btnStartClustering.innerHTML
  : '';

function updateClusteringButtonState() {
  if (!btnStartClustering) return;

  const isReady =
    state.uploadStatus === 'ready' &&
    state.readyDatasetId != null &&
    state.geocodedPointCount >= 3;

  btnStartClustering.disabled = !isReady || state.isClustering;

  // Ubah tampilan tanpa mengubah CSS utama
  btnStartClustering.style.opacity =
    state.isClustering || isReady ? '1' : '0.55';

  btnStartClustering.style.filter =
    state.isClustering || isReady ? '' : 'grayscale(1)';

  btnStartClustering.style.cursor =
    state.isClustering ? 'wait' :
    isReady ? 'pointer' : 'not-allowed';

  if (!state.isClustering) {
    btnStartClustering.innerHTML = clusteringBtnDefaultHtml;
  }

  if (state.isClustering) {
    btnStartClustering.title = 'Clustering sedang berlangsung';
  } else if (state.uploadStatus === 'uploading') {
    btnStartClustering.title = 'Tunggu proses upload dan preprocessing';
  } else if (state.uploadStatus === 'geocoding') {
    btnStartClustering.title = 'Tunggu proses geocoding selesai';
  } else if (isReady) {
    btnStartClustering.title = 'Jalankan K-Means dan HBCDP';
  } else {
    btnStartClustering.title =
      'Unggah dataset dan selesaikan geocoding terlebih dahulu';
  }
}

  // Geocoding progress
  const progressBarFill = document.getElementById('progress-bar-fill');
  const progressTextLabel = document.getElementById('progress-text-label');
  const progressPercentText = document.getElementById('progress-percent-text');

  // Download buttons
  const btnDownloadExcel = document.getElementById('btn-download-excel');
  const btnDownloadCsv = document.getElementById('btn-download-csv');
  const btnDownloadResultCsv = document.getElementById('btn-download-result-csv');

  // ------------------------------------------------------------------------
  // 1. Navigation & Routing
  // ------------------------------------------------------------------------
  function switchView(viewId) {
    state.currentView = viewId;
    window.location.hash = viewId;

    navItems.forEach(item => {
      if (item.dataset.view === viewId) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    viewPages.forEach(page => {
      if (page.id === `view-${viewId}`) {
        page.classList.add('active');
      } else {
        page.classList.remove('active');
      }
    });

    if (sidebar && sidebar.classList.contains('mobile-open')) {
      sidebar.classList.remove('mobile-open');
    }

    setTimeout(() => {
      if (viewId === 'dashboard') {
        updateDashboardView();
      } else if (viewId === 'zona') {
        renderZonaMap();
      } else if (viewId === 'evaluasi') {
        updateEvaluasiView();
      } else if (viewId === 'hapus-dataset') {
        loadDeleteDatasets();
      }
    }, 150);
  }

  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      switchView(item.dataset.view);
    });
  });

  if (mobileToggle) {
    mobileToggle.addEventListener('click', () => {
      sidebar.classList.toggle('mobile-open');
    });
  }

  function initRouting() {
    const hash = window.location.hash.replace('#', '');
    const path = window.location.pathname.replace(/^\//, '').replace(/\.html$/, '');
    if (['dashboard', 'upload', 'zona', 'evaluasi', 'hapus-dataset'].includes(hash)) {
      switchView(hash);
    } else if (['dashboard', 'upload', 'zona', 'evaluasi', 'hapus-dataset'].includes(path)) {
      switchView(path);
    } else {
      switchView('dashboard');
    }
  }

  // ------------------------------------------------------------------------
  // 2. Flask API Integration & Dataset Syncing
  // ------------------------------------------------------------------------
  function formatDateTimeIndo(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const bulan = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
    const tgl = String(d.getDate()).padStart(2, '0');
    const bln = bulan[d.getMonth()];
    const thn = d.getFullYear();
    const jam = String(d.getHours()).padStart(2, '0');
    const mnt = String(d.getMinutes()).padStart(2, '0');
    return `${tgl} ${bln} ${thn}, ${jam}:${mnt}`;
  }

  async function syncDatasetsFromBackend() {
    if (!isServerMode) {
      updateDashboardView();
      updateZonaSummary();
      renderAnggotaTable();
      updateEvaluasiView();
      return;
    }

    try {
      const resp = await fetch('/api/datasets');
      const json = await resp.json();
      if (!resp.ok || !json.success) throw new Error(json.error || 'Gagal memuat dataset.');
      state.datasets = json.data || [];
      state.deleteDatasetError = '';
      renderDeleteDatasets();
      if (json.success && json.data && json.data.length > 0) {
        if (processSelector) {
          processSelector.innerHTML = '';
          json.data.forEach((ds) => {
            const opt = document.createElement('option');
            opt.value = `db_${ds.id_dataset}`;

            // 1. Keterangan jumlah titik yang diproses
            let titikText = '';
            if (ds.titik_diproses && ds.titik_diproses > 0) {
              titikText = `${GeoUtils.formatNumber(ds.titik_diproses)} titik diproses`;
            } else if (ds.status === 'UPLOADED' || !ds.titik_diproses) {
              titikText = 'Belum diproses';
            } else {
              titikText = `${GeoUtils.formatNumber(ds.jumlah_data)} titik`;
            }

            // 2. Keterangan tanggal dan waktu proses (tanpa id_dataset)
            const waktuStr = ds.waktu_proses || ds.waktu_upload;
            const waktuDisplay = formatDateTimeIndo(waktuStr) || ds.tanggal_data || '';

            opt.textContent = `${ds.nama_file} (${titikText}) — ${waktuDisplay}`;
            processSelector.appendChild(opt);
          });

          // Pilih dataset pertama dari database jika belum terpilih
          const targetId = json.data.some(ds => ds.id_dataset === state.currentDbDatasetId)
            ? state.currentDbDatasetId : json.data[0].id_dataset;
          processSelector.value = `db_${targetId}`;
          await loadDatasetFromDb(targetId);
        }
      } else {
        // Database kosong: reset tampilan ke empty state tanpa fallback mock
        if (processSelector) {
          processSelector.innerHTML = '<option value="none">-- Belum ada dataset (Silakan unggah) --</option>';
        }
        state.activeDatasetKey = null;
        state.currentDbDatasetId = null;
        updateDashboardView();
        updateZonaSummary();
        renderAnggotaTable();
        updateEvaluasiView();
      }
    } catch (e) {
      console.warn('Backend API error saat mengambil dataset:', e);
      if (processSelector) {
        processSelector.innerHTML = '<option value="none">-- Belum ada dataset (Silakan unggah) --</option>';
      }
      state.activeDatasetKey = null;
      updateDashboardView();
      updateZonaSummary();
      renderAnggotaTable();
      updateEvaluasiView();
    }
  }

  function getVisibleDeleteDatasets() {
    const search = (deleteDatasetSearch?.value || '').trim().toLocaleLowerCase('id');
    return state.deleteDatasetError ? [] : state.datasets.filter(ds =>
      ds.nama_file.toLocaleLowerCase('id').includes(search));
  }

  function updateDeleteSelectionControls() {
    const visible = getVisibleDeleteDatasets();
    const selectedVisible = visible.filter(ds => state.selectedDeleteDatasetIds.has(ds.id_dataset)).length;
    const busy = state.deletingDatasetIds.size > 0 || state.loadingDeleteDatasets;
    if (selectAllDeleteDatasets) {
      selectAllDeleteDatasets.checked = visible.length > 0 && selectedVisible === visible.length;
      selectAllDeleteDatasets.indeterminate = selectedVisible > 0 && selectedVisible < visible.length;
      selectAllDeleteDatasets.disabled = busy || visible.length === 0;
    }
    if (deleteSelectedDatasets) {
      deleteSelectedDatasets.disabled = busy || state.selectedDeleteDatasetIds.size === 0 || !!state.deleteDatasetError;
      deleteSelectedDatasets.textContent = state.deletingDatasetIds.size > 0 ? 'Menghapus…' : 'Hapus terpilih';
    }
    if (deleteDatasetSelectionCount) {
      deleteDatasetSelectionCount.textContent = `${state.selectedDeleteDatasetIds.size} dataset dipilih`;
    }
    if (refreshDeleteDatasets) refreshDeleteDatasets.disabled = busy;
    deleteDatasetsBody?.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
      checkbox.checked = state.selectedDeleteDatasetIds.has(Number(checkbox.dataset.datasetId));
      checkbox.disabled = busy;
    });
  }

  function renderDeleteDatasets() {
    if (!deleteDatasetsBody || !deleteDatasetStatus) return;
    const datasetIds = new Set(state.datasets.map(ds => ds.id_dataset));
    state.selectedDeleteDatasetIds.forEach(id => {
      if (!datasetIds.has(id)) state.selectedDeleteDatasetIds.delete(id);
    });
    const visible = getVisibleDeleteDatasets();
    deleteDatasetsBody.replaceChildren();
    updateDeleteSelectionControls();
    deleteDatasetStatus.textContent = state.deleteDatasetError || (
      state.datasets.length === 0
        ? 'Belum ada dataset tersimpan.'
        : `${visible.length} dari ${state.datasets.length} dataset ditampilkan.`
    );
    if (state.deleteDatasetError || visible.length === 0) {
      const row = deleteDatasetsBody.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 6;
      cell.textContent = state.deleteDatasetError
        ? 'Klik Muat ulang untuk mencoba kembali.'
        : state.datasets.length > 0 ? 'Tidak ada dataset yang sesuai pencarian.' : 'Dataset akan tampil setelah diunggah.';
      return;
    }
    visible.forEach(ds => {
      const row = deleteDatasetsBody.insertRow();
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.dataset.datasetId = ds.id_dataset;
      checkbox.setAttribute('aria-label', `Pilih dataset ${ds.nama_file}`);
      checkbox.checked = state.selectedDeleteDatasetIds.has(ds.id_dataset);
      checkbox.disabled = state.deletingDatasetIds.size > 0 || state.loadingDeleteDatasets;
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) state.selectedDeleteDatasetIds.add(ds.id_dataset);
        else state.selectedDeleteDatasetIds.delete(ds.id_dataset);
        updateDeleteSelectionControls();
      });
      const selectionCell = row.insertCell();
      selectionCell.className = 'delete-dataset-checkbox-cell';
      selectionCell.appendChild(checkbox);
      [ds.nama_file, ds.tanggal_data, GeoUtils.formatNumber(ds.jumlah_data),
        ds.waktu_proses ? formatDateTimeIndo(ds.waktu_proses) : 'Belum diproses'].forEach(value => {
        row.insertCell().textContent = value;
      });
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn btn-danger';
      button.dataset.datasetId = ds.id_dataset;
      button.textContent = state.deletingDatasetIds.has(ds.id_dataset) ? 'Menghapus…' : 'Hapus';
      button.setAttribute('aria-label', `Hapus dataset ${ds.nama_file}`);
      button.disabled = state.deletingDatasetIds.size > 0 || state.loadingDeleteDatasets;
      button.addEventListener('click', () => removeDatasets([ds]));
      row.insertCell().appendChild(button);
    });
  }

  async function loadDeleteDatasets() {
    if (state.deletingDatasetIds.size > 0 || state.loadingDeleteDatasets) return;
    if (!isServerMode) {
      state.deleteDatasetError = 'Hubungkan ke server untuk mengelola dataset.';
      renderDeleteDatasets();
      return;
    }
    state.loadingDeleteDatasets = true;
    renderDeleteDatasets();
    deleteDatasetStatus.textContent = 'Memuat daftar dataset…';
    try {
      const response = await fetch('/api/datasets', { cache: 'no-store' });
      const json = await response.json();
      if (!response.ok || !json.success) throw new Error(json.error || 'Gagal memuat daftar dataset.');
      state.datasets = json.data || [];
      state.deleteDatasetError = '';
    } catch (error) {
      state.deleteDatasetError = error.message;
    } finally {
      state.loadingDeleteDatasets = false;
      renderDeleteDatasets();
    }
  }

  async function removeDatasets(datasets) {
    if (state.deletingDatasetIds.size > 0 || state.loadingDeleteDatasets || datasets.length === 0) return;
    if (state.isClustering || state.uploadStatus === 'geocoding') {
      showToast('Tunggu proses geocoding atau clustering selesai sebelum menghapus dataset.');
      return;
    }
    const description = datasets.length === 1
      ? `Hapus dataset "${datasets[0].nama_file}" (${GeoUtils.formatNumber(datasets[0].jumlah_data)} titik)?`
      : `Hapus ${datasets.length} dataset terpilih (${GeoUtils.formatNumber(datasets.reduce((total, ds) => total + ds.jumlah_data, 0))} titik)?\n` +
        datasets.map(ds => `• ${ds.nama_file}`).join('\n');
    const confirmed = window.confirm(
      `${description}\n\n` +
      'Semua titik pengiriman, hasil clustering, evaluasi, zona kurir, dan riwayatnya akan dihapus permanen. Tindakan ini tidak dapat dibatalkan.'
    );
    if (!confirmed) return;
    const ids = datasets.map(ds => ds.id_dataset);
    state.deletingDatasetIds = new Set(ids);
    renderDeleteDatasets();
    try {
      const response = await fetch('/api/datasets', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids })
      });
      const json = await response.json();
      if (!response.ok || !json.success) throw new Error(json.error || 'Gagal menghapus dataset.');
      ids.forEach(id => {
        delete DATASETS[`db_${id}`];
        state.selectedDeleteDatasetIds.delete(id);
      });
      state.datasets = state.datasets.filter(item => !state.deletingDatasetIds.has(item.id_dataset));
      if (state.deletingDatasetIds.has(state.currentDbDatasetId)) {
        state.currentDbDatasetId = null;
        state.activeDatasetKey = null;
        state.tableCurrentPage = 1;
      }
      if (state.deletingDatasetIds.has(state.readyDatasetId)) {
        state.readyDatasetId = null;
        state.geocodedPointCount = 0;
        state.uploadStatus = 'idle';
        updateClusteringButtonState();
      }
      state.deleteDatasetError = '';
      renderDeleteDatasets();
      showToast(json.message);
      await syncDatasetsFromBackend();
      renderZonaMap();
    } catch (error) {
      showToast(error.message);
    } finally {
      state.deletingDatasetIds.clear();
      renderDeleteDatasets();
    }
  }

  deleteDatasetSearch?.addEventListener('input', renderDeleteDatasets);
  refreshDeleteDatasets?.addEventListener('click', loadDeleteDatasets);
  selectAllDeleteDatasets?.addEventListener('change', () => {
    getVisibleDeleteDatasets().forEach(ds => {
      if (selectAllDeleteDatasets.checked) state.selectedDeleteDatasetIds.add(ds.id_dataset);
      else state.selectedDeleteDatasetIds.delete(ds.id_dataset);
    });
    updateDeleteSelectionControls();
  });
  deleteSelectedDatasets?.addEventListener('click', () => {
    removeDatasets(state.datasets.filter(ds => state.selectedDeleteDatasetIds.has(ds.id_dataset)));
  });

  async function loadDatasetFromDb(id_dataset) {
    try {
      const [detailRes, pointsRes] = await Promise.all([
        fetch(`/api/dataset/${id_dataset}`),
        fetch(`/api/dataset/${id_dataset}/points`)
      ]);

      const detailJson = await detailRes.json();
      const pointsJson = await pointsRes.json();

      if (detailJson.success && pointsJson.success) {
        const d = detailJson.data;
        console.log('DEBUG JUMLAH CLUSTER:', {
  id_dataset: id_dataset,
  jumlah_kurir_database: d.dataset.jumlah_kurir,
  jumlah_cluster_kmeans: (d.clusters_kmeans || []).length,
  jumlah_zona_hbcdp: (d.zonas_hbcdp || []).length
});
        const dsKey = `db_${id_dataset}`;
        state.currentDbDatasetId = id_dataset;

        // Hitung jumlah titik yang benar-benar diproses clustering
        const processedCount = (d.clusters_kmeans && d.clusters_kmeans.length > 0)
          ? d.clusters_kmeans.reduce((sum, c) => sum + (c.jumlah_anggota || 0), 0)
          : d.dataset.jumlah_data;

        // Periksa apakah hasil clustering benar-benar tersedia
const hasKmeansResult =
  Array.isArray(d.clusters_kmeans) &&
  d.clusters_kmeans.length > 0;

const hasHbcdpResult =
  Array.isArray(d.zonas_hbcdp) &&
  d.zonas_hbcdp.length > 0;

// Siapkan objek dataset terintegrasi
DATASETS[dsKey] = {
          id: dsKey,
          dbId: id_dataset,
          label: `${d.dataset.nama_file} (${GeoUtils.formatNumber(processedCount)} titik diproses)`,
          totalPoints: processedCount,
          rawTotalPoints: d.dataset.jumlah_data,
          fileName: d.dataset.nama_file,
          k: hasKmeansResult
  ? (
      d.clustering && d.clustering.jumlah_cluster != null
        ? Number(d.clustering.jumlah_cluster)
        : d.clusters_kmeans.length
    )
  : null,
          clusters: {
            kmeans: (d.clusters_kmeans || []).map(c => ({
              id: c.nomor_cluster,
              name: `Cluster ${c.nomor_cluster}`,
              count: c.jumlah_anggota
            })),
            hbcdp: (d.zonas_hbcdp || []).map(z => ({
              id: z.nomor_zona,
              name: `Cluster ${z.nomor_zona}`,
              count: z.jumlah_anggota
            }))
          },
          evaluation: {
            kmeans: {
              silhouette: (d.clustering && d.clustering.silhouette_score != null) ? d.clustering.silhouette_score : null,
              dbi: (d.clustering && d.clustering.dbi != null) ? d.clustering.dbi : null,
              z1: (d.clustering && d.clustering.z1 != null) ? d.clustering.z1 : null,
              z2: 0.00
            },
            hbcdp: {
              silhouette: (d.optimasi && d.optimasi.silhouette_score != null) ? d.optimasi.silhouette_score : null,
              dbi: (d.optimasi && d.optimasi.dbi != null) ? d.optimasi.dbi : null,
              z1: (d.optimasi && d.optimasi.nilai_z1 != null) ? d.optimasi.nilai_z1 : null,
              z2: (d.optimasi && d.optimasi.nilai_z2 != null) ? d.optimasi.nilai_z2 : null
            },
            steps: (d.optimasi && d.optimasi.steps && d.optimasi.steps.length > 0)
              ? d.optimasi.steps
              : []
          },
          points: (pointsJson.data || []).map((pt, i) => {
  const cInit = hasKmeansResult ? (pt.c_init ?? null) : null;
  const cFinal = hasHbcdpResult ? (pt.c_final ?? null) : null;

  return {
    id: `A${i + 1}`,
    resi: pt.nosi ?? '-',
    alamat: pt.alamat_bersih || pt.alamat_asli,
    kecamatan: 'Malang',
    lat: pt.latitude || KCU_ORIGIN.lat,
    lng: pt.longitude || KCU_ORIGIN.lng,

    c_init: cInit,
    c_final: cFinal,

    status: cInit != null && cFinal != null
      ? (pt.status || (cFinal !== cInit ? 'Berpindah' : 'Tetap'))
      : null
  };
})
        };

        state.activeDatasetKey = dsKey;
        updateDashboardView();
        updateZonaSummary();
        renderAnggotaTable();
        updateEvaluasiView();
      }
    } catch (err) {
      console.error('Error loading dataset from DB:', err);
    }
  }

  // ------------------------------------------------------------------------
  // 3. Dashboard Updating
  // ------------------------------------------------------------------------
  function updateDashboardView() {
    const dsKey = state.activeDatasetKey;
    const ds = dsKey ? DATASETS[dsKey] : null;

    const kpiTitik = document.getElementById('kpi-jumlah-titik');
    const kpiCluster = document.getElementById('kpi-jumlah-cluster');

    if (!ds) {
      if (kpiTitik) kpiTitik.textContent = '-';
      if (kpiCluster) kpiCluster.textContent = '-';
      updateEvaluationTable(null);
      updateClusterDistributionTable(null);
      renderDashboardMaps();
      return;
    }

    if (kpiTitik) {
  kpiTitik.textContent = GeoUtils.formatNumber(ds.totalPoints);
}

if (kpiCluster) {
  kpiCluster.textContent =
    (ds.k != null && Number.isInteger(ds.k) && ds.k > 0)
      ? ds.k
      : '-';
}

    updateEvaluationTable(ds.evaluation);
    updateClusterDistributionTable(ds.clusters);
    renderDashboardMaps();
  }

  function updateEvaluationTable(evaluation) {
    const kmSilhouette = document.getElementById('eval-km-silhouette');
    const hbSilhouette = document.getElementById('eval-hb-silhouette');
    const kmDbi = document.getElementById('eval-km-dbi');
    const hbDbi = document.getElementById('eval-hb-dbi');
    const kmZ1 = document.getElementById('eval-km-z1');
    const hbZ1 = document.getElementById('eval-hb-z1');
    const kmZ2 = document.getElementById('eval-km-z2');
    const hbZ2 = document.getElementById('eval-hb-z2');

    if (!evaluation) {
      [kmSilhouette, hbSilhouette, kmDbi, hbDbi, kmZ1, hbZ1, kmZ2, hbZ2].forEach(el => {
        if (el) el.textContent = '-';
      });
      return;
    }

    if (kmSilhouette) kmSilhouette.textContent = (evaluation.kmeans && evaluation.kmeans.silhouette != null) ? evaluation.kmeans.silhouette.toFixed(3) : '-';
    if (hbSilhouette) hbSilhouette.textContent = (evaluation.hbcdp && evaluation.hbcdp.silhouette != null) ? evaluation.hbcdp.silhouette.toFixed(3) : '-';
    if (kmDbi) kmDbi.textContent = (evaluation.kmeans && evaluation.kmeans.dbi != null) ? evaluation.kmeans.dbi.toFixed(3) : '-';
    if (hbDbi) hbDbi.textContent = (evaluation.hbcdp && evaluation.hbcdp.dbi != null) ? evaluation.hbcdp.dbi.toFixed(3) : '-';
    if (kmZ1) kmZ1.textContent = (evaluation.kmeans && evaluation.kmeans.z1 != null) ? GeoUtils.formatNumber(evaluation.kmeans.z1, 2) : '-';
    if (hbZ1) hbZ1.textContent = (evaluation.hbcdp && evaluation.hbcdp.z1 != null) ? GeoUtils.formatNumber(evaluation.hbcdp.z1, 2) : '-';
    if (kmZ2) kmZ2.textContent = (evaluation.kmeans && evaluation.kmeans.z2 != null) ? `${GeoUtils.formatNumber(evaluation.kmeans.z2, 2)} m` : '-';
    if (hbZ2) hbZ2.textContent = (evaluation.hbcdp && evaluation.hbcdp.z2 != null) ? `${GeoUtils.formatNumber(evaluation.hbcdp.z2, 2)} m` : '-';
  }

  function updateClusterDistributionTable(clusters) {
    const tbody = document.getElementById('table-cluster-distribution-body');
    if (!tbody) return;

    if (!clusters || !clusters.kmeans || clusters.kmeans.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: #64748b; padding: 24px;">Belum ada data cluster. Silakan unggah dataset.</td></tr>';
      return;
    }

    let rowsHtml = '';
    const maxK = Math.max(clusters.kmeans.length, (clusters.hbcdp || []).length);
    for (let i = 0; i < maxK; i++) {
      const km = clusters.kmeans[i] || { count: '-' };
      const hb = (clusters.hbcdp && clusters.hbcdp[i]) || { count: '-' };
      const cMeta = getClusterMetadata(i + 1);
      rowsHtml += `
        <tr>
          <td>
  <span style="display: inline-flex; align-items: center; gap: 8px;">
    <span style="
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: ${cMeta.color};
    "></span>
    Cluster ${i + 1}
  </span>
</td>
          <td style="text-align: center;">${typeof km.count === 'number' ? GeoUtils.formatNumber(km.count) : km.count}</td>
          <td style="text-align: center;">${typeof hb.count === 'number' ? GeoUtils.formatNumber(hb.count) : hb.count}</td>
        </tr>
      `;
    }
    tbody.innerHTML = rowsHtml;
  }

  // ------------------------------------------------------------------------
  // 4. Map Rendering
  // ------------------------------------------------------------------------
  function renderDashboardMaps() {
    mapManager.initMap('map-kmeans-dash');
    mapManager.initMap('map-hbcdp-dash');

    const ds = state.activeDatasetKey ? DATASETS[state.activeDatasetKey] : null;
    if (!ds || !ds.points || ds.points.length === 0) {
      setTimeout(() => {
        mapManager.renderEmptyMap('map-kmeans-dash');
        mapManager.renderEmptyMap('map-hbcdp-dash');
      }, 100);
      return;
    }

    setTimeout(() => {
      mapManager.renderClustering('map-kmeans-dash', ds.points, 'kmeans');
      mapManager.renderClustering('map-hbcdp-dash', ds.points, 'hbcdp');
    }, 100);
  }

  function renderZonaMap() {
    mapManager.initMap('map-zona-large', { zoom: 12 });

    const ds = state.activeDatasetKey ? DATASETS[state.activeDatasetKey] : null;
    if (!ds || !ds.points || ds.points.length === 0) {
      setTimeout(() => {
        mapManager.renderEmptyMap('map-zona-large');
      }, 100);
    } else {
      setTimeout(() => {
        mapManager.renderClustering('map-zona-large', ds.points, state.zonaMode);
      }, 100);
    }

    updateZonaSummary();
    renderAnggotaTable();
  }

  // ------------------------------------------------------------------------
  // 5. Hasil Pembagian Zona Page Handlers
  // ------------------------------------------------------------------------
  if (tabKmeans && tabHbcdp) {
    tabKmeans.addEventListener('click', () => {
      state.zonaMode = 'kmeans';
      tabKmeans.classList.add('active');
      tabHbcdp.classList.remove('active');
      if (zonaMapTitle) zonaMapTitle.textContent = 'Visualisasi Zona - K-Means Awal';
      if (zonaSummaryTitle) zonaSummaryTitle.textContent = 'Ringkasan Jumlah Titik per Cluster (K-Means Awal)';
      renderZonaMap();
    });

    tabHbcdp.addEventListener('click', () => {
      state.zonaMode = 'hbcdp';
      tabHbcdp.classList.add('active');
      tabKmeans.classList.remove('active');
      if (zonaMapTitle) zonaMapTitle.textContent = 'Visualisasi Zona - HBCDP (Hasil Akhir)';
      if (zonaSummaryTitle) zonaSummaryTitle.textContent = 'Ringkasan Jumlah Titik per Cluster (HBCDP Hasil Akhir)';
      renderZonaMap();
    });
  }

  function updateZonaSummary() {
    const ds = state.activeDatasetKey ? DATASETS[state.activeDatasetKey] : null;
    const tbody = document.getElementById('table-zona-summary-body');
    const totalCell = document.getElementById('table-zona-total-count');
    if (!tbody) return;

    if (!ds || !ds.clusters) {
      tbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: #64748b; padding: 20px;">Belum ada data zona</td></tr>';
      if (totalCell) totalCell.textContent = '-';
      return;
    }

    const clusterList = state.zonaMode === 'kmeans' ? ds.clusters.kmeans : ds.clusters.hbcdp;

    let rowsHtml = '';
    let total = 0;

    (clusterList || []).forEach(c => {
  const cMeta = getClusterMetadata(c.id);
  total += (typeof c.count === 'number' ? c.count : 0);

  rowsHtml += `
    <tr>
      <td>
        <span style="display: inline-flex; align-items: center; gap: 8px;">
          <span style="
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: ${cMeta.color};
          "></span>
          ${c.name}
        </span>
      </td>
      <td style="text-align: center;">
        ${typeof c.count === 'number' ? GeoUtils.formatNumber(c.count) : c.count}
      </td>
    </tr>
  `;
});

    tbody.innerHTML = rowsHtml || '<tr><td colspan="2" style="text-align: center; color: #64748b; padding: 20px;">Belum ada data zona</td></tr>';
    if (totalCell) totalCell.textContent = total > 0 ? GeoUtils.formatNumber(total) : '-';
  }

  function renderAnggotaTable() {
    const ds = state.activeDatasetKey ? DATASETS[state.activeDatasetKey] : null;
    if (!tableBody) return;

    if (!ds || !ds.points || ds.points.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #64748b; padding: 20px;">Belum ada data titik pengiriman</td></tr>';
      if (paginationInfo) paginationInfo.textContent = 'Menampilkan 0 data';
      if (paginationControls) paginationControls.innerHTML = '';
      return;
    }

    const clusterKey = state.zonaMode === 'kmeans' ? 'c_init' : 'c_final';
    const query = state.tableSearchQuery.toLowerCase().trim();

    let filtered = ds.points.filter(pt => {
      if (!query) return true;
      return (pt.resi && pt.resi.toLowerCase().includes(query)) ||
             (pt.alamat && pt.alamat.toLowerCase().includes(query)) ||
             (pt.id && pt.id.toLowerCase().includes(query));
    });

    const totalCount = ds.totalPoints || filtered.length;
    const filteredCount = filtered.length;
    const totalPages = Math.ceil(filteredCount / state.tablePageSize) || 1;

    if (state.tableCurrentPage > totalPages) {
      state.tableCurrentPage = 1;
    }

    const startIdx = (state.tableCurrentPage - 1) * state.tablePageSize;
    const pageItems = filtered.slice(startIdx, startIdx + state.tablePageSize);

    if (pageItems.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: #9ca3af; padding: 20px;">Tidak ada data ditemukan</td></tr>`;
    } else {
      let rowsHtml = '';
      pageItems.forEach((pt, index) => {
        const rowNo = startIdx + index + 1;
        const cId = pt[clusterKey];
const cMeta = cId != null ? getClusterMetadata(cId) : null;
        rowsHtml += `
          <tr>
            <td style="text-align: center;">${rowNo}</td>
            <td><strong>${pt.resi}</strong> <span style="color: #6b7280; font-size: 11px;">(${pt.id})</span></td>
            <td>${pt.alamat}</td>
            <td style="text-align: center;">
  ${cMeta ? `
    <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11.5px; background: ${cMeta.fillColor}; color: ${cMeta.color};">
      ${cMeta.name}
    </span>
  ` : '-'}
</td>
          </tr>
        `;
      });
      tableBody.innerHTML = rowsHtml;
    }

    if (paginationInfo) {
      const displayStart = filteredCount > 0 ? startIdx + 1 : 0;
      const displayEnd = Math.min(startIdx + state.tablePageSize, filteredCount);
      paginationInfo.textContent = `Menampilkan ${displayStart} - ${displayEnd} dari ${GeoUtils.formatNumber(totalCount)} data`;
    }

    if (paginationControls) {
      let controlsHtml = '';
      controlsHtml += `<button class="btn-page" ${state.tableCurrentPage === 1 ? 'disabled' : ''} data-page="${state.tableCurrentPage - 1}">&lt;</button>`;

      const maxButtons = 5;
      let startP = Math.max(1, state.tableCurrentPage - 2);
      let endP = Math.min(totalPages, startP + maxButtons - 1);
      if (endP - startP < maxButtons - 1) {
        startP = Math.max(1, endP - maxButtons + 1);
      }

      for (let p = startP; p <= endP; p++) {
        controlsHtml += `<button class="btn-page ${p === state.tableCurrentPage ? 'active' : ''}" data-page="${p}">${p}</button>`;
      }

      if (endP < totalPages) {
        controlsHtml += `<span style="padding: 0 4px; color: #9ca3af;">...</span>`;
        controlsHtml += `<button class="btn-page" data-page="${totalPages}">${totalPages}</button>`;
      }

      controlsHtml += `<button class="btn-page" ${state.tableCurrentPage === totalPages ? 'disabled' : ''} data-page="${state.tableCurrentPage + 1}">&gt;</button>`;
      paginationControls.innerHTML = controlsHtml;

      paginationControls.querySelectorAll('.btn-page').forEach(btn => {
        btn.addEventListener('click', () => {
          const page = parseInt(btn.dataset.page);
          if (page && page >= 1 && page <= totalPages) {
            state.tableCurrentPage = page;
            renderAnggotaTable();
          }
        });
      });
    }
  }

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      state.tableSearchQuery = e.target.value;
      state.tableCurrentPage = 1;
      renderAnggotaTable();
    });
  }

  // ------------------------------------------------------------------------
  // 6. Evaluasi Page Handlers
  // ------------------------------------------------------------------------
  function updateEvaluasiView() {
    const ds = state.activeDatasetKey ? DATASETS[state.activeDatasetKey] : null;

    const kmSil = document.getElementById('card-eval-km-silhouette');
    const kmDbi = document.getElementById('card-eval-km-dbi');
    const kmZ1 = document.getElementById('card-eval-km-z1');
    const kmZ2 = document.getElementById('card-eval-km-z2');

    const hbSil = document.getElementById('card-eval-hb-silhouette');
    const hbDbi = document.getElementById('card-eval-hb-dbi');
    const hbZ1 = document.getElementById('card-eval-hb-z1');
    const hbZ2 = document.getElementById('card-eval-hb-z2');

    const tbodySteps = document.getElementById('table-eval-steps-body');

    if (!ds || !ds.evaluation) {
      [kmSil, kmDbi, kmZ1, kmZ2, hbSil, hbDbi, hbZ1, hbZ2].forEach(el => {
        if (el) el.textContent = '-';
      });
      if (tbodySteps) {
        tbodySteps.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #64748b; padding: 20px;">Belum ada riwayat iterasi penyeimbangan beban kurir</td></tr>';
      }
      return;
    }

    if (kmSil) kmSil.textContent = (ds.evaluation.kmeans && ds.evaluation.kmeans.silhouette != null) ? ds.evaluation.kmeans.silhouette.toFixed(3) : '-';
    if (kmDbi) kmDbi.textContent = (ds.evaluation.kmeans && ds.evaluation.kmeans.dbi != null) ? ds.evaluation.kmeans.dbi.toFixed(3) : '-';
    if (kmZ1) kmZ1.textContent = (ds.evaluation.kmeans && ds.evaluation.kmeans.z1 != null) ? GeoUtils.formatNumber(ds.evaluation.kmeans.z1, 2) : '-';
    if (kmZ2) kmZ2.textContent = (ds.evaluation.kmeans && ds.evaluation.kmeans.z2 != null) ? `${GeoUtils.formatNumber(ds.evaluation.kmeans.z2, 2)} m` : '-';

    if (tbodySteps) {
      if (ds.evaluation.steps && ds.evaluation.steps.length > 0) {
        let rowsHtml = '';
        ds.evaluation.steps.forEach(step => {
          rowsHtml += `
            <tr>
              <td><strong>${step.step}</strong></td>
              <td style="text-align: center; font-family: monospace;">${step.cardinality}</td>
              <td style="text-align: center;">${step.z1}</td>
              <td style="text-align: center;">${step.z2}</td>
              <td style="text-align: center;">${step.reassigned}</td>
            </tr>
          `;
        });
        tbodySteps.innerHTML = rowsHtml;
      } else {
        tbodySteps.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #64748b; padding: 20px;">Belum ada riwayat iterasi penyeimbangan beban kurir</td></tr>';
      }
    }

    if (hbSil) hbSil.textContent = (ds.evaluation.hbcdp && ds.evaluation.hbcdp.silhouette != null) ? ds.evaluation.hbcdp.silhouette.toFixed(3) : '-';
    if (hbDbi) hbDbi.textContent = (ds.evaluation.hbcdp && ds.evaluation.hbcdp.dbi != null) ? ds.evaluation.hbcdp.dbi.toFixed(3) : '-';
    if (hbZ1) hbZ1.textContent = (ds.evaluation.hbcdp && ds.evaluation.hbcdp.z1 != null) ? GeoUtils.formatNumber(ds.evaluation.hbcdp.z1, 2) : '-';
    if (hbZ2) hbZ2.textContent = (ds.evaluation.hbcdp && ds.evaluation.hbcdp.z2 != null) ? `${GeoUtils.formatNumber(ds.evaluation.hbcdp.z2, 2)} m` : '-';
  }

  // ------------------------------------------------------------------------
  // 7. Process Selector Event
  // ------------------------------------------------------------------------
  if (processSelector) {
    processSelector.addEventListener('change', async (e) => {
      const selectedVal = e.target.value;
      if (selectedVal === 'none') {
        state.activeDatasetKey = null;
        state.currentDbDatasetId = null;
        updateDashboardView();
        updateZonaSummary();
        renderAnggotaTable();
        updateEvaluasiView();
        showToast('Mode tampilan awal: data dikosongkan.');
      } else if (selectedVal.startsWith('db_')) {
        const dbId = parseInt(selectedVal.replace('db_', ''));
        showToast(`Mengambil data dari PostgreSQL...`);
        await loadDatasetFromDb(dbId);
      } else if (DATASETS[selectedVal]) {
        state.activeDatasetKey = selectedVal;
        updateDashboardView();
        updateZonaSummary();
        renderAnggotaTable();
        updateEvaluasiView();
        showToast(`Memuat data: ${DATASETS[selectedVal].label}`);
      }
    });
  }

  // ------------------------------------------------------------------------
  // 8. File Upload & Server-side Geocoding
  // ------------------------------------------------------------------------
  if (btnSelectFile && fileInput) {
    btnSelectFile.addEventListener('click', () => fileInput.click());
  }

  if (fileInput) {
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];

    // Reset nilai input agar file yang sama
    // dapat dipilih dan diproses kembali
    e.target.value = '';

    if (file) {
      handleFileSelected(file);
    }
  });
}

  if (dropzone) {
    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.remove('drag-over');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
      const dt = e.dataTransfer;
      const file = dt.files[0];
      if (file) handleFileSelected(file);
    });
  }

// Menampilkan ringkasan hasil preprocessing
function tampilkanHasilPreprocessing(data) {
  const card = document.getElementById('preprocessing-card');
  const totalAwal = document.getElementById('preprocessing-total-awal');
  const totalEliminasi = document.getElementById('preprocessing-total-eliminasi');
  const jumlahValid = document.getElementById('preprocessing-jumlah-valid');
  const summary = document.getElementById('preprocessing-summary');
  const status = document.getElementById('preprocessing-status');
  const progressFill = document.getElementById('preprocessing-progress-fill');

  if (!card || !data) return;

  const awal = Number(data.total_awal ?? 0);
  const eliminasi = Number(data.total_eliminasi ?? 0);
  const valid = Number(data.jumlah_data ?? 0);

  if (totalAwal) totalAwal.textContent = GeoUtils.formatNumber(awal);
  if (totalEliminasi) totalEliminasi.textContent = GeoUtils.formatNumber(eliminasi);
  if (jumlahValid) jumlahValid.textContent = GeoUtils.formatNumber(valid);

  if (summary) {
  if (valid === 0) {
    summary.textContent =
      `Seluruh ${GeoUtils.formatNumber(awal)} baris data tereliminasi ` +
      `pada tahap preprocessing. Tidak ada data yang dapat ` +
      `dilanjutkan ke proses geocoding.`;
  } else {
    summary.textContent =
      `${GeoUtils.formatNumber(valid)} dari ${GeoUtils.formatNumber(awal)} baris data ` +
      `memenuhi kriteria preprocessing dan dilanjutkan ke tahap geocoding.`;
  }
}

if (status) {
  status.textContent =
    valid === 0 ? 'Selesai — tidak ada data valid' : '✓ Selesai';

  status.style.color =
    valid === 0 ? '#d97706' : '#16a34a';
}

  if (progressFill) {
    progressFill.style.width = '100%';
  }

  card.style.display = 'block';
}

  // Mengembalikan tampilan preprocessing ke kondisi awal
function resetPreprocessing() {
  const totalAwal = document.getElementById('preprocessing-total-awal');
  const totalEliminasi = document.getElementById('preprocessing-total-eliminasi');
  const jumlahValid = document.getElementById('preprocessing-jumlah-valid');
  const summary = document.getElementById('preprocessing-summary');
  const status = document.getElementById('preprocessing-status');
  const progressFill = document.getElementById('preprocessing-progress-fill');

  // Reset jumlah data
  if (totalAwal) totalAwal.textContent = '0';
  if (totalEliminasi) totalEliminasi.textContent = '0';
  if (jumlahValid) jumlahValid.textContent = '0';

  // Reset keterangan
  if (summary) {
    summary.textContent = 'Belum ada proses preprocessing';
  }

  // Reset status
  if (status) {
    status.textContent = 'Belum diproses';
    status.style.color = '#64748b';
  }

  // Kosongkan progress bar
  if (progressFill) {
    progressFill.style.width = '0%';
  }
}

  function resetGeocodingProgress() {
    state.geocodingProgress = 0;

    if (progressBarFill) progressBarFill.style.width = '0%';
    if (progressPercentText) progressPercentText.textContent = '0%';
    if (progressTextLabel) {
      progressTextLabel.textContent = 'Belum ada proses geocoding';
    }
  }


  async function handleFileSelected(file) {
        // Cegah upload baru saat proses sebelumnya berlangsung
    if (
      state.isClustering ||
      state.uploadStatus === 'uploading' ||
      state.uploadStatus === 'geocoding'
    ) {
      showToast(
        'Tunggu proses yang sedang berlangsung selesai.',
        'error'
      );
      if (fileInput) fileInput.value = '';
      return;
    }
    const validExtensions = ['.csv', '.xlsx', '.xls'];
    const fileName = file.name;
    const fileExt = fileName.slice(fileName.lastIndexOf('.')).toLowerCase();

if (!validExtensions.includes(fileExt)) {
  showToast('Format file tidak didukung. Harap gunakan format .xlsx, .xls, atau .csv', 'error');
  if (fileInput) fileInput.value = '';
  return;
}

    // Dataset baru belum siap untuk clustering
state.uploadStatus = 'uploading';
state.readyDatasetId = null;
state.geocodedPointCount = 0;
updateClusteringButtonState();

// Reset tampilan proses dataset sebelumnya
resetPreprocessing();
resetGeocodingProgress();

const geocodingStatus = document.getElementById('geocoding-status');

if (geocodingStatus) {
  geocodingStatus.textContent = 'Belum diproses';
  geocodingStatus.style.color = '#64748b';
}
    if (selectedFileName) selectedFileName.textContent = fileName;
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    if (selectedFileMeta) selectedFileMeta.textContent = `Memproses • ${sizeMb.replace('.', ',')} MB`;
    if (selectedFileCard) selectedFileCard.style.display = 'block';

    if (isServerMode) {
      showToast(`Mengunggah ${fileName} ke server Flask...`);
      const formData = new FormData();
      formData.append('file', file);

      try {
        const resp = await fetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        const res = await resp.json();
        if (res.success) {

  // Preprocessing selesai, tetapi seluruh data tereliminasi.
  if (res.preprocessing_only === true) {
    state.currentDbDatasetId = null;
    state.readyDatasetId = null;
    state.geocodedPointCount = 0;
    state.uploadStatus = 'idle';

    if (selectedFileMeta) {
      selectedFileMeta.textContent =
        `${GeoUtils.formatNumber(res.data.total_awal)} baris • ${sizeMb.replace('.', ',')} MB`;
    }

    tampilkanHasilPreprocessing(res.data);
    resetGeocodingProgress();

    const geocodingStatus = document.getElementById('geocoding-status');

    if (geocodingStatus) {
      geocodingStatus.textContent = 'Belum diproses';
      geocodingStatus.style.color = '#64748b';
    }

    updateClusteringButtonState();

    showToast(res.message);

    return;
  }

  // Alur normal: dataset memiliki data valid.
  state.currentDbDatasetId = res.data.id_dataset;

  if (selectedFileMeta) {
    selectedFileMeta.textContent =
      `${GeoUtils.formatNumber(res.data.total_awal)} baris • ${sizeMb.replace('.', ',')} MB`;
  }

  // Tampilkan hasil preprocessing sebelum geocoding
  tampilkanHasilPreprocessing(res.data);

  showToast(`File tersimpan di PostgreSQL! (ID: ${res.data.id_dataset})`);

state.uploadStatus = 'geocoding';
updateClusteringButtonState();

const geocodingBerhasil = await performServerGeocoding(
  res.data.id_dataset,
  res.data.jumlah_data
);

if (geocodingBerhasil && state.geocodedPointCount >= 3) {
  state.readyDatasetId = res.data.id_dataset;
  state.uploadStatus = 'ready';

  showToast('Data siap untuk proses clustering.');
} else {
  state.readyDatasetId = null;
  state.uploadStatus = 'error';

  if (geocodingBerhasil) {
    showToast(
      'Clustering memerlukan minimal 3 titik yang berhasil di-geocoding.',
      'error'
    );
  }
}

updateClusteringButtonState();
await syncDatasetsFromBackend();
        } else {
          // Upload ditolak oleh server
          state.uploadStatus = 'error';
          state.readyDatasetId = null;
          state.geocodedPointCount = 0;
          updateClusteringButtonState();

          resetGeocodingProgress();
          if (selectedFileMeta) selectedFileMeta.textContent = 'Upload gagal';
          showToast(`Gagal: ${res.error}`, 'error');
        }
      } catch (err) {
        // Upload gagal karena koneksi atau kesalahan lainnya
        console.error('Upload gagal:', err);

        state.uploadStatus = 'error';
        state.readyDatasetId = null;
        state.geocodedPointCount = 0;
        updateClusteringButtonState();

        resetGeocodingProgress();
        if (selectedFileMeta) selectedFileMeta.textContent = 'Upload gagal';
        showToast('Gagal mengunggah file ke server.', 'error');
      }
    } else {
      // Website dibuka tanpa server Flask
      state.uploadStatus = 'error';
      state.readyDatasetId = null;
      state.geocodedPointCount = 0;
      updateClusteringButtonState();

      showToast('Upload dan clustering membutuhkan server Flask.', 'error');
    }
  }

if (btnRemoveFile) {
  btnRemoveFile.addEventListener('click', () => {

    // Cegah pembatalan saat proses masih berlangsung
    if (
      state.isClustering ||
      state.uploadStatus === 'uploading' ||
      state.uploadStatus === 'geocoding'
    ) {
      showToast(
        'Tunggu proses selesai sebelum membatalkan file.',
        'error'
      );
      return;
    }

    // Reset status dataset yang siap untuk clustering
    state.uploadStatus = 'idle';
    state.readyDatasetId = null;
    state.geocodedPointCount = 0;
    updateClusteringButtonState();

    // Kosongkan file yang dipilih
    if (fileInput) fileInput.value = '';
    if (selectedFileCard) selectedFileCard.style.display = 'none';

    // Reset tampilan preprocessing
    resetPreprocessing();

    // Reset tampilan geocoding
    resetGeocodingProgress();

    // Reset status geocoding
    const geocodingStatus = document.getElementById('geocoding-status');

    if (geocodingStatus) {
      geocodingStatus.textContent = 'Belum diproses';
      geocodingStatus.style.color = '#64748b';
    }

    showToast('File telah dibatalkan.');
  });
}

  
async function performServerGeocoding(datasetId, totalAddresses) {
  const statusElement = document.getElementById('geocoding-status');

  function updateProgress(processed, total, percentage) {
    state.geocodingProgress = percentage;

    if (progressBarFill) {
      progressBarFill.style.width = `${percentage}%`;
    }

    if (progressPercentText) {
      progressPercentText.textContent = `${percentage}%`;
    }

    if (progressTextLabel) {
      progressTextLabel.textContent =
        `${GeoUtils.formatNumber(processed)} dari ${GeoUtils.formatNumber(total)} alamat diproses`;
    }
  }

  updateProgress(0, totalAddresses, 0);

  if (statusElement) {
    statusElement.textContent = 'Sedang diproses...';
    statusElement.style.color = '#2563eb';
  }

  let pollingActive = true;

  // Membaca progres aktual dari Flask setiap 500 ms
  const pollingPromise = (async () => {
    while (pollingActive) {
      try {
        const response = await fetch(
          `/api/dataset/${datasetId}/geocode/progress`,
          { cache: 'no-store' }
        );

        if (response.ok) {
          const result = await response.json();

          if (result.success && result.data) {
            const progress = result.data;

            if (progress.status !== 'NOT_STARTED') {
              updateProgress(
                progress.processed,
                progress.total,
                progress.percentage
              );
            }
          }
        }
      } catch (error) {
        console.warn('Gagal membaca progres geocoding:', error);
      }

      if (pollingActive) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    }
  })();

  try {
    const response = await fetch(`/api/dataset/${datasetId}/geocode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });

    const result = await response.json();

    pollingActive = false;
    await pollingPromise;

    if (!response.ok || !result.success) {
      throw new Error(result.error || 'Kesalahan server');
    }

const total = result.data.total_points;
const berhasil = result.data.successful_points;
const gagal = result.data.failed_points;

// Simpan jumlah titik yang berhasil di-geocoding
state.geocodedPointCount = Number(berhasil) || 0;

updateProgress(total, total, 100);

    if (statusElement) {
      statusElement.textContent = '✓ Selesai';
      statusElement.style.color = '#16a34a';
    }

    if (progressTextLabel) {
      progressTextLabel.textContent =
        `${GeoUtils.formatNumber(total)} alamat diperiksa (${berhasil} berhasil, ${gagal} gagal)`;
    }

    showToast(`Geocoding selesai: ${berhasil} berhasil, ${gagal} gagal.`);
    return true;

  } catch (error) {
    pollingActive = false;
    await pollingPromise;

    console.error('Geocoding gagal:', error);

    if (statusElement) {
      statusElement.textContent = 'Gagal';
      statusElement.style.color = '#dc2626';
    }

    showToast(`Geocoding gagal: ${error.message}`, 'error');
    return false;
  }
}


  function simulateGeocoding(totalAddresses = 8615) {
    let currentPercent = 0;
    const targetPercent = 72;

    const interval = setInterval(() => {
      currentPercent += 4;
      if (currentPercent >= targetPercent) {
        currentPercent = targetPercent;
        clearInterval(interval);
      }
      const processed = Math.round((currentPercent / 100) * totalAddresses);
      if (progressBarFill) progressBarFill.style.width = `${currentPercent}%`;
      if (progressPercentText) progressPercentText.textContent = `${currentPercent}%`;
      if (progressTextLabel) {
        progressTextLabel.textContent = `${GeoUtils.formatNumber(processed)} dari ${GeoUtils.formatNumber(totalAddresses)} alamat berhasil diproses`;
      }
    }, 40);
  }

  // ------------------------------------------------------------------------
  // 9. Eksekusi Clustering (K-Means & HBCDP)
  // ------------------------------------------------------------------------
if (btnStartClustering) {
  btnStartClustering.addEventListener('click', async () => {

    // Pastikan dataset baru sudah siap
    if (
      state.uploadStatus !== 'ready' ||
      state.readyDatasetId == null ||
      state.geocodedPointCount < 3 ||
      state.isClustering
    ) {
      showToast(
        'Unggah dataset dan selesaikan geocoding terlebih dahulu.',
        'error'
      );
      return;
    }

    // Validasi nilai K
    const kVal = Number(inputClusterK?.value);

    if (
      !Number.isInteger(kVal) ||
      kVal < 2 ||
      kVal >= state.geocodedPointCount
    ) {
      showToast(
        `Jumlah Kurir (K) harus bilangan bulat antara 2 dan ${state.geocodedPointCount - 1}.`,
        'error'
      );
      return;
    }

    state.isClustering = true;

    updateClusteringButtonState();

    btnStartClustering.innerHTML = `
      <svg class="animate-spin" width="16" height="16"
           viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
        <path d="M12 2a10 10 0 0 1 10 10"
              stroke-linecap="round"></path>
      </svg>
      Memproses K-Means & HBCDP...
    `;

    // Gunakan ID dataset yang baru selesai di-geocoding
    const datasetId = state.readyDatasetId;

    try {
      if (!isServerMode) {
        throw new Error('Server Flask tidak tersedia.');
      }

      const resp = await fetch(`/api/cluster/${datasetId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ k: kVal })
      });

      const res = await resp.json();

      if (!resp.ok || !res.success) {
        throw new Error(res.error || 'Proses clustering gagal.');
      }

      showToast(
        'Clustering berhasil diselesaikan dan disimpan ke PostgreSQL!'
      );

      // Perbarui daftar dataset dan hasil clustering
      await syncDatasetsFromBackend();
      await loadDatasetFromDb(datasetId);

      if (processSelector) {
        processSelector.value = `db_${datasetId}`;
      }

      switchView('zona');

    } catch (error) {
      console.error('Clustering gagal:', error);

      showToast(
        `Clustering gagal: ${error.message}`,
        'error'
      );

    } finally {
      state.isClustering = false;
      resetClusteringBtn();
    }
  });
}

function resetClusteringBtn() {
  if (!btnStartClustering) return;

  btnStartClustering.innerHTML = clusteringBtnDefaultHtml;

  updateClusteringButtonState();
}

  function fallbackLocalClustering() {
    showToast('Proses clustering selesai.');
    updateDashboardView();
    updateZonaSummary();
    renderAnggotaTable();
    updateEvaluasiView();
  }

  // ------------------------------------------------------------------------
  // 10. Template & Result Downloads
  // ------------------------------------------------------------------------
  function downloadBlob(content, fileName, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }, 100);
  }

  if (btnDownloadCsv) {
    btnDownloadCsv.addEventListener('click', () => {
      if (isServerMode) {
        window.location.href = '/api/download/template/csv';
      } else {
        const csvContent =
          'No.,Nosi,Tgl Antaran Pertama,Alamat,Kota\n' +
          '1,nosi_1,2025-08-01,Jl. Contoh No. 1,Malang\n' +
          '2,nosi_2,2025-08-01,Jl. Contoh No. 2,Malang\n' +
          '3,nosi_3,2025-08-01,Jl. Contoh No. 3,Malang\n' +
          '4,nosi_4,2025-08-01,Jl. Contoh No. 4,Malang\n' +
          '5,nosi_5,2025-08-01,Jl. Contoh No. 5,Malang\n';
        downloadBlob(csvContent, 'Template_Dataset_GeoKurir.csv', 'text/csv;charset=utf-8;');
      }
      showToast('Template CSV berhasil diunduh.');
    });
  }

  if (btnDownloadExcel) {
    btnDownloadExcel.addEventListener('click', () => {
      if (isServerMode) {
        window.location.href = '/api/download/template/excel';
      } else if (typeof XLSX !== 'undefined') {
        const wsData = [
          ['No.', 'Nosi', 'Tgl Antaran Pertama', 'Alamat', 'Kota'],
          [1, 'nosi_1', '2025-08-01', 'Jl. Contoh No. 1', 'Malang'],
          [2, 'nosi_2', '2025-08-01', 'Jl. Contoh No. 2', 'Malang'],
          [3, 'nosi_3', '2025-08-01', 'Jl. Contoh No. 3', 'Malang'],
          [4, 'nosi_4', '2025-08-01', 'Jl. Contoh No. 4', 'Malang'],
          [5, 'nosi_5', '2025-08-01', 'Jl. Contoh No. 5', 'Malang']
        ];
        const ws = XLSX.utils.aoa_to_sheet(wsData);
        ws['!cols'] = [{ wch: 6 }, { wch: 14 }, { wch: 22 }, { wch: 35 }, { wch: 15 }];
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, 'Template Pengiriman');
        XLSX.writeFile(wb, 'Template_Dataset_GeoKurir.xlsx');
      } else {
        window.location.href = '/api/download/template/excel';
      }
      showToast('Template Excel (.xlsx) berhasil diunduh.');
    });
  }

  if (btnDownloadResultCsv) {
    btnDownloadResultCsv.addEventListener('click', () => {
      const ds = state.activeDatasetKey ? DATASETS[state.activeDatasetKey] : null;
      if (!ds && !state.currentDbDatasetId) {
        showToast('Belum ada dataset hasil clustering untuk diunduh.', 'error');
        return;
      }
      if (isServerMode && state.currentDbDatasetId) {
        window.location.href = `/api/download/export/${state.currentDbDatasetId}`;
      } else if (ds && ds.points) {
        let csvContent = 'No,Nosi,Alamat,Kecamatan,Latitude,Longitude,Cluster_KMeans_Awal,Cluster_HBCDP_Akhir,Status\n';
        ds.points.forEach((pt, idx) => {
          csvContent += `${idx + 1},${pt.resi},"${pt.alamat}",${pt.kecamatan},${pt.lat},${pt.lng},Cluster ${pt.c_init},Cluster ${pt.c_final},${pt.status}\n`;
        });
        downloadBlob(csvContent, `Hasil_Pembagian_Zona_${ds.fileName || 'GeoKurir'}.csv`, 'text/csv;charset=utf-8;');
        showToast('Hasil clustering berhasil diunduh sebagai CSV.');
      } else {
        showToast('Belum ada data untuk diunduh.', 'error');
      }
    });
  }

  // ------------------------------------------------------------------------
  // 11. Toast Helper
  // ------------------------------------------------------------------------
  function showToast(msg, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="16" x2="12" y2="12"></line>
        <line x1="12" y1="8" x2="12.01" y2="8"></line>
      </svg>
      <span></span>
    `;
    toast.querySelector('span').textContent = msg;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  async function loadConfigFromBackend() {
    if (!isServerMode) return;
    try {
      const resp = await fetch('/api/config');
      const json = await resp.json();
      if (json.success && json.google_maps_api_key) {
        window.GOOGLE_MAPS_API_KEY = json.google_maps_api_key;
      }
    } catch (e) {
      console.warn('Gagal memuat config Google Maps dari backend:', e);
    }
  }

// ------------------------------------------------------------------------
// Boot
// ------------------------------------------------------------------------

// Pastikan tombol clustering nonaktif saat website pertama dibuka
updateClusteringButtonState();

initRouting();
updateDashboardView();
updateZonaSummary();
renderAnggotaTable();
updateEvaluasiView();

// Sync dengan PostgreSQL jika server Flask aktif
if (isServerMode) {
  loadConfigFromBackend();
  syncDatasetsFromBackend();
}
});
