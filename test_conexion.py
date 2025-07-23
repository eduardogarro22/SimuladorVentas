import pyodbc

try:
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=EDU\\SQLEXPRESS;"
        "DATABASE=Fabrica_de_prueba;"
        "Trusted_Connection=yes;"
    )
    print("✅ Conexión exitosa, MR. Edu!")
except Exception as e:
    print("❌ Error de conexión:")
    print(e)
