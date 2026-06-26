import subprocess
import os

def run_git_to_doc(diff_file):
    filename = os.path.basename(diff_file)
    try:
        output = subprocess.check_output(["python", "git-to-doc/main.py", diff_file], text=True, stderr=subprocess.STDOUT).strip()
        commit = output.split("```\n")[1].split("\n```")[0].strip()
        return filename, commit
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {filename} - Validation failed! Output: {e}")
        return filename, "ERROR"

if __name__ == "__main__":
    fixtures_dir = "git-to-doc/tests/fixtures/"
    diff_files = [f for f in os.listdir(fixtures_dir) if f.endswith(".diff")]
    results = []
    for diff_file in diff_files:
        filename, commit = run_git_to_doc(os.path.join(fixtures_dir, diff_file))
        results.append((filename, commit))

    # Print results in a table format (you can customize this)
    print("-" * 30)
    print("| Filename | Commit Message |")
    print("-" * 30)
    for filename, commit in results:
        print(f"| {filename:<15} | {commit:<25} |")
    print("-" * 30)
