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
    distributionMode: 'aktual',
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
uploadStatus: 'idle',
readyDatasetId: null,
geocodedPointCount: 0,
isClustering: false,
completedClusteringDatasetId: null
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
  const tabAktual = document.getElementById('tab-aktual');
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

  const isCompleted =
    isReady &&
    state.completedClusteringDatasetId === state.readyDatasetId;

  btnStartClustering.disabled =
    !isReady || state.isClustering || isCompleted;

  btnStartClustering.style.opacity =
    state.isClustering || isReady ? '1' : '0.55';

  btnStartClustering.style.filter =
    state.isClustering || isReady ? '' : 'grayscale(1)';

  btnStartClustering.style.cursor =
    state.isClustering
      ? 'wait'
      : isCompleted || !isReady
        ? 'not-allowed'
        : 'pointer';

  btnStartClustering.style.background =
    isCompleted ? '#16803c' : '';

  if (!state.isClustering) {
    if (isCompleted) {
      btnStartClustering.innerHTML = `
        <svg width="18" height="18"
             viewBox="0 0 24 24"
             fill="none"
             stroke="currentColor"
             stroke-width="2.5"
             stroke-linecap="round"
             stroke-linejoin="round">
          <path d="M20 6 9 17l-5-5"></path>
        </svg>
        Clustering Selesai
      `;
    } else {
      btnStartClustering.innerHTML = clusteringBtnDefaultHtml;
    }
  }

  if (state.isClustering) {
    btnStartClustering.title = 'Clustering sedang berlangsung';
  } else if (isCompleted) {
    btnStartClustering.title = 'Clustering berhasil diselesaikan';
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
  const btnDownloadMap = document.getElementById('btn-download-map');

  // ------------------------------------------------------------------------
  // 1. Navigation & Routing
  // ------------------------------------------------------------------------
  function switchView(viewId) {
  const previousView = state.currentView;

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
        if (
          state.uploadStatus !== 'uploading' &&
          state.uploadStatus !== 'geocoding' &&
          !state.isClustering
        ) 
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
      if (
        state.uploadStatus !== 'uploading' &&
        state.uploadStatus !== 'geocoding' &&
        !state.isClustering
      ) {
        resetUploadReadiness();
      }
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
        updateActualPanel(null);
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

        // N adalah seluruh titik dengan koordinat hasil geocoding, bukan subset evaluasi.
        const validPoints = (pointsJson.data || []).filter(pt =>
          (pt.latitude ?? pt.lat) != null && (pt.longitude ?? pt.lng) != null &&
          Number.isFinite(Number(pt.latitude ?? pt.lat)) && Number.isFinite(Number(pt.longitude ?? pt.lng)) &&
          (!pt.status_geocoding || String(pt.status_geocoding).toUpperCase() === 'SUCCESS'));
        const processedCount = d.aktual?.jumlah_titik_geocoding ?? validPoints.length;

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
          aktual: d.aktual || null,
          perbandingan: d.perbandingan || null,
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
              z2: hasKmeansResult ? 0 : null
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
          points: validPoints.map((pt, i) => {
  const cInit = hasKmeansResult ? (pt.c_init ?? null) : null;
  const cFinal = hasHbcdpResult ? (pt.c_final ?? null) : null;

  return {
    id: `A${i + 1}`,
    resi: pt.nosi ?? '-',
    id_pengiriman: pt.id_pengiriman,
    petugas: typeof pt.petugas === 'string' && pt.petugas.trim() ? pt.petugas.trim().replace(/\s+/g, ' ') : null,
    status_geocoding: pt.status_geocoding,
    alamat: pt.alamat_bersih || pt.alamat_asli,
    kecamatan: 'Malang',
    lat: Number(pt.latitude ?? pt.lat),
    lng: Number(pt.longitude ?? pt.lng),

    c_init: cInit,
    c_final: cFinal,

    status: cInit != null && cFinal != null
      ? (pt.status || (cFinal !== cInit ? 'Berpindah' : 'Tetap'))
      : null
          };
        }),
        polygons: d.polygons || {
          kmeans: d.polygons_kmeans || {},
          hbcdp: d.polygons_hbcdp || {}
        }
      };
        const actualCounts = new Map();
        DATASETS[dsKey].points.forEach(pt => {
          if (pt.petugas) {
          const name = pt.petugas.toUpperCase();
          actualCounts.set(name, (actualCounts.get(name) || 0) + 1);
        }
        });
        const actualNames = [...actualCounts.keys()].sort();
        const actualIds = new Map(actualNames.map((name, index) => [name, index + 1]));
        DATASETS[dsKey].points.forEach(pt => {
        pt.c_actual = actualIds.get(pt.petugas?.toUpperCase()) ?? null;
      });
        DATASETS[dsKey].clusters.aktual = actualNames.map(name => ({
          id: actualIds.get(name), name, count: actualCounts.get(name)
        }));
        DATASETS[dsKey].waktu_komputasi_str = d.clustering ? (d.clustering.waktu_komputasi_str || '-') : '-';
        DATASETS[dsKey].preprocessing = d.dataset.preprocessing;
        DATASETS[dsKey].geocoding_summary = d.geocoding_summary;
        // Sinkronkan tampilan geocoding hanya untuk dataset sesi upload aktif
        if (
          state.readyDatasetId === id_dataset &&
          d.geocoding_summary
        ) {
          updateGeocodingDisplay(d.geocoding_summary);
        }
        state.activeDatasetKey = dsKey;
        updateDashboardView();
        updateZonaSummary();
        renderAnggotaTable();
        updateEvaluasiView();
        if (state.currentView === 'zona') {
          renderZonaMap();
        }
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
    const kpiAktual = document.getElementById('kpi-kurir-aktual');
    if (kpiAktual) kpiAktual.textContent = ds?.aktual?.jumlah_kurir_aktual ?? 'N/A';

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

    updateEvaluationTable(ds);
    updateClusterDistributionTable(ds);
    renderDashboardMaps();
  }

  function metricText(value, digits = 3) {
    return value == null || !Number.isFinite(Number(value)) ? 'N/A' : GeoUtils.formatNumber(Number(value), digits);
  }

  function comparisonMetrics(ds, mode) {
    const original = ds?.evaluation?.[mode] || {};
    const saved = ds?.perbandingan?.[mode];
    return saved ? { silhouette: saved.silhouette_score, dbi: saved.dbi, z1: saved.z1, z2: original.z2 } : original;
  }

  function comparisonScope(ds) {
    if (!ds) return 'Belum ada dataset.';
    const n = ds.perbandingan?.jumlah_titik_evaluasi ?? ds.aktual?.jumlah_titik_evaluasi ?? 0;
    if (!ds.perbandingan) return `Baseline aktual: N evaluasi (Petugas valid) = ${GeoUtils.formatNumber(n)}; N geocoding = ${GeoUtils.formatNumber(ds.totalPoints)}. Perbandingan tersimpan belum tersedia; metrik algoritma yang tersedia merupakan diagnostik seluruh titik.`;
    const scope = ds.perbandingan.scope === 'seluruh_titik' ? 'seluruh titik geocoding (baseline aktual tidak tersedia)' : 'titik dengan Petugas valid yang sama; penugasan algoritma tidak dihitung ulang';
    return `Perbandingan SS / DBI / Z₁: ${scope}. N evaluasi = ${GeoUtils.formatNumber(n)}; N geocoding = ${GeoUtils.formatNumber(ds.totalPoints)}. Z₂ dan tahap HBCDP adalah diagnostik seluruh titik.`;
  }

  function algorithmMetricReasons(ds) {
    return ['kmeans', 'hbcdp'].map(mode => {
      const reason = ds?.perbandingan?.[mode]?.alasan_na;
      return reason ? `${mode === 'kmeans' ? 'K-Means' : 'HBCDP'}: ${reason}` : '';
    }).filter(Boolean).join(' ');
  }

  function fillMetricElements(prefix, values) {
    ['silhouette', 'dbi', 'z1', 'z2'].forEach(key => {
      const el = document.getElementById(`${prefix}-${key}`);
      if (el) el.textContent = metricText(values?.[key], key === 'z1' || key === 'z2' ? 2 : 3) + (key === 'z2' && values?.[key] != null ? ' m' : '');
    });
  }

  function updateEvaluationTable(ds) {
    fillMetricElements('eval-actual', { silhouette: ds?.aktual?.silhouette_score, dbi: ds?.aktual?.dbi, z1: ds?.aktual?.z1 });
    fillMetricElements('eval-km', comparisonMetrics(ds, 'kmeans'));
    fillMetricElements('eval-hb', comparisonMetrics(ds, 'hbcdp'));
    const scope = document.getElementById('dashboard-comparison-scope');
    if (scope) scope.textContent = comparisonScope(ds);
    const reason = document.getElementById('dashboard-actual-reason');
    if (reason) reason.textContent = ds?.aktual?.alasan_na || (!ds?.aktual ? 'Baseline aktual belum dihitung.' : '');
    const algorithmReason = document.getElementById('dashboard-algorithm-reason');
    if (algorithmReason) algorithmReason.textContent = algorithmMetricReasons(ds);
  }


function updateActualPanel(actual) {
  const panel = document.getElementById('actual-baseline-panel');
  if (!panel) return;

  panel.hidden = !actual;
  if (!actual) return;

  const formatCount = value =>
    value == null || !Number.isFinite(Number(value))
      ? 'N/A'
      : GeoUtils.formatNumber(Number(value));

  // Ringkasan jumlah titik dan kurir
  document.getElementById('actual-baseline-counts').textContent =
    `Titik berhasil geocoding: ${formatCount(actual.jumlah_titik_geocoding)} · ` +
    `Titik dievaluasi (Petugas valid): ${formatCount(actual.jumlah_titik_evaluasi)} · ` +
    `Kurir aktual: ${formatCount(actual.jumlah_kurir_aktual)}`;

  // Terjemahkan status backend untuk tampilan
  const rawStatus = String(actual.status_evaluasi ?? '').trim();
  const normalizedStatus = rawStatus.toUpperCase().replace(/[\s-]+/g, '_');

  const statusLabels = {
    PARTIAL: 'Sebagian metrik tersedia',
    PARTIALLY_AVAILABLE: 'Sebagian metrik tersedia',
    SEBAGIAN: 'Sebagian metrik tersedia',
    SEBAGIAN_METRIK_TERSEDIA: 'Sebagian metrik tersedia',
    TERSEDIA: 'Metrik evaluasi aktual tersedia (Z₂ tidak berlaku)',
    COMPLETE: 'Metrik evaluasi aktual tersedia (Z₂ tidak berlaku)',
    COMPLETED: 'Metrik evaluasi aktual tersedia (Z₂ tidak berlaku)',
    AVAILABLE: 'Metrik evaluasi aktual tersedia (Z₂ tidak berlaku)',
    LENGKAP: 'Metrik evaluasi aktual tersedia (Z₂ tidak berlaku)',
    UNAVAILABLE: 'Metrik belum tersedia',
    NOT_AVAILABLE: 'Metrik belum tersedia',
    TIDAK_TERSEDIA: 'Metrik belum tersedia'
  };

  const statusText = statusLabels[normalizedStatus] ||
    (/PARTIAL|SEBAGIAN/.test(normalizedStatus)
      ? 'Sebagian metrik tersedia'
      : (rawStatus ? rawStatus.replace(/_/g, ' ') : 'Belum tersedia'));

  document.getElementById('actual-baseline-status').textContent =
    `Status evaluasi: ${statusText}`;

  document.getElementById('actual-baseline-reason').textContent =
    actual.alasan_na ||
    'Baseline aktual tersimpan. K tetap ditentukan manual dan boleh berbeda dari jumlah kurir aktual.';

  fillMetricElements('upload-actual', {
    silhouette: actual.silhouette_score,
    dbi: actual.dbi,
    z1: actual.z1
  });
}


  function resetUploadReadiness() {
  state.readyDatasetId = null;
  state.geocodedPointCount = 0;
  state.uploadStatus = 'idle';
  state.completedClusteringDatasetId = null;

  updateActualPanel(null);
  updateClusteringButtonState();
}

  function updateClusterDistributionTable(ds) {
    const tbody = document.getElementById('table-cluster-distribution-body');
    if (!tbody) return;
    const groups = ds?.clusters?.[state.distributionMode] || [];
    const label = document.getElementById('distribution-group-label');
    if (label) label.textContent = state.distributionMode === 'aktual' ? 'Petugas' : 'Cluster';
    tbody.innerHTML = groups.length ? groups.map(c => {
      const color = getClusterMetadata(c.id).color;
      return `<tr><td><span style="color:${color}">●</span> ${escapeHtml(c.name)}</td><td style="text-align:center">${GeoUtils.formatNumber(c.count)}</td></tr>`;
    }).join('') : '<tr><td colspan="2" class="empty-state">Belum ada kelompok yang tersedia.</td></tr>';
  }

  document.querySelectorAll('[data-distribution-mode]').forEach(button => {
    button.addEventListener('click', () => {
      state.distributionMode = button.dataset.distributionMode;
      document.querySelectorAll('[data-distribution-mode]').forEach(tab => tab.classList.toggle('active', tab === button));
      updateClusterDistributionTable(DATASETS[state.activeDatasetKey] || null);
    });
  });

  // ------------------------------------------------------------------------
  // 4. Map Rendering
  // ------------------------------------------------------------------------
  function actualPoints(ds) {
    return (ds?.points || []).filter(pt => pt.petugas && pt.c_actual != null);
  }

  function renderDashboardMaps() {
    const ds = DATASETS[state.activeDatasetKey] || null;
    ['aktual', 'kmeans', 'hbcdp'].forEach(mode => {
      const id = mode === 'aktual' ? 'map-actual-dash' : `map-${mode}-dash`;
      mapManager.initMap(id);
      const points = mode === 'aktual' ? actualPoints(ds) : (ds?.points || []);
      setTimeout(() => mapManager.renderClustering(id, points, mode, ds?.polygons?.[mode]), 100);
    });
    const message = document.getElementById('actual-map-message');

    if (message) {
      message.textContent = actualPoints(ds).length
        ? 'Menampilkan titik pengiriman berdasarkan petugas aktual, dengan warna berbeda untuk setiap petugas.'
        : 'Peta aktual belum tersedia karena belum ada titik pengiriman dengan nama petugas dan koordinat yang valid.';
    }
  }
  function renderZonaMap() {
    mapManager.initMap('map-zona-large', { zoom: 12 });

    const ds = state.activeDatasetKey ? DATASETS[state.activeDatasetKey] : null;
    const points = state.zonaMode === 'aktual' ? actualPoints(ds) : (ds?.points || []);
  
    const message = document.getElementById('zona-actual-message');

    if (message) {
      if (state.zonaMode === 'aktual') {
        message.textContent = points.length
          ? 'Menampilkan titik pengiriman berdasarkan pembagian tugas aktual PT Pos, beserta nama petugas yang menangani pengiriman.'
          : 'Peta aktual tidak tersedia karena belum ada titik pengiriman dengan Petugas valid.';
      } else if (state.zonaMode === 'kmeans') {
        message.textContent = 'Menampilkan hasil pengelompokan awal titik pengiriman menggunakan algoritma K-Means++, sebelum dilakukan proses penyeimbangan cluster.';
      } else if (state.zonaMode === 'hbcdp') {
        message.textContent = 'Menampilkan hasil pembagian zona pengiriman setelah proses penyeimbangan cluster menggunakan HBCDP, beserta informasi perpindahan titik antar-cluster jika terjadi.';
      }
    }
    if (!points.length) {
      setTimeout(() => {
        mapManager.renderEmptyMap('map-zona-large');
      }, 100);
    } else {
      setTimeout(() => {
        mapManager.renderClustering('map-zona-large', points, state.zonaMode, ds?.polygons?.[state.zonaMode]);
      }, 100);
    }

    updateZonaSummary();
    renderAnggotaTable();
  }

  // ------------------------------------------------------------------------
  // 5. Hasil Pembagian Zona Page Handlers
  // ------------------------------------------------------------------------
  [['aktual', tabAktual], ['kmeans', tabKmeans], ['hbcdp', tabHbcdp]].forEach(([mode, tab]) => {
    tab?.addEventListener('click', () => {
      state.zonaMode = mode;
      state.tableCurrentPage = 1;
      [tabAktual, tabKmeans, tabHbcdp].forEach(button => button?.classList.toggle('active', button === tab));
      const title = mode === 'aktual' ? 'Aktual PT Pos' : mode === 'kmeans' ? 'K-Means Awal' : 'HBCDP (Hasil Akhir)';
      if (zonaMapTitle) zonaMapTitle.textContent = `Visualisasi Zona - ${title}`;
      if (zonaSummaryTitle) zonaSummaryTitle.textContent = `Ringkasan Jumlah Titik - ${title}`;
      document.getElementById('anggota-group-heading').textContent = mode === 'aktual' ? 'Petugas Aktual' : 'Cluster';
      renderZonaMap();
    });
  });

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

    const clusterList = ds.clusters[state.zonaMode];

    let rowsHtml = '';
    let total = 0;

    (clusterList || []).forEach(c => {
  const cMeta = getClusterMetadata(c.id);
  total += (typeof c.count === 'number' ? c.count : 0);

  rowsHtml += `
    <tr class="clickable-cluster-row" data-cluster-id="${c.id}" title="Klik untuk zoom ke wilayah ${escapeHtml(c.name)}">
      <td>
        <span style="display: inline-flex; align-items: center; gap: 8px;">
          <span style="
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: ${cMeta.color};
          "></span>
          <strong>${escapeHtml(c.name)}</strong>
        </span>
      </td>
      <td style="text-align: center; font-weight: 600;">
        ${typeof c.count === 'number' ? GeoUtils.formatNumber(c.count) : c.count}
      </td>
    </tr>
  `;
});

    tbody.innerHTML = rowsHtml || '<tr><td colspan="2" style="text-align: center; color: #64748b; padding: 20px;">Belum ada data zona</td></tr>';
    if (totalCell) totalCell.textContent = total > 0 ? GeoUtils.formatNumber(total) : '-';

    // Klik baris cluster langsung zoom ke wilayah cluster tersebut di peta (Revisi 29 Oktober)
    tbody.querySelectorAll('.clickable-cluster-row').forEach(row => {
      row.addEventListener('click', () => {
        const clusterId = row.getAttribute('data-cluster-id');
        if (mapManager && typeof mapManager.zoomToCluster === 'function') {
          mapManager.zoomToCluster(clusterId, 'map-zona-large');
        }
      });
    });
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

    const clusterKey = state.zonaMode === 'aktual' ? 'c_actual' : state.zonaMode === 'kmeans' ? 'c_init' : 'c_final';
    const query = state.tableSearchQuery.toLowerCase().trim();

    const sourcePoints = state.zonaMode === 'aktual' ? actualPoints(ds) : ds.points;

    let filtered = sourcePoints.filter(pt => {
      if (!query) return true;

      const clusterId = pt[clusterKey];

      const namaCluster = clusterId != null
        ? (state.zonaMode === 'aktual'
            ? pt.petugas || ''
            : `Cluster ${clusterId}`)
        : '';

      return [
        pt.resi,
        pt.alamat,
        pt.id,
        pt.petugas,
        namaCluster
      ].some(value =>
        String(value ?? '').toLowerCase().includes(query)
      );
    });

    const totalCount = filtered.length;
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
const cMeta = cId != null ? { ...getClusterMetadata(cId), name: state.zonaMode === 'aktual' ? pt.petugas : getClusterMetadata(cId).name } : null;
        rowsHtml += `
          <tr>
            <td style="text-align: center;">${rowNo}</td>
            <td>
            <button
            type="button"
            class="clickable-resi resi-map-link"
            data-point-id="${escapeHtml(pt.id)}"
            title="Klik untuk melihat lokasi pengiriman"
          >
            ${escapeHtml(pt.resi)}
          </button>

          </td>
            <td>${escapeHtml(pt.alamat)}</td>
            <td style="text-align: center;">
  ${cMeta ? `
    <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11.5px; background: ${cMeta.fillColor}; color: ${cMeta.color};">
      ${escapeHtml(cMeta.name)}
    </span>
  ` : '-'}
</td>
          </tr>
        `;
      });
      tableBody.innerHTML = rowsHtml;
      // Klik No. Resi untuk zoom ke titik pengiriman
      tableBody.querySelectorAll('.clickable-resi').forEach(button => {
        button.addEventListener('click', () => {
          const pointId = button.dataset.pointId;

          const selectedPoint = ds.points.find(
            pt => String(pt.id) === String(pointId)
          );

          if (!selectedPoint) {
            showToast('Titik pengiriman tidak ditemukan.', 'error');
            return;
          }

          if (mapManager && typeof mapManager.zoomToPoint === 'function') {
            const success = mapManager.zoomToPoint(
            selectedPoint.id,
            'map-zona-large'
          );

            if (success === false) {
              showToast('Titik belum tersedia pada peta.', 'error');
            }
          } else {
            showToast('Fitur zoom titik belum tersedia pada peta.', 'error');
          }
        });
      });
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
    const ds = DATASETS[state.activeDatasetKey] || null;
    document.getElementById('card-eval-n').textContent = ds ? GeoUtils.formatNumber(ds.totalPoints) : 'N/A';
    document.getElementById('card-eval-k').textContent = ds?.k ?? 'N/A';
    document.getElementById('card-eval-actual-couriers').textContent = ds?.aktual?.jumlah_kurir_aktual ?? 'N/A';
    document.getElementById('card-eval-waktu-komputasi').textContent = ds?.waktu_komputasi_str || 'N/A';
    document.getElementById('evaluation-comparison-scope').textContent = comparisonScope(ds);
    document.getElementById('evaluation-actual-reason').textContent = ds?.aktual?.alasan_na || (!ds?.aktual ? 'Baseline aktual belum dihitung.' : '');
    document.getElementById('evaluation-algorithm-reason').textContent = algorithmMetricReasons(ds);
    fillMetricElements('card-eval-actual', { silhouette: ds?.aktual?.silhouette_score, dbi: ds?.aktual?.dbi, z1: ds?.aktual?.z1 });
    fillMetricElements('card-eval-km', comparisonMetrics(ds, 'kmeans'));
    fillMetricElements('card-eval-hb', comparisonMetrics(ds, 'hbcdp'));
    const tbody = document.getElementById('table-eval-steps-body');
    const steps = ds?.evaluation?.steps || [];
    if (tbody) tbody.innerHTML = steps.length ? steps.map(step =>
      `<tr><td><strong>${escapeHtml(step.step)}</strong></td><td style="text-align:center;font-family:monospace">${escapeHtml(step.cardinality)}</td><td>${escapeHtml(step.z1 ?? 'N/A')}</td><td>${escapeHtml(step.z2 ?? 'N/A')}</td><td>${escapeHtml(step.reassigned ?? 'N/A')}</td></tr>`
    ).join('') : '<tr><td colspan="5" class="empty-state">Belum ada proses penyeimbangan jumlah pengiriman antar-kurir.</td></tr>';
  }

  // ------------------------------------------------------------------------
  // 7. Process Selector Event
  // ------------------------------------------------------------------------
  if (processSelector) {
    processSelector.addEventListener('change', async (e) => {
      const selectedVal = e.target.value;
// Pemilihan dataset di Dashboard tidak mereset sesi Upload Data.
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

function escapeHtml(text) {
  if (text == null) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

window.togglePrepDrawer = function(type) {
  const drawer = document.getElementById(`drawer-${type}`);
  const chevron = document.getElementById(`chevron-${type}`);
  if (!drawer) return;
  const isHidden = drawer.style.display === 'none';
  drawer.style.display = isHidden ? 'block' : 'none';
  if (chevron) {
    if (isHidden) {
      chevron.classList.add('rotated');
    } else {
      chevron.classList.remove('rotated');
    }
  }
};

// Event listener dropdown rincian preprocessing
[
  'data-kosong',
  'resi-duplikat'
].forEach(type => {
  const header = document.getElementById(`header-${type}`);

  if (header) {
    header.style.cursor = 'pointer';

    header.addEventListener('click', () => {
      window.togglePrepDrawer(type);
    });
  }
});

window.toggleGeocodingGagalDrawer = function() {
  const drawer = document.getElementById('drawer-geocoding-gagal');
  const chevron = document.getElementById('chevron-geocoding-gagal');
  if (!drawer) return;
  const isHidden = drawer.style.display === 'none';
  drawer.style.display = isHidden ? 'block' : 'none';
  if (chevron) {
    if (isHidden) {
      chevron.classList.add('rotated');
    } else {
      chevron.classList.remove('rotated');
    }
  }
};


function ensurePreprocessingProgressLabel() {
  const progressFill = document.getElementById(
    'preprocessing-progress-fill'
  );

  if (!progressFill || !progressFill.parentElement) return;

  // Warna progress bar sama dengan Geocoding
  progressFill.style.background =
    'linear-gradient(90deg, #1c2d5a 0%, #ef4123 100%)';

  let info = document.getElementById(
    'preprocessing-progress-info'
  );

  if (!info) {
    info = document.createElement('div');
    info.id = 'preprocessing-progress-info';

    info.style.cssText = `
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-top: 8px;
      font-size: 13px;
      color: #64748b;
    `;

    info.innerHTML = `
      <span id="preprocessing-progress-label">
        Belum ada proses preprocessing
      </span>
      <strong
        id="preprocessing-progress-percent"
        style="color: #ef4123; font-weight: 700; white-space: nowrap;"
      >0%</strong>
    `;

    progressFill.parentElement.insertAdjacentElement(
      'afterend',
      info
    );
  }
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
  const detailsContainer = document.getElementById('preprocessing-details-container');

  if (!card || !data) return;

  const awal = Number(data.total_awal ?? 0);
  const eliminasi = Number(data.total_eliminasi ?? 0);
  const valid = Number(data.total_valid ?? data.jumlah_data ?? 0);

  if (totalAwal) totalAwal.textContent = GeoUtils.formatNumber(awal);
  if (totalEliminasi) totalEliminasi.textContent = GeoUtils.formatNumber(eliminasi);
  if (jumlahValid) jumlahValid.textContent = GeoUtils.formatNumber(valid);

  if (status) {
    status.textContent = valid === 0 ? 'Selesai — tidak ada data valid' : '✓ Selesai';
    status.style.color = valid === 0 ? '#d97706' : '#16a34a';
  }

  
  // Semua baris telah diperiksa, termasuk yang tereliminasi
  updatePreprocessingProgress({
    total: awal,
    processed: awal,
    percentage: 100,
    status: 'COMPLETED'
  });

  if (status && valid === 0) {
    status.textContent = 'Selesai — tidak ada data valid';
    status.style.color = '#d97706';
  }


  // Render rincian jika ada
  const prep = data.preprocessing || (data.rincian ? data : null);
  if (prep && prep.rincian && detailsContainer) {
    const rincian = prep.rincian;

const hasPetugas = prep.has_petugas === true;

[
  'data-kosong',
  'resi-duplikat'
].forEach(type => {
  const tbody = document.getElementById(`table-${type}-body`);
  const headerRow = tbody?.closest('table')?.querySelector('thead tr');

  if (!headerRow) return;

  headerRow.querySelectorAll('.prep-petugas-header').forEach(el => el.remove());

  if (hasPetugas) {
    const th = document.createElement('th');
    th.className = 'prep-petugas-header';
    th.textContent = 'Petugas';

    headerRow.children[2]?.insertAdjacentElement('afterend', th);
  }
});


    // 1. Data Kosong
    const countKosong = document.getElementById('count-data-kosong');
    const tbodyKosong = document.getElementById('table-data-kosong-body');
    if (rincian.data_kosong) {
      if (countKosong) countKosong.textContent = `${rincian.data_kosong.count} data`;
      if (tbodyKosong) {
        let h = '';
        (rincian.data_kosong.items || []).forEach((item, idx) => {
          h += `<tr><td style="text-align: center;">${idx + 1}</td><td style="text-align: center;">${item.baris}</td><td>${escapeHtml(item.resi)}</td>${hasPetugas ? `<td>${escapeHtml(item.petugas || '-')}</td>` : ''}<td>${escapeHtml(item.alamat)}</td><td><span style="color: #dc2626;">${escapeHtml(item.keterangan || '')}</span></td></tr>`;
        });
        tbodyKosong.innerHTML = h || `<tr><td colspan="${hasPetugas ? 6 : 5}" style="text-align: center; color: #64748b; padding: 12px;">Tidak ada data kosong</td></tr>`;
      }
    }

    // 2. Resi Duplikat
    const countDuplikat = document.getElementById('count-resi-duplikat');
    const tbodyDuplikat = document.getElementById('table-resi-duplikat-body');
    if (rincian.resi_duplikat) {
      if (countDuplikat) countDuplikat.textContent = `${rincian.resi_duplikat.count} data`;
      if (tbodyDuplikat) {
        let h = '';
        (rincian.resi_duplikat.items || []).forEach((item, idx) => {
          h += `<tr><td style="text-align: center;">${idx + 1}</td><td style="text-align: center;">${item.baris}</td><td>${escapeHtml(item.resi)}</td>${hasPetugas ? `<td>${escapeHtml(item.petugas || '-')}</td>` : ''}<td>${escapeHtml(item.alamat)}</td><td><span style="color: #dc2626;">${escapeHtml(item.keterangan || '')}</span></td></tr>`;
        });
        tbodyDuplikat.innerHTML = h || `<tr><td colspan="${hasPetugas ? 6 : 5}" style="text-align: center; color: #64748b; padding: 12px;">Tidak ada resi duplikat</td></tr>`;
      }
    }

    // 3. Normalisasi Alamat
    const normText = document.getElementById('preprocessing-normalisasi-text');
    if (normText) {
      normText.textContent = `Alamat pada ${GeoUtils.formatNumber(valid)} data valid distandarisasi untuk penulisan Jalan, Gang, dan Nomor serta dirapikan spasinya sebelum geocoding.`;
    }

    // Footer
    const footerText = document.getElementById('preprocessing-footer-text');
    if (footerText) {
      footerText.textContent = `${GeoUtils.formatNumber(valid)} dari ${GeoUtils.formatNumber(awal)} data siap dilanjutkan.`;
    }

    detailsContainer.style.display = 'block';
    if (summary) summary.style.display = 'none';
  } else {
    if (summary) {
      summary.style.display = 'block';
      summary.textContent = valid === 0
        ? `Seluruh ${GeoUtils.formatNumber(awal)} baris data tereliminasi pada tahap preprocessing.`
        : `${GeoUtils.formatNumber(valid)} dari ${GeoUtils.formatNumber(awal)} baris data memenuhi kriteria preprocessing dan dilanjutkan ke tahap geocoding.`;
    }
    if (detailsContainer) detailsContainer.style.display = 'none';
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
  const detailsContainer = document.getElementById('preprocessing-details-container');

  // Reset jumlah data
  if (totalAwal) totalAwal.textContent = '0';
  if (totalEliminasi) totalEliminasi.textContent = '0';
  if (jumlahValid) jumlahValid.textContent = '0';

  // Reset keterangan
  if (summary) {
    summary.textContent = 'Belum ada hasil preprocessing.';
    summary.style.display = 'block';
  }

  if (detailsContainer) {
    detailsContainer.style.display = 'none';
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

  ensurePreprocessingProgressLabel();

  const progressLabel = document.getElementById(
    'preprocessing-progress-label'
  );
  const progressPercent = document.getElementById(
    'preprocessing-progress-percent'
  );

  if (progressLabel) {
    progressLabel.textContent = 'Belum ada proses preprocessing';
  }

  if (progressPercent) {
    progressPercent.textContent = '0%';
  }
}



function updateGeocodingDisplay(geoSummary) {
  if (!geoSummary) return;

  const kpiDiproses = document.getElementById('geocoding-kpi-diproses');
  const kpiBerhasil = document.getElementById('geocoding-kpi-berhasil');
  const kpiGagal = document.getElementById('geocoding-kpi-gagal');
  const container = document.getElementById('geocoding-gagal-container');
  const badge = document.getElementById('geocoding-gagal-badge');
  const tbody = document.getElementById('table-geocoding-gagal-body');

  const total = Number(
    geoSummary.total ?? geoSummary.total_points ?? geoSummary.total_diproses ?? 0
  );
  const berhasil = Number(
    geoSummary.berhasil ?? geoSummary.successful_points ?? 0
  );
  const gagal = Number(
    geoSummary.gagal ?? geoSummary.failed_points ?? 0
  );

  if (kpiDiproses) kpiDiproses.textContent = GeoUtils.formatNumber(total);
  if (kpiBerhasil) kpiBerhasil.textContent = GeoUtils.formatNumber(berhasil);
  if (kpiGagal) kpiGagal.textContent = GeoUtils.formatNumber(gagal);

  const items = geoSummary.gagal_items || [];

  if (!container || !badge || !tbody) return;

  // Petugas opsional: mengikuti metadata dari backend.
  const hasPetugas = geoSummary.has_petugas === true;

// Tambahkan atau hapus header Petugas secara dinamis.
const table = tbody.closest('table');
const headerRow = table?.querySelector('thead tr');

if (headerRow) {
  headerRow.querySelectorAll('.geo-petugas-header')
    .forEach(el => el.remove());

  if (hasPetugas) {
    const th = document.createElement('th');
    th.className = 'geo-petugas-header';
    th.textContent = 'Petugas';

    // Setelah No. Resi, sebelum Alamat.
    headerRow.children[1]?.insertAdjacentElement('afterend', th);
  }

  // Atur lebar kolom secara proporsional.
  const widths = hasPetugas
    ? ['5%', '12%', '15%', '43%', '25%']
    : ['5%', '15%', '55%', '25%'];

  if (table) {
    table.style.width = '100%';
    table.style.tableLayout = 'fixed';
  }

  Array.from(headerRow.children).forEach((th, index) => {
    th.style.width = widths[index];
  });
}

  if (gagal > 0 && items.length > 0) {
    badge.textContent = `${items.length} data`;

    let rowsHtml = '';

    items.forEach((it, idx) => {
      rowsHtml += `
        <tr>
          <td style="text-align: center; color: #64748b;">
            ${idx + 1}
          </td>
          <td>
            ${escapeHtml(it.resi ?? it.nosi ?? '-')}
          </td>
          ${hasPetugas ? `
            <td>
              ${escapeHtml(it.petugas || '-')}
            </td>
          ` : ''}
          <td>
             ${escapeHtml(it.alamat)}
          </td>
          <td>
            <span style="color: #dc2626; font-weight: 600;">
              ${escapeHtml(it.keterangan || 'Lokasi tidak ditemukan')}
            </span>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = rowsHtml;
    container.style.display = 'block';
  } else {
    container.style.display = 'none';
    tbody.innerHTML = '';
  }
}


function resetGeocodingProgress() {
  state.geocodingProgress = 0;
  updateActualPanel(null);

  if (progressBarFill) progressBarFill.style.width = '0%';
  if (progressPercentText) progressPercentText.textContent = '0%';
  if (progressTextLabel) {
    progressTextLabel.textContent = 'Belum ada proses geocoding';
  }

  const kpiDiproses = document.getElementById('geocoding-kpi-diproses');
  const kpiBerhasil = document.getElementById('geocoding-kpi-berhasil');
  const kpiGagal = document.getElementById('geocoding-kpi-gagal');
  const container = document.getElementById('geocoding-gagal-container');
  if (kpiDiproses) kpiDiproses.textContent = '0';
  if (kpiBerhasil) kpiBerhasil.textContent = '0';
  if (kpiGagal) kpiGagal.textContent = '0';
  if (container) container.style.display = 'none';
}

function resetUploadPage() {
  // Jangan reset saat proses masih berjalan
  if (
    state.uploadStatus === 'uploading' ||
    state.uploadStatus === 'geocoding' ||
    state.isClustering
  ) {
    return;
  }

  // Reset file yang dipilih
  if (fileInput) fileInput.value = '';
  if (selectedFileCard) {
    selectedFileCard.style.display = 'none';
  }

  // Reset tampilan preprocessing dan geocoding
  resetPreprocessing();
  resetGeocodingProgress();

  // Reset status geocoding
  const geoStatus = document.getElementById('geocoding-status');
  if (geoStatus) {
    geoStatus.textContent = 'Belum diproses';
    geoStatus.style.color = '#64748b';
  }

  // Reset kesiapan clustering pada sesi upload
  resetUploadReadiness();
}
  

function updatePreprocessingProgress(progress) {
  const total = Math.max(0, Number(progress.total) || 0);

  const processed = Math.min(
    total,
    Math.max(0, Number(progress.processed) || 0)
  );

  const percentage = total > 0
    ? Math.round((processed / total) * 100)
    : 0;

  const currentStatus = progress.status || 'NOT_STARTED';

  const card = document.getElementById(
    'preprocessing-card'
  );

  const status = document.getElementById(
    'preprocessing-status'
  );

  const progressFill = document.getElementById(
    'preprocessing-progress-fill'
  );

  const summary = document.getElementById(
    'preprocessing-summary'
  );

  ensurePreprocessingProgressLabel();

  if (card) {
    card.style.display = 'block';
  }

  if (progressFill) {
    progressFill.style.width = `${percentage}%`;
  }

  const label = document.getElementById(
    'preprocessing-progress-label'
  );

  const percentText = document.getElementById(
    'preprocessing-progress-percent'
  );

  if (label) {
    label.textContent = total > 0
      ? `${GeoUtils.formatNumber(processed)} dari ${GeoUtils.formatNumber(total)} data diperiksa`
      : 'Menunggu pemeriksaan dataset...';
  }

  if (percentText) {
    percentText.textContent = `${percentage}%`;
  }

  if (status) {
    const statusLabels = {
      VALIDATING: 'Memvalidasi dataset...',
      PROCESSING: 'Sedang diproses...',
      SAVING: 'Menyimpan hasil preprocessing...',
      COMPLETED: '✓ Selesai',
      FAILED: 'Gagal'
    };

    status.textContent =
      statusLabels[currentStatus] || 'Mengunggah dataset...';

    status.style.color =
      currentStatus === 'COMPLETED' ? '#16a34a' :
      currentStatus === 'FAILED' ? '#dc2626' :
      '#2563eb';
  }

  if (summary && currentStatus !== 'COMPLETED') {
    summary.style.display = 'block';

    summary.textContent = total > 0
      ? `${GeoUtils.formatNumber(processed)} dari ${GeoUtils.formatNumber(total)} baris dataset telah diperiksa.`
      : 'Menunggu server memulai preprocessing...';
  }
}


async function pollPreprocessingProgress(uploadId, isActive) {
  while (isActive()) {
    try {
      const response = await fetch(
        `/api/preprocessing/progress/${encodeURIComponent(uploadId)}`,
        { cache: 'no-store' }
      );

      if (response.ok) {
        const result = await response.json();

        if (
        isActive() &&
        result.success &&
        result.data &&
        result.data.status !== 'NOT_STARTED'
      ) {
        updatePreprocessingProgress(result.data);
      }
      }
    } catch (error) {
      console.warn('Gagal membaca progress preprocessing:', error);
    }

    if (isActive()) {
      await new Promise(resolve => setTimeout(resolve, 250));
    }
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
    const validExtensions = ['.csv', '.xlsx'];
    const fileName = file.name;
    const fileExt = fileName.slice(fileName.lastIndexOf('.')).toLowerCase();

if (!validExtensions.includes(fileExt)) {
  showToast(
    'Format file tidak didukung. Harap gunakan format .csv atau .xlsx',
    'error'
  );
  if (fileInput) fileInput.value = '';
  return;
}

// Reset hanya setelah file baru lolos validasi
resetUploadPage();

    // Dataset baru belum siap untuk clustering
state.uploadStatus = 'uploading';
state.readyDatasetId = null;
state.geocodedPointCount = 0;
updateClusteringButtonState();

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

    const uploadId = crypto.randomUUID();

    const formData = new FormData();
    formData.append('file', file);
    formData.append('upload_id', uploadId);

    let preprocessingPollingActive = true;

    const preprocessingPollingPromise = pollPreprocessingProgress(
      uploadId,
      () => preprocessingPollingActive
    );

    try {
      const resp = await fetch('/api/upload', {

          method: 'POST',
          body: formData
        });
        
        const res = await resp.json();

        preprocessingPollingActive = false;
        await preprocessingPollingPromise;

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
      } finally {
        preprocessingPollingActive = false;
        await preprocessingPollingPromise;
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



    // Ambil hasil final geocoding dari database
    const detailResponse = await fetch(
      `/api/dataset/${datasetId}`,
      { cache: 'no-store' }
    );

    if (!detailResponse.ok) {
      throw new Error('Gagal mengambil hasil geocoding dari database.');
    }

    const detailResult = await detailResponse.json();

    if (!detailResult.success || !detailResult.data?.geocoding_summary) {
      throw new Error('Ringkasan geocoding tidak tersedia.');
    }

    const summary = detailResult.data.geocoding_summary;

    const total = Number(summary.total ?? 0);
    const berhasil = Number(summary.berhasil ?? 0);
    const gagal = Number(summary.gagal ?? 0);

    if (
      !Number.isFinite(total) ||
      !Number.isFinite(berhasil) ||
      !Number.isFinite(gagal) ||
      total !== berhasil + gagal
    ) {
      throw new Error('Ringkasan hasil geocoding tidak konsisten.');
    }

    state.geocodedPointCount = berhasil;

    updateProgress(total, total, 100);

    if (statusElement) {
      statusElement.textContent = '✓ Selesai';
      statusElement.style.color = '#16a34a';
    }

    if (progressTextLabel) {
      progressTextLabel.textContent =
        `${GeoUtils.formatNumber(total)} alamat diperiksa ` +
        `(${berhasil} berhasil, ${gagal} gagal)`;
    }

    updateGeocodingDisplay(summary);
    updateActualPanel(detailResult.data.aktual || null);

    await loadDatasetFromDb(datasetId);

    showToast(
      `Geocoding selesai: ${berhasil} berhasil, ${gagal} gagal.`
    );

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
        `Jumlah Cluster (K) harus bilangan bulat antara 2 dan ${state.geocodedPointCount - 1}.`,
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

      // Perbarui daftar dataset dan hasil clustering
      await syncDatasetsFromBackend();

      // Tandai clustering berhasil untuk dataset sesi ini
      state.completedClusteringDatasetId = datasetId;

      if (processSelector) {
        processSelector.value = `db_${datasetId}`;
      }

      // Tetap di halaman Upload Data
      showToast(
        'Clustering berhasil diselesaikan dan disimpan ke PostgreSQL!'
      );

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
          'No.,Nosi,Tgl Antaran Pertama,Alamat,Kota,Petugas\n' +
          '1,nosi_1,01/08/2025,Jl. Contoh No. 1,Malang,Kurir A\n' +
          '2,nosi_2,01/08/2025,Jl. Contoh No. 2,Malang,Kurir B\n' +
          '3,nosi_3,01/08/2025,Jl. Contoh No. 3,Malang,Kurir A\n' +
          '4,nosi_4,01/08/2025,Jl. Contoh No. 4,Malang,Kurir B\n' +
          '5,nosi_5,01/08/2025,Jl. Contoh No. 5,Malang,\n';
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
          ['No.', 'Nosi', 'Tgl Antaran Pertama', 'Alamat', 'Kota', 'Petugas'],
          [1, 'nosi_1', '01/08/2025', 'Jl. Contoh No. 1', 'Malang', 'Kurir A'],
          [2, 'nosi_2', '01/08/2025', 'Jl. Contoh No. 2', 'Malang', 'Kurir B'],
          [3, 'nosi_3', '01/08/2025', 'Jl. Contoh No. 3', 'Malang', 'Kurir A'],
          [4, 'nosi_4', '01/08/2025', 'Jl. Contoh No. 4', 'Malang', 'Kurir B'],
          [5, 'nosi_5', '01/08/2025', 'Jl. Contoh No. 5', 'Malang', '']
        ];
        const ws = XLSX.utils.aoa_to_sheet(wsData);
        ws['!cols'] = [{ wch: 6 }, { wch: 14 }, { wch: 22 }, { wch: 35 }, { wch: 15 }, { wch: 20 }];
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
        const csvCell = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
        let csvContent = 'No,Nosi,Alamat,Kecamatan,Latitude,Longitude,Petugas Aktual,Cluster_KMeans_Awal,Cluster_HBCDP_Akhir,Status\n';
        ds.points.forEach((pt, idx) => {
          csvContent += [idx + 1, pt.resi, pt.alamat, pt.kecamatan, pt.lat, pt.lng, pt.petugas, pt.c_init == null ? '' : `Cluster ${pt.c_init}`, pt.c_final == null ? '' : `Cluster ${pt.c_final}`, pt.status].map(csvCell).join(',') + '\n';
        });
        downloadBlob(csvContent, `Hasil_Pembagian_Zona_${ds.fileName || 'GeoKurir'}.csv`, 'text/csv;charset=utf-8;');
        showToast('Hasil clustering berhasil diunduh sebagai CSV.');
      } else {
        showToast('Belum ada data untuk diunduh.', 'error');
      }
    });
  }


    // ------------------------------------------------------------------------
  // Unduh Peta - Playwright melalui Flask Backend
  // ------------------------------------------------------------------------
  if (btnDownloadMap) {
    const originalButtonHtml = btnDownloadMap.innerHTML;

    btnDownloadMap.addEventListener('click', async () => {
      const ds = state.activeDatasetKey
        ? DATASETS[state.activeDatasetKey]
        : null;

      const filenames = {
        aktual: 'Peta_Aktual_PT_Pos.png',
        kmeans: 'Peta_KMeans_Awal.png',
        hbcdp: 'Peta_HBCDP_Hasil_Akhir.png'
      };

      const mode = state.zonaMode;
      const datasetId = ds?.dbId ?? state.currentDbDatasetId;

      if (!isServerMode) {
        showToast('Unduh peta membutuhkan server Flask.', 'error');
        return;
      }

      if (!ds?.points?.length || !datasetId) {
        showToast('Belum ada peta untuk diunduh.', 'error');
        return;
      }

      if (!['aktual', 'kmeans', 'hbcdp'].includes(mode)) {
        showToast('Mode peta tidak valid.', 'error');
        return;
      }

      btnDownloadMap.disabled = true;
      btnDownloadMap.textContent = 'Menyiapkan Peta...';

      try {
          const map = mapManager.maps['map-zona-large'];

          if (!map) {
              throw new Error('Peta belum siap untuk diunduh.');
          }

          const center = map.getCenter();
          const zoom = map.getZoom();
          const mapSize = map.getSize();

          const params = new URLSearchParams({
              lat: String(center.lat),
              lng: String(center.lng),
              zoom: String(zoom),
              width: String(Math.round(mapSize.x)),
              height: String(Math.round(mapSize.y))
          });

          const response = await fetch(
              `/api/download/map/${encodeURIComponent(datasetId)}/${encodeURIComponent(mode)}?${params.toString()}`,
              {
                  method: 'GET',
                  cache: 'no-store'
              }
          );

        if (!response.ok) {
          const contentType = response.headers.get('content-type') || '';
          let message = `Gagal mengunduh peta (HTTP ${response.status}).`;

          if (contentType.includes('application/json')) {
            const result = await response.json();
            message = result.error || result.message || message;
          }

          throw new Error(message);
        }

        const blob = await response.blob();

        if (!blob.size || !blob.type.includes('image/png')) {
          throw new Error('Server tidak mengembalikan gambar PNG yang valid.');
        }

        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');

        link.href = url;
        link.download = filenames[mode];
        document.body.appendChild(link);
        link.click();
        link.remove();

        setTimeout(() => URL.revokeObjectURL(url), 1000);

        showToast('Peta berhasil diunduh.');
      } catch (error) {
        console.error('Unduh peta gagal:', error);
        showToast(error.message || 'Gagal mengunduh peta.', 'error');
      } finally {
        btnDownloadMap.disabled = false;
        btnDownloadMap.innerHTML = originalButtonHtml;
      }
    });
  }


  // Handler tombol Lihat Proses Geocoding pada kartu Preprocessing 
  const btnLanjutGeo = document.getElementById('btn-lanjut-geocoding');
  if (btnLanjutGeo) {
    btnLanjutGeo.addEventListener('click', () => {
      const cardGeo = document.getElementById('card-geocoding');
      if (cardGeo) {
        cardGeo.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  }

  // Handler toggle Panduan Membaca Metrik Evaluasi 
  const btnTogglePanduan = document.getElementById('btn-toggle-panduan-eval');
  const panduanBody = document.getElementById('panduan-eval-body');
  const textPanduan = document.getElementById('text-panduan-eval');
  const arrowPanduan = document.getElementById('arrow-panduan-eval');
  if (btnTogglePanduan && panduanBody) {
    btnTogglePanduan.addEventListener('click', () => {
      const isHidden = panduanBody.style.display === 'none';
      panduanBody.style.display = isHidden ? 'grid' : 'none';
      if (textPanduan) textPanduan.textContent = isHidden ? 'Sembunyikan' : 'Tampilkan';
      if (arrowPanduan) arrowPanduan.textContent = isHidden ? '^' : 'v';
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
ensurePreprocessingProgressLabel();

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
