# rencana_bmn/forms.py
# File ini berisi semua definisi Form Django untuk aplikasi rencana_bmn

from django import forms
from django.urls import reverse # Diperlukan jika masih ada sisa penggunaan di widget
from django.utils import timezone
from .models import (
    BarangBMN,
    RencanaPenggunaan,
    RencanaPemanfaatan,
    RencanaPemindahtanganan,
    RencanaPenghapusan,
)

# 1. Form untuk CRUD Barang BMN
class BarangBMNForm(forms.ModelForm):
    """Form untuk menambah/mengedit data Barang BMN."""
    class Meta:
        model = BarangBMN
        fields = [
            'kode_barang', 'uraian_barang', 'nup', 'nilai_perolehan',
            'tahun_perolehan', 'masa_manfaat_standar',
        ]
        widgets = {
            'uraian_barang': forms.Textarea(attrs={'rows': 3}),
            'nilai_perolehan': forms.NumberInput(attrs={'step': '0.01'}),
            'tahun_perolehan': forms.NumberInput(attrs={'min': 1900, 'max': 2100}),
            'masa_manfaat_standar': forms.NumberInput(attrs={'min': 1}),
        }
        labels = {
            'nup': 'NUP (Nomor Urut Pendaftaran)',
            'masa_manfaat_standar': 'Masa Manfaat Standar (Tahun)',
        }
        help_texts = {
            'kode_barang': 'Contoh: 3.01.02.03.004',
            'nilai_perolehan': 'Gunakan titik (.) sebagai pemisah desimal jika ada.',
        }

# 2. Form untuk Memilih Jenis Rencana (di Halaman Detail Barang)
class PilihRencanaForm(forms.Form):
    """Form awal di detail barang untuk memilih tahun dan jenis rencana."""
    tahun_rencana = forms.ChoiceField(
        label="Tahun Rencana",
        choices=[], # Diisi dinamis di view detail_barang
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    JENIS_RENCANA_CHOICES = [
        ('', '---------'),
        ('PENGGUNAAN', 'Penggunaan'),
        ('PEMANFAATAN', 'Pemanfaatan'),
        ('PEMINDAHTANGANAN', 'Pemindahtanganan'),
        ('PENGHAPUSAN', 'Penghapusan (Sebab Lain)'), # Hanya Sebab Lain untuk manual
    ]
    jenis_rencana = forms.ChoiceField(
        label="Jenis Rencana",
        choices=JENIS_RENCANA_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            # Atribut HTMX dipindah ke template detail_barang.html
            'id':'id_jenis_rencana_selector' # Beri ID eksplisit
            })
    )

# 3. Forms Spesifik per Jenis Rencana (untuk Penambahan Individual / Perubahan)
class RencanaPenggunaanForm(forms.ModelForm):
    """Form untuk detail Rencana Penggunaan."""
    class Meta:
        model = RencanaPenggunaan
        fields = ['jenis_penggunaan'] # Nanti bisa ditambahkan tahun_rencana jika form perubahan butuh
        widgets = {
            'jenis_penggunaan': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }
        labels = {'jenis_penggunaan': ''} # Kosongkan label jika sudah jelas

class RencanaPemanfaatanForm(forms.ModelForm):
    """Form untuk detail Rencana Pemanfaatan."""
    class Meta:
        model = RencanaPemanfaatan
        fields = ['jenis_pemanfaatan']
        widgets = {
            'jenis_pemanfaatan': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }
        labels = {'jenis_pemanfaatan': ''}

class RencanaPemindahtangananForm(forms.ModelForm):
    """Form untuk detail Rencana Pemindahtanganan."""
    class Meta:
        model = RencanaPemindahtanganan
        fields = ['jenis_pemindahtanganan']
        widgets = {
            'jenis_pemindahtanganan': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }
        labels = {'jenis_pemindahtanganan': ''}

class RencanaPenghapusanForm(forms.ModelForm):
    """Form untuk detail Rencana Penghapusan (fokus input manual 'Sebab Lain')."""
    class Meta:
        model = RencanaPenghapusan
        fields = ['jenis_penghapusan', 'keterangan_sebab_lain']
        widgets = {
            'jenis_penghapusan': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'keterangan_sebab_lain': forms.Textarea(attrs={'rows': 2, 'class': 'form-control form-control-sm'}),
        }
        labels = {
            'jenis_penghapusan': 'Alasan Penghapusan Manual',
            'keterangan_sebab_lain': 'Keterangan (jika Sebab Lain)',
         }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter pilihan agar hanya muncul 'Sebab Lain'
        self.fields['jenis_penghapusan'].choices = [
            ('', '---------'),
            ('SEBAB_LAIN', 'Sebab-Sebab Lain')
        ]

    def clean(self):
        cleaned_data = super().clean()
        jenis = cleaned_data.get('jenis_penghapusan')
        keterangan = cleaned_data.get('keterangan_sebab_lain')

        if jenis == 'SEBAB_LAIN' and not keterangan:
            self.add_error('keterangan_sebab_lain', 'Keterangan wajib diisi.')
        elif jenis != 'SEBAB_LAIN' and keterangan:
             cleaned_data['keterangan_sebab_lain'] = '' # Kosongkan jika bukan sebab lain

        # Pastikan tidak bisa memilih jenis pemindahtanganan scr manual
        if jenis in [p[0] for p in RencanaPemindahtanganan.JENIS_PEMINDAHTANGANAN_CHOICES]:
             self.add_error('jenis_penghapusan', 'Jenis ini otomatis dari Rencana Pemindahtanganan.')

        return cleaned_data

# 4. Form untuk Alasan Perubahan/Pembatalan
class AlasanForm(forms.Form):
    """Form sederhana untuk menangkap alasan perubahan/pembatalan."""
    alasan = forms.CharField(
        label="Alasan Perubahan/Pembatalan",
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        required=True,
        help_text="Jelaskan alasan mengapa perubahan atau pembatalan ini dilakukan."
    )

# 5. Form untuk Impor File Excel
class ImportExcelForm(forms.Form):
    """Form untuk mengunggah file Excel."""
    excel_file = forms.FileField(
        label="Pilih File Excel (.xlsx)",
        required=True,
        widget=forms.ClearableFileInput(attrs={'accept': '.xlsx'}) # Batasi hanya .xlsx
    )

# 6. Form untuk Definisi Rencana Bulk
class BulkRencanaForm(forms.Form):
    """Form untuk mendefinisikan rencana yang akan diterapkan ke banyak barang."""
    tahun_rencana = forms.ChoiceField(
        label="Tahun Rencana", choices=[], # Diisi di view
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # Gunakan choices dari PilihRencanaForm agar konsisten
    jenis_rencana = forms.ChoiceField(
        label="Jenis Rencana", choices=PilihRencanaForm.JENIS_RENCANA_CHOICES, required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_bulk_jenis_rencana'})
    )

    # Field untuk detail spesifik (awalnya tidak required)
    jenis_penggunaan = forms.ChoiceField(
        label="Jenis Penggunaan", choices=RencanaPenggunaan.JENIS_PENGGUNAAN_CHOICES, required=False,
        widget=forms.Select(attrs={'class': 'form-select detail-field', 'data_jenis': 'PENGGUNAAN'})
    )
    jenis_pemanfaatan = forms.ChoiceField(
        label="Jenis Pemanfaatan", choices=RencanaPemanfaatan.JENIS_PEMANFAATAN_CHOICES, required=False,
        widget=forms.Select(attrs={'class': 'form-select detail-field', 'data_jenis': 'PEMANFAATAN'})
    )
    jenis_pemindahtanganan = forms.ChoiceField(
        label="Jenis Pemindahtanganan", choices=RencanaPemindahtanganan.JENIS_PEMINDAHTANGANAN_CHOICES, required=False,
        widget=forms.Select(attrs={'class': 'form-select detail-field', 'data_jenis': 'PEMINDAHTANGANAN'})
    )
    jenis_penghapusan = forms.ChoiceField( # Hanya Sebab Lain untuk bulk
        label="Alasan Penghapusan Manual", choices=[('', '---------'),('SEBAB_LAIN', 'Sebab-Sebab Lain')], required=False,
        widget=forms.Select(attrs={'class': 'form-select detail-field', 'data_jenis': 'PENGHAPUSAN'})
    )
    keterangan_sebab_lain = forms.CharField(
        label="Keterangan Sebab Lain", required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control detail-field', 'data_jenis': 'PENGHAPUSAN'})
    )

    def clean(self):
        cleaned_data = super().clean()
        jenis_rencana = cleaned_data.get('jenis_rencana')

        # Validasi field detail spesifik wajib diisi berdasarkan jenis_rencana
        detail_field_name = None
        is_required = True # Defaultnya required jika jenis dipilih

        if jenis_rencana == 'PENGGUNAAN': detail_field_name = 'jenis_penggunaan'
        elif jenis_rencana == 'PEMANFAATAN': detail_field_name = 'jenis_pemanfaatan'
        elif jenis_rencana == 'PEMINDAHTANGANAN': detail_field_name = 'jenis_pemindahtanganan'
        elif jenis_rencana == 'PENGHAPUSAN':
            detail_field_name = 'jenis_penghapusan'
            # Jika jenis penghapusan adalah Sebab Lain, keterangan jadi wajib
            if cleaned_data.get(detail_field_name) == 'SEBAB_LAIN' and not cleaned_data.get('keterangan_sebab_lain'):
                self.add_error('keterangan_sebab_lain', 'Keterangan wajib diisi untuk Sebab Lain.')
            elif cleaned_data.get(detail_field_name) != 'SEBAB_LAIN':
                 # Jika jenis penghapusan bukan Sebab Lain (misal kosong), keterangan tidak masalah
                 pass
        else:
            # Jika jenis rencana utama tidak dipilih, detail tidak required
             is_required = False


        if is_required and detail_field_name and not cleaned_data.get(detail_field_name):
            field_label = self.fields[detail_field_name].label
            self.add_error(detail_field_name, f'{field_label} wajib dipilih untuk jenis rencana ini.')

        return cleaned_data