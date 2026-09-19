// Test sitesi: bağımsız CRM ve Marketing sayfaları için demo giriş kontrolü.
async function guardProtectedPage() {
    if (sessionStorage.getItem('ai_manager_demo_admin') !== '1') {
        window.location.href = '/login.html'
        return false
    }
    document.documentElement.classList.remove('auth-pending')
    document.body.classList.remove('auth-pending')
    return true
}
