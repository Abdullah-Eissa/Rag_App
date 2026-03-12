import os

class TemplateParser:
    
    def __init__(self, language: str=None, default_language='en'):
        self.current_path = os.path.dirname(os.path.abspath(__file__)) # templates folder
        self.default_language = default_language
        self.language = None
        
        self.set_language(language)
    
    def set_language(self, language: str):
        if not language:
            self.language = self.default_language
            
        language_path = os.path.join(self.current_path, 'locales', language)
        
        if os.path.exists(language_path):
            self.language = language
        else:
            self.language = self.default_language
            
    def get(self, group: str, key: str, vars: dict={}):
        if not group or not key: # if they are not empty
            return None
        
        group_path = os.path.join(self.current_path, 'locales', self.language, f'{group}.py')
        targeted_language = self.language
        if not os.path.exists(group_path): # if this condition is True, then group is not exists in this language
            group_path = os.path.join(self.current_path, 'locales', self.default_language, f'{group}.py')
            targeted_language = self.default_language
            
        if not os.path.exists(group_path):
            return None
        
        
        # In this part, we got the group_path correctly
        # Now we need to import the group module during the runtime in the following code:
# In our case, we need to import rag.py during the runtime to get the keys and variables from it and parsing them
        module = __import__(
            f'stores.llm.templates.locales.{targeted_language}.{group}',
            fromlist=[group] # import group (rag.py) from all of these modules
        )
        
        if not module:
            return None
        
        key_attribute = getattr(module, key) # get the key
        return key_attribute.substitute(vars) # fill the key by values of dictionary vars, then return string