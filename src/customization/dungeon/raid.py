class Helper:
    def __init__(self, instance):
        self._instance = instance

def customize(instance):
    print(f'{__name__:<45}start to costomize!')

    helper = Helper(instance)