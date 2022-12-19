import jinja2
from jinja2 import StrictUndefined
import os
from pathlib import Path
import sys

# temperatures = [240.0, 260.0, 280.0, 290.0, 300.0, 310.0, 320.0, 340.0]
# temperatures = [250.0, 270.0, 298.15, 331.0]
temperatures = [298.15, 331.0]
NSTEP1 = 100000
NSTEP2 = 250000

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
TOP_TEMPLATE2_STR = open(os.path.join("templates", "topology2.template")).read()
TOP_TEMPLATE2 = jinja2.Template(TOP_TEMPLATE2_STR, undefined=StrictUndefined)

CRYSTAL_TEMPLATE_STR = open(os.path.join("templates", "crystal.template")).read()
CRYSTAL_TEMPLATE = jinja2.Template(CRYSTAL_TEMPLATE_STR, undefined=StrictUndefined)
DCM_TEMPLATE_STR = open(os.path.join("templates", "mdcm.template")).read()
DCM_TEMPLATE = jinja2.Template(DCM_TEMPLATE_STR, undefined=StrictUndefined)
FDCM_TEMPLATE_STR = open(os.path.join("templates", "fdcm.template")).read()
FDCM_TEMPLATE = jinja2.Template(FDCM_TEMPLATE_STR, undefined=StrictUndefined)
KERN_TEMPLATE_STR = open(os.path.join("templates", "kernel.template")).read()
KERN_TEMPLATE = jinja2.Template(KERN_TEMPLATE_STR, undefined=StrictUndefined)

SIM1_TEMPLATE_STR = open(os.path.join("templates", "sim1.template")).read()
SIM1_TEMPLATE = jinja2.Template(SIM1_TEMPLATE_STR, undefined=StrictUndefined)
SIM2_TEMPLATE_STR = open(os.path.join("templates", "sim2.template")).read()
SIM2_TEMPLATE = jinja2.Template(SIM2_TEMPLATE_STR, undefined=StrictUndefined)

JOB_TEMPLATE_STR = open(os.path.join("templates", "job.template")).read()
JOB_TEMPLATE = jinja2.Template(JOB_TEMPLATE_STR, undefined=StrictUndefined)
JOB2_TEMPLATE_STR = open(os.path.join("templates", "job2.template")).read()
JOB2_TEMPLATE = jinja2.Template(JOB2_TEMPLATE_STR, undefined=StrictUndefined)

ANALYSIS_TEMPLATE_STR = open(os.path.join("templates", "analysis.template")).read()
ANALYSIS_TEMPLATE = jinja2.Template(ANALYSIS_TEMPLATE_STR, undefined=StrictUndefined)

ALL_JOBS_TEMPLATE_STR = open(os.path.join("templates", "all_jobs.template")).read()
ALL_JOBS_TEMPLATE = jinja2.Template(ALL_JOBS_TEMPLATE_STR, undefined=StrictUndefined)

ANALYSIS_JOB_TEMPLATE_STR = open(os.path.join("templates", "analysis_job.template")).read()
ANALYSIS_JOB_TEMPLATE = jinja2.Template(ANALYSIS_JOB_TEMPLATE_STR, undefined=StrictUndefined)


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


def make_directories(BASE, INPUT, TEMPS, scale, escale, NPROC=16, fmdcm=False, mdcm=False, kernel=False,
                     cluster="pc-beethoven"):
    if scale is None:
        scale = 1

    if fmdcm and mdcm:
        print("Only fMDCM or MDCM can be loaded at one time")
        sys.exit(1)

    runs_dir = os.path.join(BASE)

    KEY = BASE.split("/")[-1]

    # base directory
    safe_mkdir(BASE)

    module = ""
    if cluster == "pc-beethoven":
        module = "module load charmm/c45a1-gcc9.2.0-ompi4.0.2"
    elif cluster == "pc-nccr-cluster":
        module = "module load charmm/gfortran-openmpi-1.10.4-hfi"
    elif cluster == "pc-bach":
        module = "module load gcc/gcc-12.2.0-cmake-3.25.1-openmpi-4.1.4"

    # runs
    safe_mkdir(runs_dir)
    #  make subdirectories inside run
    t_paths = temperature_filenames(TEMPS)

    slurm_paths = []

    for temperature, t_path in zip(TEMPS, t_paths):
        subdir = os.path.join(runs_dir, t_path)
        safe_mkdir(subdir)
        #  charmm input
        charm_file_path = os.path.join(subdir, "job.inp")
        with open(charm_file_path, "w") as f:
            f.write(make_charmm_input(temperature, subdir, INPUT, scale, escale,
                                      fmdcm=fmdcm, mdcm=mdcm, kernel=kernel))
        f.close()

        #  sbatch script
        slurm_file_path = os.path.join(subdir, "job.sh")
        with open(slurm_file_path, "w") as f:
            f.write(JOB_TEMPLATE.render(NPROC=NPROC, NAME=KEY, module=module))

        slurm_paths.append(subdir)

        #  add directories for heat, eq, anal, etc.
        for sub in charmm_sub_dirs:
            subdirpath = os.path.join(subdir, sub)
            safe_mkdir(subdirpath)

        #  make gas phase simulation
        gas_phase_dir = os.path.join(subdir, "gas")
        safe_mkdir(gas_phase_dir)

        slurm_file_path = os.path.join(gas_phase_dir, "job.sh")
        with open(slurm_file_path, "w") as f:
            f.write(JOB2_TEMPLATE.render(NPROC=1, NAME=KEY, module=module))
        slurm_paths.append(gas_phase_dir)

        gas_phase_chm_file = os.path.join(gas_phase_dir, "job.inp")
        with open(gas_phase_chm_file, "w") as f:
            f.write(make_charm_input_gasphase(temperature,
                                              gas_phase_dir,
                                              INPUT,
                                              scale,
                                              escale,
                                              fmdcm=fmdcm, mdcm=mdcm, kernel=kernel))

        for sub in charmm_sub_dirs:
            subdirpath = os.path.join(gas_phase_dir, sub)
            safe_mkdir(subdirpath)

    #  write the analysis job
    with open(os.path.join(runs_dir, "analysis.sh"), "w") as f:
        f.write(ANALYSIS_JOB_TEMPLATE.render(NAME=KEY, PATH=runs_dir))

    #  write the submission job
    with open(os.path.join(runs_dir, "submit.sh"), "w") as f:
        job_str = ALL_JOBS_TEMPLATE.render(NAME=KEY)
        for job in slurm_paths:
            job_str.write("cd {} \n".format(os.path.join(BASE, job)))
            job_str.write("sbatch {}\n".format(os.path.join(BASE, job, "job.sh")))
            job_str.write(f"cd {BASE}\n")

        job_str.write("sbatch analysis.sh\n")
        f.write(job_str)


def format_topology(scale, TEMPLATE, e_scale):
    """scale the LJ params in the topology"""
    OG311_e = "{:.3f}".format(LJ_dict["OG311"][0] * e_scale[0])
    OG311_S = "{:.3f}".format(LJ_dict["OG311"][1] * scale)
    CG331_e = "{:.3f}".format(LJ_dict["CG331"][0] * e_scale[1])
    CG331_S = "{:.3f}".format(LJ_dict["CG331"][1] * scale)
    HGP1_e = "{:.3f}".format(LJ_dict["HGP1"][0] * e_scale[2])
    HGP1_S = "{:.3f}".format(LJ_dict["HGP1"][1] * scale)
    HGA3_e = "{:.3f}".format(LJ_dict["HGA3"][0] * e_scale[3])
    HGA3_S = "{:.3f}".format(LJ_dict["HGA3"][1] * scale)

    _ = TEMPLATE.render(OG311_e=OG311_e,
                        OG311_S=OG311_S,
                        CG331_e=CG331_e,
                        CG331_S=CG331_S,
                        HGP1_e=HGP1_e,
                        HGP1_S=HGP1_S,
                        HGA3_e=HGA3_e,
                        HGA3_S=HGA3_S,
                        scale=scale)
    return _


def make_charmm_input(temperature, basepath, inputpath, scale, escale, fmdcm=False, mdcm=False, kernel=False):
    output = ""
    # header
    output += HEADER_TEMPLATE.render(BASEPATH=basepath, INPUTPATH=inputpath)
    # topology
    output += format_topology(scale, TOP_TEMPLATE, escale)
    # crystal
    output += CRYSTAL_TEMPLATE.render()
    #  if using advanced charge models
    if fmdcm:
        output += FDCM_TEMPLATE_STR
    if mdcm:
        output += DCM_TEMPLATE_STR
    if kernel:
        output += KERN_TEMPLATE_STR
    # simulation
    output += SIM1_TEMPLATE.render(TEMP=temperature, NSTEP1=NSTEP1, NSTEP2=NSTEP2)
    output += ANALYSIS_TEMPLATE_STR

    return output


def make_charm_input_gasphase(temperature, basepath, inputpath, scale, escale, fmdcm=False, mdcm=False, kernel=False):
    output = ""
    # header
    output += HEADER_TEMPLATE.render(BASEPATH=basepath, INPUTPATH=inputpath)
    # topology
    output += format_topology(scale, TOP_TEMPLATE2, escale)

    #  if using advanced charge models
    if fmdcm:
        output += FDCM_TEMPLATE_STR
    if mdcm:
        output += DCM_TEMPLATE_STR
    if kernel:
        output += KERN_TEMPLATE_STR
    # simulation
    output += SIM2_TEMPLATE.render(TEMP=temperature, NSTEP1=NSTEP1, NSTEP2=NSTEP2)

    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Fiddle with the parameters until they give you what you want...')
    parser.add_argument('-v', '--v', help='version of the code ("charmm", "fmdcm", "mdcm")', required=True)
    parser.add_argument('-s', '--s', help='scale separation', required=True)
    parser.add_argument('-p_in', '--p_in', help='input path', required=True)
    parser.add_argument('-p_out', '--p_out', help='output path', required=True)
    parser.add_argument('-e1', '--e1', help='e1', required=True)
    parser.add_argument('-e2', '--e2', help='e2', required=True)
    parser.add_argument('-e3', '--e3', help='e3', required=True)
    parser.add_argument('-e4', '--e4', help='e4', required=True)
    parser.add_argument('-c', '--c', help="cluster", default="pc-beethoven")
    args = vars(parser.parse_args())

    arguments = sys.argv
    path = args["p_out"]
    input_path = args["p_in"]
    scale = float(args["s"])
    dcm = args["v"]
    e1 = args["e1"]
    e2 = args["e2"]
    e3 = args["e3"]
    e4 = args["e4"]
    cluster = args["c"]

    e_scale = [float(_) for _ in [e1, e2, e3, e4]]

    if dcm == "charmm":
        print("generating standard CHARMM input")
        make_directories(path, input_path, temperatures, scale, e_scale, cluster=cluster)
    elif dcm == "fmdcm":
        print("generating fMDCM input")
        make_directories(path, input_path, temperatures, scale, e_scale, fmdcm=True, cluster=cluster)
    elif dcm == "kernel":
        print("generating kernel input")
        make_directories(path, input_path, temperatures, scale, e_scale, kernel=True, cluster=cluster)
    elif dcm == "mdcm":
        print("generating MDCM input")
        make_directories(path, input_path, temperatures, scale, e_scale, mdcm=True, cluster=cluster)
    else:
        print("incorrect input.")
        sys.exit(1)
