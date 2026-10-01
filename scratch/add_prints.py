with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
'''        try:
            logger.info(
                f"[DiscoveryOrchestrator] Executing Action -> Provider='{action.provider}', Query='{action.query}', "
                f"Page={action.page}, Location='{loc_param}'"
            )
            records = connector.search_leads(''',
'''        try:
            logger.warning(
                f"[DiscoveryOrchestrator] Executing Action -> Provider='{action.provider}', Query='{action.query}', "
                f"Page={action.page}, Location='{loc_param}'"
            )
            print(f">>> EXECUTING {action.provider} with query {action.query}")
            records = connector.search_leads('''
)

text = text.replace(
'''        except Exception as e:
            self.metrics.sources_failed.add(action.provider)''',
'''        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f">>> CRASHED IN {action.provider}: {e}")
            self.metrics.sources_failed.add(action.provider)'''
)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(text)
