// AI Manager — Supabase Gerçek Auth & Rol Yönetimi
// localStorage kullanıcı deposu YOK — tüm auth Supabase üzerinden

const SUPABASE_URL = 'https://jxfllwlngrjctjhclwzj.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_2zas0AHgplp6PhaEzAPdnQ_c-LXgjeg';

let supabaseClient = null;
try {
    if (typeof window !== 'undefined' && window.supabase && typeof window.supabase.createClient === 'function') {
        supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
            auth: {
                persistSession: true,
                autoRefreshToken: true,
                detectSessionInUrl: true
            }
        });
    }
} catch (e) {
    console.warn('[AI Manager] Supabase SDK yüklenemedi:', e);
}

// ================================================================
// 1. KULLANICI KAYDI (Sign Up)
// ================================================================
async function registerUser({ email, password, name, role = 'user', title = '', customerId = null }) {
    const cleanEmail = (email || '').trim().toLowerCase();
    const cleanPass  = (password || '').trim();
    const cleanName  = (name || '').trim();

    if (!cleanEmail || !cleanEmail.includes('@'))
        return { success: false, error: 'Lütfen geçerli bir e-posta adresi giriniz.' };
    if (!cleanPass || cleanPass.length < 8)
        return { success: false, error: 'Şifreniz en az 8 karakterden oluşmalıdır.' };
    if (!cleanName)
        return { success: false, error: 'Lütfen ad ve soyadınızı giriniz.' };

    if (!supabaseClient)
        return { success: false, error: 'Bağlantı hatası: Supabase yüklenemedi. Lütfen sayfayı yenileyin.' };

    // Rol: kayıt formu her zaman 'user' oluşturur.
    // Admin yetkisi Supabase Dashboard'dan verilir.
    const safeRole  = 'user';
    const safeTitle = title || 'Ekip Üyesi';

    const { data, error } = await supabaseClient.auth.signUp({
        email: cleanEmail,
        password: cleanPass,
        options: {
            data: {
                name: cleanName,
                role: safeRole,
                title: safeTitle,
                customer_id: customerId || null
            }
        }
    });

    if (error) {
        let msg = error.message || 'Kayıt başarısız.';
        if (msg.includes('already registered') || msg.includes('already exists'))
            msg = 'Bu e-posta adresi ile kayıtlı bir hesap zaten mevcut.';
        if (msg.includes('Password'))
            msg = 'Şifreniz en az 8 karakter olmalıdır.';
        return { success: false, error: msg };
    }

    // Profil trigger zaten oluşturacak; yine de user objesini döndür
    const user = {
        id: data.user?.id,
        email: cleanEmail,
        name: cleanName,
        role: safeRole,
        title: safeTitle,
        customerId: null
    };
    return { success: true, user, needsConfirmation: !data.session };
}

// ================================================================
// 2. KULLANICI GİRİŞİ (Sign In)
// ================================================================
async function authenticateUser(identifier, password) {
    const idClean   = (identifier || '').trim().toLowerCase();
    const passClean = (password   || '').trim();

    if (!idClean)   return { success: false, error: 'E-posta adresinizi giriniz.' };
    if (!passClean) return { success: false, error: 'Şifrenizi giriniz.' };

    if (!supabaseClient)
        return { success: false, error: 'Bağlantı hatası: Supabase yüklenemedi.' };

    // E-posta formatında değilse hata ver (username bypass kaldırıldı)
    const emailToUse = idClean.includes('@') ? idClean : null;
    if (!emailToUse)
        return { success: false, error: 'Lütfen e-posta adresi formatında giriş yapınız.' };

    const { data, error } = await supabaseClient.auth.signInWithPassword({
        email: emailToUse,
        password: passClean
    });

    if (error) {
        let msg = error.message || 'Giriş başarısız.';
        if (msg.includes('Invalid login') || msg.includes('invalid_credentials'))
            msg = 'E-posta veya şifre hatalı. Lütfen kontrol ediniz.';
        if (msg.includes('Email not confirmed'))
            msg = 'E-posta adresinizi onaylamanız gerekiyor. Lütfen gelen kutunuzu kontrol edin.';
        return { success: false, error: msg };
    }

    // Profil bilgisini çek
    const profile = await _fetchProfile(data.user.id);
    const user = {
        id: data.user.id,
        email: data.user.email,
        name: profile?.name || data.user.user_metadata?.name || data.user.email,
        role: profile?.role || 'user',
        title: profile?.title || 'Ekip Üyesi',
        customerId: profile?.customer_id || null
    };

    return { success: true, user };
}

// ================================================================
// 3. OTURUM OKUMA
// ================================================================
async function getCurrentUser() {
    if (!supabaseClient) return null;

    try {
        const { data: { session }, error } = await supabaseClient.auth.getSession();
        if (error || !session) return null;

        const profile = await _fetchProfile(session.user.id);
        return {
            id: session.user.id,
            email: session.user.email,
            name: profile?.name || session.user.user_metadata?.name || session.user.email,
            role: profile?.role || session.user.user_metadata?.role || 'user',
            title: profile?.title || session.user.user_metadata?.title || 'Ekip Üyesi',
            customerId: profile?.customer_id || null
        };
    } catch (e) {
        return null;
    }
}

// Senkron fallback — sayfadaki gösterim amaçlı (yükleme sırasında)
function getCurrentUserSync() {
    try {
        const raw = sessionStorage.getItem('ai_manager_cached_user');
        if (raw) return JSON.parse(raw);
    } catch (e) {}
    return null;
}

// ================================================================
// 4. ÇIKIŞ
// ================================================================
async function handleSignOut() {
    if (supabaseClient) {
        await supabaseClient.auth.signOut();
    }
    sessionStorage.removeItem('ai_manager_cached_user');
    window.location.href = 'login.html';
}

// ================================================================
// 5. SAYFA KORUMA & ROL KONTROLÜ (gerçek redirect)
// ================================================================
async function guardProtectedPage(requiredRole = null) {
    const user = await getCurrentUser();

    if (!user) {
        // Oturum yok → login sayfasına yönlendir, bypass yok
        if (!window.location.pathname.includes('login.html')) {
            window.location.href = 'login.html';
        }
        return false;
    }

    // Kullanıcı bilgisini session cache'e yaz (senkron gösterim için)
    sessionStorage.setItem('ai_manager_cached_user', JSON.stringify(user));

    // Client rolündeyse portal'a yönlendir
    if (user.role === 'client' && !window.location.pathname.includes('portal.html')) {
        window.location.href = 'portal.html' + (user.customerId ? `?cid=${encodeURIComponent(user.customerId)}` : '');
        return false;
    }

    // Yeterli rol yoksa ana sayfaya
    if (requiredRole && user.role !== requiredRole && user.role !== 'admin') {
        alert('Bu sayfaya erişim için yönetici yetkisi gereklidir.');
        window.location.href = 'index.html';
        return false;
    }

    document.documentElement.classList.remove('auth-pending');
    if (document.body) document.body.classList.remove('auth-pending');
    return true;
}

// ================================================================
// 6. YARDIMCI — Profil çekme
// ================================================================
async function _fetchProfile(userId) {
    if (!supabaseClient || !userId) return null;
    try {
        const { data, error } = await supabaseClient
            .from('profiles')
            .select('name, role, title, customer_id')
            .eq('id', userId)
            .single();
        if (error) return null;
        return data;
    } catch (e) {
        return null;
    }
}

// ================================================================
// 7. Supabase bağlantı durumu
// ================================================================
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

// ================================================================
// 8. Supabase client'ı dışa aç (app.js için)
// ================================================================
function getSupabaseClient() {
    return supabaseClient;
}
