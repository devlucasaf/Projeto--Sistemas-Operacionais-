import time
import random
import psutil

SERVIDOR_COR = {
    1: "\033[91m",  # Vermelho
    2: "\033[92m",  # Verde
    3: "\033[94m",  # Azul
}
RESET = "\033[0m"

comeco = time.perf_counter()

SERVIDORES_CONFIG = [
    {"id": 1, "capacidade_max": 3, "capacidade_uso": 0},
    {"id": 2, "capacidade_max": 2, "capacidade_uso": 0},
    {"id": 3, "capacidade_max": 1, "capacidade_uso": 0},
]

REQUISIÇÕES_INICIAIS = [
    {"id": 101, "tipo": "visao_computacional", "prioridade": 1, "tempo_exec": 8, "chegada": 0},
    {"id": 102, "tipo": "nlp", "prioridade": 3, "tempo_exec": 3, "chegada": 0},
    {"id": 103, "tipo": "vaz", "prioridade": 1, "tempo_exec": 5, "chegada": 0},
    {"id": 104, "tipo": "nlp", "prioridade": 2, "tempo_exec": 4, "chegada": 0},
    {"id": 105, "tipo": "imagem", "prioridade": 1, "tempo_exec": 9, "chegada": 0},
]

REQUISICAO_ID_COUNTER = 106

def simular_chegada_aleatoria(tempo_atual):
    global REQUISICAO_ID_COUNTER
    novas_chegadas = []

    if random.random() < 0:  # configure se quiser gerar chegadas automáticas
        id_nova = REQUISICAO_ID_COUNTER
        REQUISICAO_ID_COUNTER += 1

        tipo = random.choice(["visao_computacional", "nlp", "fala", "analise_imagem"])
        prioridade = random.randint(1, 3)
        tempo_exec = random.randint(1, 10)

        nova_req = {
            "id": id_nova,
            "tipo": tipo,
            "prioridade": prioridade,
            "tempo_exec": tempo_exec,
            "chegada": tempo_atual,
        }
        novas_chegadas.append(nova_req)

        print(f"Requisição {id_nova} CHEGOU (P:{prioridade}, T_exec:{tempo_exec}).")

    return novas_chegadas


def passo_simulação(servidores, fila_execucao, fila_concluídas, tempo_atual):
    tarefas_concluidas = []

    # Decrementa tempo das tarefas
    for req in list(fila_execucao):
        req['tempo_restante'] -= 1

        if req['tempo_restante'] <= 0:
            tarefas_concluidas.append(req)
            fila_execucao.remove(req)

    # Finalizar tarefas concluídas
    for req_concluida in tarefas_concluidas:
        servidor_id = req_concluida['servidor_id']

        for s in servidores:
            if s['id'] == servidor_id:
                s['capacidade_uso'] -= 1
                break

        tempo_resposta = tempo_atual - req_concluida['chegada']
        req_concluida['tempo_resposta'] = tempo_resposta
        req_concluida['estado'] = 'concluída'
        fila_concluídas.append(req_concluida)

        cor = SERVIDOR_COR[servidor_id]
        print(cor + f"[CONCLUÍDA] Req {req_concluida['id']} | Servidor {servidor_id} liberado "
                    f"| Tempo resposta: {tempo_resposta}s" + RESET)

    return len(tarefas_concluidas)


def main_simulation_loop(politica, tempo_maximo=30):
    servidores = [d.copy() for d in SERVIDORES_CONFIG]
    fila_pendente = [d.copy() for d in REQUISIÇÕES_INICIAIS]
    fila_execucao = []
    fila_concluídas = []

    ultimo_servidor_rr_id = None

    print("=" * 60)
    print(f"SIMULAÇÃO: POLÍTICA {politica}")
    print(f"Servidores: {len(servidores)} | Capacidade total: {sum(s['capacidade_max'] for s in servidores)}")
    print("=" * 60)

    tempo_atual = 0
    while tempo_atual < tempo_maximo:
        print(f"\n--- TICK {tempo_atual} ---")

        novas_req = simular_chegada_aleatoria(tempo_atual)
        fila_pendente.extend(novas_req)

        capacidade_livre = sum(s['capacidade_max'] - s['capacidade_uso'] for s in servidores)

        while fila_pendente and capacidade_livre > 0:

            if politica == 'PRIORIDADE':
                req_idx = min(range(len(fila_pendente)), key=lambda i: fila_pendente[i]['prioridade'])
            elif politica == 'SJF':
                req_idx = min(range(len(fila_pendente)), key=lambda i: fila_pendente[i]['tempo_exec'])
            else:
                req_idx = 0

            requisicao = fila_pendente.pop(req_idx)
            servidor_alvo = None

            # ROUND ROBIN
            if politica == 'RR':
                servidores_ordenados = sorted(servidores, key=lambda s: s['id'])
                start_index = 0

                if ultimo_servidor_rr_id is not None:
                    try:
                        idx = next(i for i, s in enumerate(servidores_ordenados)
                                   if s['id'] == ultimo_servidor_rr_id)
                        start_index = (idx + 1) % len(servidores_ordenados)
                    except StopIteration:
                        pass

                for i in range(len(servidores_ordenados)):
                    s = servidores_ordenados[(start_index + i) % len(servidores_ordenados)]
                    if s['capacidade_uso'] < s['capacidade_max']:
                        servidor_alvo = s
                        ultimo_servidor_rr_id = s['id']
                        break

            else:
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
                capacidade_livre -= 1

                cor = SERVIDOR_COR[servidor_alvo['id']]
                print(cor + f"[ESCALONADO] Req {requisicao['id']} → Servidor {servidor_alvo['id']}" + RESET)
            else:
                fila_pendente.append(requisicao)
                print(f"Requisição {requisicao['id']} re-enfileirada (cluster cheio).")
                break

        passo_simulação(servidores, fila_execucao, fila_concluídas, tempo_atual)

        # STATUS colorido dos servidores
        uso_colorido = []
        for s in servidores:
            cor = SERVIDOR_COR[s['id']]
            uso_colorido.append(cor + f"S{s['id']} {s['capacidade_uso']}/{s['capacidade_max']}" + RESET)

        print("STATUS: Uso: [" + ", ".join(uso_colorido) +
              f"] | Pendentes: {len(fila_pendente)} | Executando: {len(fila_execucao)}")

        if not fila_pendente and not fila_execucao:
            break

        tempo_atual += 1

    final = time.perf_counter()
    total = final - comeco

    print("=" * 60)
    print(f"SIMULAÇÃO CONCLUÍDA ({politica})")
    print(f"Tempo total: {total:.8f}s")
    print(f"CPU utilizada: {psutil.cpu_percent(interval=1)}%")
    print(f"Ticks: {tempo_atual}")
    print(f"Requisições concluídas: {len(fila_concluídas)}")
    print("=" * 60)

    return fila_concluídas

# main_simulation_loop(politica='RR')
# main_simulation_loop(politica='SJF')
main_simulation_loop(politica='PRIORIDADE')
