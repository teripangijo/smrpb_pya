# rencana_bmn/admin.py
from django.contrib import admin
from .models import (
    BarangBMN,
    RencanaPenggunaan,
    RencanaPemanfaatan,
    RencanaPemindahtanganan,
    RencanaPenghapusan,
    LogPerubahanRencana,
)

@admin.register(BarangBMN)
class BarangBMNAdmin(admin.ModelAdmin):
    list_display = ('kode_barang', 'uraian_barang', 'nup', 'tahun_perolehan', 'nilai_perolehan', 'masa_manfaat_standar')
    search_fields = ('kode_barang', 'uraian_barang')
    list_filter = ('tahun_perolehan',)

# Daftarkan juga model-model rencana agar bisa diakses via admin
@admin.register(RencanaPenggunaan)
class RencanaPenggunaanAdmin(admin.ModelAdmin):
    list_display = ('barang', 'tahun_rencana', 'jenis_penggunaan')
    list_filter = ('tahun_rencana', 'jenis_penggunaan')
    search_fields = ('barang__kode_barang', 'barang__uraian_barang')
    autocomplete_fields = ['barang'] # Memudahkan pemilihan barang

@admin.register(RencanaPemanfaatan)
class RencanaPemanfaatanAdmin(admin.ModelAdmin):
    list_display = ('barang', 'tahun_rencana', 'jenis_pemanfaatan')
    list_filter = ('tahun_rencana', 'jenis_pemanfaatan')
    search_fields = ('barang__kode_barang', 'barang__uraian_barang')
    autocomplete_fields = ['barang']

@admin.register(RencanaPemindahtanganan)
class RencanaPemindahtangananAdmin(admin.ModelAdmin):
    list_display = ('barang', 'tahun_rencana', 'jenis_pemindahtanganan')
    list_filter = ('tahun_rencana', 'jenis_pemindahtanganan')
    search_fields = ('barang__kode_barang', 'barang__uraian_barang')
    autocomplete_fields = ['barang']

@admin.register(RencanaPenghapusan)
class RencanaPenghapusanAdmin(admin.ModelAdmin):
    list_display = ('barang', 'tahun_rencana', 'jenis_penghapusan', 'keterangan_sebab_lain')
    list_filter = ('tahun_rencana', 'jenis_penghapusan')
    search_fields = ('barang__kode_barang', 'barang__uraian_barang')
    autocomplete_fields = ['barang']

@admin.register(LogPerubahanRencana)
class LogPerubahanRencanaAdmin(admin.ModelAdmin):
    list_display = ('tanggal_aksi', 'barang', 'get_rencana_display', 'aksi', 'user', 'status_proses', 'alasan')
    list_filter = ('aksi', 'status_proses', 'tanggal_aksi', 'content_type', 'user')
    search_fields = ('barang__kode_barang', 'barang__uraian_barang', 'alasan', 'object_id')
    readonly_fields = ('content_type', 'object_id', 'rencana_object', 'barang', 'aksi', 'tanggal_aksi', 'user', 'status_proses', 'detail_sebelum', 'detail_sesudah') # Umumnya log tidak diedit

    def get_rencana_display(self, obj):
        return obj.get_rencana_display()
    get_rencana_display.short_description = 'Objek Rencana'