class OpenaiService:
    # Обертка для всех классов, связанных с OpenAI
    def __init__(self, interaction_manager, prompt_manager, limit_manager):
        self.interaction_manager = interaction_manager
        self.prompt_manager = prompt_manager
        self.limit_manager = limit_manager
