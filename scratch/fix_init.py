import re

with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
content = content.replace('''                "valid_count": job.valid_count or 0,
            }

    def _is_job_cancelled''', '''                "valid_count": job.valid_count or 0,
            }
        
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

    def _is_job_cancelled''')

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(content)
