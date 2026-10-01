with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
'''    def stage_2_enrich_and_verify(self, viable_candidates: list[NormalizedLeadRecord]) -> list[dict[str, Any]]:''',
'''    def stage_2_enrich_and_verify(self, viable_candidates: list[NormalizedLeadRecord]) -> list[dict[str, Any]]:
        print(f">>> STAGE 2 ENTERED WITH {len(viable_candidates)} candidates")'''
)

text = text.replace(
'''        logger.info(
            f"[DiscoveryOrchestrator] Stage 1 Completed: Gathered {len(viable_candidates)}/{target} viable candidates "''',
'''        print(f">>> STAGE 1 FINISHED! Gathering {len(viable_candidates)} candidates")
        logger.warning(
            f"[DiscoveryOrchestrator] Stage 1 Completed: Gathered {len(viable_candidates)}/{target} viable candidates "'''
)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(text)
