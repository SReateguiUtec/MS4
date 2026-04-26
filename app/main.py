import json
from datetime import datetime, timedelta
from openai import OpenAI
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

ms2_url = os.getenv('MS2_URL', 'http://localhost:5002')
ms3_url = os.getenv('MS3_URL', 'http://localhost:5003')

openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
groq_api_key = os.getenv('GROQ_API_KEY', '').strip()
groq_model = os.getenv('GROQ_MODEL').strip()

# OpenRouter → Señales IA (`generar_recomendacion`)
ai_client = None
if openrouter_api_key and openrouter_api_key != 'your_openrouter_api_key':
    ai_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_api_key,
    )

# Groq → FinBot (`/api/chat`), API compatible con OpenAI
groq_client = None
if groq_api_key:
    groq_client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=groq_api_key,
    )

def analizar_sentimiento(simbolo):
    try:
        response = requests.get(f"{ms3_url}/api/noticias/{simbolo}/sentimiento", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def obtener_precios(simbolo):
    try:
        fin = datetime.now()
        inicio = fin - timedelta(days=15)
        fin_str = fin.strftime("%Y-%m-%dT%H:%M:%S")
        inicio_str = inicio.strftime("%Y-%m-%dT%H:%M:%S")
        
        response = requests.get(f"{ms2_url}/api/precios/{simbolo}/range?inicio={inicio_str}&fin={fin_str}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            data.sort(key=lambda x: x['fecha'], reverse=True)
            return data
        return []
    except Exception as e:
        print(f"Error obteniendo precios: {e}")
        return []


def generar_recomendacion(simbolo, precios, sentimiento_data):
    if not precios or not sentimiento_data:
        return {
            'senal': 'Sin datos suficientes',
            'confianza': 0,
            'mensaje': 'No hay datos para generar una recomendación'
        }

    sentimiento = sentimiento_data.get('sentimiento', 'Neutral')
    precio_actual = precios[0].get('close') if precios else None
    precio_anterior = precios[1].get('close') if len(precios) > 1 else None
    
    variacion = 0
    if precio_actual and precio_anterior:
        variacion = ((precio_actual - precio_anterior) / precio_anterior) * 100

    if ai_client:
        try:
            precios_resumen = [{"fecha": p["fecha"].split("T")[0], "close": p["close"]} for p in precios[:10]]
            prompt = f"""
Eres un analista financiero experto. Analiza estos datos recientes de {simbolo}.
Tendencia de sentimiento de noticias: {sentimiento}
Últimos precios de cierre (más reciente primero): {precios_resumen}
Variación del último día: {variacion:.2f}%

Con esta información, decide si la recomendación debe ser 'Compra', 'Venta' o 'Mantener'.
Responde ESTRICTAMENTE con un objeto JSON que contenga estas 3 llaves:
- "senal": Solo puede ser "Compra", "Venta" o "Mantener"
- "confianza": Un número entero del 0 al 100 indicando tu nivel de seguridad
- "mensaje": Una justificación en 1 oración (máximo 15 palabras)

No devuelvas Markdown (como ```json), solo el JSON puro.
"""
            response = ai_client.chat.completions.create(
                model="openrouter/free",
                messages=[{"role": "user", "content": prompt}],
            )
            texto = response.choices[0].message.content.strip()
            if texto.startswith("```json"): texto = texto[7:]
            if texto.startswith("```"): texto = texto[3:]
            if texto.endswith("```"): texto = texto[:-3]
                
            resultado_ia = json.loads(texto.strip())
            return {
                'senal': resultado_ia.get('senal', 'Mantener'),
                'confianza': int(resultado_ia.get('confianza', 50)),
                'mensaje': resultado_ia.get('mensaje', 'Análisis generado por IA'),
                'sentimiento': sentimiento,
                'variacion_precio': round(variacion, 2)
            }
        except Exception as e:
            print(f"Error Gemini: {e}")

    # Fallback matemático
    confianza = 50
    senal = 'Mantener'
    mensaje = ''

    if sentimiento == 'Bullish':
        if variacion > 0:
            senal = 'Compra'
            confianza = min(95, 60 + variacion * 5)
            mensaje = f'Noticias optimistas y tendencia alcista confirmada (+{variacion:.2f}%)'
        else:
            senal = 'Mantener'
            confianza = max(40, 50 + variacion)
            mensaje = f'Noticias optimistas, pero el precio está retrocediendo ({variacion:.2f}%)'
            
    elif sentimiento == 'Bearish':
        if variacion < 0:
            senal = 'Venta'
            confianza = min(95, 60 + abs(variacion) * 5)
            mensaje = f'Noticias pesimistas y caída confirmada del precio ({variacion:.2f}%)'
        else:
            senal = 'Mantener'
            confianza = max(40, 50 - variacion)
            mensaje = f'Noticias pesimistas, pero el mercado resiste (+{variacion:.2f}%)'
            
    else: # Neutral
        if variacion > 1.5:
            senal = 'Compra'
            confianza = min(85, 50 + variacion * 4)
            mensaje = f'Fuerte impulso alcista (+{variacion:.2f}%) pese a falta de noticias'
        elif variacion < -1.5:
            senal = 'Venta'
            confianza = min(85, 50 + abs(variacion) * 4)
            mensaje = f'Corrección bajista evidente ({variacion:.2f}%) en entorno neutral'
        else:
            senal = 'Mantener'
            # Le damos una variación matemática leve para que no sea siempre 50% clavado
            confianza = min(60, 50 + abs(variacion) * 2)
            mensaje = f'Mercado lateralizado ({variacion:.2f}%), sin catalizadores claros'

    return {
        'senal': senal,
        'confianza': round(confianza, 2),
        'mensaje': mensaje,
        'sentimiento': sentimiento,
        'variacion_precio': round(variacion, 2)
    }


@app.route('/api/senales/<simbolo>', methods=['GET'])
def get_senal(simbolo):
    sentimiento_data = analizar_sentimiento(simbolo)
    precios = obtener_precios(simbolo)
    
    recomendacion = generar_recomendacion(simbolo, precios, sentimiento_data)
        
    return jsonify({
        'simbolo': simbolo,
        'precios_disponibles': len(precios),
        **recomendacion
    })


@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json()
    if not data:
        return jsonify({"mensaje": "No se recibieron datos"}), 400
        
    mensajes = data.get('messages', [])
    contexto = data.get('contexto', {})
    
    chat_client = groq_client or ai_client
    if not chat_client:
        return jsonify({
            "mensaje": (
                "La Inteligencia Artificial no está configurada en MS4. "
                "Configura GROQ_API_KEY (FinBot) u OPENROUTER_API_KEY (alternativa de chat)."
            ),
        }), 200

    try:
        ultimo_mensaje = mensajes[-1]['text'] if mensajes and mensajes[-1]['role'] == 'user' else ''
        
        # Inyección de datos en tiempo real para símbolos conocidos
        empresas_comunes = {
            'nvidia': 'NVDA', 'nvda': 'NVDA',
            'apple': 'AAPL', 'aapl': 'AAPL',
            'microsoft': 'MSFT', 'msft': 'MSFT',
            'tesla': 'TSLA', 'tsla': 'TSLA',
            'google': 'GOOGL', 'googl': 'GOOGL',
            'amazon': 'AMZN', 'amzn': 'AMZN',
            'meta': 'META', 'facebook': 'META',
            'netflix': 'NFLX', 'nflx': 'NFLX'
        }
        
        datos_extra = ""
        mensaje_lower = ultimo_mensaje.lower()
        simbolos_detectados = set()
        for nombre, ticker in empresas_comunes.items():
            # buscamos si el nombre o ticker está en el mensaje
            # agregamos padding para evitar detectar "meta" dentro de "metamorfosis"
            if f" {nombre} " in f" {mensaje_lower} " or f" {ticker.lower()} " in f" {mensaje_lower} ":
                simbolos_detectados.add(ticker)
                
        if simbolos_detectados:
            datos_extra = "\nDatos financieros extraídos en tiempo real para tu respuesta:\n"
            for ticker in simbolos_detectados:
                try:
                    sent_data = analizar_sentimiento(ticker)
                    precios = obtener_precios(ticker)
                    if precios:
                        precio_actual = precios[0].get('close', 0)
                        datos_extra += f"- {ticker}: Precio actual ${precio_actual}. Sentimiento: {sent_data.get('sentimiento', 'Neutral')}.\n"
                except:
                    pass
        
        historial_str = ""
        for m in mensajes[:-1]:
            historial_str += f"{m['role'].upper()}: {m['text']}\n"
            
        contexto_str = json.dumps(contexto, ensure_ascii=False) if contexto else "Sin contexto específico."
        
        prompt = f"""
Eres Finbot, el asistente financiero inteligente de la plataforma FinTrend.
Tienes un tono profesional, experto, accesible y conciso.

Contexto actual del usuario (sus portafolios guardados):
{contexto_str}
{datos_extra}
Historial de conversación:
{historial_str}

Usuario pregunta:
{ultimo_mensaje}

Responde directamente a la pregunta del usuario usando formato Markdown. No envíes JSON, solo texto Markdown bien formateado, corto y muy útil. Si te preguntan por recomendaciones o análisis, usa el contexto proporcionado.
"""
        if groq_client:
            response = groq_client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": prompt}],
            )
        else:
            response = ai_client.chat.completions.create(
                model="openrouter/free",
                messages=[{"role": "user", "content": prompt}],
            )
        return jsonify({"mensaje": response.choices[0].message.content.strip()})
        
    except Exception as e:
        print(f"Error en chat: {e}")
        return jsonify({"mensaje": "Hubo un error al procesar tu solicitud con la IA."}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004, debug=True)