import jinja2
from jinja2 import StrictUndefined
import os
from pathlib import Path
import sys

# temperatures = [240.0, 260.0, 280.0, 290.0, 300.0, 310.0, 320.0, 340.0]
temperatures = [245.0, 298.15, 310.0]
NSTEP1 =  100000
NSTEP2 = 1000000

#  methanol
LJ_dict = {"OG311": [-0.1921, 1.7650],
           "CG331": [-0.0780, 2.0500],
           "HGP1": [-0.0460, 0.2245],
           "HGA3": [-0.0240, 1.3400]}


def temperature_filenames(ts):
    return ["t" + str(_) for _ in ts]


charmm_sub_dirs = ["min", "heq", "eq", "anal"]

# templates
HEADER_TEMPLATE_STR = open(os.path.join("templates", "head.template")).read()
HEADER_TEMPLATE = jinja2.Template(HEADER_TEMPLATE_STR, undefined=StrictUndefined)
TOP_TEMPLATE_STR = open(os.path.join("templates", "topology.template")).read()
TOP_TEMPLATE = jinja2.Template(TOP_TEMPLATE_STR, undefined=StrictUndefined)
CRYSTAL_TEMPLATE_STR = open(os.path.join("templates", "crystal.template")).read()
CRYSTAL_TEMPLATE = jinja2.Template(CRYSTAL_TEMPLATE_STR, undefined=StrictUndefined)
DCM_TEMPLATE_STR = open(os.path.join("templates", "mdcm.template")).read()
DCM_TEMPLATE = jinja2.Template(DCM_TEMPLATE_STR, undefined=StrictUndefined)
FDCM_TEMPLATE_STR = open(os.path.join("templates", "fdcm.template")).read()
FDCM_TEMPLATE = jinja2.Template(FDCM_TEMPLATE_STR, undefined=StrictUndefined)
SIM1_TEMPLATE_STR = open(os.path.join("templates", "sim1.template")).read()
SIM1_TEMPLATE = jinja2.Template(SIM1_TEMPLATE_STR, undefined=StrictUndefined)
JOB_TEMPLATE_STR = open(os.path.join("templates", "job.template")).read()
JOB_TEMPLATE = jinja2.Template(JOB_TEMPLATE_STR, undefined=StrictUndefined)
ANALYSIS_TEMPLATE_STR = open(os.path.join("templates", "analysis.template")).read()
ANALYSIS_TEMPLATE = jinja2.Template(ANALYSIS_TEMPLATE_STR, undefined=StrictUndefined)


def safe_mkdir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


"""
- input # files shared between runs, eg coords, topology, crystal lattice etc

- HOME # base directory, each time parameters are updated, a new directory is needed
        - T1  # this is the BASE for each charmm simulation
        - T2 ...
            - min
            - heq
            - eq
            - anal
"""


def make_directories(BASE, INPUT, TEMPS, scale, NPROC=16, fmdcm=False, mdcm=False):
    if scale is None:
        scale = 1

    if fmdcm and mdcm:
        print("Only fMDCM or MDCM can be loaded at one time")
        sys.exit(1)

    # input_dir = os.path.join(BASE, "input")
    runs_dir = os.path.join(BASE)
    # base directory
    safe_mkdir(BASE)

    # runs
    safe_mkdir(runs_dir)
    #  make subdirectories inside run
    t_paths = temperature_filenames(TEMPS)
    for temperature, t_path in zip(TEMPS, t_paths):
        subdir = os.path.join(runs_dir, t_path)
        safe_mkdir(subdir)
        #  charmm input
        charm_file_path = os.path.join(subdir, "job.inp")
        with open(charm_file_path, "w") as f:
            f.write(make_charmm_input(temperature, subdir, INPUT, scale, fmdcm=fmdcm, mdcm=mdcm))
        f.close()

        #  sbatch script
        slurm_file_path = os.path.join(subdir, "job.sh")
        with open(slurm_file_path, "w") as f:
            f.write(JOB_TEMPLATE.render(NPROC=NPROC, NAME="test"))
        f.close()

        #  add directories for heat, eq, anal, etc.
        for sub in charmm_sub_dirs:
            subdirpath = os.path.join(subdir, sub)
            safe_mkdir(subdirpath)


def format_topology(scale):
    # S = 1.5 to 2.2, e = 0 to -0.5
    # S_scale = scale
    # e_scale = scale
    """scale the LJ params in the topology"""
    OG311_e = "{:.3f}".format(LJ_dict["OG311"][0] * scale)
    OG311_S = "{:.3f}".format(LJ_dict["OG311"][1] * scale)
    CG331_e = "{:.3f}".format(LJ_dict["CG331"][0] * scale)
    CG331_S = "{:.3f}".format(LJ_dict["CG331"][1] * scale)
    HGP1_e = "{:.3f}".format(LJ_dict["HGP1"][0] * scale)
    HGP1_S = "{:.3f}".format(LJ_dict["HGP1"][1] * scale)
    HGA3_e = "{:.3f}".format(LJ_dict["HGA3"][0] * scale)
    HGA3_S = "{:.3f}".format(LJ_dict["HGA3"][1] * scale)

    _ = TOP_TEMPLATE.render(OG311_e=OG311_e,
                            OG311_S=OG311_S,
                            CG331_e=CG331_e,
                            CG331_S=CG331_S,
                            HGP1_e=HGP1_e,
                            HGP1_S=HGP1_S,
                            HGA3_e=HGA3_e,
                            HGA3_S=HGA3_S,
                            scale=scale)
    return _


def make_charmm_input(temperature, basepath, inputpath, scale, fmdcm=False, mdcm=False):
    output = ""
    # header
    output += HEADER_TEMPLATE.render(BASEPATH=basepath, INPUTPATH=inputpath)
    # topology
    output += format_topology(scale)

    # crystal
    output += CRYSTAL_TEMPLATE.render()

    #  if using advanced charge models
    if fmdcm:
        output += FDCM_TEMPLATE_STR
    if mdcm:
        output += DCM_TEMPLATE_STR

    # simulation
    output += SIM1_TEMPLATE.render(TEMP=temperature, NSTEP1=NSTEP1, NSTEP2=NSTEP2)

    output += ANALYSIS_TEMPLATE_STR

    return output


def make_job(PATH):
    pass


if __name__ == "__main__":
    arguments = sys.argv
    path = arguments[1]
    input_path = arguments[2]
    scale = float(arguments[3])
    dcm = False

    if len(arguments) > 4:
        dcm = arguments[4]

    if not dcm:
        print("generating standard CHARMM input")
        make_directories(path, input_path, temperatures, scale)
    elif dcm == "fmdcm":
        print("generating fMDCM input")
        make_directories(path, input_path, temperatures, scale, fmdcm=True)
    elif dcm == "mdcm":
        print("generating MDCM input")
        make_directories(path, input_path, temperatures, scale, mdcm=True)
    else:
        print("incorrect input.")
        sys.exit(1)
