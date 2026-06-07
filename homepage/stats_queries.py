import mysql.connector
conn = mysql.connector.connect(host='localhost', port=3306, user='root', password='', database='flask_db')
cursor = conn.cursor()

print('===== 1. FACE RECOGNITION STATS (usuarios.rostro_facial) =====')
cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rostro_facial IS NOT NULL AND rostro_facial != ''")
face_registered = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(*) FROM usuarios')
total_users = cursor.fetchone()[0]
face_not_registered = total_users - face_registered
print(f'  Total users: {total_users}')
print(f'  Face registered: {face_registered}')
print(f'  Face NOT registered: {face_not_registered}')
if total_users > 0:
    print(f'  Face registration rate: {face_registered/total_users*100:.1f}%')
print()

print('===== 2. WASTE RECOGNITION STATS (registros_clasificacion) =====')
cursor.execute('SELECT COUNT(*) FROM registros_clasificacion')
total_classifications = cursor.fetchone()[0]
print(f'  Total classifications: {total_classifications}')
print()
cursor.execute("SELECT residuo_detectado, COUNT(*) AS cnt FROM registros_clasificacion WHERE residuo_detectado IS NOT NULL GROUP BY residuo_detectado ORDER BY cnt DESC")
print('  Breakdown by residuo_detectado:')
for row in cursor:
    print(f'    {str(row[0]):25s} -> {row[1]} ({row[1]/total_classifications*100:.1f}%)')
cursor.execute("SELECT COUNT(*) FROM registros_clasificacion WHERE residuo_detectado IS NULL OR residuo_detectado = ''")
null_residuo = cursor.fetchone()[0]
if null_residuo > 0:
    print(f'    (null/empty)            -> {null_residuo} ({null_residuo/total_classifications*100:.1f}%)')
print()

print('===== 3. SEGREGATION CORRECT/INCORRECT STATS =====')
cursor.execute('SELECT es_correcto, COUNT(*) AS cnt FROM registros_clasificacion GROUP BY es_correcto ORDER BY es_correcto')
for row in cursor:
    label = 'Correct (1)' if row[0] == 1 else 'Incorrect (0)'
    print(f'  {label:20s}: {row[1]} ({row[1]/total_classifications*100:.1f}%)')
print()
print('  Breakdown by categoria_asignada vs categoria_correcta:')
cursor.execute("SELECT categoria_asignada, COUNT(*) AS cnt FROM registros_clasificacion WHERE categoria_asignada IS NOT NULL AND categoria_asignada != '' GROUP BY categoria_asignada ORDER BY cnt DESC")
print('  categoria_asignada:')
for row in cursor:
    print(f'    {str(row[0]):25s} -> {row[1]}')
cursor.execute("SELECT categoria_correcta, COUNT(*) AS cnt FROM registros_clasificacion WHERE categoria_correcta IS NOT NULL AND categoria_correcta != '' GROUP BY categoria_correcta ORDER BY cnt DESC")
print('  categoria_correcta:')
for row in cursor:
    print(f'    {str(row[0]):25s} -> {row[1]}')
print()

print('===== 4. ECOLOGICAL POINTS / BIN-RELATED STATS =====')
print('(No separate table found for puntos_ecologicos, canecas, or contenedores)')
print()
print('  Checking container_color in registros_clasificacion:')
cursor.execute("SELECT container_color, COUNT(*) AS cnt FROM registros_clasificacion WHERE container_color IS NOT NULL AND container_color != '' GROUP BY container_color ORDER BY cnt DESC")
bin_data = cursor.fetchall()
if bin_data:
    for row in bin_data:
        print(f'    {str(row[0]):25s} -> {row[1]}')
else:
    print('    No container_color data found.')
print()
cursor.execute("SELECT COUNT(*) FROM registros_clasificacion WHERE container_color IS NOT NULL AND container_color != ''")
bin_total = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(*) FROM registros_clasificacion')
total = cursor.fetchone()[0]
if total > 0:
    print(f'  Total records with container_color: {bin_total} / {total} ({bin_total/total*100:.1f}%)')

conn.close()
