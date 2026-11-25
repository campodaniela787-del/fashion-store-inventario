import base64
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# FASHION STORE - Control de inventario (Proyecto SIGA, grupo 10)
# ------------------------------------------------------------
st.set_page_config(page_title="Fashion Store · Inventario", page_icon="🧵", layout="wide", initial_sidebar_state="expanded")

DB_PATH = "siga_clase.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def inicializar_db():
    """Crea las 4 tablas, la vista y los datos de prueba si no existen."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        ciudad TEXT
    );
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        categoria TEXT NOT NULL,
        precio REAL NOT NULL CHECK (precio > 0),
        id_proveedor INTEGER,
        fecha_vencimiento TEXT,
        FOREIGN KEY (id_proveedor) REFERENCES proveedores(id)
    );
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        tipo TEXT,
        ciudad TEXT
    );
    CREATE TABLE IF NOT EXISTS movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_producto INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK (tipo IN ('entrada','salida')),
        cantidad INTEGER NOT NULL CHECK (cantidad > 0),
        fecha TEXT NOT NULL,
        id_cliente INTEGER,
        FOREIGN KEY (id_producto) REFERENCES productos(id),
        FOREIGN KEY (id_cliente)  REFERENCES clientes(id)
    );

    DROP VIEW IF EXISTS vw_inventario_actual;
    CREATE VIEW vw_inventario_actual AS
    SELECT p.id, p.nombre, p.categoria, p.precio,
           COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.cantidad ELSE -m.cantidad END), 0) AS stock
    FROM productos p
    LEFT JOIN movimientos m ON m.id_producto = p.id
    GROUP BY p.id, p.nombre, p.categoria, p.precio;
    """)

    cursor.execute("SELECT COUNT(*) FROM proveedores")
    if cursor.fetchone()[0] == 0:
        cursor.executescript("""
        INSERT INTO proveedores (nombre, ciudad) VALUES
         ('fartelas', 'cali'), ('induboton', 'yumbo'),
         ('insumos_valle', 'cali'), ('distribuidora_textil', 'bogota');

        INSERT INTO clientes (nombre, tipo, ciudad) VALUES
         ('confecciones_maquila', 'empresa textil (maquila)', 'cali'),
         ('studio_f', 'tienda de ropa', 'cali'),
         ('cc_chipichape', 'centro comercial', 'cali'),
         ('moda_online', 'e-commerce', 'bogota');

        INSERT INTO productos (nombre, categoria, precio, id_proveedor, fecha_vencimiento) VALUES
         ('telas_lino', 'rollo', 600000, 1, '2028-03-15'),
         ('telas_algodon', 'rollo', 700000, 1, '2028-05-12'),
         ('telas_seda', 'rollo', 800000, 4, '2027-12-30'),
         ('hilos', 'carreto', 10000, 2, '2029-12-10'),
         ('cremalleras', 'caja', 40000, 3, NULL),
         ('botones', 'caja', 20000, 2, NULL),
         ('cintas', 'carreto', 200000, 3, '2027-12-20'),
         ('herrajes', 'caja', 100000, 3, NULL),
         ('resortes', 'carreto', 200000, 3, '2027-12-20');

        INSERT INTO movimientos (id_producto, tipo, cantidad, fecha) VALUES
         (1,'entrada',100,'2026-09-01'),(2,'entrada',80,'2026-09-01'),(3,'entrada',40,'2026-09-02'),
         (4,'entrada',60,'2026-09-02'),(5,'entrada',50,'2026-09-03'),(6,'entrada',5,'2026-09-03'),
         (7,'entrada',30,'2026-09-05'),(8,'entrada',200,'2026-09-05'),(9,'entrada',50,'2026-09-06');

        INSERT INTO movimientos (id_producto, tipo, cantidad, fecha, id_cliente) VALUES
         (1,'salida',30,'2026-09-10',1),(2,'salida',20,'2026-09-12',2),(3,'salida',15,'2026-09-15',2),
         (4,'salida',25,'2026-09-18',1),(8,'salida',120,'2026-09-20',3),(1,'salida',25,'2026-09-25',4),
         (5,'salida',10,'2026-09-26',4),(9,'salida',15,'2026-09-28',1),(7,'salida',10,'2026-10-02',3),
         (1,'salida',10,'2026-10-03',2);
        """)
    conn.commit()
    conn.close()


def leer(sql, params=()):
    conn = get_connection()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def registrar_movimiento(id_producto, tipo, cantidad, fecha, id_cliente=None):
    """Registra una entrada o salida con BEGIN / COMMIT / ROLLBACK."""
    if not isinstance(cantidad, int) or cantidad <= 0:
        return False, "La cantidad debe ser un número entero mayor que 0."

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN")
        cursor.execute("SELECT nombre FROM productos WHERE id = ?", (id_producto,))
        fila = cursor.fetchone()
        if fila is None:
            raise ValueError(f"El producto con ID {id_producto} no existe.")
        nombre = fila[0]

        if tipo == "salida":
            cursor.execute("SELECT stock FROM vw_inventario_actual WHERE id = ?", (id_producto,))
            stock = cursor.fetchone()[0]
            if cantidad > stock:
                raise ValueError(
                    f"Stock insuficiente de {nombre}: hay {stock} unidades y se piden {cantidad}."
                )

        cursor.execute(
            "INSERT INTO movimientos (id_producto, tipo, cantidad, fecha, id_cliente) VALUES (?, ?, ?, ?, ?)",
            (id_producto, tipo, cantidad, fecha, id_cliente if tipo == "salida" else None),
        )
        conn.commit()
        return True, f"{tipo.capitalize()} registrada: {cantidad} unidades de {nombre}."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


# ------------------------------------------------------------
# DISEÑO: estilos CSS y animaciones
# ------------------------------------------------------------
st.markdown("""
<style>
#MainMenu, footer {visibility: hidden;}
header[data-testid="stHeader"] {background: #0B0B0B; height: 3rem; border-bottom: 2px solid #C9A227;}
.block-container {padding-top: 3.6rem; max-width: 1250px;}

/* ---------- barra lateral azul oscuro ---------- */
section[data-testid="stSidebar"] {background: #0B0B0B; border-right: 1px solid #2A2418;}
section[data-testid="stSidebar"] * {color: #EDE3C8;}
.brand {margin: -1rem -1rem .6rem -1rem; padding: 8px 10px; background: #000000; text-align: center;}
.brand img {width: 100%; max-width: 250px; border-radius: 6px; animation: aparecer .8s ease both;}
.menu-title {font-size: .75rem; text-transform: uppercase; letter-spacing: 1px; color: #C9A227 !important;
             margin: 18px 0 6px 4px; font-weight: 700;}
.menu-item {display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 8px;
            font-weight: 600; margin-bottom: 2px; transition: background .2s, transform .2s;}
.menu-item:hover {background: #1E1A12; transform: translateX(4px);}

.menu-item .n {margin-left: auto; background: #C9A227; color: #0B0B0B !important; font-weight: 800; border-radius: 999px; padding: 1px 9px; font-size: .78rem;}
.side-foot {margin-top: 26px; font-size: .75rem; color: #9C8B62 !important;}

/* ---------- encabezado con dibujo animado ---------- */
.hero {background: linear-gradient(90deg, #000000 0%, #000000 55%, #1A150C 100%); border-radius: 18px;
       padding: 10px 30px; display: flex; align-items: center; justify-content: space-between; gap: 20px;
       border: 1px solid #3A311C; box-shadow: 0 8px 26px rgba(0, 0, 0, .35); margin-bottom: 1.1rem;
       animation: aparecer .6s ease both; position: relative; overflow: hidden;}
.hero::after {content: ""; position: absolute; top: 0; left: -60%; width: 40%; height: 100%;
              background: linear-gradient(100deg, transparent, rgba(255, 215, 120, .18), transparent);
              animation: brillo 5s ease-in-out infinite;}
.hero .logo-hero {height: 230px; animation: latido 4s ease-in-out infinite;}
.hero-title {font-size: 1.9rem; font-weight: 800; color: #F5E6B8; line-height: 1.2;}
.hero p {color: #BFA765; margin: 6px 0 0 0;}
.hero svg {width: 210px; height: 120px; flex-shrink: 0;}

/* ---------- tarjetas con icono ---------- */
.icard {display: flex; gap: 14px; background: #141414; border: 1px solid #3A311C; border-radius: 10px; padding: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,.18); margin-bottom: 14px; min-height: 86px;
        animation: aparecer .6s ease both; transition: transform .25s, box-shadow .25s;}
.icard:hover {transform: translateY(-6px) scale(1.02); box-shadow: 0 12px 24px rgba(201,162,39,.35); border-color: #C9A227;}
.icard .ico {width: 66px; min-width: 66px; height: 66px; border-radius: 8px; display: flex;
             align-items: center; justify-content: center; font-size: 2rem;}
.icard .ico span {display: inline-block; animation: flotar 2.6s ease-in-out infinite;}
.icard:hover .ico span {animation: saltar .6s ease infinite;}
.icard .txt {flex: 1; display: flex; flex-direction: column; justify-content: space-between; padding: 4px 6px 2px 0;}
.icard .t {color: #FFFFFF; font-weight: 700; font-size: .98rem;}
.icard .num {color: #E9C766; font-weight: 800; font-size: 1.55rem; text-align: right; line-height: 1;}
.azul {background: linear-gradient(135deg, #F3D57A, #B8902F);} .turquesa {background: linear-gradient(135deg, #E9C766, #8C6A1E);}
.amarillo {background: linear-gradient(135deg, #FFE9A8, #C9A227);} .naranja {background: linear-gradient(135deg, #D9A441, #7A5512);}
.morado {background: linear-gradient(135deg, #CFB57A, #6E5A2C);} .rosa {background: linear-gradient(135deg, #F1DFB0, #A88A45);}
.marino {background: linear-gradient(135deg, #3A3A3A, #000000); border: 1px solid #C9A227;}
.verde {background: linear-gradient(135deg, #7BC67E, #2E7D32);} .rojo {background: linear-gradient(135deg, #F07167, #B3261E);}

.section-title {font-size: 1.25rem; font-weight: 800; color: #1A1A1A; border-left: 5px solid #C9A227; padding-left: 10px; margin: 1.3rem 0 .6rem 0;}

/* ---------- pestañas ---------- */
.stTabs div[role="tablist"] {gap: 8px; background: #0B0B0B; padding: 7px; border-radius: 12px;
                             box-shadow: 0 2px 8px rgba(0,0,0,.06); border: none;}
.stTabs [role="tab"] {border-radius: 9px; padding: 9px 20px; background: transparent; height: auto; transition: background .2s;}
.stTabs [role="tab"]:hover {background: #1E1A12;}
.stTabs [role="tab"] p {color: #EDE3C8;}
.stTabs [role="tab"] p {font-weight: 700; font-size: .97rem;}
.stTabs [role="tab"][aria-selected="true"] {background: linear-gradient(135deg, #E9C766, #B8902F);}
.stTabs [role="tab"][aria-selected="true"] p {color: #0B0B0B !important;}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"], .stTabs .react-aria-SelectionIndicator {display: none;}

div[data-testid="stForm"] {background: #FFFFFF; border: none; border-radius: 14px; padding: 22px;
                           box-shadow: 0 4px 14px rgba(0,0,0,.07); animation: aparecer .5s ease both;}
div[data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,.06);
                                animation: aparecer .6s ease both;}
.stButton button, .stDownloadButton button, div[data-testid="stFormSubmitButton"] button {
    border-radius: 9px; font-weight: 700; transition: transform .2s;}
.stButton button:hover, .stDownloadButton button:hover, div[data-testid="stFormSubmitButton"] button:hover {transform: translateY(-2px);}
.pie {display: flex; justify-content: space-between; color: #6B7A90; font-size: .8rem; margin-top: 2.2rem;
      border-top: 1px solid #E1E7F0; padding-top: 10px;}
.pie b {color: #B8902F;}

/* ---------- animaciones ---------- */
@keyframes aparecer {from {opacity: 0; transform: translateY(16px);} to {opacity: 1; transform: translateY(0);}}
@keyframes flotar {0%, 100% {transform: translateY(0) rotate(0);} 50% {transform: translateY(-5px) rotate(-6deg);}}
@keyframes saltar {0%, 100% {transform: translateY(0) scale(1);} 50% {transform: translateY(-8px) scale(1.15);}}
@keyframes girar {from {transform: rotate(0);} to {transform: rotate(360deg);}}
@keyframes brillo {0% {left: -60%;} 60%, 100% {left: 130%;}}
@keyframes latido {0%, 100% {transform: scale(1);} 50% {transform: scale(1.03);}}
@keyframes columpio {0%, 100% {transform: rotate(-6deg);} 50% {transform: rotate(6deg);}}
@keyframes coser {0%, 100% {transform: translateY(0);} 50% {transform: translateY(9px);}}
@keyframes hilo {to {stroke-dashoffset: -40;}}
.svg-flota {animation: flotar 2.4s ease-in-out infinite;}
.hero-txt {display: block;}
.svg-vestido {transform-box: fill-box; transform-origin: top center; animation: columpio 3s ease-in-out infinite;}
.svg-aguja {animation: coser .7s ease-in-out infinite;}
.svg-hilo {stroke-dasharray: 6 6; animation: hilo 1.2s linear infinite;}
</style>
""", unsafe_allow_html=True)

# Dibujo animado (SVG): carrete que gira, hilo en movimiento, aguja cosiendo y vestido que se balancea
DIBUJO = """
<svg viewBox="0 0 230 130" xmlns="http://www.w3.org/2000/svg">
  <ellipse cx="115" cy="122" rx="105" ry="6" fill="#2A2418"/>
  <g class="svg-flota">
    <rect x="18" y="40" width="52" height="10" rx="3" fill="#8B5E3C"/>
    <rect x="24" y="50" width="40" height="40" fill="#C9A227"/>
    <line x1="24" y1="58" x2="64" y2="58" stroke="#F3D57A" stroke-width="3"/>
    <line x1="24" y1="68" x2="64" y2="68" stroke="#F3D57A" stroke-width="3"/>
    <line x1="24" y1="78" x2="64" y2="78" stroke="#F3D57A" stroke-width="3"/>
    <rect x="18" y="90" width="52" height="10" rx="3" fill="#8B5E3C"/>
  </g>
  <path class="svg-hilo" d="M64 70 C 90 40, 100 100, 120 62" stroke="#E9C766" stroke-width="2.5" fill="none"/>
  <g class="svg-aguja">
    <line x1="120" y1="20" x2="120" y2="70" stroke="#D9D9D9" stroke-width="3" stroke-linecap="round"/>
    <ellipse cx="120" cy="26" rx="2" ry="4" fill="#FFFFFF" stroke="#D9D9D9" stroke-width="1.5"/>
  </g>
  <line x1="150" y1="14" x2="215" y2="14" stroke="#E9C766" stroke-width="3" stroke-linecap="round"/>
  <g class="svg-vestido">
    <path d="M182 14 L182 24" stroke="#E9C766" stroke-width="2"/>
    <path d="M172 30 Q182 22 192 30 L188 46 L204 112 L160 112 L176 46 Z" fill="#FFFFFF"/>
    <path d="M176 46 L188 46" stroke="#C9A227" stroke-width="4"/>
    <circle cx="182" cy="62" r="2.5" fill="#C9A227"/><circle cx="182" cy="74" r="2.5" fill="#C9A227"/>
  </g>
</svg>
"""


def logo_base64():
    """Lee logo.png (en la misma carpeta que app.py) y lo devuelve en base64."""
    ruta = Path(__file__).parent / "logo.png"
    if ruta.exists():
        return base64.b64encode(ruta.read_bytes()).decode()
    return None


LOGO = logo_base64()
LOGO_IMG = f"data:image/png;base64,{LOGO}" if LOGO else None


def icard(icono, color, titulo_card, numero, retraso=0.0):
    st.markdown(
        f'<div class="icard" style="animation-delay:{retraso}s">'
        f'<div class="ico {color}"><span style="animation-delay:{retraso}s">{icono}</span></div>'
        f'<div class="txt"><div class="t">{titulo_card}</div><div class="num">{numero}</div></div></div>',
        unsafe_allow_html=True,
    )


def titulo(texto):
    st.markdown(f'<div class="section-title">{texto}</div>', unsafe_allow_html=True)


def bonito(nombre):
    """telas_lino -> Telas lino"""
    return nombre.replace("_", " ").capitalize()


def pesos(valor):
    return "$" + f"{valor:,.0f}".replace(",", ".")


inicializar_db()
UMBRAL_BAJO = 30

# Datos para tarjetas y barra lateral
df_inv = leer("SELECT * FROM vw_inventario_actual")
n_prov = int(leer("SELECT COUNT(*) AS n FROM proveedores")["n"].iloc[0])
n_cli = int(leer("SELECT COUNT(*) AS n FROM clientes")["n"].iloc[0])
mov_tipo = leer("SELECT tipo, COUNT(*) AS n FROM movimientos GROUP BY tipo").set_index("tipo")["n"]
n_ent = int(mov_tipo.get("entrada", 0))
n_sal = int(mov_tipo.get("salida", 0))
bajos = int((df_inv["stock"] < UMBRAL_BAJO).sum())

# ---------------- BARRA LATERAL ----------------
with st.sidebar:
    marca = (f'<div class="brand"><img src="{LOGO_IMG}" alt="FASHION STORE"></div>' if LOGO_IMG
             else '<div class="brand" style="color:#E9C766;font-weight:800;padding:16px">🧵 FASHION STORE</div>')
    st.markdown(marca + f"""
    <div class="menu-title">Secciones</div>
    <div class="menu-item">📊 Inicio</div>
    <div class="menu-item">📝 Registrar movimiento</div>
    <div class="menu-item">📦 Inventario</div>
    <div class="menu-item">🚨 Alertas <span class="n">{bajos}</span></div>
    <div class="menu-title">Base de datos</div>
    <div class="menu-item">🚚 Proveedores <span class="n">{n_prov}</span></div>
    <div class="menu-item">🧶 Productos <span class="n">{len(df_inv)}</span></div>
    <div class="menu-item">👥 Clientes <span class="n">{n_cli}</span></div>
    <div class="menu-item">🔄 Movimientos <span class="n">{n_ent + n_sal}</span></div>
    <div class="side-foot">Proyecto SIGA · Programación 2<br>Grupo 10 · 445A</div>
    """, unsafe_allow_html=True)

hoy = date.today().strftime("%d/%m/%Y")
st.markdown(
    '<div class="hero">'
    + (f'<img class="logo-hero" src="{LOGO_IMG}" alt="FASHION STORE">' if LOGO_IMG else "")
    + '<div class="hero-txt"><div class="hero-title">Sistema web de inventario</div>'
    f'<p>Control de materias primas para confección · {hoy}</p></div>'
    + DIBUJO.replace("\n", "") + "</div>",
    unsafe_allow_html=True,
)

tab_inicio, tab_registrar, tab_inventario, tab_alertas = st.tabs(
    ["Inicio", "Registrar movimiento", "Inventario", "Alertas"]
)

# ---------------- PESTAÑA 1: INICIO ----------------
with tab_inicio:
    valor = (df_inv["stock"] * df_inv["precio"]).sum()
    tarjetas = [
        ("🧶", "azul", "Materiales", len(df_inv)),
        ("📥", "turquesa", "Entradas (compras)", n_ent),
        ("📤", "amarillo", "Salidas (ventas)", n_sal),
        ("💰", "marino", "Valor en stock", f"${valor / 1_000_000:,.0f} M"),
        ("🚚", "naranja", "Proveedores", n_prov),
        ("📦", "morado", "Unidades en stock", f"{int(df_inv['stock'].sum()):,}".replace(",", ".")),
        ("👥", "rosa", "Clientes", n_cli),
        ("🚨", "rojo" if bajos else "verde", "Alertas de stock", bajos),
    ]
    for fila in range(0, len(tarjetas), 4):
        cols = st.columns(4)
        for j, col in enumerate(cols):
            ico, color, t, n = tarjetas[fila + j]
            with col:
                icard(ico, color, t, n, retraso=(fila + j) * 0.08)

    izq, der = st.columns([3, 2], gap="large")
    with izq:
        titulo("🕒 Últimos movimientos")
        mov = leer("""
            SELECT m.fecha, p.nombre AS producto, m.tipo, m.cantidad, c.nombre AS cliente
            FROM movimientos m
            JOIN productos p ON p.id = m.id_producto
            LEFT JOIN clientes c ON c.id = m.id_cliente
            ORDER BY m.id DESC LIMIT 8
        """)
        mov["producto"] = mov["producto"].map(bonito)
        mov["cliente"] = mov["cliente"].map(lambda x: bonito(x) if isinstance(x, str) else "—")
        mov["tipo"] = mov["tipo"].map({"entrada": "📥 Entrada", "salida": "📤 Salida"})
        st.dataframe(
            mov, hide_index=True, width="stretch",
            column_config={
                "fecha": st.column_config.TextColumn("Fecha"),
                "producto": st.column_config.TextColumn("Material"),
                "tipo": st.column_config.TextColumn("Tipo"),
                "cantidad": st.column_config.NumberColumn("Cantidad"),
                "cliente": st.column_config.TextColumn("Cliente"),
            },
        )
    with der:
        titulo("📊 Stock por categoría")
        cat = df_inv.groupby("categoria", as_index=False)["stock"].sum()
        cat["categoria"] = cat["categoria"].str.capitalize()
        st.bar_chart(cat, x="categoria", y="stock", color="#C9A227", height=300)

# ---------------- PESTAÑA 2: REGISTRAR MOVIMIENTO ----------------
with tab_registrar:
    productos = leer("SELECT id, nombre FROM productos ORDER BY nombre")
    clientes = leer("SELECT id, nombre FROM clientes ORDER BY nombre")
    opciones_prod = {bonito(row["nombre"]): int(row["id"]) for _, row in productos.iterrows()}
    opciones_cli = {"(sin cliente)": None}
    opciones_cli.update({bonito(row["nombre"]): int(row["id"]) for _, row in clientes.iterrows()})

    form_col, info_col = st.columns([3, 2], gap="large")
    with form_col:
        titulo("📝 Registrar entrada o salida")
        with st.form("form_movimiento"):
            producto = st.selectbox("Materia prima", list(opciones_prod.keys()))
            tipo = st.radio("Tipo de movimiento", ["entrada", "salida"], horizontal=True,
                            format_func=lambda t: "📥 Entrada (compra)" if t == "entrada" else "📤 Salida (venta)")
            a, b = st.columns(2)
            with a:
                cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)
            with b:
                fecha = st.date_input("Fecha", value=date.today())
            cliente = st.selectbox("Cliente (solo para salidas)", list(opciones_cli.keys()))
            enviar = st.form_submit_button("Registrar movimiento", type="primary", width="stretch")

        if enviar:
            ok, msg = registrar_movimiento(
                opciones_prod[producto], tipo, int(cantidad), str(fecha), opciones_cli[cliente]
            )
            if ok:
                st.success(msg, icon="✅")
                st.balloons()
            else:
                st.error(msg, icon="🚫")

    with info_col:
        titulo("📦 Stock disponible")
        fila = leer("SELECT nombre, categoria, stock FROM vw_inventario_actual WHERE id = ?",
                    (opciones_prod[producto],))
        s = int(fila["stock"].iloc[0])
        icard("🧶", "rojo" if s < UMBRAL_BAJO else "verde", bonito(fila["nombre"].iloc[0]), f"{s} unid.")
        icard("🏷️", "azul", "Categoría", fila["categoria"].iloc[0].capitalize(), retraso=0.1)
        st.caption("Las salidas no pueden superar el stock disponible. Si ocurre un error, "
                   "la transacción se deshace (ROLLBACK) y no se guarda nada.")

# ---------------- PESTAÑA 3: INVENTARIO ----------------
with tab_inventario:
    titulo("📦 Inventario actual · vista vw_inventario_actual")
    f1, f2 = st.columns([2, 1])
    with f1:
        busqueda = st.text_input("Buscar material", placeholder="Ej: telas, hilos, botones…")
    df_vista = leer("SELECT id, nombre, categoria, precio, stock FROM vw_inventario_actual ORDER BY nombre")
    with f2:
        cat_inv = st.selectbox("Categoría", ["Todas"] + sorted(df_vista["categoria"].unique().tolist()),
                               key="cat_inv")
    if busqueda:
        df_vista = df_vista[df_vista["nombre"].str.contains(busqueda, case=False)]
    if cat_inv != "Todas":
        df_vista = df_vista[df_vista["categoria"] == cat_inv]

    tabla = df_vista.copy()
    tabla["nombre"] = tabla["nombre"].map(bonito)
    tabla["categoria"] = tabla["categoria"].str.capitalize()
    tabla["valor"] = tabla["precio"] * tabla["stock"]
    tabla["estado"] = tabla["stock"].map(lambda s: "🔴 Bajo" if s < UMBRAL_BAJO else ("🟡 Medio" if s < 60 else "🟢 Bien"))
    max_stock = int(max(tabla["stock"].max(), 1)) if not tabla.empty else 1
    st.dataframe(
        tabla, hide_index=True, width="stretch",
        column_order=["id", "nombre", "categoria", "precio", "stock", "valor", "estado"],
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "nombre": st.column_config.TextColumn("Material"),
            "categoria": st.column_config.TextColumn("Categoría"),
            "precio": st.column_config.NumberColumn("Precio unitario", format="$%,.0f"),
            "stock": st.column_config.ProgressColumn("Stock", format="%d", min_value=0, max_value=max_stock),
            "valor": st.column_config.NumberColumn("Valor en stock", format="$%,.0f"),
            "estado": st.column_config.TextColumn("Estado"),
        },
    )
    st.download_button(
        "⬇️ Descargar inventario (CSV)",
        df_vista.to_csv(index=False).encode("utf-8"),
        file_name="inventario_fashion_store.csv",
        mime="text/csv",
    )

# ---------------- PESTAÑA 4: ALERTAS ----------------
with tab_alertas:
    titulo("🚨 Alertas de stock bajo")
    df_al = leer("SELECT nombre, categoria, stock FROM vw_inventario_actual")

    c1, c2 = st.columns(2)
    with c1:
        minimo = st.slider("Mostrar materiales con stock menor a:", min_value=5, max_value=200, value=30, step=5)
    with c2:
        categorias = ["Todas"] + sorted(df_al["categoria"].unique().tolist())
        categoria = st.selectbox("Categoría", categorias, key="cat_alertas")

    if categoria != "Todas":
        df_al = df_al[df_al["categoria"] == categoria]
    alertas = df_al[df_al["stock"] < minimo].sort_values("stock")

    if alertas.empty:
        st.success(f"No hay materiales con stock menor a {minimo} unidades.", icon="✅")
    else:
        st.warning(f"{len(alertas)} material(es) con stock menor a {minimo} unidades:", icon="⚠️")
        cols = st.columns(min(len(alertas), 4))
        for k, (_, r) in enumerate(alertas.head(4).iterrows()):
            with cols[k]:
                icard("⚠️", "rojo", bonito(r["nombre"]), f"{int(r['stock'])} unid.", retraso=k * 0.08)
        vista_al = alertas.copy()
        vista_al["nombre"] = vista_al["nombre"].map(bonito)
        vista_al["categoria"] = vista_al["categoria"].str.capitalize()
        vista_al["faltan"] = minimo - vista_al["stock"]
        st.dataframe(
            vista_al, hide_index=True, width="stretch",
            column_config={
                "nombre": st.column_config.TextColumn("Material"),
                "categoria": st.column_config.TextColumn("Categoría"),
                "stock": st.column_config.NumberColumn("Stock actual"),
                "faltan": st.column_config.NumberColumn("Unidades para llegar al mínimo"),
            },
        )

    titulo("📊 Stock por material")
    graf = df_al.copy()
    graf["Material"] = graf["nombre"].map(bonito)
    graf["Bajo el mínimo"] = graf["stock"].where(graf["stock"] < minimo, 0)
    graf["Suficiente"] = graf["stock"].where(graf["stock"] >= minimo, 0)
    st.caption("🟥 Rojo: por debajo del mínimo elegido · 🟨 Dorado: stock suficiente")
    st.bar_chart(graf, x="Material", y=["Bajo el mínimo", "Suficiente"], color=["#D64541", "#C9A227"], height=360)

st.markdown('<div class="pie"><span>FASHION STORE · <b>Proyecto SIGA</b> · Grupo 10</span>'
            '<span>Versión 2.0</span></div>', unsafe_allow_html=True)
