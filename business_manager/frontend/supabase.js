// AI Manager — Supabase Client Config
// Bu dosyayı frontend/ klasöründe tut
// SUPABASE_ANON_KEY güvenlidir, frontend'de kullanılabilir
// SERVICE_ROLE_KEY asla buraya konulmamalı!

const SUPABASE_URL = 'https://jxfllwlngrjctjhclwzj.supabase.co'
const SUPABASE_ANON_KEY = 'sb_publishable_2zas0AHgplp6PhaEzAPdnQ_c-LXgjeg'

// Supabase client oluştur
const { createClient } = window.supabase
const supabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

// Auth helper: giriş kontrolü
async function requireAuth() {
    const { data: { session } } = await supabaseClient.auth.getSession()
    if (!session) {
        window.location.href = '/login.html'
        return null
    }
    return session
}

// Auth helper: çıkış
async function signOut() {
    await supabaseClient.auth.signOut()
    window.location.href = '/login.html'
}
