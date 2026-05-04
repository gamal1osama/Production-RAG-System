from ..LLMInterface import LLMInterface
from ..LLMEnums import CohereEnums, DocumentTypeEnums

import cohere
import logging




class CohereProvider(LLMInterface):
    
    def __init__(self, api_key: str,
                 default_input_max_characters: int=2048, 
                 default_output_max_tokens: int=2048,
                 default_temperature: float=0.2):
        

        self.api_key = api_key

        self.default_input_max_characters = default_input_max_characters
        self.default_output_max_tokens = default_output_max_tokens
        self.default_temperature = default_temperature

        self.generation_model_id = None
        
        self.embedding_model_id = None
        self.embedding_size = None

        self.client = cohere.Client(api_key=self.api_key)

        self.logger = logging.getLogger(__name__)
    

    

    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id


    def set_embedding_model(self, model_id: str, embedding_size: int=None):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    
    def generate_text(self, prompt: str, chat_history: list=[], 
                      max_output_tokens: int=None, temperature: float=None) -> str:  
              
        if not self.client:
            self.logger.error("Cohere client is not initialized.")
            return None
        
        if not self.generation_model_id:
            self.logger.error("Generation model ID is not set.")
            return None
        


        max_output_tokens = max_output_tokens if max_output_tokens else self.default_output_max_tokens
        temperature = temperature if temperature else self.default_temperature

        response = self.client.chat(
            model=self.generation_model_id,
            chat_history=chat_history,
            message=self.process_text(prompt),
            max_tokens=max_output_tokens,
            temperature=temperature,
        )

        if not response or not response.message or not response.message.content or not response.message.content[0] or not response.message.content[0].text:
            self.logger.error("Invalid response from Cohere API.")
            return None

        return response.message.content[0].text
    

    def embed_text(self, text: str, document_type: str=None) -> list:
        
        if not self.client:
            self.logger.error("Cohere client is not initialized.")
            return None
        
        if not self.embedding_model_id:
            self.logger.error("Embedding model ID is not set.")
            return None
        

        input_type = None
        if document_type and document_type.lower() == "query":
            input_type = CohereEnums.QUERY.value
        elif document_type and document_type.lower() == "document":
            input_type = CohereEnums.DOCUMENT.value
        
        response = self.client.embed(
            texts=[self.process_text(text)],
            model=self.embedding_model_id,
            dimensions=self.embedding_size,
            document_type=input_type,
            embedding_types=['float']
        )

        if not response or not response.embeddings or not response.embeddings.float or len(response.embeddings.float) == 0:
            self.logger.error("Error While fetching embedding from Cohere API.")
            return None

        return response.embeddings.float[0] # need to verify is this response.embeddings.float[0]
    


    
    def construct_prompt(self, prompt: str, role: str) -> str:
        return {
            "role": role,
            "text": self.process_text(prompt)
        }
    
    
    # helper method for this provider to do any necessary text preprocessing before sending to the API
    # No need to add it in the LLMInterface since it might be specific to this provider and not needed for others
    def process_text(self, text: str) -> str:

        return text[:self.default_input_max_characters].strip()
    