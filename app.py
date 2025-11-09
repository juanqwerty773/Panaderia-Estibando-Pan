from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)

# --- Función auxiliar para ejecutar consultas ---
import sqlite3

def ejecutar_consulta(query, params=(), fetch=False):
    con = sqlite3.connect("panaderia.db")
    cur = con.cursor()

    try:
        cur.execute(query, params)

        if fetch:
            datos = cur.fetchall()
            con.commit()     # ✅ siempre confirmamos antes de cerrar
            return datos
        else:
            con.commit()
            return cur.lastrowid  # ✅ útil para INSERTs

    except sqlite3.Error as e:
        print("❌ Error en la consulta:", e)
        con.rollback()
        raise
    finally:
        con.close()


# --- Página principal ---
@app.route('/')
def inicio():
    return render_template("base.html")

# --- Productos ---
@app.route('/productos')
def productos():
    datos = ejecutar_consulta("SELECT * FROM productos", fetch=True)
    return render_template("productos.html", productos=datos)

@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    nombre = request.form['nombre']
    precio = float(request.form['precio'])
    stock = int(request.form['stock'])
    ejecutar_consulta("INSERT INTO productos (nombre, precio, stock) VALUES (?, ?, ?)",
                      (nombre, precio, stock))
    return redirect('/productos')

@app.route('/modificar_producto/<int:id>', methods=['POST'])
def modificar_producto(id):
    nombre = request.form['nombre']
    precio = float(request.form['precio'])
    stock = int(request.form['stock'])
    ejecutar_consulta("UPDATE productos SET nombre=?, precio=?, stock=? WHERE id=?",
                      (nombre, precio, stock, id))
    return redirect('/productos')

# --- Registrar ventas ---
@app.route('/nueva_venta')
def nueva_venta():
    productos = ejecutar_consulta("SELECT * FROM productos", fetch=True)
    return render_template("nueva_venta.html", productos=productos)

@app.route('/agregar_venta', methods=['POST'])
def agregar_venta():
    conexion = sqlite3.connect('panaderia.db')
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    productos = ejecutar_consulta("SELECT id, nombre, precio, stock FROM productos", fetch=True)
    
    total = 0
    detalles = []

    for prod in productos:
        id_prod, nombre, precio_unit, stock_actual = prod
        cantidad = int(request.form.get(f'cantidad_{id_prod}', 0))
        if cantidad <= 0:
            continue
        subtotal = precio_unit * cantidad
        total += subtotal
        detalles.append((id_prod, cantidad, precio_unit, subtotal))
        # Actualizar stock
        ejecutar_consulta("UPDATE productos SET stock=? WHERE id=?", (stock_actual - cantidad, id_prod))

    # Guardar en ventas
    cur = ejecutar_consulta("INSERT INTO ventas (fecha, total) VALUES (?, ?)", (fecha, total))
    id_venta = cur
    # Guardar detalle de venta
    for det in detalles:
        ejecutar_consulta(
            "INSERT INTO detalle_ventas (id_venta, id_producto, cantidad, precio_unitario, subtotal) VALUES (?, ?, ?, ?, ?)",
            (id_venta, det[0], det[1], det[2], det[3])
        )
        print(det)
    conexion.commit()
    conexion.close()
    return redirect('/ventas')


# --- Ver ventas ---
@app.route('/ventas')
def ventas():
    ventas = ejecutar_consulta("SELECT * FROM ventas ORDER BY fecha DESC", fetch=True)
    detalle = {}
    for v in ventas:
        id_v = v[0]
        detalle[id_v] = ejecutar_consulta(
            """SELECT p.nombre, d.cantidad, d.precio_unitario, d.subtotal 
               FROM detalle_ventas d 
               JOIN productos p ON d.id_producto = p.id
               WHERE d.id_venta=?""", (id_v,), fetch=True
        )
        print(detalle)
    return render_template("ventas.html", ventas=ventas, detalle=detalle)

# --- Resumen diario ---
@app.route('/resumen_diario')
def resumen_diario():
    # Traer todas las ventas ordenadas por fecha
    ventas = ejecutar_consulta("SELECT * FROM ventas ORDER BY fecha ASC", fetch=True)

    # Diccionario para detalle de cada venta
    detalle = {}
    for v in ventas:
        id_v = v[0]
        detalle[id_v] = ejecutar_consulta(
            """SELECT p.nombre, d.cantidad, d.precio_unitario, d.subtotal
               FROM detalle_ventas d
               JOIN productos p ON d.id_producto = p.id
               WHERE d.id_venta=?""", (id_v,), fetch=True
        )

    # Calcular totales por día y cantidad por producto
    resumen_diario = {}
    for v in ventas:
        fecha_dia = v[1][:10]  # YYYY-MM-DD
        if fecha_dia not in resumen_diario:
            resumen_diario[fecha_dia] = {
                "total_dia": 0,
                "productos": {}  # {"pan": 3, "medialuna": 5}
            }
        resumen_diario[fecha_dia]["total_dia"] += v[2]  # total de la venta
        for d in detalle[v[0]]:
            nombre = d[0]
            cantidad = d[1]
            if nombre not in resumen_diario[fecha_dia]["productos"]:
                resumen_diario[fecha_dia]["productos"][nombre] = 0
            resumen_diario[fecha_dia]["productos"][nombre] += cantidad

    return render_template("resumen_diario.html",
                           ventas=ventas,
                           detalle=detalle,
                           resumen_diario=resumen_diario)

if __name__ == '__main__':
    app.run(debug=True)