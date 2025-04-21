# rencana_bmn/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User # Jika ingin melacak user pengubah
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings # Untuk User ForeignKey
from decimal import Decimal, ROUND_HALF_UP

# Fungsi helper untuk mendapatkan tahun saat ini
def get_current_year():
    return timezone.now().year

class BarangBMN(models.Model):
    """Merepresentasikan data dasar Barang Milik Negara."""
    # Hapus unique=True dari kode_barang
    kode_barang = models.CharField(max_length=50, verbose_name="Kode Barang")
    uraian_barang = models.TextField(verbose_name="Uraian Barang")
    nup = models.IntegerField(verbose_name="Nomor Urut Pendaftaran (NUP)")
    nilai_perolehan = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="Nilai Perolehan")
    tahun_perolehan = models.IntegerField(verbose_name="Tahun Perolehan")
    masa_manfaat_standar = models.PositiveIntegerField(
        verbose_name="Masa Manfaat Standar (Tahun)",
        help_text="Umur ekonomis standar aset dalam tahun (0 jika tidak disusutkan)."
    )

    class Meta:
        verbose_name = "Barang BMN"
        verbose_name_plural = "Daftar Barang BMN"
        # Tambahkan unique_together untuk kode_barang dan nup
        unique_together = ('kode_barang', 'nup')
        ordering = ['kode_barang', 'nup']

    def __str__(self):
        return f"{self.kode_barang} - {self.uraian_barang} (NUP: {self.nup})"

    def clean(self):
        """Validasi data model."""
        if self.tahun_perolehan > get_current_year():
            raise ValidationError({'tahun_perolehan': 'Tahun perolehan tidak boleh melebihi tahun berjalan.'})
        if self.nilai_perolehan < 0:
             raise ValidationError({'nilai_perolehan': 'Nilai perolehan tidak boleh negatif.'})
        # Ubah validasi masa manfaat agar 0 diizinkan
        if self.masa_manfaat_standar < 0:
             raise ValidationError({'masa_manfaat_standar': 'Masa manfaat standar tidak boleh negatif.'})

    def _hitung_akumulasi_susut(self, tahun_acuan):
        """Menghitung akumulasi penyusutan sampai AKHIR TAHUN ACUAN."""
        # Jika masa manfaat 0 atau nilai 0, susut selalu 0
        if self.masa_manfaat_standar <= 0 or self.nilai_perolehan <= 0:
            return Decimal(0)

        jumlah_tahun_susut = max(0, tahun_acuan - self.tahun_perolehan + 1)
        jumlah_tahun_susut = min(jumlah_tahun_susut, self.masa_manfaat_standar)

        if tahun_acuan < self.tahun_perolehan:
            return Decimal(0)

        susut_tahunan = (self.nilai_perolehan / Decimal(self.masa_manfaat_standar)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        akumulasi_susut = susut_tahunan * jumlah_tahun_susut
        akumulasi_susut = min(akumulasi_susut, self.nilai_perolehan)

        return akumulasi_susut.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_nilai_buku(self, tahun_acuan):
        """Menghitung nilai buku pada AKHIR TAHUN ACUAN."""
        akumulasi_susut = self._hitung_akumulasi_susut(tahun_acuan)
        nilai_buku = self.nilai_perolehan - akumulasi_susut
        return max(Decimal(0), nilai_buku).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_nilai_susut_saat_penyusunan(self, tahun_penyusunan):
        """Menghitung akumulasi penyusutan sampai TAHUN PENYUSUNAN."""
        return self._hitung_akumulasi_susut(tahun_penyusunan)


class RencanaPengelolaanBase(models.Model):
    """Model dasar untuk semua jenis rencana pengelolaan."""
    barang = models.ForeignKey(BarangBMN, on_delete=models.CASCADE, related_name='%(class)s_set')
    tahun_rencana = models.IntegerField(verbose_name="Tahun Rencana")

    class Meta:
        abstract = True
        unique_together = ('barang', 'tahun_rencana')
        ordering = ['tahun_rencana', 'barang']

    def __str__(self):
        # Coba akses barang dengan aman jika mungkin belum tersimpan
        barang_str = getattr(getattr(self, 'barang', None), '__str__', lambda: f"Barang ID {self.barang_id}")()
        return f"{barang_str} - Tahun {self.tahun_rencana}"

    def clean(self):
        """Validasi dasar tahun rencana."""
        if self.tahun_rencana is not None:
            current_year = get_current_year()
            # Ubah validasi tahun rencana agar tahun berjalan diizinkan
            if self.tahun_rencana < current_year:
                raise ValidationError(
                    {'tahun_rencana': f'Tahun rencana ({self.tahun_rencana}) tidak boleh sebelum tahun berjalan ({current_year}).'}
                )
            if self.barang_id and hasattr(self, 'barang') and self.barang:
                 if self.tahun_rencana < self.barang.tahun_perolehan:
                     raise ValidationError(
                         {'tahun_rencana': f'Tahun rencana ({self.tahun_rencana}) tidak boleh sebelum tahun perolehan barang ({self.barang.tahun_perolehan}).'}
                     )

# === Model Rencana Konkret ===
class RencanaPenggunaan(RencanaPengelolaanBase):
    JENIS_PENGGUNAAN_CHOICES = [('SENDIRI', 'Digunakan Sendiri'), ('PIHAK_LAIN', 'Digunakan Pihak Lain')]
    jenis_penggunaan = models.CharField(max_length=20, choices=JENIS_PENGGUNAAN_CHOICES, verbose_name="Jenis Penggunaan")
    class Meta(RencanaPengelolaanBase.Meta):
        verbose_name = "Rencana Penggunaan"; verbose_name_plural = "Rencana Penggunaan"

class RencanaPemanfaatan(RencanaPengelolaanBase):
    JENIS_PEMANFAATAN_CHOICES = [('SEWA', 'Sewa'), ('PINJAM_PAKAI', 'Pinjam Pakai'), ('BGS_BSG', 'BGS/BSG'), ('KETUPI', 'KETUPI')]
    jenis_pemanfaatan = models.CharField(max_length=20, choices=JENIS_PEMANFAATAN_CHOICES, verbose_name="Jenis Pemanfaatan")
    class Meta(RencanaPengelolaanBase.Meta):
        verbose_name = "Rencana Pemanfaatan"; verbose_name_plural = "Rencana Pemanfaatan"

class RencanaPemindahtanganan(RencanaPengelolaanBase):
    JENIS_PEMINDAHTANGANAN_CHOICES = [('LELANG', 'Penjualan dengan Lelang'), ('HIBAH', 'Hibah'), ('TUKAR_MENUKAR', 'Tukar Menukar')]
    jenis_pemindahtanganan = models.CharField(max_length=20, choices=JENIS_PEMINDAHTANGANAN_CHOICES, verbose_name="Jenis Pemindahtanganan")
    class Meta(RencanaPengelolaanBase.Meta):
        verbose_name = "Rencana Pemindahtanganan"; verbose_name_plural = "Rencana Pemindahtanganan"

class RencanaPenghapusan(RencanaPengelolaanBase):
    JENIS_PENGHAPUSAN_CHOICES = RencanaPemindahtanganan.JENIS_PEMINDAHTANGANAN_CHOICES + [('SEBAB_LAIN', 'Sebab-Sebab Lain')]
    jenis_penghapusan = models.CharField(max_length=20, choices=JENIS_PENGHAPUSAN_CHOICES, verbose_name="Jenis/Alasan Penghapusan")
    keterangan_sebab_lain = models.TextField(blank=True, null=True, verbose_name="Keterangan Sebab Lain")
    class Meta(RencanaPengelolaanBase.Meta):
        verbose_name = "Rencana Penghapusan"; verbose_name_plural = "Rencana Penghapusan"

    def clean(self):
        super().clean()
        if self.jenis_penghapusan == 'SEBAB_LAIN' and not self.keterangan_sebab_lain:
             raise ValidationError({'keterangan_sebab_lain': 'Keterangan wajib diisi jika memilih Sebab-Sebab Lain.'})
        if self.jenis_penghapusan != 'SEBAB_LAIN' and self.keterangan_sebab_lain:
             self.keterangan_sebab_lain = None


# === Model Untuk Log Perubahan / Pembatalan ===
class LogPerubahanRencana(models.Model):
    AKSI_CHOICES = [('UBAH', 'Perubahan Data'), ('BATAL', 'Pembatalan Rencana')]
    STATUS_CHOICES = [('BERHASIL', 'Berhasil Diproses'), ('GAGAL', 'Gagal Diproses')]
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, limit_choices_to={'model__in': ('rencanapenggunaan', 'rencanapemanfaatan', 'rencanapemindahtanganan', 'rencanapenghapusan')})
    object_id = models.PositiveIntegerField()
    rencana_object = GenericForeignKey('content_type', 'object_id')
    barang = models.ForeignKey(BarangBMN, on_delete=models.CASCADE, related_name='log_perubahan')
    aksi = models.CharField(max_length=10, choices=AKSI_CHOICES, verbose_name="Jenis Aksi")
    alasan = models.TextField(verbose_name="Alasan Perubahan/Pembatalan")
    tanggal_aksi = models.DateTimeField(auto_now_add=True, verbose_name="Waktu Aksi")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="User Pelaksana")
    status_proses = models.CharField(max_length=10, choices=STATUS_CHOICES, default='BERHASIL', verbose_name="Status Proses")
    detail_sebelum = models.JSONField(null=True, blank=True, verbose_name="Data Sebelum")
    detail_sesudah = models.JSONField(null=True, blank=True, verbose_name="Data Sesudah")

    class Meta:
        verbose_name = "Log Perubahan Rencana"; verbose_name_plural = "Log Perubahan Rencana"; ordering = ['-tanggal_aksi']

    def __str__(self):
        return f"{self.get_aksi_display()} pada {self.content_type.model} ({self.object_id}) - {self.tanggal_aksi.strftime('%Y-%m-%d %H:%M')}"

    def get_rencana_display(self):
        if self.rencana_object: return str(self.rencana_object)
        return f"{self.content_type.model} (ID: {self.object_id}) - Mungkin sudah dihapus"