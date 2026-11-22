"""
GeoKurir Malang - Preprocessing Service

Tahapan preprocessing:
1. Pemeriksaan Data Kosong
2. Pemeriksaan Resi Duplikat
3. Normalisasi Alamat

Hanya dua tahap pertama yang dapat mengeliminasi data.
Normalisasi alamat tidak mengurangi jumlah data valid.


"""

import re
from typing import Dict, List, Any


class PreprocessingService:

    def bersihkan_alamat(self, alamat_raw: str) -> str:
        """
        Normalisasi alamat:
        - JL / JLN / JALAN menjadi Jalan
        - GG / GANG menjadi Gang
        - NO / NOMOR menjadi No.
        - Merapikan spasi berlebih
        """
        if not alamat_raw:
            return ""

        teks = re.sub(
            r"\s+",
            " ",
            str(alamat_raw).strip()
        )

        teks = re.sub(
            r"\b(?:JL|JLN|JALAN)\.?(?=\s|$)",
            "Jalan",
            teks,
            flags=re.IGNORECASE
        )

        teks = re.sub(
            r"\b(?:GG|GANG)\.?(?=\s|$)",
            "Gang",
            teks,
            flags=re.IGNORECASE
        )

        teks = re.sub(
            r"\b(?:NO|NOMOR)\.?(?=\s|\d|$)",
            "No.",
            teks,
            flags=re.IGNORECASE
        )

        teks = re.sub(
            r"\bNo\.\s*(?=\d)",
            "No. ",
            teks
        )

        teks = re.sub(r"\s+", " ", teks).strip()

        return teks


    def proses_dataset(
        self,
        rows: List[Dict[str, Any]],
        col_map: Dict[str, str],
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Menjalankan preprocessing dataset pengiriman.

        Mengembalikan:
        - summary: ringkasan dan rincian eliminasi
        - valid_rows: data yang lolos preprocessing
        """
        total_awal = len(rows)

        def laporkan_progres(jumlah):
            if progress_callback is not None:
                progress_callback(jumlah, total_awal)


        data_kosong_items = []
        resi_duplikat_items = []
        valid_rows = []

        seen_resi = set()
        jumlah_alamat_berubah = 0
        has_petugas = "Petugas" in col_map

        for idx, r in enumerate(rows):
            nomor_baris = idx + 1

            resi = str(
                r.get(col_map.get("Nosi", ""), "") or ""
            ).strip()

            alamat = str(
                r.get(col_map.get("Alamat", ""), "") or ""
            ).strip()

            kota = str(
                r.get(col_map.get("Kota", ""), "") or ""
            ).strip()

            tgl = str(
                r.get(
                    col_map.get("Tgl Antaran Pertama", ""),
                    ""
                ) or ""
            ).strip()
            petugas = " ".join(
                str(
                    r.get(col_map.get("Petugas", ""), "") or ""
                ).split()
            ) or None

            # --------------------------------------------------
            # TAHAP 1: PEMERIKSAAN DATA KOSONG
            # --------------------------------------------------
            if not resi or not alamat:
                alasan = []

                if not resi:
                    alasan.append("Nosi kosong")

                if not alamat:
                    alasan.append("Alamat kosong")

                data_kosong_items.append({
                    "baris": nomor_baris,
                    "resi": resi or "-",
                    "petugas": petugas or "-",
                    "alamat": alamat or "-",
                    "kota": kota or "-",
                    "keterangan": ", ".join(alasan)
                })
                laporkan_progres(idx + 1)
                continue

            # --------------------------------------------------
            # TAHAP 2: PEMERIKSAAN RESI DUPLIKAT
            # --------------------------------------------------
            if resi in seen_resi:
                resi_duplikat_items.append({
                    "baris": nomor_baris,
                    "resi": resi,
                    "petugas": petugas or "-",
                    "alamat": alamat,
                    "kota": kota,
                    "keterangan": (
                        "Nosi sudah ditemukan "
                        "pada baris sebelumnya"
                    )
                })
                laporkan_progres(idx + 1)
                continue

            seen_resi.add(resi)

            # --------------------------------------------------
            # TAHAP 3: NORMALISASI ALAMAT
            # --------------------------------------------------
            alamat_bersih = self.bersihkan_alamat(alamat)

            if alamat_bersih != alamat:
                jumlah_alamat_berubah += 1


            valid_rows.append({
                "baris": nomor_baris,
                "resi": resi,
                "alamat_asli": alamat,
                "alamat_bersih": alamat_bersih,
                "kota": kota,
                "tgl_antaran": tgl,
                "petugas": petugas
            })

            laporkan_progres(idx + 1)

            
        total_eliminasi = (
            len(data_kosong_items)
            + len(resi_duplikat_items)
        )

        total_valid = len(valid_rows)

        summary = {
            "total_awal": total_awal,
            "total_eliminasi": total_eliminasi,
            "total_valid": total_valid,
            "has_petugas": has_petugas,
            "rincian": {
                "data_kosong": {
                    "kategori": "Data Kosong",
                    "deskripsi": (
                        "Nomor resi atau alamat tidak terisi"
                    ),
                    "count": len(data_kosong_items),
                    "items": data_kosong_items
                },
                "resi_duplikat": {
                    "kategori": "Resi Duplikat",
                    "deskripsi": (
                        "Nomor resi sudah ditemukan "
                        "pada baris sebelumnya"
                    ),
                    "count": len(resi_duplikat_items),
                    "items": resi_duplikat_items
                },
                "normalisasi": {
                    "kategori": "Normalisasi Alamat",
                    "deskripsi": (
                        f"Sebanyak {total_valid} alamat valid "
                        "diperiksa dan dinormalisasi sebelum "
                        "geocoding. "
                        f"{jumlah_alamat_berubah} alamat "
                        "mengalami perubahan penulisan."
                    ),
                    "count": total_valid,
                    "jumlah_berubah": jumlah_alamat_berubah
                }
            }
        }

        return {
            "summary": summary,
            "valid_rows": valid_rows
        }


# Singleton instance
preprocessing_service = PreprocessingService()
