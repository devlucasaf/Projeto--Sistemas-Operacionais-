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

def simular_chegada_aleatoria(tempo_atual):
    global REQUISICAO_ID_COUNTER
    novas_chegadas = []
    
    # !!!ALTERAR ISSO PARA GERAR FUNÇÕES ALEATÓRIAS
    if random.random() < 0:
        id_nova = REQUISICAO_ID_COUNTER
        REQUISICAO_ID_COUNTER += 1
        
        # Geração de requisições aleatórias para testes
        tipo = random.choice(["visao_computacional", "nlp", "fala", "analise_imagem"])
        prioridade = random.randint(1, 3) # 1 - Maior prioradade | 10 - Menor prioridade
        tempo_exec = random.randint(1, 10) 
        
        nova_req = {
            "id": id_nova,
            "tipo": tipo,
            "prioridade": prioridade,
            "tempo_exec": tempo_exec,
            "chegada": tempo_atual,
        }
        novas_chegadas.append(nova_req)
        print(f"Requisição {id_nova} (P:{prioridade}, T_exec:{tempo_exec}) CHEGOU.")
            
    return novas_chegadas