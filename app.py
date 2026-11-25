import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# FASHION STORE - Control de inventario (Proyecto SIGA, grupo 10)
# ------------------------------------------------------------
st.set_page_config(page_title="Fashion Store - Inventario", layout="wide")
st.title("🧵 FASHION STORE - Control de Inventario")

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


inicializar_db()

tab_inicio, tab_registrar, tab_inventario, tab_alertas = st.tabs(
    ["Inicio", "Registrar movimiento", "Inventario", "Alertas"]
)

# ---------------- PESTAÑA 1: INICIO ----------------
with tab_inicio:
    st.header("Resumen del inventario")
    st.write(
        "FASHION STORE es una empresa de confección de prendas de vestir. "
        "Esta aplicación controla las entradas y salidas de sus materias primas: "
        "telas, hilos, cremalleras, botones, cintas, herrajes y resortes."
    )
    df_inv = leer("SELECT * FROM vw_inventario_actual")
    col1, col2, col3 = st.columns(3)
    col1.metric("Referencias", f"{len(df_inv)} materiales")
    col2.metric("Unidades en stock", f"{int(df_inv['stock'].sum())}")
    col3.metric("Valor del inventario", f"${(df_inv['stock'] * df_inv['precio']).sum():,.0f} COP")

    st.subheader("Últimos movimientos")
    st.dataframe(
        leer("""
            SELECT m.fecha, p.nombre AS producto, m.tipo, m.cantidad, c.nombre AS cliente
            FROM movimientos m
            JOIN productos p ON p.id = m.id_producto
            LEFT JOIN clientes c ON c.id = m.id_cliente
            ORDER BY m.id DESC LIMIT 10
        """),
        width="stretch",
        hide_index=True,
    )

# ---------------- PESTAÑA 2: REGISTRAR MOVIMIENTO ----------------
with tab_registrar:
    st.header("Registrar entrada o salida")
    productos = leer("SELECT id, nombre FROM productos ORDER BY nombre")
    clientes = leer("SELECT id, nombre FROM clientes ORDER BY nombre")
    opciones_prod = {row["nombre"]: int(row["id"]) for _, row in productos.iterrows()}
    opciones_cli = {"(sin cliente)": None}
    opciones_cli.update({row["nombre"]: int(row["id"]) for _, row in clientes.iterrows()})

    with st.form("form_movimiento"):
        producto = st.selectbox("Materia prima", list(opciones_prod.keys()))
        tipo = st.radio("Tipo de movimiento", ["entrada", "salida"], horizontal=True)
        cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)
        cliente = st.selectbox("Cliente (solo para salidas)", list(opciones_cli.keys()))
        fecha = st.date_input("Fecha", value=date.today())
        enviar = st.form_submit_button("Registrar")

    if enviar:
        ok, msg = registrar_movimiento(
            opciones_prod[producto], tipo, int(cantidad), str(fecha), opciones_cli[cliente]
        )
        if ok:
            st.success(msg)
        else:
            st.error(msg)

# ---------------- PESTAÑA 3: INVENTARIO ----------------
with tab_inventario:
    st.header("Inventario actual (vista vw_inventario_actual)")
    busqueda = st.text_input("Buscar material por nombre")
    df_vista = leer("SELECT id, nombre, categoria, precio, stock FROM vw_inventario_actual ORDER BY nombre")
    if busqueda:
        df_vista = df_vista[df_vista["nombre"].str.contains(busqueda, case=False)]
    st.dataframe(df_vista, width="stretch", hide_index=True)
    st.download_button(
        "Descargar inventario (CSV)",
        df_vista.to_csv(index=False).encode("utf-8"),
        file_name="inventario_fashion_store.csv",
        mime="text/csv",
    )

# ---------------- PESTAÑA 4: ALERTAS ----------------
with tab_alertas:
    st.header("Alertas de stock bajo")
    df_al = leer("SELECT nombre, categoria, stock FROM vw_inventario_actual")

    c1, c2 = st.columns(2)
    with c1:
        minimo = st.slider("Mostrar materiales con stock menor a:", min_value=5, max_value=200, value=30, step=5)
    with c2:
        categorias = ["Todas"] + sorted(df_al["categoria"].unique().tolist())
        categoria = st.selectbox("Categoría", categorias)

    if categoria != "Todas":
        df_al = df_al[df_al["categoria"] == categoria]
    alertas = df_al[df_al["stock"] < minimo].sort_values("stock")

    if alertas.empty:
        st.success(f"No hay materiales con stock menor a {minimo} unidades.")
    else:
        st.warning(f"{len(alertas)} material(es) con stock menor a {minimo} unidades:")
        st.dataframe(alertas, width="stretch", hide_index=True)

    st.subheader("Stock por material")
    st.bar_chart(df_al.set_index("nombre")["stock"])
