from ..LLMInterface import LLMInterface
from ..LLMEnums import OpenAIEnums

from openai import OpenAI
import logging
from typing import Union, List




class OpenAIProvider(LLMInterface):

    def __init__(self, api_key: str, base_url: str=None,
                 default_input_max_characters: int=2048, 
                 default_output_max_tokens: int=2048,
                 default_temperature: float=0.2):
        

        self.api_key = api_key
        self.base_url = base_url

        self.default_input_max_characters = default_input_max_characters
        self.default_output_max_tokens = default_output_max_tokens
        self.default_temperature = default_temperature

        self.generation_model_id = None
        
        self.embedding_model_id = None
        self.embedding_size = None

        self.client = OpenAI(
            api_key=self.api_key, 
            base_url=self.base_url if (self.base_url and len(self.base_url)) else None
        )

        self.logger = logging.getLogger("uvicorn.error")

        self.enums = OpenAIEnums
        



    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id


    def set_embedding_model(self, model_id: str, embedding_size: int=None):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size


    def generate_text(self, prompt: str, chat_history: list=[], 
                      max_output_tokens: int=None, temperature: float=None) -> str:  
              
        if not self.client:
            self.logger.error("OpenAI client is not initialized.")
            return None
        
        if not self.generation_model_id:
            self.logger.error("Generation model ID is not set.")
            return None
        


        max_output_tokens = max_output_tokens if max_output_tokens else self.default_output_max_tokens
        temperature = temperature if temperature else self.default_temperature
        chat_history.append(
            self.construct_prompt(prompt, role=OpenAIEnums.USER.value)
        )

        response = self.client.chat.completions.create(
            model=self.generation_model_id,
            messages=chat_history,
            max_tokens=max_output_tokens,
            temperature=temperature,
        )

        if not response or not response.choices or len(response.choices) == 0 or not response.choices[0].message or not response.choices[0].message.content:
            self.logger.error("Error While fetching generation from OpenAI API.")
            return None
        
        return response.choices[0].message.content
    

    def embed_text(self, text: Union[str, List[str]], document_type: str=None) -> list:
        
        if not self.client:
            self.logger.error("OpenAI client is not initialized.")
            return None
        
        if not self.embedding_model_id:
            self.logger.error("Embedding model ID is not set.")
            return None
        
        if isinstance(text, str):
            text = [text]

        response = self.client.embeddings.create(
            input=[self.process_text(t) for t in text],
            model=self.embedding_model_id,
            dimensions=self.embedding_size
        )

        if not response or not response.data or len(response.data) == 0 or not response.data[0].embedding:
            self.logger.error("Error While fetching embedding from OpenAI API.")
            return None
        
        return [d.embedding for d in response.data]

    def construct_prompt(self, prompt: str, role: str) -> str:
        return {
            "role": role,
            "content": prompt
        }
    


    # helper method for this provider to do any necessary text preprocessing before sending to the API
    # No need to add it in the LLMInterface since it might be specific to this provider and not needed for others
    def process_text(self, text: str) -> str:

        return text[:self.default_input_max_characters].strip()
    