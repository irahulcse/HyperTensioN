import csv
import subprocess
import re
import json
import os
from pathlib import Path
import pyRAPL

class HypeEnergyProfiler:
    def __init__(self, config_path):
        self.script_dir = Path(__file__).parent.resolve()
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.base_input_dir = (self.script_dir / self.config['input_directory']).resolve()
        self.output_root = (self.script_dir / self.config['output_directory']).resolve()
        self.funcs_file = (self.script_dir / self.config['function_selection_file']).resolve()
        self.hype_rb = (self.script_dir / self.config['binary_path']).resolve()
        self.timeout = self.config.get('timeout', 30)
        
        self.tracked_functions = self.load_functions()
        pyRAPL.setup()

    def load_functions(self):
        with open(self.funcs_file, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]

    def run_command(self, cmd):
        meter = pyRAPL.Measurement("Hype")
        meter.begin()
        timed_out = False
        try:
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        meter.end()
        return 0 if timed_out else sum(meter.result.pkg)

    def get_breakdown(self, callgrind_file):
        results = {}
        if not os.path.exists(callgrind_file): return {}
        try:
            output = subprocess.check_output(f"callgrind_annotate --auto=yes {callgrind_file}", shell=True, text=True)
            total_match = re.search(r'([\d,]+)\s+\(100\.0%\)\s+PROGRAM TOTALS', output)
            if not total_match: return {}
            total_instr = float(total_match.group(1).replace(',', ''))
            for line in output.splitlines():
                for func in self.tracked_functions:
                    if func in line:
                        match = re.search(r'^\s*([\d,]+)', line)
                        if match:
                            instr_count = float(match.group(1).replace(',', ''))
                            results[func] = results.get(func, 0) + (instr_count / total_instr * 100)
        except Exception as e: print(f"    [!] Error: {e}")
        return results

    def execute(self):
        domains = [d for d in self.base_input_dir.iterdir() if d.is_dir()]
        for domain_path in domains:
            domain_name = domain_path.name
            domain_file = domain_path / "domain.hddl"
            if not domain_file.exists(): continue
            problems = sorted([p for p in domain_path.glob("*.hddl") if "domain" not in p.name.lower()])
            print(f"\n=== Hype Domain: {domain_name} ===")
            for problem_path in problems:
                prob_dir = self.output_root / domain_name / problem_path.stem
                prob_dir.mkdir(parents=True, exist_ok=True)
                csv_path = prob_dir / f"{problem_path.stem}.csv"
                print(f"  > Problem: {problem_path.name}")
                self.profile_problem(domain_file, problem_path, csv_path, prob_dir)

    def profile_problem(self, domain_file, problem_path, csv_path, prob_dir):
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Rep', 'Total_uJ', 'Function', 'Percent', 'Func_uJ'])
            for rep in range(1, self.config['repetitions'] + 1):
                base_cmd = f"ruby {self.hype_rb} {domain_file} {problem_path} run"
                if rep == 1:
                    cg_file = prob_dir / "profile.callgrind"
                    cmd = f"valgrind --tool=callgrind --max-stackframe=20000000 --callgrind-out-file={cg_file} {base_cmd}"
                    uj = self.run_command(cmd)
                    breakdown = self.get_breakdown(cg_file)
                    if not breakdown: writer.writerow([rep, uj, "TIMEOUT_OR_NONE", 0, 0])
                    for func, pct in breakdown.items():
                        writer.writerow([rep, uj, func, pct, (pct/100)*uj])
                else:
                    uj = self.run_command(base_cmd)
                    writer.writerow([rep, uj, "PHASE_TOTAL", 100, uj])

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, required=True)
    args = parser.parse_args()
    HypeEnergyProfiler(args.config).execute()