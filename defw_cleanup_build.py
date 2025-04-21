import yaml, glob, sys, os

def clean(cfg):
	if not cfg:
		return None
	with open(cfg, 'r') as f:
		cy = yaml.load(f, Loader=yaml.FullLoader)

	if 'defw' not in cy or 'swigify' not in cy['defw']:
		raise ValueError(f"Badly formed configuration file {cfg}")

	swigify_info = cy['defw']['swigify']
	for entry in swigify_info:
		name = entry['name']
		files = glob.glob(os.path.join('src', "*"+name+"*"))
		rm_cmd = f"rm -Rf {' '.join(files)}"
		print(rm_cmd)
		os.system(rm_cmd)

	return cy

if __name__ == "__main__":
	if len(sys.argv) != 2:
		raise ValueError("script should be called with DEFW build configuration file")

	clean(sys.argv[1])
