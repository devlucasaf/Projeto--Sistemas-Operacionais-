from src.scheduler import Scheduler
from src.worker import Worker

class Orchestrator:
    def __init__(self, servidores, policy):
        self.servers = [Worker(s['id'], s['capacidade']) for s in servidores]
        self.scheduler = Scheduler()
        self.pending = []
        self.policy = policy

    def adicionar_tarefa(self, task):
        self.pending.append(task)

    def executar(self):
        while self.pending:
            task = self.scheduler.schedule(self.pending, self.policy)
            servidor = self.servers[0]  # simplificado
            servidor.processar(task)
