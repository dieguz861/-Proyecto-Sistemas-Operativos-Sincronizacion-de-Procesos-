import threading
import time
import random
from collections import deque

# --- Configuración de la Simulación ---
TAMANO_BUFFER = 10
NUM_PRODUCTORES = 10
NUM_CONSUMIDORES = 2 
ITEMS_A_PRODUCIR_POR_PRODUCTOR = 5 # Cada productor creará esta cantidad de items

# --- Variables Globales para Métricas ---
total_items_producidos = 0
total_items_consumidos = 0
total_tiempo_espera_productores = 0.0
total_tiempo_espera_consumidores = 0.0
productores_data = [[] for _ in range(NUM_PRODUCTORES)] # Lista de listas para guardar tiempos de espera
consumidores_data = [[] for _ in range(NUM_CONSUMIDORES)] # Lista de listas para guardar tiempos de espera


class MonitorProductorConsumidor:
    """
    Esta clase implementa el Monitor.
    Usa un Lock para la exclusión mutua y dos variables de condición.
    """
    def __init__(self, tamano_maximo):
        self.buffer = deque()
        self.tamano_maximo = tamano_maximo
        
        # El Lock principal del monitor
        self.lock = threading.Lock()
        
        # Variables de condición
        self.cond_no_lleno = threading.Condition(self.lock)
        self.cond_no_vacio = threading.Condition(self.lock)

    def producir(self, item, productor_id):
        global total_tiempo_espera_productores
        
        with self.lock: # Adquiere el lock (Entra al monitor)
            
            start_wait = time.time()
            while len(self.buffer) == self.tamano_maximo:
                # Buffer lleno, esperar
                self.cond_no_lleno.wait()
            
            # --- Métrica: Tiempo de Espera ---
            tiempo_espera = time.time() - start_wait
            total_tiempo_espera_productores += tiempo_espera
            productores_data[productor_id].append(tiempo_espera) # Guardamos la espera individual
            
            # Producir el item
            self.buffer.append(item)
            print(f"Productor {productor_id}: Produce {item} (Buffer: {len(self.buffer)})")
            
            # Notificar a un consumidor que hay un item disponible
            self.cond_no_vacio.notify()

        # Sale del monitor (Libera el lock automáticamente con 'with')

    # ↓↓↓ CAMBIO 1: Añadido "consumidor_thread" como argumento
    def consumir(self, consumidor_id, consumidor_thread):
        global total_tiempo_espera_consumidores
        
        with self.lock: # Adquiere el lock (Entra al monitor)
            
            start_wait = time.time()
            while len(self.buffer) == 0:
                
                # ↓↓↓ CAMBIO 2: Comprobar si debemos parar ANTES de dormir
                if not consumidor_thread.running:
                    return None # Devolvemos None para señalar que hay que parar
                
                # Buffer vacío, esperar
                self.cond_no_vacio.wait()
            
            # --- Métrica: Tiempo de Espera ---
            tiempo_espera = time.time() - start_wait
            total_tiempo_espera_consumidores += tiempo_espera
            consumidores_data[consumidor_id].append(tiempo_espera) # Guardamos la espera individual

            # Consumir el item
            item = self.buffer.popleft()
            print(f"Consumidor {consumidor_id}: Consume {item} (Buffer: {len(self.buffer)})")
            
            # Notificar a un productor que hay espacio disponible
            self.cond_no_lleno.notify()
            
            return item
        
        # Sale del monitor (Libera el lock automáticamente con 'with')

# --- Hilos de Trabajo ---

class Productor(threading.Thread):
    def __init__(self, monitor, productor_id, items_a_producir):
        super().__init__()
        self.monitor = monitor
        self.productor_id = productor_id
        self.items_a_producir = items_a_producir

    def run(self):
        global total_items_producidos
        for i in range(self.items_a_producir):
            item = f"Item(P{self.productor_id}-{i})"
            time.sleep(random.uniform(0.1, 0.5)) # Simula el tiempo de "producir"
            self.monitor.producir(item, self.productor_id)
            with monitor.lock: # Usamos el lock del monitor para actualizar la variable global
                 total_items_producidos += 1


class Consumidor(threading.Thread):
    def __init__(self, monitor, consumidor_id):
        super().__init__()
        self.monitor = monitor
        self.consumidor_id = consumidor_id
        self.running = True

    def run(self):
        global total_items_consumidos
        while self.running:
            try:
                time.sleep(random.uniform(0.1, 0.6)) # Simula el tiempo de "consumir"
                
                # ↓↓↓ CAMBIO 3: Pasamos "self" al monitor
                item = self.monitor.consumir(self.consumidor_id, self)
                
                # Si el monitor devuelve None, es la señal para parar
                if item is None:
                    break # Salir del bucle 'while self.running'
                    
                with monitor.lock: # Usamos el lock del monitor para actualizar la variable global
                    total_items_consumidos += 1
            except Exception as e:
                # Esto no debería pasar, pero es bueno tenerlo
                print(f"Error en consumidor {self.consumidor_id}: {e}")
                break

    def stop(self):
        self.running = False
        # ↓↓↓ CAMBIO 4: Despertar a TODOS los hilos dormidos
        with self.monitor.cond_no_vacio:
            self.monitor.cond_no_vacio.notify_all()


# --- Función Principal (Simulación) ---

if __name__ == "__main__":
    
    print(f"Iniciando simulación: {NUM_PRODUCTORES} Productores, {NUM_CONSUMIDORES} Consumidores, Buffer: {TAMANO_BUFFER}")
    
    monitor = MonitorProductorConsumidor(TAMANO_BUFFER)
    productores = []
    consumidores = []

    # --- Métrica: Throughput (Tiempo Total) ---
    start_time_simulacion = time.time()

    # Crear e iniciar productores
    for i in range(NUM_PRODUCTORES):
        p = Productor(monitor, i, ITEMS_A_PRODUCIR_POR_PRODUCTOR)
        productores.append(p)
        p.start()

    # Crear e iniciar consumidores
    for i in range(NUM_CONSUMIDORES):
        c = Consumidor(monitor, i)
        consumidores.append(c)
        c.start()

    # Esperar a que todos los productores terminen
    for p in productores:
        p.join()

    print("--- Todos los productores han terminado. ---")

    # Asegurarse de que los consumidores terminen después de que no haya más items
    # Esperamos hasta que todos los items producidos sean consumidos
    total_items_objetivo = NUM_PRODUCTORES * ITEMS_A_PRODUCIR_POR_PRODUCTOR
    while True:
        with monitor.lock:
            if total_items_consumidos == total_items_objetivo:
                break
        time.sleep(0.1) # Pequeña espera para no saturar el lock

    print("--- Todos los items han sido consumidos. ---")

    # Detener hilos consumidores
    for c in consumidores:
        c.stop()
    for c in consumidores:
        c.join() # Ahora esto no se colgará

    end_time_simulacion = time.time()
    
    # --- Métrica: Cálculo Final ---
    tiempo_total_simulacion = end_time_simulacion - start_time_simulacion

    # --- PRESENTACIÓN DE MÉTRICAS ---
    print("\n\n" + "="*40)
    print("--- Resultados de la Simulación ---")
    print("="*40)
    print(f"Tiempo total de ejecución: {tiempo_total_simulacion:.4f} segundos")
    print(f"Total de items producidos: {total_items_producidos}")
    print(f"Total de items consumidos: {total_items_consumidos}")

    # 1. Throughput
    throughput = total_items_consumidos / tiempo_total_simulacion if tiempo_total_simulacion > 0 else 0
    print(f"\n[Métrica] Throughput: {throughput:.4f} items/segundo")

    # 2. Tiempo de Espera (Promedio)
    avg_espera_productor = total_tiempo_espera_productores / total_items_producidos if total_items_producidos > 0 else 0
    avg_espera_consumidor = total_tiempo_espera_consumidores / total_items_consumidos if total_items_consumidos > 0 else 0
    print(f"[Métrica] Tiempo de espera promedio (Productor): {avg_espera_productor:.6f} seg (Total: {total_tiempo_espera_productores:.4f} seg)")
    print(f"[Métrica] Tiempo de espera promedio (Consumidor): {avg_espera_consumidor:.6f} seg (Total: {total_tiempo_espera_consumidores:.4f} seg)")

    # 3. Fairness (Equidad)
    print("\n[Métrica] Fairness (Equidad) - Desglose por Hilo:")
    for i in range(NUM_PRODUCTORES):
        items = len(productores_data[i])
        avg_wait = sum(productores_data[i]) / items if items > 0 else 0
        print(f"  Productor {i}: {items} items, espera prom: {avg_wait:.6f} seg")
        
    for i in range(NUM_CONSUMIDORES):
        items = len(consumidores_data[i])
        avg_wait = sum(consumidores_data[i]) / items if items > 0 else 0
        print(f"  Consumidor {i}: {items} items, espera prom: {avg_wait:.6f} seg")

    # 4. Overhead de Sincronización
    print("\n[Métrica] Overhead de Sincronización:")
    print(f"  El 'Tiempo de espera total' ({total_tiempo_espera_productores + total_tiempo_espera_consumidores:.4f} seg) es el principal indicador del overhead.")
    print("  (Es el tiempo que los hilos pasaron 'dormidos' por contención, en lugar de trabajando)")
    





# --- PRESENTACIÓN DE MÉTRICAS ---
print("\n\n" + "="*40)
print("--- Resultados de la Simulación ---")
print("="*40)
print(f"Tiempo total de ejecución: {tiempo_total_simulacion:.4f} segundos")
print(f"Total de items producidos: {total_items_producidos}")
print(f"Total de items consumidos: {total_items_consumidos}")
print(f"[Métrica] Throughput: {throughput:.4f} items/segundo")
avg_espera_productor = total_tiempo_espera_productores / total_items_producidos if total_items_producidos > 0 else 0
avg_espera_consumidor = total_tiempo_espera_consumidores / total_items_consumidos if total_items_consumidos > 0 else 0
print(f"[Métrica] Tiempo de espera promedio (Productor): {avg_espera_productor:.6f} seg (Total: {total_tiempo_espera_productores:.4f} seg)")
print(f"[Métrica] Tiempo de espera promedio (Consumidor): {avg_espera_consumidor:.6f} seg (Total: {total_tiempo_espera_consumidores:.4f} seg)")

print(f"[Métrica] Fairness (Equidad) - Desglose por Hilo:")
print("\n[Métrica] Fairness (Equidad) - Desglose por Hilo:")
for i in range(NUM_PRODUCTORES):
    items = len(productores_data[i])
    avg_wait = sum(productores_data[i]) / items if items > 0 else 0
    print(f"  Productor {i}: {items} items, espera prom: {avg_wait:.6f} seg")
    
for i in range(NUM_CONSUMIDORES):
    items = len(consumidores_data[i])
    avg_wait = sum(consumidores_data[i]) / items if items > 0 else 0
    print(f"  Consumidor {i}: {items} items, espera prom: {avg_wait:.6f} seg")


# 5. Hit/Miss Ratio (Tasa de Acierto/Espera)
# Contamos cuántas veces la espera fue > 0 (un "miss")
# (Usamos un umbral pequeño por si hay esperas de 0.000001 seg)
UMBRAL_ESPERA = 0.0001 
total_esperas_productor = sum(1 for data in productores_data for t in data if t > UMBRAL_ESPERA)
total_esperas_consumidor = sum(1 for data in consumidores_data for t in data if t > UMBRAL_ESPERA)
    
total_esperas = total_esperas_productor + total_esperas_consumidor
total_accesos = total_items_producidos + total_items_consumidos # Total de intentos

miss_ratio = total_esperas / total_accesos if total_accesos > 0 else 0
hit_ratio = 1.0 - miss_ratio
    
print("\n[Métrica] Hit/Miss Ratio (Tasa de Acierto/Espera):")
print(f"  Total de accesos al buffer: {total_accesos}")
print(f"  Total de esperas (Misses):  {total_esperas} (Prod: {total_esperas_productor}, Cons: {total_esperas_consumidor})")
print(f"  Miss Ratio (Tasa de Espera): {miss_ratio * 100:.2f}%")
print(f"  Hit Ratio (Tasa de Acierto): {hit_ratio * 100:.2f}%")


# 4. Overhead de Sincronización 
print("\n[Métrica] Overhead de Sincronización:")
print("\n[Métrica] Overhead de Sincronización:")
print(f"  El 'Tiempo de espera total' ({total_tiempo_espera_productores + total_tiempo_espera_consumidores:.4f} seg) es el principal indicador del overhead.")
print("  (Es el tiempo que los hilos pasaron 'dormidos' por contención, en lugar de trabajando)")

