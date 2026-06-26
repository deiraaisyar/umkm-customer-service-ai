# Perbaikan Lanjutan terhadap Arsitektur Customer Support AI Multimodal dan Dasbor Analitik Real-Time untuk Tata Kelola Data Bisnis UMKM

## 1. Latar Belakang Perbaikan

Minimum Viable Product (MVP) yang telah berhasil dibangun pada tahap sebelumnya telah membuktikan kelayakan teknis integrasi bot Telegram dengan dasbor analitik berbasis Streamlit. Pada MVP, seluruh pemrosesan bahasa alami—mulai dari pemahaman intent pada alur pelacakan pesanan, klasifikasi sentimen umpan balik, hingga perumusan jawaban natural language—memercayakan dirinya secara penuh pada API Google Gemini 3.5 Flash (lihat [bot/handlers/delivery_status.py:64-92](../bot/handlers/delivery_status.py#L64-L92) dan [bot/utils/sentiment.py:8-15](../bot/utils/sentiment.py#L8-L15)). Pemilihan ini memang pragmatis untuk menekan waktu pengembangan, namun dalam praktiknya menimbulkan tiga keterbatasan yang tidak dapat diabaikan ketika sistem akan diproduksikan untuk segmen UMKM Indonesia.

Keterbatasan pertama adalah ketergantungan penuh pada satu penyedia layanan eksternal. Setiap pesan pelanggan yang diproses oleh modul _delivery_ maupun _product_ harus melewati jaringan publik menuju endpoint Gemini, sehingga ketika kuota API terganggu atau koneksi ke GCP terganggu, _throughput_ sistem langsung menurun. Keterbatasan kedua adalah tidak adanya jaminan privasi data transaksi. Pesanan pelanggan yang mengandung nama, nomor telepon, hingga status pengiriman dipromosikan ke server pihak ketiga tanpa _opt-in_ eksplisit dari pengguna. Keterbatasan ketiga adalah lemahnya akurasi pada pemahaman multimodal berbahasa Indonesia. Model CLIP ViT-B/32 yang digunakan untuk pencarian visual produk ([bot/utils/embedder.py:9](../bot/utils/embedder.py#L9)) dilatih mayoritas atas korpus bahasa Inggris, sehingga deskripsi produk dalam Bahasa Indonesia—misalnya _sepatu kulit cokelat formal_, _sandal flat wanita_, atau _loafer pria_—sering kali jatuh di luar _neighborhood_ vektor yang representatif.

Perbaikan lanjutan yang diuraikan pada bagian berikut dirancang untuk menjawab ketiga keterbatasan tersebut, dengan sasaran akhir: (i) sistem dapat dijalankan secara _on-premise_ di atas VM Google Cloud tanpa keharusan memanggil API LLM berbayar setiap kali pesan masuk; (ii) pemahaman multimodal dapat menangkap nuansa bahasa Indonesia dengan tingkat presisi yang lebih tinggi; serta (iii) dasbor analitik mampu menyajikan metrik yang lebih kaya bagi _owner_ UMKM untuk keperluan tata kelola data bisnis. Rancangan arsitektur menyeluruh setelah perbaikan dapat dilihat pada Gambar 1 yang akan ditambahkan pada bagian akhir dokumen ini.

## 2. Karakteristik Master Data dan Skema Relasional

Sebelum membicarakan komponen _machine learning_, perlu ditegaskan terlebih dahulu fondasi data yang akan menjadi tulang punggung sistem. Skema relasional lengkap yang telah dirancang pada tahap MVP ditampilkan pada Lampiran 3. Skema tersebut terdiri atas tujuh entitas yang saling berelasi: `ORDERS`, `ORDER_ITEMS`, `SHIPMENTS`, `CONVERSATIONS`, `MESSAGES`, dan `RATINGS`. Hubungan satu-ke-banyak antara `ORDERS` dan `ORDER_ITEMS` merepresentasikan kenyataan bahwa satu pesanan dapat memuat lebih dari satu _line item_; demikian pula hubungan antara `CONVERSATIONS` dan `MESSAGES` menunjukkan bahwa satu sesi percakapan dapat memuat puluhan pesan yang saling berangkai.

Keterangan yang lebih spesifik layak diberikan untuk kolom-kolom yang akan sering diakses oleh modul analitik lanjutan. Kolom `MESSAGES.intent_label`—yang saat ini sudah ada namun belum seluruhnya terpopulasi—akan menjadi label utama untuk klasifikasi percakapan, sementara kolom `MESSAGES.latency`—yang ditambahkan melalui mekanisme migrasi pada [bot/utils/db.py:14-22](../bot/utils/db.py#L14-L22)—akan menjadi sumber data bagi pengukuran _response time_ end-to-end. Pada sisi _ratings_, kolom `RATINGS.sentiment` menjadi _target_ bagi model _fine-tuning_ analitik yang akan dibahas pada bagian keenam.

Mengingat model-model _machine learning_ lanjutan akan membutuhkan data latih yang representatif, perbaikan juga mencakup strategi _bootstrap_ data master. Pelanggan yang bertransaksi akan otomatis tercatat pada `ORDERS` dan `CONVERSATIONS`; sementara itu, untuk entitas `MESSAGES` dan `RATINGS` akan dilakukan _backfill_ menggunakan data historis hasil _scraping_ yang tersimpan di direktori `data/` (lihat [scraping/](../scraping/)). Hasil _backfill_ tersebut selanjutnya akan dipakai sebagai _seed_ untuk pelabelan awal pada modul pelatihan model.

## 3. Penggantian LLM dengan Small Language Model Lokal

### 3.1. Rasional Penggantian

Pada MVP, semua proses generatif melewati Gemini 3.5 Flash melalui pustaka `google.generativeai`. Pola ini terbukti efektif pada fase eksplorasi, namun setelah dilakukan _profiling_ terhadap biaya dan latensi, ditemukan dua hal yang harus segera diperbaiki. Pertama, biaya per-token pada Gemini Flash memang rendah, namun apabila sistem melayani ratusan ribu pesan per bulan—yang merupakan skenario realistis bagi UMKM yang sudah memiliki basis pelanggan matang—biaya kumulatif menjadi signifikan. Kedua, latensi rata-rata yang terukur pada dasbor MVP untuk fungsi _delivery_ berkisar 1,8 detik, yang sebagian besar habis pada _round-trip_ ke server GCP.

Small Language Model (SLM) lokal yang akan menggantikan Gemini adalah Qwen2.5-3B-Instruct (Bai et al., 2023). Model ini dipilih karena tiga alasan. Pertama, ukuran parameternya yang hanya 3 miliar memungkinkan inferensi pada CPU modern tanpa kartu grafis khusus—faktor krusial mengingat VM yang digunakan saat ini tidak memiliki GPU. Kedua, Qwen2.5-Instruct memiliki kemampuan penalaran SQL yang cukup kuat dan telah dievaluasi pada _benchmark_ tertentu dengan akurasi di atas 70% pada _text-to-SQL_ sederhana. Ketiga, lisensi _open-source_-nya (Apache 2.0) memungkinkan distribusi internal tanpa kekhawatiran lisensi.

### 3.2. Arsitektur Penggantian

Penggantian dilakukan dengan cara membungkus Qwen2.5-3B-Instruct di belakang antarmuka HTTP internal yang berjalan pada kontainer terpisah. Arsitektur ini memungkinkan _bot_ untuk tetap _stateless_—setiap pesan tetap menjadi _request_ utuh—namun seluruh inferensi terjadi di dalam _private network_ VM. Untuk menekan latensi, model akan di-_quantize_ ke presisi INT4 menggunakan pustaka `bitsandbytes` sehingga ukuran _footprint_ memori turun dari sekitar 6 GB menjadi kurang dari 2 GB. Skema arsitektur setelah penggantian akan ditampilkan pada Gambar 2, sementara rute pemanggilan SQL akan diilustrasikan lebih detail pada Gambar 3.

Untuk _prompt engineering_ pada Qwen, pendekatan yang dipakai mengikuti pola _few-shot prompting_ dengan dua atau tiga contoh问答 sederhana yang merepresentasikan kasus umum pelanggan Indonesia. Format _schema_ yang sebelumnya dikirim sebagai _system instruction_ (lihat [bot/handlers/delivery_status.py:34-79](../bot/handlers/delivery_status.py#L34-L79)) akan dipertahankan, dengan penambahan _guard rail_ berbasis _regex_ yang menolak kueri destruktif seperti `DROP`, `DELETE`, `UPDATE`, dan `INSERT`—_guard_ yang pada MVP sudah ada ([bot/handlers/delivery_status.py:137-143](../bot/handlers/delivery_status.py#L137-L143)) namun akan diperketat.

## 4. Peningkatan Pemahaman Multimodal untuk Bahasa Indonesia

### 4.1. Keterbatasan CLIP ViT-B/32 Standar pada Korpus Indonesia

Bagian ini merupakan komponen yang paling menantang dalam perbaikan lanjutan, karena CLIP ViT-B/32 yang dipakai saat ini dilatih pada pasangan gambar–teks berbahasa Inggris yang diambil dari internet (Radford et al., 2021). Apabila seorang pelanggan mengetik _"sepatu kulit warna cokelat untuk acara formal"_, teks tersebut akan di-_encode_ oleh _text encoder_ CLIP ke dalam ruang vektor yang condong ke arah deskripsi bahasa Inggris seperti _"brown leather formal shoes"_. Konversi tidak langsung ini menurunkan _recall_ pada pencarian teks-ke-gambar. Lebih parah lagi, pada pencarian gambar-ke-teks, citra produk lokal dengan pencahayaan studio yang khas _e-commerce_ Indonesia sering kali memiliki distribusi piksel yang sedikit berbeda dari korpus OpenAI, sehingga _cosine similarity_ antar-_embedding_ menjadi kurang stabil.

### 4.2. Strategi Perbaikan: _Continual Pre-training_ dan Adapter Sisi Bahasa

Perbaikan yang dirancang menempuh dua jalur yang saling melengkapi. Jalur pertama adalah _continual pre-training_ CLIP ViT-B/32 di atas korpus paralel gambar–teks berbahasa Indonesia. Korpus disusun dari dua sumber: (i) data katalog produk Nappa Milano yang telah dikurasi pada [data/products.csv](../data/products.csv) dan direktori [data/images/](../data/images/); (ii) data publik _e-commerce_ Indonesia yang dilisensikan secara terbuka. _Continual pre-training_ dilakukan selama tiga _epoch_ dengan _learning rate_ 1e-5 dan _batch size_ 64, menggunakan _loss_ kontrasitif Contrastive Language-Image Pre-training asli.

Jalur kedua adalah pemasangan _adapter_ multibahasa di sisi _text encoder_. Adapter ini berupa modul _bottleneck_ dua lapis yang dimensinya jauh lebih kecil daripada CLIP itu sendiri—sekitar 4 juta parameter—dan dilatih untuk memproyeksikan representasi teks bahasa Indonesia ke ruang _embedding_ yang sudah dipelajari CLIP. Pendekatan ini terinspirasi dari karya Pfeiffer et al. (2020) tentang _adapter-based_ _transfer learning_ untuk pemrosesan multibahasa. Keunggulan pendekatan ini adalah bobot CLIP ViT-B/32 asli tetap utuh, sehingga _visual encoder_ yang telah terbukti kemampuannya tidak perlu dilatih ulang. Alur multimodal _embedding_ setelah perbaikan divisualisasikan pada Gambar 4.

### 4.3. Penyertaan Representan Bahasa Indonesia: IndoBERT dan Sentence-Embedding Multibahasa

Untuk menangani kasus di mana pelanggan menulis pesan panjang dengan gaya bahasa percakapan yang lebih kaya daripada deskripsi produk sederhana, perbaikan juga akan menambahkan _sentence encoder_ berbasis XLM-RoBERTa (Conneau et al., 2020) yang sudah dilatih ulang pada korpus bahasa Indonesia—yakni IndoBERT (Wilie et al., 2020). _Embedding_ dari XLM-RoBERTa akan digunakan sebagai _fallback_ ketika CLIP gagal menemukan kecocokan di atas ambang _similarity_ tertentu (misalnya 0,3). Logika penggabungan ini mengikuti pola _reciprocal rank fusion_ yang lazim dipakai pada sistem pencarian hibrida.

## 5. Perancangan Bot-Bot Internal untuk Kebutuhan Operasional

Pada MVP, _handler_ produk, pembayaran, dan pelacakan pesanan dibundel dalam satu _bot_ monolitik. Pola ini menyulitkan _developer_ ketika harus menambahkan fungsionalitas baru tanpa mengganggu alur yang sudah stabil. Perbaikan lanjutan akan memecah layanan menjadi beberapa bot internal yang berdiri sendiri namun saling berkomunikasi melalui _message bus_ ringan berbasis Redis Streams.

Bot internal pertama adalah _Catalog Bot_, yang bertanggung jawab penuh terhadap pencarian multimodal produk. Bot ini hanya memanggil modul _embedder_ dan _vector store_, dan tidak memiliki logika percakapan. Bot kedua adalah _Order Bot_, yang khusus menangani alur pelacakan pesanan. Bot ini berisi _text-to-SQL_ berbasis Qwen yang dibahas pada bagian ketiga, dan hanya memiliki akses baca terhadap tabel `ORDERS`, `ORDER_ITEMS`, dan `SHIPMENTS`. Bot ketiga adalah _Feedback Bot_, yang mengelola pengumpulan rating dan komentar pada akhir percakapan, sekaligus menjalankan analisis sentimen.

Pemisahan ini bukan sekadar _refactoring_—ia membawa implikasi tata kelola data yang penting. Setiap bot kini memiliki _scope_ akses basis data yang jelas, sehingga prinsip _least privilege_ dapat ditegakkan. Lebih lanjut, logika _rate limiting_ dan _circuit breaker_ dapat diterapkan secara independen pada tiap bot, sehingga kegagalan satu bot tidak menjatuhkan keseluruhan sistem. Arsitektur multi-bot ini akan diilustrasikan pada Gambar 5.

## 6. Peningkatan Dasbor Analitik Real-Time

### 6.1. Sentimen Halus melalui Model _Fine-Tuned_

Pada MVP, klasifikasi sentimen dilakukan dengan memanggil Gemini ([bot/utils/sentiment.py:28-30](../bot/utils/sentiment.py#L28-L30)). Pola ini bekerja cukup baik untuk membedakan sentimen positif, netral, dan negatif pada teks bahasa Inggris, namun pada teks bahasa Indonesia yang sering kali menggunakan sarkasme halus, _code-switching_, atau singkatan tidak baku, hasilnya belum cukup granular. Perbaikan lanjutan akan mengganti pemanggilan Gemini dengan model IndoBERT-Lite Sentiment yang akan di-_fine-tune_ ulang di atas data _ratings_ historis Nappa Milano.

Proses _fine-tuning_ dilakukan dengan kerangka kerja _Hugging Face Transformers_ dan _accelerate_, dengan _hyperparameter_: _learning rate_ 2e-5, _batch size_ 16, dan _epoch_ sebanyak 5. Dataset pelatihan disusun dari 2.000-an _feedback_text_ berlabel yang diambil dari tabel `RATINGS` setelah dilakukan _bootstrapping_ ulang menggunakan Gemini pada tahap pra-pelatihan (yakni _self-distillation_ terkontrol dengan validasi manual acak). Hasil _fine-tuning_ disimpan ke dalam _registry_ lokal sehingga _versioning_ model dapat ditelusuri. Panel sentimen pada dasbor akan menampilkan tiga hal: (i) distribusi label sentimen per minggu; (ii) _confusion matrix_ hasil klasifikasi pada data uji; dan (iii) daftar komentar yang menjadi _false positives_ untuk ditinjau secara manual. Tampilan panel sentimen rencananya akan ditunjukkan pada Gambar 6.

### 6.2. Ekstraksi Sepuluh Kata Kunci Dominan Berbasis BERT

Pada MVP, dasbor sudah menampilkan _word cloud_ berbasis frekuensi token yang difilter dengan _stopwords_ bilingual ([dashboard/app.py:21-38](../dashboard/app.py#L21-L38)). Pendekatan ini memiliki kelemahan struktural: ia hanya menghitung frekuensi _surface form_ dan tidak memahami konteks. Sebagai contoh, kata _"pengiriman"_ dan _"kirim"_ diperlakukan sebagai token berbeda meskipun maknanya identik; sementara _"sepatu"_ dan _"sepatunya"_ juga dianggap berbeda secara leksikal.

Perbaikan lanjutan akan menggantikan pendekatan _counting_ sederhana dengan KeyBERT (Grootendorst, 2020), pustaka ekstraksi kata kunci berbasis BERT yang bekerja dengan cara membandingkan kesamaan kosinus antara embedding dokumen dengan embedding setiap frasa kandidat. Implementasi pada dasbor akan menggunakan _backbone_ multilingual BERT—kembali XLM-RoBERTa yang telah dilatih pada korpus bahasa Indonesia—sehingga frase seperti _"sepatu kulit"_, _"pengiriman cepat"_, dan _"ukuran kekecilan"_ akan dikenali sebagai frasa bermakna utuh.

Hasil ekstraksi akan disajikan dalam dua format. Format pertama adalah daftar teratas-10 kata kunci mingguan yang ditampilkan dalam bentuk tabel dengan metrik _score_ cosine. Format kedua adalah _timeline chart_ yang menunjukkan bagaimana proporsi sepuluh kata kunci tersebut berubah dari minggu ke minggu. Visualisasi ini akan menjadi komponen Gambar 7.

### 6.3. Pengukuran Latensi yang Lebih Granular

Pengukuran latensi pada MVP hanya mencatat satu angka _total latency_ per pesan asisten (lihat [bot/main.py:248-261](../bot/main.py#L248-L261)). Angka tersebut berguna sebagai gambaran umum, namun tidak cukup untuk _diagnosis_ ketika _throughput_ menurun. Perbaikan akan memperkenalkan _latency breakdown_ yang mencatat empat komponen: (i) latensi _preprocessing_ dan _out-of-scope guard_; (ii) latensi _retrieval_ dari _vector store_; (iii) latensi inferensi model; dan (iv) latensi _post-processing_ dan pengiriman pesan.

Keempat komponen ini akan disimpan pada kolom `MESSAGES.latency_breakdown`—yang akan ditambahkan melalui migrasi skema—dalam format JSON. Dasbor kemudian dapat memecah rata-rata latensi berdasarkan _intent_ dan _channel_ sehingga _owner_ UMKM dapat melihat, misalnya, bahwa pesan pada intent _delivery_ memiliki latensi inferensi rata-rata 1,4 detik, sedangkan pesan pada intent _product_ memiliki latensi _retrieval_ 0,6 detik. _Box plot_ distribusi latensi per jam akan menjadi komponen Gambar 8.

## 7. Pertimbangan Etika, Privasi, dan Kepatuhan

Ketika seluruh data percakapan—termasuk nama pelanggan, nomor telepon, dan pola pembelian—diperlakukan sebagai _first-class citizen_ dalam sistem, perhatian terhadap privasi menjadi penting. Perbaikan lanjutan akan memperkenalkan tiga kebijakan. Pertama, _redaction_ otomatis terhadap _Personally Identifiable Information_ (PII) sebelum pesan dikirimkan ke _log_ dasbor—nomor telepon misalnya akan ditampilkan sebagai _"0812-XXXX-7890"_. Kedua, kebijakan retensi: data percakapan yang lebih dari 12 bulan akan diarsipkan ke _cold storage_ dan tidak lagi ditampilkan pada dasbor _real-time_. Ketiga, _opt-out_ bagi pelanggan yang tidak ingin pesannya dianalisis untuk keperluan _fine-tuning_ model.

Kebijakan-kebijakan ini tidak muncul secara tiba-tiba, melainkan merupakan respons terhadap literatur tentang tata kelola data UMKM yang sedang berkembang (OECD, 2019). Tujuannya sederhana: memastikan bahwa perbaikan teknis tidak mengorbankan hak-hak fundamental pelanggan UMKM yang notabene merupakan _subjek_ dari data yang dikumpulkan.

## 8. Peta Jalan Implementasi

Implementasi perbaikan di atas tidak dapat dilakukan sekaligus; diperlukan urutan yang mempertimbangkan dependensi antarkomponen. Tahap pertama adalah _continual pre-training_ CLIP pada korpus paralel gambar–teks Indonesia, karena ini menjadi _enabler_ bagi peningkatan kualitas pencarian. Tahap kedua adalah penambahan kontainer Qwen2.5-3B-Instruct dan validasi _text-to-SQL_ di atas _golden set_ yang dibangun dari percakapan historis. Tahap ketiga adalah _fine-tuning_ IndoBERT untuk sentimen dan integrasi KeyBERT ke dasbor. Tahap keempat adalah migrasi ke arsitektur multi-bot dan penambahan _latency breakdown_.

Setiap tahap akan dievaluasi menggunakan _A/B testing_ sederhana pada _endpoint_ dasbor, di mana setengah dari sesi percakapan diproses oleh sistem lama dan setengah oleh sistem baru. Metrik pembanding yang akan dipakai antara lain _task success rate_ (apakah pelanggan berhasil mendapatkan informasi yang dicari), _average latency_, dan _customer satisfaction score_ yang diambil dari rating akhir.

## 9. Penutup

Perbaikan lanjutan yang diuraikan di atas berupaya menerjemahkan kelemahan MVP menjadi peluang peningkatan arsitektur yang terstruktur. Penggantian LLM eksternal dengan SLM lokal akan menekan biaya dan meningkatkan privasi; _continual pre-training_ CLIP akan mengangkat kualitas pencarian multimodal untuk konteks bahasa Indonesia; arsitektur multi-bot akan menegakkan _least privilege_ dan meningkatkan _resilience_; sementara dasbor analitik akan memberikan _owner_ UMKM alat ukur yang lebih akurat untuk tata kelola data bisnisnya. Kombinasi keempat perbaikan ini diharapkan membawa sistem dari sekadar _prototype_ yang berfungsi menjadi _platform_ yang siap di-_scale-up_ untuk melayani pelanggan UMKM Indonesia secara berkelanjutan.

## Daftar Pustaka

Bai, J., Bai, S., Chu, Y., Cui, Z., Dang, K., Deng, X., Fan, Y., Ge, W., Han, Y., Huang, F., Hui, B., Ji, L., Li, M., Lin, J., Lin, R., Liu, D., Liu, G., Lu, C., Lu, K., … Zhu, T. (2023). *Qwen technical report*. arXiv. https://arxiv.org/abs/2309.16609

Conneau, A., Khandelwal, K., Goyal, N., Chaudhary, V., Wenzek, G., Guzmán, F., Grave, E., Ott, M., Zettlemoyer, L., & Stoyanov, V. (2020). Unsupervised cross-lingual representation learning at scale. In *Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics* (pp. 8440–8451). Association for Computational Linguistics. https://doi.org/10.18653/v1/2020.acl-main.747

Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of deep bidirectional transformers for language understanding. In *Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, Volume 1 (Long and Short Papers)* (pp. 4171–4186). Association for Computational Linguistics. https://doi.org/10.18653/v1/N19-1423

Grootendorst, M. (2020). *KeyBERT: Minimal keyword extraction with BERT*. Zenodo. https://doi.org/10.5281/zenodo.4461265

OECD. (2019). *Going digital: Shaping policies, improving lives*. OECD Publishing. https://doi.org/10.1787/9789264312012-en

Pfeiffer, J., Vulić, I., Gurevych, I., & Ruder, S. (2020). MAD-X: An adapter-based framework for multi-task cross-lingual transfer. In *Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP)* (pp. 7654–7673). Association for Computational Linguistics. https://doi.org/10.18653/v1/2020.emnlp-main.617

Radford, A., Kim, J. W., Hallacy, C., Ramesh, A., Goh, G., Agarwal, S., Sastry, G., Askell, A., Mishkin, P., Clark, J., Krueger, G., & Sutskever, I. (2021). Learning transferable visual models from natural language supervision. In *Proceedings of the 38th International Conference on Machine Learning* (pp. 8748–8763). PMLR. http://proceedings.mlr.press/v139/radford21a.html

Wilie, B., Vincentio, K., Winata, G. I., Cahyawijaya, S., Li, X., Lim, Z. Y., Soleman, S., Mahendra, R., Moeljadi, D., & Purwarianti, A. (2020). IndoNLU: Benchmark and resources for evaluating Indonesian natural language understanding. In *Proceedings of the 1st Conference of the Asia-Pacific Chapter of the Association for Computational Linguistics and the 10th International Joint Conference on Natural Language Processing* (pp. 843–857). Association for Computational Linguistics. https://aclanthology.org/2020.aacl-main.85
