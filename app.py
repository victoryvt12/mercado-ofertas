import os
import secrets
import hashlib
import base64
import requests

from flask import Flask, redirect, request, session

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY")

ML_CLIENT_ID = os.environ.get("ML_CLIENT_ID")
ML_CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET")

REDIRECT_URI = "https://mercado-ofertas.onrender.com/oauth/mercadolibre/callback"


@app.route("/")
def home():

    access_token = session.get("access_token")
    ml_user_id = session.get("ml_user_id")

    connected = False
    nickname = None

    if access_token:

        try:
            me_response = requests.get(
                "https://api.mercadolibre.com/users/me",
                headers={
                    "Authorization": f"Bearer {access_token}"
                },
                timeout=10
            )

            if me_response.status_code == 200:
                connected = True
                user_data = me_response.json()
                nickname = user_data.get("nickname")

        except requests.RequestException:
            connected = False

    if connected:

        connection_status = """
        <div style="
            background:#e8f7ed;
            border:1px solid #8bd5a5;
            padding:20px;
            border-radius:12px;
            margin-top:20px;
        ">
            <h2 style="color:#187a3d;">🟢 Mercado Libre conectado</h2>
            <p>La conexión con tu cuenta de Mercado Libre está funcionando correctamente.</p>
        """

        if nickname:
            connection_status += f"""
            <p><strong>Cuenta:</strong> {nickname}</p>
            """

        connection_status += """
        </div>
        """

        action_button = """
        <p style="margin-top:20px;">
            <a href="/login/mercadolibre"
               style="
                    display:inline-block;
                    padding:12px 20px;
                    background:#3483fa;
                    color:white;
                    text-decoration:none;
                    border-radius:8px;
               ">
                Reconectar Mercado Libre
            </a>
        </p>

        <p style="margin-top:15px;">
            <a href="/probar-mas-vendidos"
               style="
                    display:inline-block;
                    padding:12px 20px;
                    background:#39a900;
                    color:white;
                    text-decoration:none;
                    border-radius:8px;
               ">
                🛒 Probar Más vendidos
            </a>
        </p>
        """

    else:

        connection_status = """
        <div style="
            background:#fff0f0;
            border:1px solid #e0a0a0;
            padding:20px;
            border-radius:12px;
            margin-top:20px;
        ">
            <h2 style="color:#b42318;">🔴 Mercado Libre necesita reconexión</h2>
            <p>
                La aplicación no tiene una conexión activa con Mercado Libre.
            </p>
            <p>
                Pulsa el botón para volver a autorizar la conexión.
            </p>
        </div>
        """

        action_button = """
        <p style="margin-top:20px;">
            <a href="/login/mercadolibre"
               style="
                    display:inline-block;
                    padding:12px 20px;
                    background:#3483fa;
                    color:white;
                    text-decoration:none;
                    border-radius:8px;
               ">
                Conectar Mercado Libre
            </a>
        </p>
        """

    return f"""
    <!DOCTYPE html>

    <html lang="es">

    <head>

        <meta charset="UTF-8">

        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">

        <title>Mercado Ofertas</title>

    </head>

    <body style="
        font-family:Arial, sans-serif;
        max-width:700px;
        margin:60px auto;
        padding:20px;
        color:#333;
    ">

        <h1>🛍️ Mercado Ofertas</h1>

        <p>
            Panel de control de la automatización de ofertas.
        </p>

        {connection_status}

        {action_button}

        <hr style="margin-top:40px;">

        <p style="color:#777;">
            Próximamente aquí aparecerán las ofertas detectadas,
            enlaces de afiliado y publicaciones.
        </p>

    </body>

    </html>
    """


@app.route("/health")
def health():
    return "OK"


@app.route("/probar-mas-vendidos")
def probar_mas_vendidos():

    access_token = session.get("access_token")

    if not access_token:
        return """
        <h2>🔴 Mercado Libre no está conectado</h2>
        <p>Primero debes conectar tu cuenta.</p>
        <p><a href="/">← Volver al panel</a></p>
        """, 401

    # Categoría de prueba:
    # MLB = Brasil / categoría de ejemplo.
    # Más adelante utilizaremos las categorías de México (MLM)
    # automáticamente.

    url = "https://api.mercadolibre.com/trends/MLM"

    try:

        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            timeout=30
        )

    except requests.RequestException as error:

        return f"""
        <h2>❌ Error de conexión</h2>
        <p>{error}</p>
        <p><a href="/">← Volver al panel</a></p>
        """, 500

    if response.status_code != 200:

        return f"""
        <h2>❌ Mercado Libre rechazó la consulta</h2>

        <p>
            <strong>Código HTTP:</strong>
            {response.status_code}
        </p>

        <p>
            <strong>Respuesta:</strong>
        </p>

        <pre>{response.text}</pre>

        <p>
            <a href="/">← Volver al panel</a>
        </p>
        """, 400

    data = response.json()

    products = data.get("content", [])

    html_products = ""

    for product in products:

        product_id = product.get("id", "Sin ID")
        position = product.get("position", "Sin posición")
        product_type = product.get("type", "Sin tipo")

        html_products += f"""
        <li style="margin-bottom:15px;">
            <strong>#{position}</strong>
            — ID: {product_id}
            — Tipo: {product_type}
        </li>
        """

    return f"""
    <!DOCTYPE html>

    <html lang="es">

    <head>
        <meta charset="UTF-8">
        <title>Más vendidos</title>
    </head>

    <body style="
        font-family:Arial, sans-serif;
        max-width:800px;
        margin:50px auto;
        padding:20px;
    ">

        <h1>🛒 Más vendidos</h1>

        <p>
            Mercado Libre respondió correctamente.
        </p>

        <p>
            <strong>Categoría consultada:</strong> {category_id}
        </p>

        <p>
            <strong>Productos recibidos:</strong> {len(products)}
        </p>

        <hr>

        <ol>
            {html_products}
        </ol>

        <p style="margin-top:30px;">
            <a href="/">← Volver al panel</a>
        </p>

    </body>

    </html>
    """


@app.route("/login/mercadolibre")
def login_mercadolibre():

    state = secrets.token_urlsafe(32)

    code_verifier = secrets.token_urlsafe(64)

    digest = hashlib.sha256(
        code_verifier.encode("utf-8")
    ).digest()

    code_challenge = base64.urlsafe_b64encode(
        digest
    ).decode("utf-8").rstrip("=")

    session["oauth_state"] = state
    session["code_verifier"] = code_verifier

    authorization_url = (
        "https://auth.mercadolibre.com.mx/authorization"
        f"?response_type=code"
        f"&client_id={ML_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    return redirect(authorization_url)


@app.route("/oauth/mercadolibre/callback")
def mercadolibre_callback():

    error = request.args.get("error")

    if error:
        return f"""
        <h2>Error de autorización</h2>
        <p>{error}</p>
        <p>
            <a href="/">Volver a Mercado Ofertas</a>
        </p>
        """, 400

    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        return "No se recibió código de autorización.", 400

    if not state or state != session.get("oauth_state"):
        return "Error de seguridad: state inválido.", 400

    code_verifier = session.get("code_verifier")

    if not code_verifier:
        return "No se encontró el code_verifier de PKCE.", 400

    token_response = requests.post(
        "https://api.mercadolibre.com/oauth/token",
        headers={
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded"
        },
        data={
            "grant_type": "authorization_code",
            "client_id": ML_CLIENT_ID,
            "client_secret": ML_CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier
        },
        timeout=30
    )

    if token_response.status_code != 200:

        return f"""
        <h2>❌ Error al obtener el token</h2>

        <p>
            Mercado Libre rechazó el intercambio de autorización.
        </p>

        <p>
            Código HTTP: {token_response.status_code}
        </p>

        <p>
            <a href="/">Volver a Mercado Ofertas</a>
        </p>
        """, 400

    token_data = token_response.json()

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    user_id = token_data.get("user_id")

    if not access_token:

        return """
        <h2>❌ Mercado Libre no devolvió un Access Token.</h2>
        <p>
            <a href="/">Volver a Mercado Ofertas</a>
        </p>
        """, 400

    session["access_token"] = access_token
    session["refresh_token"] = refresh_token
    session["ml_user_id"] = user_id

    me_response = requests.get(
        "https://api.mercadolibre.com/users/me",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        timeout=30
    )

    if me_response.status_code != 200:

        return """
        <h2>⚠️ Token obtenido, pero falló la prueba de API.</h2>
        <p>
            <a href="/">Volver a Mercado Ofertas</a>
        </p>
        """, 400

    user_data = me_response.json()

    nickname = user_data.get(
        "nickname",
        "No disponible"
    )

    site_id = user_data.get(
        "site_id",
        "No disponible"
    )

    return f"""
    <!DOCTYPE html>

    <html lang="es">

    <head>
        <meta charset="UTF-8">
        <title>Mercado Ofertas</title>
    </head>

    <body style="
        font-family:Arial, sans-serif;
        max-width:700px;
        margin:60px auto;
        padding:20px;
    ">

        <div style="
            background:#e8f7ed;
            border:1px solid #8bd5a5;
            padding:25px;
            border-radius:12px;
        ">

            <h2 style="color:#187a3d;">
                🟢 ¡Mercado Libre conectado correctamente!
            </h2>

            <p>
                La API de Mercado Libre respondió correctamente.
            </p>

            <p>
                <strong>Cuenta:</strong> {nickname}
            </p>

            <p>
                <strong>User ID:</strong> {user_id}
            </p>

            <p>
                <strong>Site:</strong> {site_id}
            </p>

            <p>
                <strong>Access Token:</strong>
                obtenido correctamente.
            </p>

        </div>

        <p style="margin-top:25px;">
            <a href="/">← Volver al panel</a>
        </p>

    </body>

    </html>
    """


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
