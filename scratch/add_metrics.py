with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if 'self.job_state = {' in line:
        pass
    if '                "valid_count": job.valid_count or 0,' in line:
        # After the dictionary ends
        pass
    if line.strip() == '}' and lines[i-1].strip() == '"valid_count": job.valid_count or 0,':
        # Add the init logic
        new_lines.append('''
        self.redis = _global_limiter._redis_client
        self.resolver = LifecycleResolver()
        self.discovery_engine = ZeroBudgetDiscoveryEngine()
        self.enricher = ProductionWebsiteEnricher()

        target = self.job_state.get('target_lead_count') or 100
        self.metrics = OrchestratorMetrics(
            requested=target,
            max_requests=max_request_budget,
        )
        self.seen_observation_keys: set[str] = set()
        self.action_queue: list[DiscoveryAction] = []
        self._initialize_provider_health()
''')

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
