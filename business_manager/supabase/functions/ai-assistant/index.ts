// Sanal CEO — Groq proxy. Anahtar burada, Supabase secret store'undan okunur;
// hiçbir zaman frontend koduna veya git'e yazılmaz.
const GROQ_API_KEY = Deno.env.get('GROQ_API_KEY');
const GROQ_MODEL = 'openai/gpt-oss-120b';

const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

Deno.serve(async (req: Request) => {
    if (req.method === 'OPTIONS') {
        return new Response('ok', { headers: corsHeaders });
    }

    if (!GROQ_API_KEY) {
        return new Response(JSON.stringify({ error: { message: 'GROQ_API_KEY secret tanımlı değil.' } }), {
            status: 500,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
    }

    try {
        const { messages } = await req.json();
        if (!Array.isArray(messages) || messages.length === 0) {
            return new Response(JSON.stringify({ error: { message: 'messages dizisi gerekli.' } }), {
                status: 400,
                headers: { ...corsHeaders, 'Content-Type': 'application/json' },
            });
        }

        const groqRes = await fetch('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${GROQ_API_KEY}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: GROQ_MODEL,
                messages,
                temperature: 0.7,
            }),
        });

        const data = await groqRes.json();
        return new Response(JSON.stringify(data), {
            status: groqRes.status,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
    } catch (err) {
        return new Response(JSON.stringify({ error: { message: String(err) } } ), {
            status: 500,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
    }
});
