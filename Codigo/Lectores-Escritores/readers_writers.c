#include <pthread.h>
#include <semaphore.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <time.h>
#include <math.h>

sem_t sem_escritura;     // Controla el acceso a los libros
sem_t sem_turno;         // Garantiza el orden FIFO (justicia)
pthread_mutex_t mutex;   // Protege el conteo de lectores activos
int lectores_activos = 0;
int libros = 1;          // Recurso compartido: cantidad o estado de los libros

// ====== Variables para métricas ======
double *tiempos_espera;
int total_hilos;
int operaciones_completadas = 0;
pthread_mutex_t mutex_metricas;

// Función auxiliar para obtener tiempo en segundos
double get_time() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

void *lector(void *arg)
{
    int id = *((int *)arg);
    sleep(rand() % 3); // Simula llegada aleatoria

    double inicio_espera = get_time();

    sem_wait(&sem_turno); // Espera su turno (FIFO)
    pthread_mutex_lock(&mutex);
    lectores_activos++;
    if (lectores_activos == 1)
        sem_wait(&sem_escritura); // El primer lector bloquea a los escritores
    pthread_mutex_unlock(&mutex);
    sem_post(&sem_turno); // Libera el turno

    double fin_espera = get_time();
    tiempos_espera[id - 1] = fin_espera - inicio_espera;

    printf("📖 Lector %d leyó los libros = %d\n", id, libros);
    sleep(1); // Tiempo de lectura

    pthread_mutex_lock(&mutex);
    lectores_activos--;
    if (lectores_activos == 0)
        sem_post(&sem_escritura); // El último lector libera a los escritores
    pthread_mutex_unlock(&mutex);

    pthread_mutex_lock(&mutex_metricas);
    operaciones_completadas++;
    pthread_mutex_unlock(&mutex_metricas);

    return NULL;
}

void *escritor(void *arg)
{
    int id = *((int *)arg);
    sleep(rand() % 3); // Simula llegada aleatoria

    double inicio_espera = get_time();

    sem_wait(&sem_turno);     // Espera su turno (FIFO)
    sem_wait(&sem_escritura); // Espera permiso para escribir
    sem_post(&sem_turno);     // Libera el turno

    double fin_espera = get_time();
    tiempos_espera[id - 1] = fin_espera - inicio_espera;

    libros += 3; // Modifica el recurso
    printf("✍️  Escritor %d actualizó los libros a %d\n", id, libros);
    sleep(1); // Tiempo de escritura

    sem_post(&sem_escritura); // Libera el recurso

    pthread_mutex_lock(&mutex_metricas);
    operaciones_completadas++;
    pthread_mutex_unlock(&mutex_metricas);

    return NULL;
}

int main()
{
    int n_lectores, n_escritores;
    srand(time(NULL));

    printf("=== Simulación Lectores–Escritores (FIFO justa, con métricas) ===\n");
    printf("Ingrese número de lectores: ");
    scanf("%d", &n_lectores);
    printf("Ingrese número de escritores: ");
    scanf("%d", &n_escritores);

    total_hilos = n_lectores + n_escritores;
    tiempos_espera = malloc(sizeof(double) * total_hilos);

    pthread_t lectores[n_lectores], escritores[n_escritores];
    int id_lectores[n_lectores], id_escritores[n_escritores];

    pthread_mutex_init(&mutex, NULL);
    pthread_mutex_init(&mutex_metricas, NULL);
    sem_init(&sem_escritura, 0, 1);
    sem_init(&sem_turno, 0, 1);

    double inicio_total = get_time();

    // Crear hilos lectores
    for (int i = 0; i < n_lectores; i++) {
        id_lectores[i] = i + 1;
        pthread_create(&lectores[i], NULL, lector, &id_lectores[i]);
    }

    // Crear hilos escritores
    for (int i = 0; i < n_escritores; i++) {
        id_escritores[i] = n_lectores + i + 1;
        pthread_create(&escritores[i], NULL, escritor, &id_escritores[i]);
    }

    // Esperar finalización
    for (int i = 0; i < n_lectores; i++)
        pthread_join(lectores[i], NULL);
    for (int i = 0; i < n_escritores; i++)
        pthread_join(escritores[i], NULL);

    double fin_total = get_time();
    double duracion_total = fin_total - inicio_total;

    // ==== Cálculo de métricas ====
    double suma = 0, suma_cuadrados = 0;
    for (int i = 0; i < total_hilos; i++) {
        suma += tiempos_espera[i];
        suma_cuadrados += tiempos_espera[i] * tiempos_espera[i];
    }

    double promedio_espera = suma / total_hilos;
    double varianza = (suma_cuadrados / total_hilos) - (promedio_espera * promedio_espera);
    double fairness = sqrt(varianza);
    double throughput = operaciones_completadas / duracion_total;
    double overhead = promedio_espera / total_hilos;

    printf("\n=== MÉTRICAS DEL ESCENARIO ===\n");
    printf("⏱ Duración total: %.3f s\n", duracion_total);
    printf("📊 Tiempo promedio de espera por recurso: %.3f s\n", promedio_espera);
    printf("⚙️  Throughput: %.3f operaciones/s\n", throughput);
    printf("⚖️  Fairness (desviación estándar): %.3f s\n", fairness);
    printf("🔁 Overhead de sincronización: %.6f s\n", overhead);

    printf("\nCantidad final de libros: %d\n", libros);
    printf("=== Fin de la simulación ===\n");

    // Liberar recursos
    pthread_mutex_destroy(&mutex);
    pthread_mutex_destroy(&mutex_metricas);
    sem_destroy(&sem_escritura);
    sem_destroy(&sem_turno);
    free(tiempos_espera);

    return 0;
}
