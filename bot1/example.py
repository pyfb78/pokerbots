import holdem_calc
import time

start_time = time.time()
print(holdem_calc.calculate(["As", "Ks", "Jd"], False, 10000, None, ["8s", "7s", "?", "?"], False))
end_time = time.time()

elapsed_time = end_time - start_time
print(f"Elapsed time: {elapsed_time:.4f} seconds")
