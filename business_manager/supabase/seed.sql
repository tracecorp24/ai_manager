-- AI Manager Demo Verileri
-- Supabase SQL Editor'da migration'dan sonra çalıştır

INSERT INTO companies (registration_no, name, district, status, sector, email) VALUES
('BM-DEMO-01', 'Arven Makine Teknolojileri', 'İstanbul', 'Faal', 'Makine', 'info1@businessdemo.local'),
('BM-DEMO-02', 'Kuzey Kalıp Sistemleri', 'Kocaeli', 'Faal', 'Kalıp', 'info2@businessdemo.local'),
('BM-DEMO-03', 'Nova Otomasyon', 'Ankara', 'Faal', 'Otomasyon', 'info3@businessdemo.local'),
('BM-DEMO-04', 'Eksen Endüstriyel Tasarım', 'Bursa', 'Faal', 'Tasarım', 'info4@businessdemo.local'),
('BM-DEMO-05', 'MaviHat Yazılım', 'İzmir', 'Faal', 'Yazılım', 'info5@businessdemo.local'),
('BM-DEMO-06', 'Pera Robotik', 'İstanbul', 'Faal', 'Robotik', 'info6@businessdemo.local'),
('BM-DEMO-07', 'Atlas Prototip', 'Eskişehir', 'Faal', 'Prototip', 'info7@businessdemo.local'),
('BM-DEMO-08', 'Rota Enerji Sistemleri', 'Konya', 'Faal', 'Enerji', 'info8@businessdemo.local'),
('BM-DEMO-09', 'Beyaz Metal Sanayi', 'Tekirdağ', 'Faal', 'Metal', 'info9@businessdemo.local'),
('BM-DEMO-10', 'Vizyon Mühendislik', 'Sakarya', 'Faal', 'Mühendislik', 'info10@businessdemo.local')
ON CONFLICT (registration_no) DO NOTHING;
