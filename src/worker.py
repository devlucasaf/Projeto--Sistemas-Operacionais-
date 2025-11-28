import time

class Worker:
    def __init__(self, id, capacidade):
        self.id = id
        self.capacidade = capacidade
        self.ocupado = False

    def processar(self, task):
        print(f"[Worker {self.id}] executando tarefa {task.id}")
        time.sleep(task.tempo_exec)
        print(f"[Worker {self.id}] terminou tarefa {task.id}")
