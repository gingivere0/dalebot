class Lora:
    name_pairs = {}
    instances = []

    def __init__(self, name, alias):
        self.name = name
        self.alias = alias
        self.nickname = name
        self.keyword = ''
        Lora.name_pairs[name] = self
        Lora.name_pairs[alias] = self
        Lora.instances.append(self)

    def add_nickname(self, nickname):
        self.nickname = nickname
        if nickname not in Lora.name_pairs:
            Lora.name_pairs[nickname] = self
        return self

    def set_keyword(self, keyword):
        self.keyword = keyword
        return self

    # append the lora, including its keyword if it has one
    def apply(self, prompt, strength=1):
        added_keyword = '' if self.keyword in prompt else self.keyword + ' '
        lora_tag = ' <lora:{alias}:{strength}>'.format(alias=self.alias, strength=strength)
        return added_keyword + prompt + lora_tag

    @classmethod
    def get_lora(cls, name):
        if name in cls.name_pairs:
            return cls.name_pairs[name]
        return None

    @classmethod
    def is_lora(cls, keyword):
        return keyword in cls.name_pairs