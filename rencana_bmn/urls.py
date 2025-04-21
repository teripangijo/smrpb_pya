# rencana_bmn/urls.py
from django.urls import path
# Import LoginView dan LogoutView (jika ingin logout kustom juga nanti)
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # --- URL Autentikasi Kustom ---
    path('login/',
         auth_views.LoginView.as_view(template_name='rencana_bmn/login.html'),
         name='login'),
    # Gunakan LogoutView bawaan, tapi pastikan LOGOUT_REDIRECT_URL di settings benar
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # ... (URL index, Barang BMN, dan Rencana HTMX yang sudah ada) ...
    path('', views.index, name='index'),
    path('barang/', views.daftar_barang, name='daftar_barang'),
    path('barang/tambah/', views.tambah_barang, name='tambah_barang'),
    path('barang/<int:pk>/', views.detail_barang, name='detail_barang'),
    path('barang/<int:pk>/edit/', views.edit_barang, name='edit_barang'),
    path('barang/<int:pk>/hapus/', views.hapus_barang, name='hapus_barang'),
    path('barang/<int:pk>/rencana/get-form-spesifik/', views.get_form_rencana_spesifik, name='get_form_rencana_spesifik'),
    path('barang/<int:pk>/rencana/tambah/', views.tambah_rencana, name='tambah_rencana'),
    path('barang/<int:pk>/rencana/<int:rencana_id>/<slug:jenis_rencana_slug>/hapus/', views.hapus_rencana, name='hapus_rencana'),

    # --- URL Fitur Perubahan Rencana ---
    path('rencana/perubahan/', views.daftar_semua_rencana, name='daftar_semua_rencana'),

    # URL untuk proses perubahan (GET untuk form, POST untuk proses)
    path('rencana/perubahan/<int:ct_id>/<int:obj_id>/ajukan/', views.ajukan_perubahan_rencana, name='ajukan_perubahan_rencana'),

    # URL untuk proses pembatalan (GET untuk konfirmasi, POST untuk proses)
    path('rencana/perubahan/<int:ct_id>/<int:obj_id>/batal/', views.konfirmasi_pembatalan_rencana, name='konfirmasi_pembatalan_rencana'),

    # URL untuk HTMX delete (jika menggunakan pendekatan itu)
    # path('rencana/perubahan/<int:ct_id>/<int:obj_id>/proses-batal/', views.proses_pembatalan_rencana_htmx, name='proses_pembatalan_rencana_htmx'),

    # --- URL untuk Ekspor/Impor ---
    path('rencana/export/csv/', views.export_rencana_csv, name='export_rencana_csv'),
    path('barang/import/excel/', views.import_barang_excel, name='import_barang_excel'),
    path('rencana/bulk/get-form/', views.get_bulk_rencana_form, name='get_bulk_rencana_form'),
    path('rencana/bulk/proses/', views.proses_bulk_rencana, name='proses_bulk_rencana'),
    path('rencana/import/excel/', views.import_rencana_excel, name='import_rencana_excel'),
]