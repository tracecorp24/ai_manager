// AI Manager — Supabase Client, Gerçek Kullanıcı Kimlik Doğrulama & Rol Yönetimi
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

// 1. Kayıt (Sign Up) — gerçek Supabase Auth hesabı oluşturur
async function registerUser({ email, password, name }) {
    const cleanEmail = (email || '').trim().toLowerCase();
    const cleanPass = (password || '').trim();
    const cleanName = (name || '').trim();

    if (!cleanEmail || !cleanEmail.includes('@')) {
        return { success: false, error: 'Lütfen geçerli bir e-posta adresi giriniz.' };
    }
    if (!cleanPass || cleanPass.length < 8) {
        return { success: false, error: 'Şifreniz en az 8 karakterden oluşmalıdır.' };
    }
    if (!cleanName) {
        return { success: false, error: 'Lütfen ad ve soyadınızı giriniz.' };
    }
    if (!supabaseClient) {
        return { success: false, error: 'Sunucuya bağlanılamadı. Lütfen daha sonra tekrar deneyin.' };
    }

    const { data, error } = await supabaseClient.auth.signUp({
        email: cleanEmail,
        password: cleanPass,
        options: { data: { name: cleanName } }
    });

    if (error) {
        return { success: false, error: error.message || 'Kayıt başarısız oldu.' };
    }

    return { success: true, user: data.user, needsConfirmation: !data.session };
}

// 2. Giriş (Sign In) — gerçek Supabase Auth oturumu açar
async function authenticateUser(identifier, password) {
    const cleanEmail = (identifier || '').trim().toLowerCase();
    const cleanPass = (password || '').trim();

    if (!supabaseClient) {
        return { success: false, error: 'Sunucuya bağlanılamadı. Lütfen daha sonra tekrar deneyin.' };
    }

    const { data, error } = await supabaseClient.auth.signInWithPassword({
        email: cleanEmail,
        password: cleanPass
    });

    if (error) {
        return { success: false, error: 'E-posta veya şifre hatalı. Lütfen kontrol ediniz.' };
    }

    const user = await buildUserProfile(data.user.id, data.user.email);
    return { success: true, user };
}

// 3. Profiles tablosundan rol/isim bilgisini çek
async function buildUserProfile(userId, email) {
    let role = 'user';
    let name = email;
    let title = 'Ekip Üyesi';
    let customerId = null;

    if (supabaseClient) {
        try {
            const { data } = await supabaseClient.from('profiles').select('*').eq('id', userId).maybeSingle();
            if (data) {
                role = data.role || role;
                name = data.name || name;
                title = data.title || title;
                customerId = data.customer_id || null;
            }
        } catch (e) {}
    }

    return { id: userId, email, name, role, title, customerId };
}

// 4. Aktif oturumu getir
async function getCurrentUser() {
    if (!supabaseClient) return null;
    try {
        const { data } = await supabaseClient.auth.getSession();
        const session = data?.session;
        if (!session) return null;
        return await buildUserProfile(session.user.id, session.user.email);
    } catch (e) {
        return null;
    }
}

// 5. Çıkış
function handleSignOut() {
    if (supabaseClient) {
        supabaseClient.auth.signOut().finally(() => { window.location.href = 'login.html'; });
    } else {
        window.location.href = 'login.html';
    }
}

// 6. Sayfa Koruma & Rol Kontrolü
async function guardProtectedPage(requiredRole = null) {
    const user = await getCurrentUser();
    if (!user) {
        window.location.href = 'login.html';
        return false;
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

// 7. Supabase Sağlık Kontrolü
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
