# rencana_bmn/views.py
# ------------------------------------------------------
# KODE LENGKAP & BENAR views.py (Termasuk Fix Masa Manfaat & Unique Key Impor)
# ------------------------------------------------------
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat
from django.views.decorators.http import require_POST, require_http_methods
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.forms.models import model_to_dict
from django.template.loader import render_to_string
import json
import csv
from django.utils.text import slugify
from datetime import date
import openpyxl
from decimal import Decimal

# Impor model dan form Anda (sudah termasuk semua)
from .models import (
    BarangBMN, RencanaPenggunaan, RencanaPemanfaatan,
    RencanaPemindahtanganan, RencanaPenghapusan, LogPerubahanRencana,
)
from .forms import (
    BarangBMNForm, PilihRencanaForm, RencanaPenggunaanForm, RencanaPemanfaatanForm,
    RencanaPemindahtangananForm, RencanaPenghapusanForm, AlasanForm,
    ImportExcelForm, BulkRencanaForm
)


# === View Dasar ===
@login_required
def index(request):
    """Menampilkan halaman utama/dashboard dengan data ringkasan."""
    total_barang = BarangBMN.objects.count()
    tahun_sekarang = timezone.now().year
    # Hitung total rencana untuk tahun SEKARANG (sesuai modifikasi terakhir)
    total_rencana_aktif = (
        RencanaPenggunaan.objects.filter(tahun_rencana=tahun_sekarang).count() +
        RencanaPemanfaatan.objects.filter(tahun_rencana=tahun_sekarang).count() +
        RencanaPemindahtanganan.objects.filter(tahun_rencana=tahun_sekarang).count() +
        RencanaPenghapusan.objects.filter(tahun_rencana=tahun_sekarang).count()
    )
    perubahan_terakhir = LogPerubahanRencana.objects.order_by('-tanggal_aksi').first()
    context = {
        'nama_aplikasi': 'Sistem Manajemen Rencana Pengelolaan BMN (SMRPB)',
        'total_barang': total_barang,
        'total_rencana_aktif': total_rencana_aktif,
        'perubahan_terakhir': perubahan_terakhir,
        'tahun_sekarang': tahun_sekarang,
    }
    return render(request, 'rencana_bmn/index.html', context)

# === Views untuk Barang BMN (CRUD) ===
@login_required
def daftar_barang(request):
    """Menampilkan daftar semua Barang BMN."""
    query = request.GET.get('q', '')
    list_barang = BarangBMN.objects.all()
    if query:
        list_barang = list_barang.filter(
            Q(kode_barang__icontains=query) | Q(uraian_barang__icontains=query)
        )
    list_barang = list_barang.order_by('kode_barang', 'nup')
    context = { 'list_barang': list_barang, 'query': query }
    return render(request, 'rencana_bmn/daftar_barang.html', context)

@login_required
def tambah_barang(request):
    """Menampilkan form dan memproses penambahan Barang BMN baru."""
    if request.method == 'POST':
        form = BarangBMNForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Barang BMN baru berhasil ditambahkan.')
            return redirect('daftar_barang')
        else:
            messages.error(request, 'Terdapat kesalahan pada form.')
    else:
        form = BarangBMNForm()
    context = { 'form': form, 'form_title': 'Tambah Barang BMN Baru' }
    return render(request, 'rencana_bmn/form_barang.html', context)

@login_required
def edit_barang(request, pk):
    """Menampilkan form dan memproses perubahan data Barang BMN."""
    barang = get_object_or_404(BarangBMN, pk=pk)
    if request.method == 'POST':
        form = BarangBMNForm(request.POST, instance=barang)
        if form.is_valid():
            form.save()
            messages.success(request, f'Data barang {barang.kode_barang} berhasil diperbarui.')
            return redirect('daftar_barang')
        else:
            messages.error(request, 'Terdapat kesalahan pada form.')
    else:
        form = BarangBMNForm(instance=barang)
    context = { 'form': form, 'barang': barang, 'form_title': f'Edit Barang BMN: {barang.kode_barang}' }
    return render(request, 'rencana_bmn/form_barang.html', context)

@login_required
def detail_barang(request, pk):
    """Menampilkan detail Barang BMN beserta rencana pengelolaannya."""
    barang = get_object_or_404(BarangBMN, pk=pk)
    tahun_sekarang = timezone.now().year
    # Gunakan 4 tahun mulai sekarang
    tahun_rencana_list = [tahun_sekarang + i for i in range(4)]

    nilai_buku_rencana = { tahun: barang.get_nilai_buku(tahun) for tahun in tahun_rencana_list }

    # Ambil semua rencana untuk 4 tahun
    rencana_penggunaan = RencanaPenggunaan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)
    rencana_pemanfaatan = RencanaPemanfaatan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)
    rencana_pemindahtanganan = RencanaPemindahtanganan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)
    rencana_penghapusan = RencanaPenghapusan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)

    # Gabungkan semua rencana
    all_rencana = []
    ct_penggunaan = ContentType.objects.get_for_model(RencanaPenggunaan) # Untuk hapus nanti
    ct_pemanfaatan = ContentType.objects.get_for_model(RencanaPemanfaatan)
    ct_pemindahtanganan = ContentType.objects.get_for_model(RencanaPemindahtanganan)
    ct_penghapusan = ContentType.objects.get_for_model(RencanaPenghapusan)

    all_rencana.extend(list(rencana_penggunaan.annotate(jenis_rencana_display=Value('Penggunaan'), jenis_rencana_slug=Value('penggunaan'), content_type_id=Value(ct_penggunaan.id))))
    all_rencana.extend(list(rencana_pemanfaatan.annotate(jenis_rencana_display=Value('Pemanfaatan'), jenis_rencana_slug=Value('pemanfaatan'), content_type_id=Value(ct_pemanfaatan.id))))
    all_rencana.extend(list(rencana_pemindahtanganan.annotate(jenis_rencana_display=Value('Pemindahtanganan'), jenis_rencana_slug=Value('pemindahtanganan'), content_type_id=Value(ct_pemindahtanganan.id))))
    all_rencana.extend(list(rencana_penghapusan.annotate(jenis_rencana_display=Value('Penghapusan'), jenis_rencana_slug=Value('penghapusan'), content_type_id=Value(ct_penghapusan.id))))

    all_rencana.sort(key=lambda x: (x.tahun_rencana, x.jenis_rencana_display))

    pilih_rencana_form = PilihRencanaForm()
    pilih_rencana_form.fields['tahun_rencana'].choices = [(tahun, str(tahun)) for tahun in tahun_rencana_list]

    context = {
        'barang': barang,
        'tahun_sekarang': tahun_sekarang,
        'nilai_buku_saat_ini': barang.get_nilai_buku(tahun_sekarang),
        'tahun_rencana_list': tahun_rencana_list,
        'nilai_buku_rencana': nilai_buku_rencana,
        'all_rencana': all_rencana,
        'pilih_rencana_form': pilih_rencana_form,
    }
    return render(request, 'rencana_bmn/detail_barang.html', context)

@login_required
@require_http_methods(["DELETE"]) # Pastikan decorator ini ada
def hapus_barang(request, pk):
    """Memproses penghapusan Barang BMN (via HTMX DELETE)."""
    barang = get_object_or_404(BarangBMN, pk=pk)
    # if request.method == 'DELETE': # Tidak perlu cek lagi karena decorator
    nama_barang = str(barang)
    barang.delete()
    messages.success(request, f'Barang BMN {nama_barang} berhasil dihapus.')
    response = HttpResponse(status=200)
    response['HX-Redirect'] = reverse('daftar_barang')
    return response
    # else: # Tidak perlu else lagi
    #     messages.error(request, 'Metode tidak diizinkan.')
    #     return redirect('daftar_barang')


# === Views untuk Handle Rencana via HTMX ===
@login_required
def get_form_rencana_spesifik(request, pk):
    """Mengembalikan form spesifik berdasarkan jenis rencana yang dipilih (via HTMX GET)."""
    barang = get_object_or_404(BarangBMN, pk=pk)
    hx_vals = json.loads(request.GET.get('hx_vals', '{}'))
    jenis_rencana = hx_vals.get('jenis_rencana_selector') or request.GET.get('jenis_rencana_selector')
    tahun_rencana = hx_vals.get('tahun_rencana') or request.GET.get('tahun_rencana')

    form = None
    template_name = 'rencana_bmn/_partials/form_rencana_kosong.html'
    form_map = {'PENGGUNAAN': RencanaPenggunaanForm, 'PEMANFAATAN': RencanaPemanfaatanForm, 'PEMINDAHTANGANAN': RencanaPemindahtangananForm, 'PENGHAPUSAN': RencanaPenghapusanForm }
    prefix_map = {'PENGGUNAAN': 'penggunaan', 'PEMANFAATAN': 'pemanfaatan', 'PEMINDAHTANGANAN': 'pemindahtanganan', 'PENGHAPUSAN': 'penghapusan'}

    if jenis_rencana in form_map:
        FormClass = form_map[jenis_rencana]
        prefix = prefix_map[jenis_rencana]
        form = FormClass(prefix=prefix)
        template_name = 'rencana_bmn/_partials/form_rencana_spesifik.html'

    context = {
        'barang': barang, 'form_spesifik': form, 'jenis_rencana': jenis_rencana,
        'tahun_rencana': tahun_rencana, 'form_action_url': reverse('tambah_rencana', kwargs={'pk': barang.pk})
    }
    return render(request, template_name, context)

@login_required
@require_POST
def tambah_rencana(request, pk):
    """Memproses penambahan rencana baru (via HTMX POST)."""
    barang = get_object_or_404(BarangBMN, pk=pk)
    tahun_rencana_str = request.POST.get('tahun_rencana')

    form_map = {'penggunaan': RencanaPenggunaanForm, 'pemanfaatan': RencanaPemanfaatanForm, 'pemindahtanganan': RencanaPemindahtangananForm, 'penghapusan': RencanaPenghapusanForm}
    submitted_form_prefix = None
    for prefix in form_map.keys():
        if any(key.startswith(f"{prefix}-") for key in request.POST): submitted_form_prefix = prefix; break

    if not submitted_form_prefix or not tahun_rencana_str:
        messages.error(request, "Data form tidak lengkap atau tidak valid.")
        return HttpResponseBadRequest("Form tidak valid") # Kirim Bad Request untuk HTMX

    try:
        tahun_rencana = int(tahun_rencana_str)
    except (ValueError, TypeError):
         messages.error(request, "Tahun rencana tidak valid.")
         return HttpResponseBadRequest("Tahun rencana tidak valid")

    FormClass = form_map[submitted_form_prefix]
    form = FormClass(request.POST, prefix=submitted_form_prefix)

    if form.is_valid():
        try:
            with transaction.atomic(): # Bungkus dalam transaksi
                rencana = form.save(commit=False)
                rencana.barang = barang
                rencana.tahun_rencana = tahun_rencana
                rencana.save() # Simpan rencana utama dulu

                messages.success(request, f"Rencana {submitted_form_prefix.capitalize()} tahun {tahun_rencana} ditambahkan.")

                if isinstance(rencana, RencanaPemindahtanganan):
                    jenis_penghapusan_terkait = rencana.jenis_pemindahtanganan
                    penghapusan, created = RencanaPenghapusan.objects.get_or_create(
                        barang=barang, tahun_rencana=rencana.tahun_rencana,
                        defaults={'jenis_penghapusan': jenis_penghapusan_terkait}
                    )
                    if created: messages.info(request, f"Rencana Penghapusan otomatis ditambahkan untuk {rencana.tahun_rencana}.")
                    elif penghapusan.jenis_penghapusan != jenis_penghapusan_terkait:
                        penghapusan.jenis_penghapusan = jenis_penghapusan_terkait
                        penghapusan.keterangan_sebab_lain = None; penghapusan.save()
                        messages.warning(request, f"Rencana Penghapusan tahun {rencana.tahun_rencana} diperbarui.")

            # Render ulang tabel setelah transaksi sukses
            tahun_sekarang = timezone.now().year
            tahun_rencana_list = [tahun_sekarang + i for i in range(4)] # List 4 tahun
            # --- Duplikasi Kode Fetching (bisa direfaktor) ---
            rencana_penggunaan = RencanaPenggunaan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)
            rencana_pemanfaatan = RencanaPemanfaatan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)
            rencana_pemindahtanganan = RencanaPemindahtanganan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)
            rencana_penghapusan = RencanaPenghapusan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)
            all_rencana = []
            ct_penggunaan = ContentType.objects.get_for_model(RencanaPenggunaan)
            ct_pemanfaatan = ContentType.objects.get_for_model(RencanaPemanfaatan)
            ct_pemindahtanganan = ContentType.objects.get_for_model(RencanaPemindahtanganan)
            ct_penghapusan = ContentType.objects.get_for_model(RencanaPenghapusan)
            all_rencana.extend(list(rencana_penggunaan.annotate(jenis_rencana_display=Value('Penggunaan'), jenis_rencana_slug=Value('penggunaan'), content_type_id=Value(ct_penggunaan.id))))
            all_rencana.extend(list(rencana_pemanfaatan.annotate(jenis_rencana_display=Value('Pemanfaatan'), jenis_rencana_slug=Value('pemanfaatan'), content_type_id=Value(ct_pemanfaatan.id))))
            all_rencana.extend(list(rencana_pemindahtanganan.annotate(jenis_rencana_display=Value('Pemindahtanganan'), jenis_rencana_slug=Value('pemindahtanganan'), content_type_id=Value(ct_pemindahtanganan.id))))
            all_rencana.extend(list(rencana_penghapusan.annotate(jenis_rencana_display=Value('Penghapusan'), jenis_rencana_slug=Value('penghapusan'), content_type_id=Value(ct_penghapusan.id))))
            all_rencana.sort(key=lambda x: (x.tahun_rencana, x.jenis_rencana_display))
            # --- Akhir Duplikasi ---
            html = render_to_string(
                'rencana_bmn/_partials/tabel_rencana.html',
                 {'barang': barang, 'all_rencana': all_rencana, 'messages': messages.get_messages(request), 'tahun_rencana_list': tahun_rencana_list},
                 request=request)
            return HttpResponse(html)

        except IntegrityError:
            msg = f"Gagal. Sudah ada Rencana {submitted_form_prefix.capitalize()} tahun {tahun_rencana}."
            messages.error(request, msg)
            response = HttpResponse(f"<div class='alert alert-danger alert-sm py-1'>{msg}</div>", status=400)
            response['HX-Retarget'] = '#form-rencana-messages'; response['HX-Reswap'] = 'innerHTML'
            return response
        except Exception as e: # Tangkap error lain saat save
            messages.error(request, f"Gagal menyimpan data: {e}")
            response = HttpResponse(f"<div class='alert alert-danger alert-sm py-1'>Gagal menyimpan data: {e}</div>", status=500)
            response['HX-Retarget'] = '#form-rencana-messages'; response['HX-Reswap'] = 'innerHTML'
            return response
    else:
        # Form tidak valid, kirim pesan error spesifik
        first_error_key = list(form.errors.keys())[0]
        first_error_msg = form.errors[first_error_key][0]
        field_label = form.fields.get(first_error_key).label if form.fields.get(first_error_key) else first_error_key.replace('_', ' ').title()
        error_msg = f"Error pada '{field_label}': {first_error_msg}"
        messages.error(request, error_msg)
        response = HttpResponse(f"<div class='alert alert-danger alert-sm py-1'>{error_msg}</div>", status=400)
        response['HX-Retarget'] = '#form-rencana-messages'; response['HX-Reswap'] = 'innerHTML'
        return response

@login_required
@require_http_methods(["DELETE"])
def hapus_rencana(request, pk, rencana_id, jenis_rencana_slug):
    """Menghapus item rencana spesifik (via HTMX DELETE)."""
    barang = get_object_or_404(BarangBMN, pk=pk)
    model_map = {'penggunaan': RencanaPenggunaan, 'pemanfaatan': RencanaPemanfaatan, 'pemindahtanganan': RencanaPemindahtanganan, 'penghapusan': RencanaPenghapusan}
    if jenis_rencana_slug not in model_map: return HttpResponseBadRequest("Jenis rencana tidak valid")

    ModelRencana = model_map[jenis_rencana_slug]
    rencana = get_object_or_404(ModelRencana, pk=rencana_id, barang=barang)
    tahun_rencana = rencana.tahun_rencana
    rencana.delete()
    messages.success(request, f"Rencana {jenis_rencana_slug.capitalize()} tahun {tahun_rencana} dihapus.")

    # Render ulang tabel rencana via HTMX (Duplikasi Kode Fetching)
    tahun_sekarang = timezone.now().year
    tahun_rencana_list = [tahun_sekarang + i for i in range(4)]
    # --- Duplikasi Kode Fetching (bisa direfaktor) ---
    rencana_penggunaan = RencanaPenggunaan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)
    rencana_pemanfaatan = RencanaPemanfaatan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)
    rencana_pemindahtanganan = RencanaPemindahtanganan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)
    rencana_penghapusan = RencanaPenghapusan.objects.filter(barang=barang, tahun_rencana__in=tahun_rencana_list)
    all_rencana = []
    ct_penggunaan = ContentType.objects.get_for_model(RencanaPenggunaan)
    ct_pemanfaatan = ContentType.objects.get_for_model(RencanaPemanfaatan)
    ct_pemindahtanganan = ContentType.objects.get_for_model(RencanaPemindahtanganan)
    ct_penghapusan = ContentType.objects.get_for_model(RencanaPenghapusan)
    all_rencana.extend(list(rencana_penggunaan.annotate(jenis_rencana_display=Value('Penggunaan'), jenis_rencana_slug=Value('penggunaan'), content_type_id=Value(ct_penggunaan.id))))
    all_rencana.extend(list(rencana_pemanfaatan.annotate(jenis_rencana_display=Value('Pemanfaatan'), jenis_rencana_slug=Value('pemanfaatan'), content_type_id=Value(ct_pemanfaatan.id))))
    all_rencana.extend(list(rencana_pemindahtanganan.annotate(jenis_rencana_display=Value('Pemindahtanganan'), jenis_rencana_slug=Value('pemindahtanganan'), content_type_id=Value(ct_pemindahtanganan.id))))
    all_rencana.extend(list(rencana_penghapusan.annotate(jenis_rencana_display=Value('Penghapusan'), jenis_rencana_slug=Value('penghapusan'), content_type_id=Value(ct_penghapusan.id))))
    all_rencana.sort(key=lambda x: (x.tahun_rencana, x.jenis_rencana_display))
    # --- Akhir Duplikasi ---
    html = render_to_string(
        'rencana_bmn/_partials/tabel_rencana.html',
            {'barang': barang, 'all_rencana': all_rencana, 'messages': messages.get_messages(request), 'tahun_rencana_list': tahun_rencana_list}, request=request)
    return HttpResponse(html)

# === Views untuk Perubahan Rencana ===
@login_required
def daftar_semua_rencana(request):
    """Menampilkan daftar semua rencana dari semua barang untuk fitur perubahan/pembatalan."""
    penggunaan = RencanaPenggunaan.objects.select_related('barang').all()
    pemanfaatan = RencanaPemanfaatan.objects.select_related('barang').all()
    pemindahtanganan = RencanaPemindahtanganan.objects.select_related('barang').all()
    penghapusan = RencanaPenghapusan.objects.select_related('barang').all()
    all_rencana = []
    ct_penggunaan = ContentType.objects.get_for_model(RencanaPenggunaan)
    ct_pemanfaatan = ContentType.objects.get_for_model(RencanaPemanfaatan)
    ct_pemindahtanganan = ContentType.objects.get_for_model(RencanaPemindahtanganan)
    ct_penghapusan = ContentType.objects.get_for_model(RencanaPenghapusan)
    for item in penggunaan: item.jenis_rencana_display = "Penggunaan"; item.jenis_rencana_slug = "penggunaan"; item.detail_spesifik = item.get_jenis_penggunaan_display(); item.content_type_id = ct_penggunaan.id; all_rencana.append(item)
    for item in pemanfaatan: item.jenis_rencana_display = "Pemanfaatan"; item.jenis_rencana_slug = "pemanfaatan"; item.detail_spesifik = item.get_jenis_pemanfaatan_display(); item.content_type_id = ct_pemanfaatan.id; all_rencana.append(item)
    for item in pemindahtanganan: item.jenis_rencana_display = "Pemindahtanganan"; item.jenis_rencana_slug = "pemindahtanganan"; item.detail_spesifik = item.get_jenis_pemindahtanganan_display(); item.content_type_id = ct_pemindahtanganan.id; all_rencana.append(item)
    for item in penghapusan: item.jenis_rencana_display = "Penghapusan"; item.jenis_rencana_slug = "penghapusan"; detail = item.get_jenis_penghapusan_display(); item.detail_spesifik = detail + (f" ({item.keterangan_sebab_lain})" if item.jenis_penghapusan == 'SEBAB_LAIN' and item.keterangan_sebab_lain else ""); item.content_type_id = ct_penghapusan.id; all_rencana.append(item)
    all_rencana.sort(key=lambda x: (x.barang.kode_barang, x.barang.nup, x.tahun_rencana))
    context = {'page_title': 'Daftar Rencana Pengelolaan (Perubahan/Pembatalan)', 'all_rencana': all_rencana}
    return render(request, 'rencana_bmn/daftar_semua_rencana.html', context)

# --- Helper Function ---
def get_rencana_object_and_form(ct_id, obj_id, post_data=None, instance_needed=True):
    """Helper untuk mendapatkan objek Rencana, ContentType, dan Form yang sesuai."""
    try:
        content_type = ContentType.objects.get_for_id(ct_id)
        ModelClass = content_type.model_class()
        if not issubclass(ModelClass, (RencanaPenggunaan, RencanaPemanfaatan, RencanaPemindahtanganan, RencanaPenghapusan)): raise Http404("Jenis Rencana tidak valid.")
        rencana_object = get_object_or_404(ModelClass, pk=obj_id) if instance_needed else None
        form_map = { RencanaPenggunaan: RencanaPenggunaanForm, RencanaPemanfaatan: RencanaPemanfaatanForm, RencanaPemindahtanganan: RencanaPemindahtangananForm, RencanaPenghapusan: RencanaPenghapusanForm }
        RencanaFormClass = form_map.get(ModelClass);
        if not RencanaFormClass: raise Http404("Form tidak ditemukan.")
        rencana_form_instance = None
        prefix_map = { RencanaPenggunaan: 'penggunaan', RencanaPemanfaatan: 'pemanfaatan', RencanaPemindahtanganan: 'pemindahtanganan', RencanaPenghapusan: 'penghapusan' }
        prefix = prefix_map.get(ModelClass)
        if post_data is not None and rencana_object is not None: rencana_form_instance = RencanaFormClass(post_data, instance=rencana_object, prefix=prefix)
        elif rencana_object is not None: rencana_form_instance = RencanaFormClass(instance=rencana_object, prefix=prefix)
        return content_type, rencana_object, RencanaFormClass, rencana_form_instance
    except ObjectDoesNotExist: raise Http404("Objek ContentType atau Rencana tidak ditemukan.")

# --- View untuk Proses Perubahan ---
@login_required
def ajukan_perubahan_rencana(request, ct_id, obj_id):
    """Menampilkan form perubahan dan memprosesnya."""
    try: content_type, rencana_object, RencanaFormClass, rencana_form = get_rencana_object_and_form(ct_id, obj_id)
    except Http404 as e: messages.error(request, str(e)); return redirect('daftar_semua_rencana')

    if request.method == 'POST':
        try: _, _, _, rencana_form = get_rencana_object_and_form(ct_id, obj_id, post_data=request.POST, instance_needed=True)
        except Http404 as e: messages.error(request, str(e)); return redirect('daftar_semua_rencana')
        alasan_form = AlasanForm(request.POST)

        if rencana_form.is_valid() and alasan_form.is_valid():
            data_sebelum = model_to_dict(rencana_object)
            try:
                with transaction.atomic():
                    rencana_baru = rencana_form.save(commit=False)
                    rencana_baru.barang = rencana_object.barang # Pastikan barang tetap sama
                    rencana_baru.save()
                    data_sesudah = model_to_dict(rencana_baru)
                    LogPerubahanRencana.objects.create(
                        content_type=content_type, object_id=rencana_baru.pk, barang=rencana_baru.barang,
                        aksi='UBAH', alasan=alasan_form.cleaned_data['alasan'], user=request.user if request.user.is_authenticated else None,
                        detail_sebelum=data_sebelum, detail_sesudah=data_sesudah, status_proses='BERHASIL')

                    if isinstance(rencana_baru, RencanaPemindahtanganan):
                        tahun_lama = data_sebelum.get('tahun_rencana'); tahun_baru = rencana_baru.tahun_rencana
                        if tahun_lama != tahun_baru:
                            RencanaPenghapusan.objects.filter(barang=rencana_baru.barang, tahun_rencana=tahun_lama, jenis_penghapusan=rencana_baru.jenis_pemindahtanganan).delete()
                            penghapusan_baru, created = RencanaPenghapusan.objects.get_or_create(barang=rencana_baru.barang, tahun_rencana=tahun_baru, defaults={'jenis_penghapusan': rencana_baru.jenis_pemindahtanganan})
                            if not created and penghapusan_baru.jenis_penghapusan != rencana_baru.jenis_pemindahtanganan: penghapusan_baru.jenis_penghapusan = rencana_baru.jenis_pemindahtanganan; penghapusan_baru.keterangan_sebab_lain = None; penghapusan_baru.save()

                messages.success(request, "Perubahan rencana berhasil disimpan.")
                return redirect('daftar_semua_rencana')
            except IntegrityError: messages.error(request, f"Gagal. Sudah ada rencana sejenis di tahun {rencana_form.cleaned_data.get('tahun_rencana', 'baru')}.")
            except Exception as e: messages.error(request, f"Terjadi kesalahan saat menyimpan: {e}")
        else: messages.error(request, "Gagal menyimpan. Periksa isian form rencana dan alasan.")
    else: alasan_form = AlasanForm()

    context = {
        'page_title': 'Ajukan Perubahan Rencana', 'rencana': rencana_object, 'barang': rencana_object.barang,
        'jenis_rencana_display': content_type.name.replace('rencana ', '').capitalize(),
        'rencana_form': rencana_form, 'alasan_form': alasan_form,
    }
    return render(request, 'rencana_bmn/form_perubahan_rencana.html', context)

# --- View untuk Proses Pembatalan ---
@login_required
def konfirmasi_pembatalan_rencana(request, ct_id, obj_id):
    """Menampilkan konfirmasi pembatalan dan memprosesnya."""
    try: content_type, rencana_object, _, _ = get_rencana_object_and_form(ct_id, obj_id, instance_needed=True)
    except Http404 as e: messages.error(request, str(e)); return redirect('daftar_semua_rencana')

    if request.method == 'POST':
        alasan_form = AlasanForm(request.POST)
        if alasan_form.is_valid():
            data_sebelum = model_to_dict(rencana_object); barang_rencana = rencana_object.barang
            try:
                with transaction.atomic():
                    rencana_object.delete()
                    LogPerubahanRencana.objects.create(
                        content_type=content_type, object_id=obj_id, barang=barang_rencana,
                        aksi='BATAL', alasan=alasan_form.cleaned_data['alasan'], user=request.user if request.user.is_authenticated else None,
                        detail_sebelum=data_sebelum, status_proses='BERHASIL')

                    if content_type.model_class() == RencanaPemindahtanganan:
                        jenis_pindah = data_sebelum.get('jenis_pemindahtanganan'); tahun_rencana = data_sebelum.get('tahun_rencana')
                        if jenis_pindah and tahun_rencana: RencanaPenghapusan.objects.filter(barang=barang_rencana, tahun_rencana=tahun_rencana, jenis_penghapusan=jenis_pindah).delete()

                messages.success(request, "Rencana berhasil dibatalkan.")
                return redirect('daftar_semua_rencana')
            except Exception as e: messages.error(request, f"Terjadi kesalahan saat membatalkan: {e}"); return redirect('daftar_semua_rencana')
        else: messages.error(request, "Gagal membatalkan. Alasan wajib diisi.")
    else: alasan_form = AlasanForm()

    context = {
        'page_title': 'Konfirmasi Pembatalan Rencana', 'rencana': rencana_object, 'barang': rencana_object.barang,
        'jenis_rencana_display': content_type.name.replace('rencana ', '').capitalize(),
        'alasan_form': alasan_form,
    }
    return render(request, 'rencana_bmn/form_konfirmasi_pembatalan.html', context)


# === Views untuk Ekspor/Impor ===
@login_required
def export_rencana_csv(request):
    """Menghasilkan file CSV untuk data rencana pengelolaan (4 tahun)."""
    tipe_rencana = request.GET.get('tipe', 'semua')
    response = HttpResponse(content_type='text/csv')
    today_str = date.today().strftime('%Y%m%d')
    filename = f"export_rencana_{slugify(tipe_rencana)}_{today_str}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    header = ['Tahun Rencana', 'Jenis Rencana', 'Detail Spesifik', 'Kode Barang', 'Uraian Barang', 'NUP', 'Tahun Perolehan', 'Nilai Perolehan', 'Akumulasi Susut (sd Thn Rencana)', 'Nilai Buku (Akhir Thn Rencana)']
    writer.writerow(header)
    rencana_list = []
    tahun_sekarang = timezone.now().year
    tahun_rencana_list = [tahun_sekarang + i for i in range(4)] # 4 tahun
    if tipe_rencana == 'penggunaan' or tipe_rencana == 'semua':
        qs = RencanaPenggunaan.objects.select_related('barang').filter(tahun_rencana__in=tahun_rencana_list).order_by('barang__kode_barang', 'barang__nup', 'tahun_rencana')
        for item in qs: rencana_list.append({'tahun': item.tahun_rencana, 'jenis': 'Penggunaan', 'detail': item.get_jenis_penggunaan_display(), 'barang': item.barang})
    if tipe_rencana == 'pemanfaatan' or tipe_rencana == 'semua':
        qs = RencanaPemanfaatan.objects.select_related('barang').filter(tahun_rencana__in=tahun_rencana_list).order_by('barang__kode_barang', 'barang__nup', 'tahun_rencana')
        for item in qs: rencana_list.append({'tahun': item.tahun_rencana, 'jenis': 'Pemanfaatan', 'detail': item.get_jenis_pemanfaatan_display(), 'barang': item.barang})
    if tipe_rencana == 'pemindahtanganan' or tipe_rencana == 'semua':
        qs = RencanaPemindahtanganan.objects.select_related('barang').filter(tahun_rencana__in=tahun_rencana_list).order_by('barang__kode_barang', 'barang__nup', 'tahun_rencana')
        for item in qs: rencana_list.append({'tahun': item.tahun_rencana, 'jenis': 'Pemindahtanganan', 'detail': item.get_jenis_pemindahtanganan_display(), 'barang': item.barang})
    if tipe_rencana == 'penghapusan' or tipe_rencana == 'semua':
        qs = RencanaPenghapusan.objects.select_related('barang').filter(tahun_rencana__in=tahun_rencana_list).order_by('barang__kode_barang', 'barang__nup', 'tahun_rencana')
        for item in qs: detail = item.get_jenis_penghapusan_display() + (f" ({item.keterangan_sebab_lain})" if item.jenis_penghapusan == 'SEBAB_LAIN' and item.keterangan_sebab_lain else ""); rencana_list.append({'tahun': item.tahun_rencana, 'jenis': 'Penghapusan', 'detail': detail, 'barang': item.barang})
    if tipe_rencana == 'semua': rencana_list.sort(key=lambda x: (x['barang'].kode_barang, x['barang'].nup, x['tahun']))
    for rencana in rencana_list:
        barang = rencana['barang']; tahun_rcn = rencana['tahun']
        akumulasi_susut = barang._hitung_akumulasi_susut(tahun_rcn); nilai_buku = barang.get_nilai_buku(tahun_rcn)
        writer.writerow([rencana['tahun'], rencana['jenis'], rencana['detail'], barang.kode_barang, barang.uraian_barang, barang.nup, barang.tahun_perolehan, barang.nilai_perolehan, akumulasi_susut, nilai_buku])
    return response

@login_required
def import_barang_excel(request):
    """Menampilkan form unggah dan memproses impor data Barang BMN dari Excel."""
    context = {'form': ImportExcelForm(), 'skipped_rows': [], 'errors': [], 'imported_count': 0}
    if request.method == 'POST':
        form = ImportExcelForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']; imported_count = 0; skipped_rows = []; errors = []
            try:
                with transaction.atomic():
                    workbook = openpyxl.load_workbook(excel_file, data_only=True); sheet = workbook.active
                    header = [cell.value for cell in sheet[1]]
                    expected_headers = ['Kode Barang', 'Uraian Barang', 'NUP', 'Nilai Perolehan', 'Tahun Perolehan', 'Masa Manfaat Standar']
                    if header[:len(expected_headers)] != expected_headers: errors.append(f"Format header Excel tidak sesuai. Harusnya: {', '.join(expected_headers)}"); raise ValueError("Header tidak sesuai")
                    for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                        if not any(row): continue
                        try:
                            kode_barang = str(row[0]).strip() if row[0] else None; uraian_barang = str(row[1]).strip() if row[1] else None
                            nup_val, nilai_perolehan_val, tahun_perolehan_val, masa_manfaat_val = row[2], row[3], row[4], row[5]
                            if not all([kode_barang, uraian_barang, nup_val is not None, nilai_perolehan_val is not None, tahun_perolehan_val is not None, masa_manfaat_val is not None]): raise ValueError("Data tidak lengkap")
                            try:
                                nup = int(nup_val); nilai_perolehan = Decimal(nilai_perolehan_val); tahun_perolehan = int(tahun_perolehan_val); masa_manfaat = int(masa_manfaat_val)
                                # Perbolehkan masa manfaat 0
                                if nilai_perolehan < 0 or masa_manfaat < 0 or tahun_perolehan > date.today().year: raise ValueError("Nilai tidak valid (negatif/tahun depan)")
                            except (ValueError, TypeError) as e_type: raise ValueError(f"Tipe data salah: {e_type}")
                            # Gunakan kode_barang dan nup untuk get_or_create
                            barang, created = BarangBMN.objects.get_or_create(kode_barang=kode_barang, nup=nup, defaults={'uraian_barang': uraian_barang, 'nilai_perolehan': nilai_perolehan, 'tahun_perolehan': tahun_perolehan, 'masa_manfaat_standar': masa_manfaat})
                            if created: imported_count += 1
                            else: skipped_rows.append({'row': row_idx, 'kode': kode_barang, 'alasan': 'Kode Barang & NUP sudah ada.'})
                        except (ValueError, TypeError) as e_val: skipped_rows.append({'row': row_idx, 'kode': row[0] if row else 'N/A', 'alasan': f'Error: {e_val}'})
                        except IntegrityError as e_int: skipped_rows.append({'row': row_idx, 'kode': row[0] if row else 'N/A', 'alasan': f'Database Error: {e_int}'})
                if imported_count > 0: messages.success(request, f"Berhasil mengimpor {imported_count} data Barang BMN baru.")
                if skipped_rows: messages.warning(request, f"{len(skipped_rows)} baris dilewati karena sudah ada atau terjadi error.")
                if not errors and imported_count == 0 and not skipped_rows: messages.info(request, "Tidak ada data baru yang diimpor.")
            except ValueError as e_header: messages.error(request, f"Gagal memproses file: {e_header}")
            except Exception as e: messages.error(request, f"Terjadi kesalahan saat memproses file Excel: {e}")
            context.update({'skipped_rows': skipped_rows, 'errors': errors, 'imported_count': imported_count})
        else: messages.error(request, "Form tidak valid. Pastikan Anda memilih file Excel.")
        context['form'] = form # Tampilkan form lagi (mungkin dengan error file)
    return render(request, 'rencana_bmn/import_excel.html', context)

# === Views untuk Bulk Rencana ===
@login_required
@require_POST
def get_bulk_rencana_form(request):
    """Menyiapkan dan mengembalikan form bulk rencana dalam modal (via HTMX)."""
    selected_ids_str = request.POST.get('selected_barang_ids', '')
    selected_ids = [int(id) for id in selected_ids_str.split(',') if id.isdigit()]
    if not selected_ids: return HttpResponseBadRequest("<div class='modal-body'><div class='alert alert-danger'>Tidak ada barang BMN yang dipilih.</div></div>")
    valid_barang_count = BarangBMN.objects.filter(pk__in=selected_ids).count()
    if valid_barang_count != len(selected_ids): return HttpResponseBadRequest("<div class='modal-body'><div class='alert alert-danger'>Ada ID barang terpilih yang tidak valid.</div></div>")
    form = BulkRencanaForm()
    tahun_sekarang = timezone.now().year
    tahun_rencana_list = [tahun_sekarang + i for i in range(4)]
    form.fields['tahun_rencana'].choices = [(tahun, str(tahun)) for tahun in tahun_rencana_list]
    context = {'form': form, 'selected_ids_str': selected_ids_str, 'selected_ids_count': len(selected_ids)}
    return render(request, 'rencana_bmn/_partials/modal_bulk_rencana.html', context)

@login_required
@require_POST
def proses_bulk_rencana(request):
    """Memproses penyimpanan rencana secara bulk."""
    form = BulkRencanaForm(request.POST)
    selected_ids_str = request.POST.get('selected_barang_ids', '')
    selected_ids = [int(id) for id in selected_ids_str.split(',') if id.isdigit()]
    selected_ids_count = len(selected_ids)
    tahun_sekarang = timezone.now().year
    tahun_rencana_list = [tahun_sekarang + i for i in range(4)]
    form.fields['tahun_rencana'].choices = [(tahun, str(tahun)) for tahun in tahun_rencana_list]

    if form.is_valid():
        tahun_rencana = int(form.cleaned_data['tahun_rencana']); jenis_rencana_key = form.cleaned_data['jenis_rencana']
        model_map = {'PENGGUNAAN': (RencanaPenggunaan, 'jenis_penggunaan'), 'PEMANFAATAN': (RencanaPemanfaatan, 'jenis_pemanfaatan'), 'PEMINDAHTANGANAN': (RencanaPemindahtanganan, 'jenis_pemindahtanganan'), 'PENGHAPUSAN': (RencanaPenghapusan, 'jenis_penghapusan')}
        if jenis_rencana_key not in model_map:
             messages.error(request, "Jenis rencana yang dipilih tidak valid.")
             context = {'form': form, 'selected_ids_str': selected_ids_str, 'selected_ids_count': selected_ids_count}
             return render(request, 'rencana_bmn/_partials/modal_bulk_rencana.html', context) # Re-render modal
        ModelRencana, detail_field = model_map[jenis_rencana_key]; detail_value = form.cleaned_data[detail_field]
        keterangan_sebab_lain_value = form.cleaned_data.get('keterangan_sebab_lain') if jenis_rencana_key == 'PENGHAPUSAN' else None
        created_count, skipped_count, processed_ids = 0, 0, []
        try:
            with transaction.atomic():
                barang_objects = BarangBMN.objects.filter(pk__in=selected_ids)
                if barang_objects.count() != len(selected_ids): raise ValueError("Jumlah barang tidak sesuai ID.")
                for barang in barang_objects:
                    defaults_data = {detail_field: detail_value}
                    if keterangan_sebab_lain_value is not None: defaults_data['keterangan_sebab_lain'] = keterangan_sebab_lain_value
                    rencana, created = ModelRencana.objects.get_or_create(barang=barang, tahun_rencana=tahun_rencana, defaults=defaults_data)
                    processed_ids.append(barang.pk)
                    if created:
                        created_count += 1
                        if jenis_rencana_key == 'PEMINDAHTANGANAN':
                             jenis_hps = detail_value
                             penghapusan, created_hps = RencanaPenghapusan.objects.get_or_create(barang=barang, tahun_rencana=tahun_rencana, defaults={'jenis_penghapusan': jenis_hps})
                             if not created_hps and penghapusan.jenis_penghapusan != jenis_hps: penghapusan.jenis_penghapusan = jenis_hps; penghapusan.keterangan_sebab_lain = None; penghapusan.save()
                    else: skipped_count += 1
            skipped_count += len(selected_ids) - len(processed_ids)
            if created_count > 0: messages.success(request, f"Berhasil menerapkan rencana ke {created_count} barang.")
            if skipped_count > 0: messages.warning(request, f"{skipped_count} barang dilewati (rencana thn {tahun_rencana} sudah ada).")
            if created_count == 0 and skipped_count == len(selected_ids): messages.info(request, "Tidak ada rencana baru diterapkan.")
            response = HttpResponse(status=204); response['HX-Redirect'] = reverse('daftar_barang'); return response
        except ValueError as e: messages.error(request, f"Error: {e}")
        except Exception as e: messages.error(request, f"Kesalahan tak terduga: {e}")
        # Jika error, re-render modal
        context = {'form': form, 'selected_ids_str': selected_ids_str, 'selected_ids_count': selected_ids_count}
        return render(request, 'rencana_bmn/_partials/modal_bulk_rencana.html', context)
    else: # Form tidak valid
        messages.error(request, "Data form tidak valid, silakan periksa kembali.")
        context = {'form': form, 'selected_ids_str': selected_ids_str, 'selected_ids_count': selected_ids_count}
        return render(request, 'rencana_bmn/_partials/modal_bulk_rencana.html', context)