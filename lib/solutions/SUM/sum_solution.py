
class SumSolution:
    
    def compute(self, x, y):
        if(x < 0 or y < 0):
            raise ValueError("Both numbers must be non-negative")
        if(x >100 or y >100):
            raise ValueError("Both numbers must be less than or equal to 100")
        return x + y
