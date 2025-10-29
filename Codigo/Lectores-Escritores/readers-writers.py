#!/usr/bin/env python3
"""
Simulación Lectores–Escritores (FIFO justa) CON métricas.
Lectores y Escritores tienen IDs independientes (1..N cada uno).
Ejecutar: python3 readers-writers.py
"""

import threading
import time
import random
import math
import sys

# -----------------------
# Semáforos y locks
# -----------------------
sem_escritura = threading.Semaphore(1)  # controla acceso exclusivo a 'libros'
sem_turno = threading.Semaphore(1)      # garantiza un turno (cola simple)
mutex = threading.Lock()                # protege 'lectores_activos'
metricas_lock = threading.Lock()

# Estado del recurso
lectores_activos = 0
libros = 1

# -----------------------
# Variables de métricas (separadas por tipo)
# -----------------------
tiempos_espera_lectores = []   # index 0..n_lectores-1
tiempos_espera_escritores = [] # index 0..n_escritores-1
operaciones_completadas = 0

# helper para tiempo monotónico en segundos
def now():
    return time.monotonic()

# -----------------------
# Funciones de hilo
# -----------------------
def lector(arg_id):
    global lectores_activos, libros, operaciones_completadas

    id = arg_id
    # llegada aleatoria (simula llegada)
    time.sleep(random.randint(0, 2))

    inicio_espera = now()

    # Espera su turno FIFO
    sem_turno.acquire()
    with mutex:
        lectores_activos += 1
        if lectores_activos == 1:
            # primer lector bloquea a escritores
            sem_escritura.acquire()
    # libera turno
    sem_turno.release()

    fin_espera = now()
    # registrar en la lista de lectores (id relativo 1..n_lectores)
    tiempos_espera_lectores[id - 1] = fin_espera - inicio_espera

    # sección crítica (lectura)
    print(f"📖 Lector {id} leyó los libros = {libros}")
    time.sleep(1)  # tiempo de lectura

    # salida
    with mutex:
        lectores_activos -= 1
        if lectores_activos == 0:
            sem_escritura.release()

    # contabilizar operación terminada
    with metricas_lock:
        operaciones_completadas += 1


def escritor(arg_id):
    global libros, operaciones_completadas

    id = arg_id
    # llegada aleatoria
    time.sleep(random.randint(0, 2))

    inicio_espera = now()

    # cola FIFO
    sem_turno.acquire()
    sem_escritura.acquire()
    # libera turno (ahora el escritor tiene la exclusividad)
    sem_turno.release()

    fin_espera = now()
    # registrar en la lista de escritores (id relativo 1..n_escritores)
    tiempos_espera_escritores[id - 1] = fin_espera - inicio_espera

    # sección crítica (escritura)
    libros += 3
    print(f"✍️  Escritor {id} actualizó los libros a {libros}")
    time.sleep(1)  # tiempo de escritura

    # libera recurso
    sem_escritura.release()

    # contabilizar operación terminada
    with metricas_lock:
        operaciones_completadas += 1


# -----------------------
# Función principal
# -----------------------
def main():
    global tiempos_espera_lectores, tiempos_espera_escritores, operaciones_completadas, libros, lectores_activos

    # pedir número de lectores/escritores (igual que en C)
    try:
        n_lectores = int(input("Ingrese número de lectores: ").strip())
        n_escritores = int(input("Ingrese número de escritores: ").strip())
    except Exception:
        print("Entrada inválida. Usa números enteros.")
        sys.exit(1)

    # inicializar listas de métricas por tipo
    tiempos_espera_lectores = [0.0] * n_lectores
    tiempos_espera_escritores = [0.0] * n_escritores

    lectores_threads = []
    escritores_threads = []

    # reiniciar estado global como en C
    lectores_activos = 0
    libros = 1
    operaciones_completadas = 0

    # seed
    random.seed(int(time.time()))

    t_inicio_total = now()

    # crear lectores (IDs 1..n_lectores)
    for i in range(n_lectores):
        tid = i + 1
        th = threading.Thread(target=lector, args=(tid,))
        lectores_threads.append(th)
        th.start()

    # crear escritores (IDs 1..n_escritores)
    for i in range(n_escritores):
        tid = i + 1
        th = threading.Thread(target=escritor, args=(tid,))
        escritores_threads.append(th)
        th.start()

    # join
    for th in lectores_threads:
        th.join()
    for th in escritores_threads:
        th.join()

    t_fin_total = now()
    duracion_total = t_fin_total - t_inicio_total

    # ---- combinar las métricas para cálculo global ----
    tiempos_combinados = tiempos_espera_lectores + tiempos_espera_escritores
    total_hilos = len(tiempos_combinados)

    suma = sum(tiempos_combinados)
    suma_cuadrados = sum(x * x for x in tiempos_combinados)
    promedio_espera = suma / total_hilos if total_hilos > 0 else 0.0
    varianza = (suma_cuadrados / total_hilos - promedio_espera * promedio_espera) if total_hilos > 0 else 0.0
    fairness = math.sqrt(varianza) if varianza > 0 else 0.0
    throughput = operaciones_completadas / duracion_total if duracion_total > 0 else 0.0
    overhead = promedio_espera / total_hilos if total_hilos > 0 else 0.0

    print("\n=== MÉTRICAS DEL ESCENARIO ===")
    print(f"⏱ Duración total: {duracion_total:.3f} s")
    print(f"📊 Tiempo promedio de espera por recurso: {promedio_espera:.3f} s")
    print(f"⚙️  Throughput: {throughput:.3f} operaciones/s")
    print(f"⚖️  Fairness (desviación estándar): {fairness:.3f} s")
    print(f"🔁 Overhead de sincronización: {overhead:.6f} s")
    print(f"\nCantidad final de libros: {libros}")
    print("=== Fin de la simulación ===")

if __name__ == "__main__":
    main()
