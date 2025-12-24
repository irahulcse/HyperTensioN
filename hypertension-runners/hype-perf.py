import csv
import subprocess
import re
import json
import os
import time
import gc
from pathlib import Path

# Silence pyRAPL warnings about Mongo/Pandas
import logging
logging.getLogger("pyRAPL").setLevel(logging.ERROR)

try:
    import pyRAPL
    PYRAPL_AVAILABLE = True
except ImportError:
    PYRAPL_AVAILABLE = False

class HypeEnergyProfiler:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.root_dir = Path(self.config.get('project_root', '.')).resolve()
        self.base_input_dir = (self.root_dir / self.config['input_directory']).resolve()
        self.output_root = (self.root_dir / self.config['output_directory']).resolve()
        self.funcs_file = (self.root_dir / self.config['function_selection_file']).resolve()
        # This will now be your ./wrap_hype.sh
        self.binary_path = (self.root_dir / self.config['binary_path']).resolve()
        
        self.tracked_functions = self.load_functions()
        if PYRAPL_AVAILABLE:
            try: pyRAPL.setup()
            except: print("⚠️ RAPL Setup failed. Run with sudo.")

    def load_functions(self):
        if not self.funcs_file.exists(): return []
        with  open(self.funcs_file, 'r') as f:
            return [line.strip().split('#')[0].strip() for line in f if line.strip()]

    def parse_perf(self, data_file):
        results = {}
        top_functions = [] 
        if not data_file.exists(): return results

        try:
            # Note: We removed --demangle because we are looking for C symbols now
            cmd = f"perf report -i {data_file} --stdio --no-children -n"
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
            
            lines = output.splitlines()
            for line in lines:
                if "%" in line and len(top_functions) < 10:
                    top_functions.append(line.strip())

                for target in self.tracked_functions:
                    if target.lower() in line.lower():
                        match = re.search(r'(\d+\.\d+)%', line)
                        if match:
                            percentage = float(match.group(1))
                            results[target] = results.get(target, 0) + percentage
            
            if not results:
                print("      🔍 Tracked symbols not found. Top 3 actual symbols:")
                for fn in top_functions[:3]: print(f"        {fn}")
                    
        except Exception as e:
            print(f"    [!] Perf Parsing error: {e}")
        return results
    
    def run_command(self, cmd, is_profile=False, perf_file=None):
        uj = 0
        # Only use perf record for Rep 1
        full_cmd = f"perf record -F 999 -g -o {perf_file} -- {cmd}" if is_profile else cmd

        try:
            if PYRAPL_AVAILABLE:
                meter = pyRAPL.Measurement("Hype")
                meter.begin()
                subprocess.run(full_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=self.config.get('timeout', 600))
                meter.end()
                uj = sum(meter.result.pkg) if meter.result and meter.result.pkg else 0
            else:
                subprocess.run(full_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=self.config.get('timeout', 600))
        except subprocess.TimeoutExpired:
            print(f"    [!] TIMED OUT")
        
        gc.collect()
        return uj

    def profile_problem(self, domain_file, problem_path, csv_path, prob_dir):
        time.sleep(5) 
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Rep', 'Total_uJ', 'Function', 'Percent', 'Func_uJ'])

            # Rep 1: Profiling (uses wrap_hype.sh with 50 iterations)
            perf_data = prob_dir / "profile.data"
            profile_uj = self.run_command(f"{self.binary_path} {problem_path}", is_profile=True, perf_file=perf_data)
            breakdown = self.parse_perf(perf_data)
            
            if not breakdown:
                writer.writerow([1, profile_uj, "NONE_DETECTED", 0, 0])
            else:
                for func, pct in breakdown.items():
                    # We record the raw data, but note that profile_uj is for 50 runs
                    writer.writerow([1, profile_uj, func, pct, (pct/100)*profile_uj])
            
            if perf_data.exists(): os.remove(perf_data)

            # Reps 2-30: Clean runs (uses standard ruby call, NOT the wrapper)
            # This ensures your "Total_uJ" reflects a single solve
            for rep in range(2, self.config['repetitions'] + 1):
                clean_cmd = f"ruby ./Hype.rb {problem_path}"
                uj = self.run_command(clean_cmd, is_profile=False)
                writer.writerow([rep, uj, "PHASE_TOTAL", 100, uj])
                f.flush()
                time.sleep(2)

    def execute(self):
        # 1. Discovery: Get all domain folders
        domains = sorted([d for d in self.base_input_dir.iterdir() if d.is_dir()])
        
        for domain_path in domains:
            domain_name = domain_path.name
            
            # 2. Find all problems in this domain
            problems = sorted([
                p for p in domain_path.glob("*.hddl") 
                if "domain" not in p.name.lower()
            ])

            if not problems:
                continue

            print(f"\n--- Processing Domain: {domain_name} ({len(problems)} problems) ---")

            for idx, problem_path in enumerate(problems):
                # 3. Create pathing
                prob_dir = self.output_root / domain_name / problem_path.stem
                csv_path = prob_dir / f"{problem_path.stem}.csv"
                
                # --- RESUME LOGIC: Don't repeat work if the CSV already exists ---
                if csv_path.exists():
                    print(f"  [{idx+1}/{len(problems)}] Skipping {problem_path.name} (Result exists)")
                    continue

                prob_dir.mkdir(parents=True, exist_ok=True)
                print(f"  [{idx+1}/{len(problems)}] Profiling {problem_path.name}...")
                
                # 4. Profile the problem
                self.profile_problem(None, problem_path, csv_path, prob_dir)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, required=True)
    HypeEnergyProfiler(parser.parse_args().config).execute()