import math
from alive_progress import alive_bar

import subprocess
import time
import re


def run_program_thousand_times(program_path, delay=0.0):
    new = 0
    best = 0

    """
    Runs a program 1000 times.
    
    Args:
        program_path (str): Path to the program or script to execute.
        delay (float): Optional delay (in seconds) between executions.
    """
    iterations = 1001 
    with alive_bar(iterations) as bar:
        for i in range(1, iterations):
            try:
                # print(f"Running iteration {i}...")
                result = subprocess.run(["python", 'engine.py'], capture_output=True, text=True)
                # result = subprocess.run(["python", 'engine_best.py'], capture_output=True, text=True)
                # print(f"Iteration {i} completed. Output:\n{result.stdout}")
                if result.stderr:
                    print(f"Errors in iteration {i}:\n{result.stderr}")
                if delay > 0:
                    time.sleep(delay)
            except Exception as e:
                print(f"An error occurred on iteration {i}: {e}")
                break

            # result = list(subprocess.run(["cat", 'gamelog.txt'], capture_output=True, text=True))
            # print(result[-1])
            with open('gamelog.txt', "r") as file:
                last_line = None
                for line in file:
                    last_line = line

            # print(last_line) 
            match = list(re.findall(r'\(([^()]*)\)', last_line))
            new += int(match[0])
            best += int(match[1])
            # print(new, best)
            # print(match)
            bar()
    return new, best

if __name__ == "__main__":
    # Provide the path to the program you want to run
    program_to_run = "engine_new.py"  # Replace with the actual program file
    # delay_between_runs = 0.1  # Optional: add a small delay (e.g., 0.1 seconds)
    scores = {'new':[],'best':[]}
    for i in range(1):
        n,b = run_program_thousand_times(program_to_run)
        scores['new'].append(n)
        scores['best'].append(b)

    print(scores)
