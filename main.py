"""BSB Compute: Orquestração de Tarefas (simulação)

- Orquestrador (Master) + Servidores (Workers) como processos.
- IPC via multiprocessing.Queue.
- Políticas de escalonamento: RR, SJF, PRIORITY.
- Chegadas dinâmicas (tempo de chegada aleatório, ou configurável no JSON).
- Logs em tempo real + métricas finais (tempo médio de resposta, espera máxima, throughput,
e uma estimativa de utilização por servidor).

JSON esperado (exemplo):
{
  "servidores": [
    {"id": 1, "capacidade": 3},
    {"id": 2, "capacidade": 2},
    {"id": 3, "capacidade": 1}
  ],
  "requisicoes": [
    {"id": 101, "tipo": "visao_computacional", "prioridade": 1, "tempo_exec": 8},
    {"id": 102, "tipo": "nlp", "prioridade": 3, "tempo_exec": 3},
    {"id": 103, "tipo": "voz", "prioridade": 2, "tempo_exec": 5}
  ]
}

Campos opcionais por requisicao:
- "chegada": float (segundos desde o inicio). Se ausente, será gerado aleatoriamente.

Observações de modelagem:
- "capacidade" atua de duas formas (simulação):
  (1) paralelismo (slots por worker) e (2) aceleração do tempo (tempo_exec / capacidade).
  Isso torna servidores mais capazes realmente mais rápidos.
"""

from __future__ import annotations

import argparse
import json
import math
import queue
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from multiprocessing.synchronize import Event

import multiprocessing as mp


# ----------------------------
# Modelos
# ----------------------------


@dataclass(order=True)
class Request:
    # Campos usados para ordenação variam conforme política; vamos ordenar no Master manualmente.
    id: int
    tipo: str
    prioridade: int  # 1=alta, 2=media, 3=baixa
    tempo_exec: float  # segundos (estimado)
    chegada: float  # segundos desde o inicio

    # Métricas em runtime
    assigned_worker: Optional[int] = None
    start_ts: Optional[float] = None
    end_ts: Optional[float] = None


@dataclass
class WorkerInfo:
    id: int
    capacidade: int
    task_queue: mp.Queue

    active: int = 0
    total_effective_work: float = 0.0  # soma de (tempo_exec/capacidade) das tarefas concluídas


# ----------------------------
# Utilidades
# ----------------------------


def fmt_ts(elapsed_s: float) -> str:
    mm = int(elapsed_s // 60)
    ss = int(elapsed_s % 60)
    return f"{mm:02d}:{ss:02d}"


def now() -> float:
    return time.monotonic()


# ----------------------------
# Worker process
# ----------------------------


def worker_main(
    worker_id: int,
    capacity: int,
    in_queue: mp.Queue,
    out_queue: mp.Queue,
    stop_event: Event,
) -> None:
    """Worker: recebe tarefas via in_queue, executa em paralelo (threads) e retorna eventos no out_queue."""

    active_lock = threading.Lock()
    active_count = 0

    def set_active(delta: int) -> int:
        nonlocal active_count
        with active_lock:
            active_count += delta
            return active_count

    def run_task(msg: Dict[str, Any]) -> None:
        # Envia START imediatamente ao iniciar a execução real.
        req_id = int(msg["id"])
        prioridade = int(msg["prioridade"])
        tipo = str(msg.get("tipo", ""))
        tempo_exec = float(msg["tempo_exec"])
        t_arrival = float(msg["chegada_ts"])

        start_ts = now()
        cur_active = set_active(+1)
        out_queue.put(
            {
                "event": "START",
                "worker_id": worker_id,
                "id": req_id,
                "prioridade": prioridade,
                "tipo": tipo,
                "arrival_ts": t_arrival,
                "start_ts": start_ts,
                "active": cur_active,
            }
        )

        # Simulação de execução
        effective_time = max(0.0, tempo_exec / max(1, capacity))
        time.sleep(effective_time)

        end_ts = now()
        cur_active = set_active(-1)
        out_queue.put(
            {
                "event": "DONE",
                "worker_id": worker_id,
                "id": req_id,
                "prioridade": prioridade,
                "tipo": tipo,
                "tempo_exec": tempo_exec,
                "effective_time": effective_time,
                "arrival_ts": t_arrival,
                "start_ts": start_ts,
                "end_ts": end_ts,
                "active": cur_active,
            }
        )

    # Um processo com pool de threads para simular slots (capacidade).
    executor = ThreadPoolExecutor(max_workers=max(1, capacity))

    try:
        while not stop_event.is_set():
            try:
                msg = in_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if msg is None:
                break

            # Submete ao executor (se o pool estiver cheio, a fila interna do executor cresce).
            # O Master tenta evitar isso agendando apenas quando houver slot disponível,
            # mas mantemos robustez.
            executor.submit(run_task, msg)

    finally:
        executor.shutdown(wait=True)


# ----------------------------
# Orquestrador (Master)
# ----------------------------


def pick_next_request(pending: List[Request], policy: str, rr_index: int) -> Tuple[Request, int]:
    """Retorna (req, idx_na_lista) do request selecionado."""
    if not pending:
        raise ValueError("pending vazio")

    if policy == "rr":
        idx = rr_index % len(pending)
        return pending[idx], idx

    if policy == "sjf":
        idx = min(range(len(pending)), key=lambda i: (pending[i].tempo_exec, pending[i].chegada, pending[i].id))
        return pending[idx], idx

    if policy == "priority":
        # prioridade menor = mais alta
        idx = min(range(len(pending)), key=lambda i: (pending[i].prioridade, pending[i].chegada, pending[i].id))
        return pending[idx], idx

    raise ValueError(f"policy inválida: {policy}")


def choose_worker_bestfit(workers: List[WorkerInfo]) -> Optional[WorkerInfo]:
    """Escolhe worker com menor razão active/capacidade; desempata por maior capacidade."""
    eligible = [w for w in workers if w.active < w.capacidade]
    if not eligible:
        return None

    def score(w: WorkerInfo) -> Tuple[float, int, int]:
        ratio = w.active / max(1, w.capacidade)
        # menor ratio melhor; maior capacidade melhor; menor id para estabilidade
        return (ratio, -w.capacidade, w.id)

    return min(eligible, key=score)


def choose_worker_rr(workers: List[WorkerInfo], rr_worker_ptr: int) -> Tuple[Optional[WorkerInfo], int]:
    """Round-robin entre workers, respeitando slots livres."""
    if not workers:
        return None, rr_worker_ptr

    n = len(workers)
    for k in range(n):
        idx = (rr_worker_ptr + k) % n
        w = workers[idx]
        if w.active < w.capacidade:
            return w, (idx + 1) % n

    return None, rr_worker_ptr


def master_run(
    config: Dict[str, Any],
    policy: str,
    seed: int,
    arrival_jitter: float,
    overload_redirect_threshold: float,
) -> int:
    random.seed(seed)

    servers = config.get("servidores", [])
    reqs_in = config.get("requisicoes", [])

    if not servers or not isinstance(servers, list):
        print("Config inválida: 'servidores' deve ser uma lista não vazia.", file=sys.stderr)
        return 2

    if not reqs_in or not isinstance(reqs_in, list):
        print("Config inválida: 'requisicoes' deve ser uma lista não vazia.", file=sys.stderr)
        return 2

    # IPC
    out_queue: mp.Queue = mp.Queue()
    stop_event = mp.Event()

    workers: List[WorkerInfo] = []
    procs: List[mp.Process] = []

    for s in servers:
        wid = int(s["id"])
        cap = int(s["capacidade"])
        if cap <= 0:
            cap = 1
        tq: mp.Queue = mp.Queue()
        w = WorkerInfo(id=wid, capacidade=cap, task_queue=tq)
        workers.append(w)

        p = mp.Process(target=worker_main, args=(wid, cap, tq, out_queue, stop_event), daemon=True)
        procs.append(p)

    # Ordena workers por id para estabilidade.
    workers.sort(key=lambda w: w.id)

    # Prepara requests (chegada pode ser fornecida ou gerada)
    all_requests: List[Request] = []
    for r in reqs_in:
        rid = int(r["id"])
        tipo = str(r.get("tipo", "generic"))
        prio = int(r.get("prioridade", 2))
        te = float(r.get("tempo_exec", 1.0))
        if te < 0:
            te = 0.0

        if "chegada" in r:
            chegada = float(r["chegada"])
        else:
            # chegada aleatória: acumula pequenos intervalos, gerando tráfego contínuo.
            chegada = random.random() * arrival_jitter

        all_requests.append(Request(id=rid, tipo=tipo, prioridade=prio, tempo_exec=te, chegada=chegada))

    # Se não veio chegada no JSON, espalha ao longo do tempo somando jitter incremental
    if all("chegada" not in r for r in reqs_in):
        all_requests.sort(key=lambda x: x.id)
        t = 0.0
        for req in all_requests:
            t += random.random() * arrival_jitter
            req.chegada = t

    all_requests.sort(key=lambda r: (r.chegada, r.id))

    total_n = len(all_requests)

    # Inicia workers
    for p in procs:
        p.start()

    t0 = now()

    # Estados
    pending: List[Request] = []
    arrived_idx = 0

    req_by_id: Dict[int, Request] = {r.id: r for r in all_requests}

    rr_req_index = 0
    rr_worker_ptr = 0

    completed = 0
    start_count = 0

    response_times: List[float] = []
    wait_times: List[float] = []

    # logs
    print("-----------------------------------------------")
    print(f"Política: {policy.upper()} | Servidores: {len(workers)} | Requisições: {total_n}")
    print("-----------------------------------------------")

    def log(msg: str) -> None:
        elapsed = now() - t0
        print(f"[{fmt_ts(elapsed)}] {msg}")

    # Loop principal
    try:
        while True:
            cur_t = now() - t0

            # Chegadas
            while arrived_idx < total_n and all_requests[arrived_idx].chegada <= cur_t:
                r = all_requests[arrived_idx]
                pending.append(r)
                arrived_idx += 1
                # opcional: log de chegada

            # Consumir eventos dos workers (START/DONE)
            drained = 0
            while True:
                try:
                    ev = out_queue.get_nowait()
                except queue.Empty:
                    break

                drained += 1
                et = ev.get("event")
                wid = int(ev["worker_id"])
                rid = int(ev["id"])

                # acha worker info
                w = next((x for x in workers if x.id == wid), None)
                if w is None:
                    continue

                if et == "START":
                    start_count += 1
                    w.active = int(ev.get("active", w.active))
                    r = req_by_id.get(rid)
                    if r is not None:
                        r.start_ts = float(ev["start_ts"])
                        r.assigned_worker = wid

                elif et == "DONE":
                    w.active = int(ev.get("active", w.active))
                    eff = float(ev.get("effective_time", 0.0))
                    w.total_effective_work += eff

                    r = req_by_id.get(rid)
                    if r is not None:
                        r.end_ts = float(ev["end_ts"])
                        # chegada_ts é absoluto (monotonic) no worker; no master usaremos o r.chegada relativo.
                        # Para métricas, usamos a timeline do master (t0) + r.chegada.
                        arrival_abs = t0 + r.chegada
                        start_abs = r.start_ts if r.start_ts is not None else float(ev.get("start_ts", arrival_abs))
                        end_abs = r.end_ts

                        resp = max(0.0, end_abs - arrival_abs)
                        wait = max(0.0, start_abs - arrival_abs)
                        response_times.append(resp)
                        wait_times.append(wait)

                    completed += 1
                    log(f"Servidor {wid} concluiu Requisição {rid}")

            # Condição de saída
            if completed >= total_n:
                # garante que todos chegaram/pending vazio
                if arrived_idx >= total_n:
                    break

            # Migração/redistribuição (simples):
            # Se a razão de carga variar muito, prioriza worker menos carregado na escolha.
            # (Aqui isso já é feito por choose_worker_bestfit; a flag apenas controla quão agressivo.
            #  Mantemos o parâmetro para o relatório/experimentos.)
            _ = overload_redirect_threshold

            # Agendamento: enquanto há pending e há worker com slot livre
            while pending:
                # Escolha do worker
                if policy == "rr":
                    w, rr_worker_ptr = choose_worker_rr(workers, rr_worker_ptr)
                else:
                    w = choose_worker_bestfit(workers)

                if w is None:
                    break

                # Escolhe próxima requisição
                req, idx = pick_next_request(pending, policy, rr_req_index)

                # Para RR de requisições, avançamos o índice quando removemos do pending
                if policy == "rr":
                    rr_req_index = (rr_req_index + 1) % max(1, len(pending))

                pending.pop(idx)

                prio_txt = {1: "Alta", 2: "Média", 3: "Baixa"}.get(req.prioridade, str(req.prioridade))
                log(f"Requisição {req.id} ({prio_txt}) atribuída ao Servidor {w.id}")

                # Envia ao worker (timestamps absolutos para o worker registrar, mas métricas no master são por t0)
                w.task_queue.put(
                    {
                        "id": req.id,
                        "tipo": req.tipo,
                        "prioridade": req.prioridade,
                        "tempo_exec": req.tempo_exec,
                        "chegada_ts": t0 + req.chegada,
                    }
                )

            # Pequeno sleep para evitar busy loop
            time.sleep(0.02)

    finally:
        stop_event.set()
        for w in workers:
            try:
                w.task_queue.put(None)
            except Exception:
                pass

        for p in procs:
            p.join(timeout=2.0)

    makespan = max(1e-9, now() - t0)

    avg_resp = sum(response_times) / len(response_times) if response_times else 0.0
    max_wait = max(wait_times) if wait_times else 0.0
    throughput = total_n / makespan

    # Utilização "simulada": total_effective_work / (makespan * capacidade)
    util_by_worker: List[Tuple[int, float]] = []
    for w in workers:
        util = w.total_effective_work / (makespan * max(1, w.capacidade))
        util_by_worker.append((w.id, max(0.0, min(1.0, util))))

    avg_util = sum(u for _, u in util_by_worker) / len(util_by_worker) if util_by_worker else 0.0

    print("-----------------------------------------------")
    print("Resumo Final:")
    print(f"Tempo médio de resposta: {avg_resp:.2f}s")
    print(f"Taxa de espera máxima: {max_wait:.2f}s")
    print(f"Throughput: {throughput:.2f} tarefas/segundo")
    print(f"Utilização média (simulada): {avg_util*100:.1f}%")
    print("Utilização por servidor (simulada):")
    for wid, util in util_by_worker:
        print(f"  - Servidor {wid}: {util*100:.1f}%")
    print("-----------------------------------------------")

    return 0


# ----------------------------
# CLI
# ----------------------------


def load_config(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        # Config padrão pequena, só para rodar sem arquivo
        return {
            "servidores": [
                {"id": 1, "capacidade": 3},
                {"id": 2, "capacidade": 2},
                {"id": 3, "capacidade": 1},
            ],
            "requisicoes": [
                {"id": 101, "tipo": "visao_computacional", "prioridade": 1, "tempo_exec": 8},
                {"id": 102, "tipo": "nlp", "prioridade": 3, "tempo_exec": 3},
                {"id": 103, "tipo": "voz", "prioridade": 2, "tempo_exec": 5},
            ],
        }

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BSB Compute - Orquestração de Tarefas (simulação)")
    p.add_argument("--config", type=str, default=None, help="Caminho para JSON de entrada")
    p.add_argument("--policy", type=str, default="rr", choices=["rr", "sjf", "priority"], help="Política")
    p.add_argument("--seed", type=int, default=7, help="Seed de aleatoriedade")
    p.add_argument(
        "--arrival-jitter",
        type=float,
        default=1.2,
        help="Se 'chegada' não existir no JSON, espaça chegadas acumulando valores aleatórios em [0, jitter]",
    )
    p.add_argument(
        "--overload-redirect-threshold",
        type=float,
        default=0.35,
        help="Parâmetro reservado para experimentar agressividade de redistribuição (neste modelo já ocorre via best-fit)",
    )
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    return master_run(
        cfg,
        policy=args.policy,
        seed=args.seed,
        arrival_jitter=args.arrival_jitter,
        overload_redirect_threshold=args.overload_redirect_threshold,
    )


if __name__ == "__main__":
    # Necessário no Windows para multiprocessing.
    raise SystemExit(main(sys.argv[1:]))
