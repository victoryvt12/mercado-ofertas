import os
import secrets
import hashlib
import base64
import re
from html import escape
from urllib.parse import urlencode, urlparse

import requests
from flask import Flask, redirect, request, session


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

ML_CLIENT_ID = os.environ.get("ML_CLIENT_ID")
ML_CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET")

ML_AFFILIATE_COOKIE = os.environ.get("ML_AFFILIATE_COOKIE")
ML_AFFILIATE_CSRF = os.environ.get("ML_AFFILIATE_CSRF")
ML_AFFILIATE_TAG = os.environ.get("ML_AFFILIATE_TAG", "divi70685")

REDIRECT_URI = (
    "https://mercado-ofertas.onrender.com/"
    "oauth/mercadolibre/callback"
)


# --------------------------------------------------
# GENERAR ENLACES DE AFILIADO
# --------------------------------------------------

def create_affiliate_link(product_url):
    if not ML_AFFILIATE_COOKIE or not ML_AFFILIATE_CSRF:
        raise RuntimeError(
            "Faltan las credenciales del generador de afiliados."
        )

    parsed = urlparse(product_url)

    if parsed.scheme != "https" or parsed.hostname not in (
        "mercadolibre.com.mx",
        "www.mercadolibre.com.mx",
        "meli.la",
    ):
        raise ValueError(
            "Pega una URL HTTPS válida de Mercado Libre México."
        )

    response = requests.post(
        "https://www.mercadolibre.com.mx/"
        "affiliate-program/api/v2/affiliates/createLink",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://www.mercadolibre.com.mx",
            "Referer": (
                "https://www.mercadolibre.com.mx/"
                "afiliados/linkbuilder"
            ),
            "User-Agent": "Mozilla/5.0",
            "x-csrf-token": ML_AFFILIATE_CSRF,
            "Cookie": ML_AFFILIATE_COOKIE,
        },
        json={
            "urls": [product_url],
            "tag": ML_AFFILIATE_TAG,
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Mercado Libre respondió con HTTP "
            f"{response.status_code}: {response.text}"
        )

    data = response.json()

    if not data.get("urls"):
        raise RuntimeError(
            f"Mercado Libre no devolvió un enlace: {data}"
        )

    return data["urls"][0]["short_url"]


# --------------------------------------------------
# PANEL PRINCIPAL
# --------------------------------------------------

@app.route("/")
def home():
    access_token = session.get("access_token")
    connected = False
    nickname = None

    if access_token:
        try:
            response = requests.get(
                "https://api.mercadolibre.com/users/me",
                headers={
                    "Authorization": f"Bearer {access_token}"
                },
                timeout=10,
            )

            if response.status_code == 200:
                connected = True
                nickname = response.json().get("nickname")

        except requests.RequestException:
            connected = False

    if connected:
        status = (
            "<h2 style='color:green'>"
            "Mercado Libre conectado</h2>"
            "<p>La conexión con tu cuenta funciona.</p>"
        )

        if nickname:
            status += f"<p>Cuenta: {escape(nickname)}</p>"

        button_text = "Reconectar Mercado Libre"

    else:
        status = (
            "<h2 style='color:#b42318'>"
            "Mercado Libre necesita conexión</h2>"
            "<p>Conecta o autoriza de nuevo tu cuenta.</p>"
        )

        button_text = "Conectar Mercado Libre"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">
        <title>Mercado Ofertas</title>
    </head>
    <body style="font-family:Arial;max-width:700px;
                 margin:50px auto;padding:20px;color:#333">
        <h1>Mercado Ofertas</h1>
        <p>Panel de control de la automatización de ofertas.</p>

        {status}

        <p>
            <a href="/login/mercadolibre">
                {button_text}
            </a>
        </p>

        <hr>
        <h3>Herramientas de prueba</h3>
        <ul>
            <li><a href="/probar-ofertas">Probar acceso a ofertas</a></li>
            <li><a href="/inspeccionar-ofertas">
                Inspeccionar ofertas</a></li>
            <li><a href="/probar-afiliado">
                Generar enlace de afiliado</a></li>
            <li><a href="/probar-mas-vendidos">
                Probar más vendidos</a></li>
            <li><a href="/probar-link-afiliado">
                Probar consulta de producto por API</a></li>
        </ul>
    </body>
    </html>
    """


@app.route("/health")
def health():
    return "OK"


# --------------------------------------------------
# PRUEBA DE MÁS VENDIDOS
# --------------------------------------------------

@app.route("/probar-mas-vendidos")
def probar_mas_vendidos():
    access_token = session.get("access_token")

    if not access_token:
        return (
            '<h2>Mercado Libre no está conectado</h2>'
            '<p><a href="/">Volver al panel</a></p>'
        ), 401

    url = "https://api.mercadolibre.com/trends/MLM"

    try:
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            timeout=30,
        )

    except requests.RequestException as error:
        return f"<h2>Error de conexión</h2><p>{escape(str(error))}</p>", 500

    if response.status_code != 200:
        return f"""
        <h2>Mercado Libre rechazó la consulta</h2>
        <p>Código HTTP: {response.status_code}</p>
        <pre>{escape(response.text)}</pre>
        <p><a href="/">Volver al panel</a></p>
        """, response.status_code

    data = response.json()
    products = data.get("content", [])

    html_products = ""

    for product in products:
        html_products += (
            "<li>"
            f"ID: {escape(str(product.get('id', 'Sin ID')))} — "
            f"Posición: {escape(str(product.get('position', 'Sin posición')))}"
            "</li>"
        )

    return f"""
    <h1>Más vendidos</h1>
    <p>Categoría o sitio consultado: MLM</p>
    <p>Productos recibidos: {len(products)}</p>
    <ol>{html_products}</ol>
    <p><a href="/">Volver al panel</a></p>
    """


# --------------------------------------------------
# PRUEBA DE CONSULTA DE PRODUCTO POR API
# --------------------------------------------------

@app.route("/probar-link-afiliado")
def probar_link_afiliado():
    access_token = session.get("access_token")

    if not access_token:
        return (
            '<h2>Mercado Libre no está conectado</h2>'
            '<p><a href="/login/mercadolibre">Conectar</a></p>'
        ), 401

    item_id = "MLM25673801"

    try:
        response = requests.get(
            f"https://api.mercadolibre.com/items/{item_id}",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            timeout=30,
        )
    except requests.RequestException as error:
        return f"<p>{escape(str(error))}</p>", 500

    if response.status_code != 200:
        return f"""
        <h2>Error al consultar el producto</h2>
        <p>HTTP {response.status_code}</p>
        <pre>{escape(response.text)}</pre>
        <p><a href="/">Volver al panel</a></p>
        """, response.status_code

    data = response.json()

    return f"""
    <h1>Producto encontrado</h1>
    <p>ID: {escape(str(data.get('id')))}</p>
    <p>Título: {escape(str(data.get('title')))}</p>
    <p>Precio: ${escape(str(data.get('price')))}</p>
    <p><a href="/">Volver al panel</a></p>
    """


# --------------------------------------------------
# CONEXIÓN OAUTH CON MERCADO LIBRE
# --------------------------------------------------

@app.route("/login/mercadolibre")
def login_mercadolibre():
    if not ML_CLIENT_ID or not ML_CLIENT_SECRET:
        return "Faltan ML_CLIENT_ID o ML_CLIENT_SECRET en Render.", 500

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

    params = {
        "response_type": "code",
        "client_id": ML_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    authorization_url = (
        "https://auth.mercadolibre.com.mx/authorization?"
        + urlencode(params)
    )

    return redirect(authorization_url)


@app.route("/oauth/mercadolibre/callback")
def mercadolibre_callback():
    error = request.args.get("error")

    if error:
        return (
            f"<h2>Error de autorización</h2><p>{escape(error)}</p>"
            '<p><a href="/">Volver al panel</a></p>'
        ), 400

    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        return "No se recibió código de autorización.", 400

    if not state or state != session.get("oauth_state"):
        return "Error de seguridad: state inválido.", 400

    code_verifier = session.get("code_verifier")

    if not code_verifier:
        return "No se encontró el code_verifier de PKCE.", 400

    try:
        token_response = requests.post(
            "https://api.mercadolibre.com/oauth/token",
            headers={
                "accept": "application/json",
                "content-type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "client_id": ML_CLIENT_ID,
                "client_secret": ML_CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": code_verifier,
            },
            timeout=30,
        )
    except requests.RequestException as error:
        return f"Error de conexión: {escape(str(error))}", 500

    if token_response.status_code != 200:
        return f"""
        <h2>Error al obtener el token</h2>
        <p>Código HTTP: {token_response.status_code}</p>
        <pre>{escape(token_response.text)}</pre>
        <p><a href="/">Volver al panel</a></p>
        """, 400

    token_data = token_response.json()

    access_token = token_data.get("access_token")

    if not access_token:
        return "Mercado Libre no devolvió un Access Token.", 400

    session["access_token"] = access_token
    session["refresh_token"] = token_data.get("refresh_token")
    session["ml_user_id"] = token_data.get("user_id")

    try:
        me_response = requests.get(
            "https://api.mercadolibre.com/users/me",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            timeout=30,
        )
    except requests.RequestException as error:
        return f"Token obtenido, pero falló la consulta: {escape(str(error))}", 500

    if me_response.status_code != 200:
        return (
            "<h2>Token obtenido, pero falló la prueba de API.</h2>"
            '<p><a href="/">Volver al panel</a></p>'
        ), 400

    user_data = me_response.json()

    return f"""
    <h1>Mercado Libre conectado correctamente</h1>
    <p>Cuenta: {escape(str(user_data.get('nickname', 'No disponible')))}</p>
    <p>User ID: {escape(str(user_data.get('id', 'No disponible')))}</p>
    <p>Site: {escape(str(user_data.get('site_id', 'No disponible')))}</p>
    <p><a href="/">Volver al panel</a></p>
    """


# --------------------------------------------------
# PROBAR ACCESO A LA PÁGINA DE OFERTAS
# --------------------------------------------------

@app.route("/probar-ofertas")
def probar_ofertas():
    url = "https://www.mercadolibre.com.mx/ofertas"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        response.raise_for_status()

    except requests.RequestException as error:
        return f"""
        <h1>Error al consultar las ofertas</h1>
        <p>{escape(str(error))}</p>
        <p><a href="/">Volver al panel</a></p>
        """, 500

    return f"""
    <h1>Mercado Libre respondió</h1>
    <p>Código HTTP: {response.status_code}</p>
    <p>Tamaño de la página: {len(response.text)} caracteres</p>
    <p>Esto confirma el acceso a la página, no la extracción de ofertas.</p>
    <p><a href="/">Volver al panel</a></p>
    """


# --------------------------------------------------
# INSPECCIONAR EL HTML RECIBIDO DE MERCADO LIBRE
# --------------------------------------------------

@app.route("/inspeccionar-ofertas")
def inspeccionar_ofertas():
    url = "https://www.mercadolibre.com.mx/ofertas"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        response.raise_for_status()

        contenido = response.text

        titulo = re.search(
            r"<title[^>]*>(.*?)</title>",
            contenido,
            re.IGNORECASE | re.DOTALL,
        )

        titulo_pagina = (
            titulo.group(1).strip()
            if titulo else "Sin título"
        )

        fragmento = escape(contenido[:1200])

        enlaces = re.findall(
            r"""href=["']([^"']+)["']""",
            contenido,
            re.IGNORECASE,
        )

        productos = []

        for enlace in enlaces:
            if (
                "mercadolibre.com.mx/" in enlace
                and "/p/" in enlace
                and enlace not in productos
            ):
                productos.append(enlace)

        indicadores = [
            "andes-money-amount",
            "poly-card",
            "original_price",
            "discount",
            "price",
        ]

        resultados = "".join(
            f"<li>{escape(indicador)}: "
            f"{contenido.lower().count(indicador.lower())}</li>"
            for indicador in indicadores
        )

        muestra = "".join(
            f'<li><a href="{escape(enlace, quote=True)}">'
            f'{escape(enlace)}</a></li>'
            for enlace in productos[:15]
        )

        if not muestra:
            muestra = "<li>No se encontraron enlaces de productos.</li>"

        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head><meta charset="UTF-8"><title>Inspección</title></head>
        <body style="font-family:Arial;max-width:900px;margin:30px auto;padding:20px">
            <h1>Inspección de ofertas</h1>
            <h2>Título recibido</h2>
            <p>{escape(titulo_pagina)}</p>

            <h2>Inicio del HTML recibido</h2>
            <pre style="white-space:pre-wrap;overflow-wrap:anywhere">{fragmento}</pre>

            <p>Respuesta HTTP: {response.status_code}</p>

            <h2>Indicadores encontrados</h2>
            <ul>{resultados}</ul>

            <h2>Enlaces de productos: {len(productos)}</h2>
            <ol>{muestra}</ol>

            <p><a href="/">Volver al panel</a></p>
        </body>
        </html>
        """

    except Exception as error:
        return f"""
        <h1>Error al inspeccionar las ofertas</h1>
        <p>{escape(str(error))}</p>
        <p><a href="/">Volver al panel</a></p>
        """, 500


# --------------------------------------------------
# FORMULARIO PARA GENERAR ENLACES DE AFILIADO
# --------------------------------------------------

@app.route("/probar-afiliado", methods=["GET", "POST"])
def probar_afiliado():
    if request.method == "GET":
        return """
        <!DOCTYPE html>
        <html lang="es">
        <head><meta charset="UTF-8"><title>Generador afiliado</title></head>
        <body style="font-family:Arial;max-width:700px;margin:40px auto;padding:20px">
            <h1>Generador de enlace afiliado</h1>
            <form method="POST">
                <p><label for="producto">URL del producto de Mercado Libre:</label></p>
                <input
                    id="producto"
                    type="url"
                    name="producto"
                    placeholder="Pega aquí la URL del producto"
                    style="width:100%;max-width:500px"
                    required
                >
                <p><button type="submit">Generar enlace afiliado</button></p>
            </form>
            <p><a href="/">Volver al panel</a></p>
        </body>
        </html>
        """

    producto = request.form.get("producto", "").strip()

    if not producto:
        return "No se recibió ninguna URL.", 400

    try:
        enlace = create_affiliate_link(producto)

        return f"""
        <h1>Enlace afiliado generado</h1>
        <p>Producto:</p>
        <p><a href="{escape(producto, quote=True)}">
            {escape(producto)}
        </a></p>
        <p>Enlace afiliado:</p>
        <p><a href="{escape(enlace, quote=True)}">
            {escape(enlace)}
        </a></p>
        <p><a href="/probar-afiliado">Generar otro enlace</a></p>
        <p><a href="/">Volver al panel</a></p>
        """

    except Exception as error:
        return f"""
        <h1>Error al generar el enlace</h1>
        <p>{escape(str(error))}</p>
        <p><a href="/probar-afiliado">Intentar nuevamente</a></p>
        <p><a href="/">Volver al panel</a></p>
        """, 500


# --------------------------------------------------
# ARRANQUE LOCAL
# Render utiliza Gunicorn para ejecutar la aplicación.
# --------------------------------------------------


# --------------------------------------------------
# PRUEBA DE BÚSQUEDA OFICIAL DE MERCADO LIBRE
# --------------------------------------------------

@app.route("/probar-api-busqueda")
def probar_api_busqueda():
    access_token = session.get("access_token")

    if not access_token:
        return """
        <h1>Falta conectar Mercado Libre</h1>
        <p><a href="/login/mercadolibre">Conectar cuenta</a></p>
        """, 401

    try:
        response = requests.get(
            "https://api.mercadolibre.com/sites/MLM/search",
            params={
                "q": "audifonos",
                "limit": 5,
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            timeout=30,
        )

    except requests.RequestException as error:
        return (
            f"<h1>Error de conexión</h1>"
            f"<pre>{escape(str(error))}</pre>"
        ), 500

    if response.status_code != 200:
        return f"""
        <h1>La API rechazó la consulta</h1>
        <p>Código HTTP: {response.status_code}</p>
        <pre>{escape(response.text[:3000])}</pre>
        <p><a href="/">Volver al panel</a></p>
        """, response.status_code

    try:
        data = response.json()
    except ValueError:
        return "<h1>La respuesta no es JSON válido</h1>", 500

    productos = data.get("results", [])
    filas = ""

    for producto in productos:
        titulo = escape(str(producto.get("title", "Sin título")))
        precio = escape(str(producto.get("price", "Sin precio")))
        enlace = escape(str(producto.get("permalink", "")), quote=True)
        imagen = escape(str(producto.get("thumbnail", "")), quote=True)

        filas += f"""
        <tr>
            <td>{titulo}</td>
            <td>${precio}</td>
            <td><a href="{enlace}" target="_blank">Ver producto</a></td>
            <td>{imagen}</td>
        </tr>
        """

    if not filas:
        filas = "<tr><td colspan='4'>No se recibieron productos.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Prueba de búsqueda</title></head>
    <body style="font-family:Arial;max-width:1000px;margin:30px auto;padding:20px">
        <h1>Prueba de búsqueda oficial</h1>
        <p>Respuesta HTTP: {response.status_code}</p>
        <p>Productos recibidos: {len(productos)}</p>
        <table border="1" cellpadding="8" cellspacing="0">
            <tr>
                <th>Título</th>
                <th>Precio</th>
                <th>Enlace</th>
                <th>URL de imagen</th>
            </tr>
            {filas}
        </table>
        <p><a href="/">Volver al panel</a></p>
    </body>
    </html>
    """


# --------------------------------------------------
# PRUEBA DE BÚSQUEDA DE PRODUCTOS DE CATÁLOGO
# --------------------------------------------------

@app.route("/probar-busqueda-catalogo")
def probar_busqueda_catalogo():
    access_token = session.get("access_token")

    if not access_token:
        return """
        <h1>Falta conectar Mercado Libre</h1>
        <p><a href="/login/mercadolibre">Conectar cuenta</a></p>
        """, 401

    try:
        response = requests.get(
            "https://api.mercadolibre.com/products/search",
            params={
                "site_id": "MLM",
                "q": "audifonos",
                "status": "active",
                "limit": 5,
            },
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            timeout=30,
        )

    except requests.RequestException as error:
        return (
            "<h1>Error de conexión</h1>"
            f"<pre>{escape(str(error))}</pre>"
        ), 500

    if response.status_code != 200:
        return f"""
        <h1>Error en búsqueda de catálogo</h1>
        <p>Código HTTP: {response.status_code}</p>
        <pre>{escape(response.text[:6000])}</pre>
        <p><a href="/">Volver al panel</a></p>
        """, response.status_code

    try:
        data = response.json()
    except ValueError:
        return "<h1>La respuesta no es JSON válido</h1>", 500

    productos = data.get("results", [])
    filas = ""

    for producto in productos:
        producto_id = escape(str(producto.get("id", "")))
        nombre = escape(str(producto.get("name", "Sin nombre")))
        estado = escape(str(producto.get("status", "")))
        dominio = escape(str(producto.get("domain_id", "")))

        filas += f"""
        <tr>
            <td>{producto_id}</td>
            <td>{nombre}</td>
            <td>{estado}</td>
            <td>{dominio}</td>
        </tr>
        """

    if not filas:
        filas = "<tr><td colspan='4'>No se encontraron productos.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Prueba de catálogo</title>
    </head>
    <body style="font-family:Arial;max-width:1000px;margin:30px auto;padding:20px">
        <h1>Prueba de búsqueda de catálogo</h1>
        <p>Respuesta HTTP: {response.status_code}</p>
        <p>Productos recibidos: {len(productos)}</p>
        <table border="1" cellpadding="8" cellspacing="0">
            <tr>
                <th>ID de catálogo</th>
                <th>Nombre</th>
                <th>Estado</th>
                <th>Dominio</th>
            </tr>
            {filas}
        </table>
        <p><a href="/">Volver al panel</a></p>
    </body>
    </html>
    """

# --------------------------------------------------
# PRUEBA DEL DETALLE DE UN PRODUCTO DE CATALOGO
# --------------------------------------------------

@app.route("/probar-detalle-catalogo")
def probar_detalle_catalogo():
    access_token = session.get("access_token")

    if not access_token:
        return """
        <h1>Falta conectar Mercado Libre</h1>
        <p><a href="/login/mercadolibre">Conectar cuenta</a></p>
        """, 401

    producto_id = "MLM48308625"

    try:
        response = requests.get(
            f"https://api.mercadolibre.com/products/{producto_id}",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            timeout=30,
        )
    except requests.RequestException as error:
        return (
            "<h1>Error de conexión</h1>"
            f"<pre>{escape(str(error))}</pre>"
        ), 500

    if response.status_code != 200:
        return f"""
        <h1>Error al consultar el producto</h1>
        <p>Código HTTP: {response.status_code}</p>
        <pre>{escape(response.text[:4000])}</pre>
        """, response.status_code

    data = response.json()
    ganador = data.get("buy_box_winner")

    if not ganador:
        return f"""
        <h1>Diagnóstico del producto</h1>
        <p><b>Nombre:</b> {escape(str(data.get("name", "")))}</p>
        <p><b>Estado:</b> {escape(str(data.get("status", "")))}</p>
        <p><b>Familia:</b> {escape(str(data.get("family_name", "")))}</p>
        <p><b>Enlace de catálogo:</b>
           <a href="{escape(str(data.get("permalink", "")))}" target="_blank">
           Abrir producto</a>
        </p>
        <p><b>Publicación ganadora:</b>
           {escape(str(data.get("buy_box_winner", "Campo ausente")))}</p>
        <p><b>Campos recibidos:</b></p>
        <pre>{escape(", ".join(data.keys()))}</pre>
        <p><a href="/">Volver al panel</a></p>
        """

    item_id = ganador.get("item_id", "")
    precio = ganador.get("price", "No disponible")
    moneda = ganador.get("currency_id", "MXN")

    return f"""
    <h1>Publicación ganadora encontrada</h1>
    <p>Producto: {escape(str(data.get("name", "")))}</p>
    <p>ID de catálogo: {escape(producto_id)}</p>
    <p>ID de publicación: {escape(str(item_id))}</p>
    <p>Precio: {escape(str(precio))} {escape(str(moneda))}</p>
    <p>
        <a href="https://articulo.mercadolibre.com.mx/{escape(str(item_id))}"
           target="_blank" rel="noopener">
           Intentar abrir la publicación
        </a>
    </p>
    <p><a href="/">Volver al panel</a></p>
    """

# --------------------------------------------------
# PRUEBA DE ACCESO A LA PAGINA OFICIAL DE OFERTAS
# --------------------------------------------------

@app.route("/probar-pagina-ofertas")
def probar_pagina_ofertas():
    url = "https://www.mercadolibre.com.mx/ofertas"

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )
            },
            timeout=30,
        )
    except requests.RequestException as error:
        return (
            "<h1>Error de conexión</h1>"
            f"<pre>{escape(str(error))}</pre>"
        ), 500

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Prueba de página de ofertas</title>
    </head>
    <body style="font-family:Arial;max-width:900px;margin:30px auto">
        <h1>Prueba de página de ofertas</h1>
        <p><b>Código HTTP:</b> {response.status_code}</p>
        <p><b>URL final:</b> {escape(response.url)}</p>
        <p><b>Tamaño de respuesta:</b> {len(response.text)} caracteres</p>
        <h2>Fragmento de la página recibida</h2>
        <pre style="white-space:pre-wrap;overflow-wrap:anywhere">{escape(response.text[:5000])}</pre>
        <p><a href="/">Volver al panel</a></p>
    </body>
    </html>
    """, response.status_code


# --------------------------------------------------
# PRUEBA DE PUBLICACIONES ASOCIADAS AL CATALOGO
# --------------------------------------------------

@app.route("/probar-publicaciones-catalogo")
def probar_publicaciones_catalogo():
    access_token = session.get("access_token")

    if not access_token:
        return """
        <h1>Falta conectar Mercado Libre</h1>
        <p><a href="/login/mercadolibre">Conectar cuenta</a></p>
        """, 401

    producto_id = "MLM48308625"
    url = f"https://api.mercadolibre.com/products/{producto_id}/items"

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
    except requests.RequestException as error:
        return (
            "<h1>Error de conexión</h1>"
            f"<pre>{escape(str(error))}</pre>"
        ), 500

    return f"""
    <h1>Prueba de publicaciones asociadas</h1>
    <p><b>Código HTTP:</b> {response.status_code}</p>
    <p><b>Producto:</b> {escape(producto_id)}</p>
    <h2>Respuesta de la API</h2>
    <pre style="white-space:pre-wrap;overflow-wrap:anywhere">{escape(response.text[:6000])}</pre>
    <p><a href="/">Volver al panel</a></p>
    """, response.status_code

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000,
    )
