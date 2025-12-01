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

def passo_simulação(servidores, fila_execucao, fila_concluídas, tempo_atual):
    tarefas_concluidas = []

    # Workers executam e diminuem o tempo restante
    for req in list(fila_execucao): 
        req['tempo_restante'] -= 1
        
        # Tarefas que são completas vão para uma lista separada
        if req['tempo_restante'] <= 0:
            tarefas_concluidas.append(req)
            fila_execucao.remove(req)
            
    # Verificação da capacidade dos servidores
    for req_concluida in tarefas_concluidas:
        servidor_id = req_concluida['servidor_id']
        for s in servidores:
            if s['id'] == servidor_id:
                s['capacidade_uso'] -= 1 # Capacidade liberada
                break
        
        # Cálculo de tempo de resposta para monitoramento de cada processo
        tempo_resposta = tempo_atual - req_concluida['chegada']
        req_concluida['tempo_resposta'] = tempo_resposta
        req_concluida['estado'] = 'concluída'
        fila_concluídas.append(req_concluida)
        
        print(f"Requisição {req_concluida['id']} CONCLUÍDA (Resposta: {tempo_resposta}s). Servidor {servidor_id} liberado.")

    return len(tarefas_concluidas)

def main_simulation_loop(politica, tempo_maximo=30):
    # Reinicia o estado para cada simulação
    servidores = [d.copy() for d in SERVIDORES_CONFIG]
    fila_pendente = [d.copy() for d in REQUISIÇÕES_INICIAIS]
    fila_execucao = []
    fila_concluídas = []
    
    ultimo_servidor_rr_id = None # Para rastrear o último usado no Round Robin
    
    print(f"{'='*60}")
    print(f"SIMULAÇÃO: POLÍTICA '{politica}'")
    print(f"Servidores Ativos: {len(servidores)} | Capacidade Total: {sum(s['capacidade_max'] for s in servidores)}")
    print(f"{'='*60}")

    tempo_atual = 0
    while tempo_atual < tempo_maximo:
        print(f"Tempo (TICK): {tempo_atual}")
        
        novas_req = simular_chegada_aleatoria(tempo_atual)
        fila_pendente.extend(novas_req)
        
        # Tenta escalonar enquanto houver tarefas pendentes e capacidade livre no cluster
        capacidade_livre = sum(s['capacidade_max'] - s['capacidade_uso'] for s in servidores)
        
        while fila_pendente and capacidade_livre > 0:
            
            requisicao = None
            req_idx = -1
            
            if politica == 'PRIORIDADE':
                # Prioriza o menor valor de prioridade (1 = alta)
                req_idx = min(range(len(fila_pendente)), key=lambda i: fila_pendente[i]['prioridade'])
            elif politica == 'SJF':
                # Prioriza o menor tempo de execução
                req_idx = min(range(len(fila_pendente)), key=lambda i: fila_pendente[i]['tempo_exec'])
            else: # ROUND ROBIN 
                req_idx = 0 
                
            requisicao = fila_pendente.pop(req_idx)

            servidor_alvo = None
            if politica == 'RR':
                # Round Robin: Encontra o próximo servidor na ordem cíclica que tenha capacidade
                servidores_ordenados = sorted(servidores, key=lambda s: s['id'])
                start_index = 0
                if ultimo_servidor_rr_id is not None:
                    # Tenta encontrar o índice do servidor após o último usado
                    try:
                        last_index = next(i for i, s in enumerate(servidores_ordenados) if s['id'] == ultimo_servidor_rr_id)
                        start_index = (last_index + 1) % len(servidores_ordenados)
                    except StopIteration:
                        pass
                
                # Procura a partir do índice de início
                for i in range(len(servidores_ordenados)):
                    idx = (start_index + i) % len(servidores_ordenados)
                    servidor = servidores_ordenados[idx]
                    if servidor['capacidade_uso'] < servidor['capacidade_max']:
                        servidor_alvo = servidor
                        ultimo_servidor_rr_id = servidor['id']
                        break
                        
            else: # PRIORIDADE: Encontra o primeiro servidor com capacidade livre e escalona o processo selecionado
                for s in servidores:
                    if s['capacidade_uso'] < s['capacidade_max']:
                        servidor_alvo = s
                        break
            
            if servidor_alvo:
                servidor_alvo['capacidade_uso'] += 1
                requisicao['servidor_id'] = servidor_alvo['id']
                requisicao['tempo_restante'] = requisicao['tempo_exec']
                requisicao['tempo_inicio'] = tempo_atual
                fila_execucao.append(requisicao)
                capacidade_livre -= 1 # Atualiza a capacidade livre para o próximo loop
                
                print(f"ESCALONADO: Requisição {requisicao['id']} para Servidor {servidor_alvo['id']}.")
            else:
                # Se a requisição foi selecionada, mas a capacidade foi ocupada no meio do loop, volta para a fila
                fila_pendente.append(requisicao)
                print(f"RE-ENFILEIRADO: Requisição {requisicao['id']}. Cluster saturado.")
                break # Sai do loop de escalonamento
            
        tarefas_concluidas = passo_simulação(servidores, fila_execucao, fila_concluídas, tempo_atual)

        uso_servidores = [f"S{s['id']} : {s['capacidade_uso']}/{s['capacidade_max']}" for s in servidores]
        print(f"{'='*60}")
        print(f"STATUS: Uso: [{', '.join(uso_servidores)}] | Pendentes: {len(fila_pendente)} | Executando: {len(fila_execucao)}")

        # Condição de parada (todas as requisições, incluindo as aleatórias, terminaram)
        if not fila_pendente and not fila_execucao:
            break
            
        tempo_atual += 1

    final = time.perf_counter()
    total = final - comeco 

    print(f"{'='*60}")
    print(f"SIMULAÇÃO CONCLUÍDA: {politica}")
    print(f"Tempo decorrido: {total:.8f}")
    print(f"CPU gasta: {psutil.cpu_percent(interval=1)}%")
    print(f"Tempo Total (Ticks): {tempo_atual}")
    print(f"Requisições Concluídas: {len(fila_concluídas)}")
    print(f"{'='*60}")
    
    return fila_concluídas


# 1. Simulação Round Robin (RR)
main_simulation_loop(politica='RR')

# 2. Simulação Shortest Job First (SJF)
# main_simulation_loop(politica='SJF')

# 3. Simulação Prioridade (PRIORIDADE)
# main_simulation_loop(politica='PRIORIDADE')