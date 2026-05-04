from abc import ABC, abstractmethod


class LLMInterface(ABC):

    @abstractmethod
    def set_generation_model(self, model_id: str):
        pass

    
    @abstractmethod
    def set_embedding_model(self, model_id: str, embedding_size: int=None):
        pass


    @abstractmethod
    def generate_text(self, prompt: str, chat_history: list=[], 
                      max_output_tokens: int=None, temperature: float=None) -> str:
        pass


    @abstractmethod
    def embed_text(self, text: str, document_type: str) -> list:
        pass


    @abstractmethod
    def construct_prompt(self, prompt: str, role: str) -> str:
        pass
