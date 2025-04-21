# smrpb_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Arahkan root URL ke aplikasi rencana_bmn
    path('', include('rencana_bmn.urls')),
    # Tambahkan URL untuk login/logout bawaan Django jika diperlukan
    # path('accounts/', include('django.contrib.auth.urls')),
    # Redirect root jika perlu (misal jika halaman utama ada di /dashboard/)
    # path('', RedirectView.as_view(pattern_name='index', permanent=False)),
]