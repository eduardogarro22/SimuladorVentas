from flask import Flask, render_template, request, redirect, url_for, session, flash
import pyodbc
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura'

# Conexión SQL Server
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=Edu\\SQLExpress;"
    "DATABASE=Fabrica_de_prueba;"
    "UID=flask_user;"
    "PWD=Clave.1234"
)

def get_db_connection():
    return pyodbc.connect(conn_str)

# --------------------------- LOGIN
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT Rol FROM Usuarios WHERE Usuario = ? AND Contraseña = ?", (username, password))
        result = cursor.fetchone()
        conn.close()

        if result:
            rol = result[0]
            session['usuario'] = username
            session['rol'] = rol

            if rol == 'admin':
                return redirect(url_for('admin_home'))  # 👉 redirige al panel central de admin
            else:
                return redirect(url_for('home'))  # 👉 redirige a home normal (por ejemplo para vendedor)

        else:
            return render_template('login.html', error="Credenciales inválidas")

    return render_template('login.html')

@app.route('/admin')
def admin_home():
    if session.get('rol') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_home.html', usuario=session.get('usuario'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --------------------------- HOME
@app.route('/home')
def home():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    rol = session.get('rol')
    if rol == 'admin':
        return redirect(url_for('admin_home'))  # Cambiado aquí
    elif rol == 'vendedor':
        return redirect(url_for('registrar_venta'))
    else:
        flash('Rol no reconocido')
        return redirect(url_for('login'))


# --------------------------- REGISTRO DE VENTA

@app.route('/registrar_venta')
def registrar_venta():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    if session.get('rol') != 'vendedor':
        flash('Acceso denegado')
        return redirect(url_for('home'))
 
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Id_Cliente, Nombre + ' ' + Apellido FROM Clientes")
    clientes = cursor.fetchall()
    cursor.execute("SELECT Id_Producto, Nombre FROM Productos")
    productos = cursor.fetchall()
    cursor.execute("SELECT Id_Empleado, Nombre + ' ' + Apellido FROM Empleados")
    empleados = cursor.fetchall()
    conn.close()

    return render_template('venta.html', clientes=clientes, productos=productos, empleados=empleados)

@app.route('/registrar', methods=['POST'])
def registrar():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    try:
        # Obtener datos del formulario
        id_cliente = request.form['cliente']
        productos = request.form.getlist('producto[]')
        cantidades = request.form.getlist('cantidad[]')
        tipo_pago = request.form['tipo_pago']
        id_empleado = request.form['empleado']
        descuento = float(request.form['descuento'] or 0)

        # Limpieza y validación
        productos = [p.strip() for p in productos if p.strip().isdigit()]
        cantidades = [c.strip() for c in cantidades if c.strip().isdigit()]

        print(f"[DEBUG] Cliente: {id_cliente}")
        print(f"[DEBUG] Productos: {productos}")
        print(f"[DEBUG] Cantidades: {cantidades}")
        print(f"[DEBUG] Tipo de pago: {tipo_pago}")
        print(f"[DEBUG] Empleado: {id_empleado}")
        print(f"[DEBUG] Descuento: {descuento}")

        if not productos or not cantidades:
            flash("❌ Debes seleccionar productos y cantidades válidas.")
            return redirect(url_for('registrar_venta'))

        if len(productos) != len(cantidades):
            flash("❌ El número de productos y cantidades no coinciden.")
            return redirect(url_for('registrar_venta'))

        productos_str = ",".join(productos)
        cantidades_str = ",".join(cantidades)

        print(f"[DEBUG] productos_str: '{productos_str}'")
        print(f"[DEBUG] cantidades_str: '{cantidades_str}'")

        # Conexión a SQL Server
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ejecutar procedimiento
        cursor.execute("""
            EXEC RegistrarVentaConPago
                @Id_Cliente = ?,
                @Productos = ?,
                @Cantidades = ?,
                @Tipo_Pago = ?,
                @Id_Empleado = ?,
                @Descuento = ?
        """, (id_cliente, productos_str, cantidades_str, tipo_pago, id_empleado, descuento))

        conn.commit()
        conn.close()

        flash('✅ Venta registrada correctamente')

    except Exception as e:
        flash(f'❌ Error: {str(e)}')
        print(f"[ERROR] {str(e)}")

    return redirect(url_for('registrar_venta'))
# -----------------------------------------------
@app.route('/previsualizar_venta', methods=['POST'])
def previsualizar_venta():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    try:
        # Obtener datos del formulario
        id_cliente = request.form['cliente']
        productos = request.form.getlist('producto[]')
        cantidades = request.form.getlist('cantidad[]')
        tipo_pago = request.form['tipo_pago']
        id_empleado = request.form['empleado']
        descuento = float(request.form['descuento'] or 0)

        productos = [p.strip() for p in productos if p.strip().isdigit()]
        cantidades = [c.strip() for c in cantidades if c.strip().isdigit()]
        cantidades = list(map(int, cantidades))

        if len(productos) != len(cantidades):
            flash("❌ Productos y cantidades no coinciden.")
            return redirect(url_for('registrar_venta'))

        # Obtener precios desde la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()

        total = 0
        detalles = []

        for i in range(len(productos)):
            cursor.execute("SELECT Nombre_Producto, Precio_Venta FROM Productos WHERE Id_Producto = ?", productos[i])
            row = cursor.fetchone()
            if row:
                nombre, precio = row
                subtotal = precio * cantidades[i]
                total += subtotal
                detalles.append({
                    "nombre": nombre,
                    "precio": precio,
                    "cantidad": cantidades[i],
                    "subtotal": subtotal
                })

        total_final = total - descuento

        conn.close()

        # Mostrar pantalla de confirmación
        return render_template('confirmar_venta.html',
                               detalles=detalles,
                               total=total,
                               descuento=descuento,
                               total_final=total_final,
                               id_cliente=id_cliente,
                               productos=productos,
                               cantidades=cantidades,
                               tipo_pago=tipo_pago,
                               id_empleado=id_empleado)

    except Exception as e:
        flash(f'❌ Error: {str(e)}')
        return redirect(url_for('registrar_venta'))

#------------------------------------------------------
@app.route('/confirmar_venta', methods=['POST'])
def confirmar_venta():
    try:
        id_cliente = request.form['id_cliente']
        productos = request.form.getlist('productos[]')
        cantidades = request.form.getlist('cantidades[]')
        tipo_pago = request.form['tipo_pago']
        id_empleado = request.form['id_empleado']
        descuento = float(request.form['descuento'])

        productos_str = ",".join(productos)
        cantidades_str = ",".join(cantidades)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            EXEC RegistrarVentaConPago
                @Id_Cliente = ?,
                @Productos = ?,
                @Cantidades = ?,
                @Tipo_Pago = ?,
                @Id_Empleado = ?,
                @Descuento = ?
        """, (id_cliente, productos_str, cantidades_str, tipo_pago, id_empleado, descuento))

        conn.commit()
        conn.close()

        flash("✅ Venta registrada correctamente")
    except Exception as e:
        flash(f"❌ Error al confirmar venta: {str(e)}")

    return redirect(url_for('registrar_venta'))

# --------------------------- NUEVO CLIENTE
@app.route('/nuevo_cliente', methods=['GET', 'POST'])
def nuevo_cliente():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    if session.get('rol') != 'vendedor':
        flash('Acceso denegado')
        return redirect(url_for('home'))

    if request.method == 'POST':
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        direccion = request.form['direccion']
        telefono = request.form['telefono']
        email = request.form['email']
       
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Clientes (Nombre, Apellido, Direccion, Telefono, Email)
                VALUES (?, ?, ?, ?, ?)
            """, (nombre, apellido, direccion, telefono, email))
            conn.commit()
            conn.close()
            flash('✅ Cliente agregado correctamente.')
            return redirect(url_for('registrar_venta'))
        except Exception as e:
            flash(f'❌ Error al agregar cliente: {str(e)}')
            return redirect(url_for('nuevo_cliente'))
    return render_template('nuevo_cliente.html')

# --------------------------- ADMINISTRACIÓN DE VENTAS
@app.route('/admin/ventas', methods=['GET', 'POST'])
def admin_ventas():
    if 'usuario' not in session or session.get('rol') != 'admin':
        flash('Acceso solo para administradores')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor()

    filtro = request.form.get('filtro')
    fecha = request.form.get('fecha')
    query = """
    SELECT 
        V.Fecha, 
        C.Nombre + ' ' + C.Apellido AS Cliente,
        P.Nombre AS Producto,
        DV.Cantidad,
        DV.Precio_Unitario,
        DV.Monto_Total,
        V.Total AS TotalVenta,
        PG.Tipo_Pago,
        E.Nombre + ' ' + E.Apellido AS Empleado
    FROM Ventas V
    JOIN Detalles_Venta DV ON V.Id_Venta = DV.Id_Venta
    JOIN Productos P ON DV.Id_Producto = P.Id_Producto
    JOIN Clientes C ON V.Id_Cliente = C.Id_Cliente
    JOIN Empleados E ON V.Id_Empleado = E.Id_Empleado
    LEFT JOIN Pagos PG ON V.Id_Venta = PG.Id_Venta
    """
    params = []

    if filtro and fecha:
        try:
            fecha_dt = datetime.strptime(fecha, '%Y-%m-%d')
            if filtro == 'dia':
                query += " WHERE CAST(V.Fecha AS DATE) = ?"
                params.append(fecha_dt.date())
            elif filtro == 'mes':
                query += " WHERE MONTH(V.Fecha) = ? AND YEAR(V.Fecha) = ?"
                params.extend([fecha_dt.month, fecha_dt.year])
            elif filtro == 'anio':
                query += " WHERE YEAR(V.Fecha) = ?"
                params.append(fecha_dt.year)
        except ValueError:
            flash("Formato de fecha inválido", "danger")

    cursor.execute(query, params)
    ventas = cursor.fetchall()
    conn.close()

    # Se debe devolver la plantilla y pasar los datos de las ventas a la vista
    return render_template('admin_ventas.html', ventas=ventas)


@app.route('/empleados', methods=['GET', 'POST'])
def empleados():
    if 'usuario' not in session or session.get('rol') != 'admin':
        flash('Acceso solo para administradores')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener empleados
    cursor.execute("SELECT Id_Empleado, Nombre, Apellido, Salario FROM Empleados")
    empleados = cursor.fetchall()

    # Agregar un nuevo empleado
    if request.method == 'POST' and 'agregar_empleado' in request.form:
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        salario = request.form['salario']
        
        cursor.execute("""
            INSERT INTO Empleados (Nombre, Apellido, Salario)
            VALUES (?, ?, ?)
        """, (nombre, apellido, salario))
        conn.commit()
        flash('Empleado agregado correctamente', 'success')
        return redirect(url_for('empleados'))

    # Modificar datos de un empleado
    if request.method == 'POST' and 'modificar_empleado' in request.form:
        empleado_id = request.form['empleado_id']
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        # Aquí asignamos un sueldo fijo, por ejemplo, 3000
        sueldo_fijo = 3000
        
        # Actualizamos la base de datos con el sueldo fijo
        cursor.execute("""
            UPDATE Empleados
            SET Nombre = ?, Apellido = ?, Salario = ?
            WHERE Id_Empleado = ?
        """, (nombre, apellido, sueldo_fijo, empleado_id))
        conn.commit()
        flash('Empleado modificado correctamente', 'success')
        return redirect(url_for('empleados'))

    # Eliminar empleado
    if request.method == 'POST' and 'eliminar_empleado' in request.form:
        empleado_id = request.form['empleado_id']
        cursor.execute("""
            DELETE FROM Empleados
            WHERE Id_Empleado = ?
        """, (empleado_id,))
        conn.commit()
        flash('Empleado eliminado correctamente', 'success')
        return redirect(url_for('empleados'))

    conn.close()
    return render_template('empleados.html', empleados=empleados)




@app.route('/pago_sueldo', methods=['GET', 'POST'])
def pago_sueldo():
    if 'usuario' not in session or session.get('rol') != 'admin':
        flash('Acceso solo para administradores')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener empleados
    cursor.execute("SELECT Id_Empleado, Nombre, Apellido FROM Empleados")
    empleados = cursor.fetchall()

    if request.method == 'POST':
        empleado_id = request.form['empleado_id']
        monto = request.form['monto']
        detalle = request.form['detalle']

        # Realizar pago y actualizar tabla de pagos
        try:
            cursor.execute("""
                INSERT INTO Pagos (Empleado_Id, Monto, Detalle)
                VALUES (?, ?, ?)
            """, (empleado_id, monto, detalle))
            conn.commit()
            flash('Pago realizado correctamente', 'success')
            return redirect(url_for('home'))  # Redirige al Home después de realizar el pago
        except Exception as e:
            flash(f'Error al realizar el pago: {e}', 'danger')

    conn.close()
    return render_template('pago_sueldo.html', empleados=empleados)

# Ruta para la gestión de proveedores
@app.route('/compras_proveedores', methods=['GET', 'POST'])
def compras_proveedores():
    if 'usuario' not in session or session.get('rol') != 'admin':
        flash('Acceso solo para administradores')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        id_proveedor = request.form['proveedor']
        id_producto = request.form['producto']
        cantidad = int(request.form['cantidad'])
        precio_compra = float(request.form['precio_unitario'])

        # Insertar la compra en la tabla Compras_Proveedor
        cursor.execute("""
            INSERT INTO Compras_Proveedor (Id_Proveedor, Id_Producto, Cantidad, Precio_Compra)
            VALUES (?, ?, ?, ?)
        """, (id_proveedor, id_producto, cantidad, precio_compra))

        # Actualizar el stock en Inventario
        cursor.execute("""
            UPDATE Inventario
            SET Cantidad = Cantidad + ?
            WHERE Id_Producto = ?
        """, (cantidad, id_producto))

        conn.commit()
        flash('Compra registrada exitosamente', 'success')

    # Traer compras existentes para mostrar en la tabla
    cursor.execute("""
        SELECT CP.Fecha, P.Nombre AS Proveedor, PR.Nombre AS Producto, CP.Cantidad, CP.Precio_Compra
        FROM Compras_Proveedor CP
        JOIN Proveedores P ON CP.Id_Proveedor = P.Id_Proveedor
        JOIN Productos PR ON CP.Id_Producto = PR.Id_Producto
        ORDER BY CP.Fecha DESC
    """)
    compras = cursor.fetchall()

    # Obtener proveedores y productos para el formulario
    cursor.execute("SELECT Id_Proveedor, Nombre FROM Proveedores")
    proveedores = cursor.fetchall()

    cursor.execute("SELECT Id_Producto, Nombre FROM Productos")
    productos = cursor.fetchall()

    conn.close()
    return render_template('compras_proveedores.html', compras=compras, proveedores=proveedores, productos=productos)

# --------------------------- INICIAR FLASK
if __name__ == '__main__':
    app.run(debug=True)
