import threading
import time
import random
import keyboard
import queue # módulo queue para get y put, seguro de usar.
import math   # para la desviación estándar (fairness)

BARBEROS = 1 # monto de BARBEROS, se puede cambiar.
CLIENTES = 50 # monto de CLIENTES, se puede cambiar.
ASIENTOS = 5 # monto de ASIENTOS en la sala de espera, se puede cambiar.
ESPERAS = 1 # usar múltiplo de random.random() para que CLIENTES lleguen.

def espera(): # simula el arribo de CLIENTES a tiempo al azar.
	time.sleep(ESPERAS * random.random())

# ------------------ MÉTRICAS ------------------
t0 = time.perf_counter()     # inicio de la simulación
served_count = 0             # atendidos (para throughput)
total_wait_time = 0.0        # suma de esperas (para "tiempo de espera por recurso")

# Fairness con Welford (std dev sin listas)
fair_n = 0
fair_mean = 0.0
fair_M2 = 0.0

# Overhead de sincronización = tiempo total que el barbero pasa bloqueado en Condition.wait()
sync_overhead = 0.0

metrics_lock = threading.Lock()  # proteger acumuladores (cambios mínimos)

class Barbero(threading.Thread):
	condicion = threading.Condition() # con esto se despierte/duerme el barbero.
	alto_completo = threading.Event() # para cuando todos los CLIENTES han sido atendidos.

	def __init__(self, ID):
		super().__init__()
		self.ID = ID	# ID del barbero en caso de agregar más de 1.

	def run(self):
		global served_count, total_wait_time, fair_n, fair_mean, fair_M2, sync_overhead
		while True:
			try:	# usar try/except es mejor que revisar tamaño de queue; queue.qsize() no es seguro con hilos.
				cliente_actual = sala_espera.get(block=False) # no bloquear al tomar de la queue.
			except queue.Empty: # se lanza cuando no hay clientes en la sala_espera.
				if self.alto_completo.is_set(): # alto_completo se activa sólo cuando CLIENTES han sido atendidos completamente.
					return
				print(f"El barbero {self.ID} está durmiendo... Zzz... Zzz... ")
				# medir overhead de sincronización (tiempo bloqueado en wait)
				tw0 = time.perf_counter()
				with self.condicion:
					self.condicion.wait() # duerme y espera para que el cliente lo despierte.
				tw1 = time.perf_counter()
				with metrics_lock:
					sync_overhead += (tw1 - tw0)
			else:
				# calcular tiempo de espera del cliente desde que llegó hasta que el barbero lo toma
				wait = time.perf_counter() - cliente_actual.t_llegada
				with metrics_lock:
					total_wait_time += wait
					# actualizar fairness (desv. estándar) con Welford
					fair_n += 1
					delta = wait - fair_mean
					fair_mean += delta / fair_n
					fair_M2 += delta * (wait - fair_mean)

				# corta el cabello (el propio cliente simula el tiempo y se marca atendido)
				cliente_actual.cortar(self.ID)

				# contabilizar atendidos (para throughput)
				with metrics_lock:
					served_count += 1

class Cliente(threading.Thread):
	DURACION_CORTE = 5

	def __init__(self, ID):
		super().__init__()
		self.ID = ID

	def corte(self): # simula el corte de cabello.
		time.sleep(self.DURACION_CORTE * random.random())

	def cortar(self, id_barbero):  # llamado desde el hilo Barbero.
		print(f"El barbero {id_barbero} está cortando el cabello del cliente {self.ID}")
		self.corte() # simula el servicio
		print(f"El Barbero {id_barbero} terminó de cortar el cabello al cliente {self.ID}")
		self.atendido.set() # "set" atendido para que el cliente deje la barbería.

	def run(self):
		self.atendido = threading.Event()
		self.t_llegada = time.perf_counter()  # timestamp de llegada (para la métrica de espera)

		try:	# revisa si hay espacio en sala_espera.
			sala_espera.put(self, block=False)
		except queue.Full: # sin espacio en sala_espera se va.
			print(f"La sala de espera está llena, {self.ID} se fue...")
			return

		print(f"El cliente {self.ID} se sentó en la sala de espera.")
		with Barbero.condicion:
			Barbero.condicion.notify(1) # despierta al barbero.

		self.atendido.wait() # espera a ser atendido y luego se retira.


if __name__ == "__main__":
	TODOS_CLIENTES = []          # lista de todos CLIENTES a atender.
	sala_espera = queue.Queue(ASIENTOS) # tamaño máximo de ASIENTOS.

	for i in range(BARBEROS): # crea el/los hilos barbero.
		hilo_barbero = Barbero(i)
		hilo_barbero.start()

	for i in range(CLIENTES): # crea el hilo cliente (llegadas aleatorias).
		espera()
		cliente = Cliente(i)
		TODOS_CLIENTES.append(cliente)
		cliente.start()

	for cliente in TODOS_CLIENTES:
		cliente.join()  # espera la salida de todos los CLIENTES.

	time.sleep(0.1) # darle tiempo suficiente al barbero para limpiar tras el último cliente.
	Barbero.alto_completo.set() # permite finalizar el trabajo del/los barbero(s).
	with Barbero.condicion:
		Barbero.condicion.notify_all() # despierta en caso de que alguno esté dormido para terminar.
	
	# ------------------ IMPRESIÓN DE MÉTRICAS ------------------
	T = time.perf_counter() - t0
	with metrics_lock:
		atendidos = served_count
		avg_wait = (total_wait_time / atendidos) if atendidos > 0 else 0.0
		fairness = math.sqrt(fair_M2 / fair_n) if fair_n > 1 else 0.0
		overhead_sync = sync_overhead
	throughput = (atendidos / T) if T > 0 else 0.0

	print("\n=== MÉTRICAS ===")
	print(f"throughput: {throughput:.3f} clientes/seg")
	print(f"tiempo de espera por recurso: {avg_wait:.3f} s")
	print(f"fairness: {fairness:.3f} s (desviación estándar de esperas)")
	print(f"overhead de sincronización: {overhead_sync:.3f} s")

	# Breve explicación de cada métrica en este contexto:
	print("\nNotas:")
	print("- throughput: clientes atendidos por segundo durante toda la simulación.")
	print("- tiempo de espera por recurso: tiempo promedio que un cliente esperó desde que llegó hasta que el barbero lo tomó.")
	print("- fairness: qué tan parecidos fueron los tiempos de espera entre clientes (desviación estándar: menor = más equitativo).")
	print("- overhead de sincronización: tiempo total que el barbero pasó bloqueado en Condition.wait() (durmiendo por falta de trabajo).")

	print("\nLa Barbería está cerrada.")
	keyboard.wait("esc")
