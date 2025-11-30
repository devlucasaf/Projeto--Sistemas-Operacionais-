import time 
import random
import psutil

comeco = time.perf_counter()

SERVIDORES_CONFIG = [
    {"id": 1, "capacidade_max": 3, "capacidade_uso": 0},
    {"id": 2, "capacidade_max": 2, "capacidade_uso": 0},
    {"id": 3, "capacidade_max": 1, "capacidade_uso": 0},
]

# Iniciais = Tempo de chegada 0
REQUISIÇÕES_INICIAIS = [
    {"id": 101, "tipo": "visao_computacional", "prioridade": 1, "tempo_exec": 8, "chegada": 0},
    {"id": 102, "tipo": "nlp", "prioridade": 3, "tempo_exec": 3, "chegada": 0},
    {"id": 103, "tipo": "vaz", "prioridade": 1, "tempo_exec": 5, "chegada": 0},
    {"id": 104, "tipo": "nlp", "prioridade": 2, "tempo_exec": 4, "chegada": 0},
    {"id": 105, "tipo": "imagem", "prioridade": 1, "tempo_exec": 9, "chegada": 0},
    
]

# Contador global para IDs de novas requisições aleatórias
REQUISICAO_ID_COUNTER = 106
