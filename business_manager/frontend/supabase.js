// AI Manager — Supabase Client, Kullanıcı Kimlik & Rol Yönetimi
const SUPABASE_URL = 'https://jxfllwlngrjctjhclwzj.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_2zas0AHgplp6PhaEzAPdnQ_c-LXgjeg';

let supabaseClient = null;
try {
    if (typeof window !== 'undefined' && window.supabase && typeof window.supabase.createClient === 'function') {
        supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    }
} catch (e) {
    console.warn('[AI Manager] Supabase SDK yuklenemedi veya baslatilamadi:', e);
}

// 1. Yerleşik Kullanıcı Hesapları & Veritabanı
const DEFAULT_USERS = [
    {
        id: 'usr_admin_1',
        email: 'admin@businessmanager.com',
        username: 'admin',
        password: 'admin123',
        name: 'Emin A.',
        role: 'admin',
        title: 'Kurumsal Yönetici & Ajans Direktörü',
        created: '2026-09-01'
    },
    {
        id: 'usr_team_2',
        email: 'demo@businessmanager.com',
        username: 'demo',
        password: 'demo123',
        name: 'Ahmet Y.',
        role: 'user',
        title: 'Kıdemli Proje & Tasarım Lideri',
        created: '2026-09-05'
    },
    {
        id: 'usr_client_3',
        email: 'musteri@acme.com',
        username: 'musteri',
        password: 'musteri123',
        name: 'Burak K.',
        role: 'client',
        title: 'Müşteri Temsilcisi (Fintech Cüzdan)',
        customerId: 'CUST-8',
        created: '2026-09-10'
    }
];

function getStoredUsers() {
    try {
        const raw = localStorage.getItem('business_manager_users_v1');
        if (!raw) {
            localStorage.setItem('business_manager_users_v1', JSON.stringify(DEFAULT_USERS));
            return DEFAULT_USERS;
        }
        return JSON.parse(raw);
    } catch (e) {
        return DEFAULT_USERS;
    }
}

function saveUsers(users) {
    try {
        localStorage.setItem('business_manager_users_v1', JSON.stringify(users));
    } catch (e) {
        console.error('[AI Manager] Kullanıcı kaydetme hatası:', e);
    }
}

// 2. Kullanıcı Kaydı (Sign Up)
async function registerUser({ email, password, name, role = 'user', title = '', customerId = null }) {
    const cleanEmail = (email || '').trim().toLowerCase();
    const cleanPass = (password || '').trim();
    const cleanName = (name || '').trim();

    if (!cleanEmail || !cleanEmail.includes('@')) {
        return { success: false, error: 'Lütfen geçerli bir e-posta adresi giriniz.' };
    }
    if (!cleanPass || cleanPass.length < 4) {
        return { success: false, error: 'Şifreniz en az 4 karakterden oluşmalıdır.' };
    }
    if (!cleanName) {
        return { success: false, error: 'Lütfen ad ve soyadınızı giriniz.' };
    }

    const users = getStoredUsers();
    if (users.some(u => u.email.toLowerCase() === cleanEmail)) {
        return { success: false, error: 'Bu e-posta adresi ile kayıtlı bir hesap zaten mevcut.' };
    }

    const newUser = {
        id: `usr_${Date.now()}`,
        email: cleanEmail,
        username: cleanEmail.split('@')[0],
        password: cleanPass,
        name: cleanName,
        role: role || 'user', // 'admin' | 'user' | 'client'
        title: title || (role === 'admin' ? 'Yönetici Direktör' : (role === 'client' ? 'Kurumsal Müşteri' : 'Ekip Üyesi')),
        customerId: customerId || (role === 'client' ? 'CUST-8' : null),
        created: new Date().toISOString().split('T')[0]
    };

    users.push(newUser);
    saveUsers(users);

    // Supabase Online ise oraya da kaydetmeyi dene
    if (supabaseClient) {
        try {
            await supabaseClient.auth.signUp({ email: cleanEmail, password: cleanPass });
        } catch (err) {}
    }

    return { success: true, user: newUser };
}

// 3. Kullanıcı Girişi (Sign In)
async function authenticateUser(identifier, password) {
    const idClean = (identifier || '').trim().toLowerCase();
    const passClean = (password || '').trim();

    // Hızlı Admin Giriş Bypass'ı
    if (idClean === 'admin' || idClean === 'demo') {
        const match = getStoredUsers().find(u => u.username === idClean || u.role === (idClean === 'admin' ? 'admin' : 'user'));
        if (match) {
            setCurrentSession(match);
            return { success: true, user: match };
        }
    }

    const users = getStoredUsers();
    const found = users.find(u => 
        (u.email.toLowerCase() === idClean || (u.username && u.username.toLowerCase() === idClean)) &&
        (!passClean || u.password === passClean)
    );

    if (found) {
        setCurrentSession(found);
        return { success: true, user: found };
    }

    return { success: false, error: 'E-posta veya şifre hatalı. Lütfen kontrol ediniz.' };
}

// 4. Oturum ve Rol Yönetimi
function setCurrentSession(user) {
    const sessionData = {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role || 'user',
        title: user.title || 'Ekip Üyesi',
        customerId: user.customerId || null,
        loginTime: new Date().toISOString()
    };
    sessionStorage.setItem('ai_manager_user_session', JSON.stringify(sessionData));
    sessionStorage.setItem('ai_manager_demo_admin', '1'); // Geriye dönük uyumluluk
}

function getCurrentUser() {
    try {
        const raw = sessionStorage.getItem('ai_manager_user_session');
        if (raw) return JSON.parse(raw);
    } catch (e) {}

    // Varsayılan oturum açılmışsa admin olarak kabul et
    if (sessionStorage.getItem('ai_manager_demo_admin') === '1') {
        return {
            id: 'usr_admin_default',
            email: 'admin@businessmanager.com',
            name: 'Emin A.',
            role: 'admin',
            title: 'Kurumsal Yönetici',
            customerId: null
        };
    }
    return null;
}

function handleSignOut() {
    sessionStorage.removeItem('ai_manager_user_session');
    sessionStorage.removeItem('ai_manager_demo_admin');
    window.location.href = 'login.html';
}

// 5. Sayfa Koruma & Rol Kontrolü
async function guardProtectedPage(requiredRole = null) {
    let user = getCurrentUser();
    if (!user) {
        // Freelance Çalışma Alanı: Oturum yoksa engellemek yerine varsayılan direktör/freelancer oturumu başlat
        const defaultUser = (typeof DEFAULT_USERS !== 'undefined' && DEFAULT_USERS.length > 0) 
            ? DEFAULT_USERS[0] 
            : {
                id: 'usr_freelance_1',
                email: 'admin@businessmanager.com',
                name: 'Emin A. (Freelance)',
                role: 'admin',
                title: 'Serbest Çalışan & Proje Yöneticisi'
            };
        setCurrentSession(defaultUser);
        user = defaultUser;
    }

    // Müşteri rolündeyse doğrudan Müşteri Portalına yönlendir
    if (user.role === 'client' && !window.location.pathname.includes('portal.html')) {
        window.location.href = 'portal.html' + (user.customerId ? `?cid=${encodeURIComponent(user.customerId)}` : '');
        return false;
    }

    if (requiredRole && user.role !== requiredRole && user.role !== 'admin') {
        alert('Bu sayfaya erişim için yönetici yetkisi gereklidir.');
        window.location.href = 'index.html';
        return false;
    }

    document.documentElement.classList.remove('auth-pending');
    if (document.body) document.body.classList.remove('auth-pending');
    return true;
}

// 6. Supabase Sağlık Kontrolü
async function checkSupabaseHealth() {
    if (!supabaseClient) return { online: false, message: 'SDK yok' };
    try {
        const { data, error } = await supabaseClient.from('companies').select('id').limit(1);
        if (error) throw error;
        return { online: true, message: 'Supabase Canlı' };
    } catch (e) {
        return { online: false, message: 'Yerel Mod' };
    }
}
