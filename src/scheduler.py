class Scheduler:
    def schedule(self, tasks, policy):
        if policy == "RR":
            return tasks.pop(0)

        if policy == "SJF":
            tasks.sort(key=lambda t: t.tempo_exec)
            return tasks.pop(0)

        if policy == "PRIORIDADE":
            tasks.sort(key=lambda t: t.prioridade)
            return tasks.pop(0)
