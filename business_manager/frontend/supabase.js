// AI Manager — Supabase Client & Hibrit Veri Katmanı
const SUPABASE_URL = 'https://jxfllwlngrjctjhclwzj.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_2zas0AHgplp6PhaEzAPdnQ_c-LXgjeg';

let supabaseClient = null;
try {
    if (window.supabase && typeof window.supabase.createClient === 'function') {
        supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    }
} catch (e) {
    console.warn('[AI Manager] Supabase SDK yuklenemedi veya baslatilamadi:', e);
}

// Test/Demo giris kontrolu (admin bypass destekli)
async function guardProtectedPage() {
    if (sessionStorage.getItem('ai_manager_demo_admin') !== '1') {
        window.location.href = 'login.html';
        return false;
    }
    document.documentElement.classList.remove('auth-pending');
    if (document.body) document.body.classList.remove('auth-pending');
    return true;
}

function handleSignOut() {
    sessionStorage.removeItem('ai_manager_demo_admin');
    window.location.href = 'login.html';
}

// Supabase durumunu kontrol et
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
