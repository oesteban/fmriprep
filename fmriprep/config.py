# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""*fMRIPrep* settings."""
import os
import sys
import logging
import warnings
from multiprocessing import set_start_method


def redirect_warnings(message, category, filename, lineno, file=None, line=None):
    """Redirect other warnings."""
    logger = logging.getLogger()
    logger.debug('Captured warning (%s): %s', category, message)


warnings.showwarning = redirect_warnings

try:
    set_start_method('forkserver')
except RuntimeError:
    pass  # context has been already set
finally:
    # Defer all custom import for after initializing the forkserver and
    # redirecting warnings
    from uuid import uuid4
    from pathlib import Path
    from time import strftime
    from niworkflows.utils.spaces import SpatialReferences as _SRs, Reference as _Ref
    from nipype import logging as nlogging, __version__ as _nipype_ver
    from . import __version__

logging.addLevelName(25, 'IMPORTANT')  # Add a new level between INFO and WARNING
logging.addLevelName(15, 'VERBOSE')  # Add a new level between INFO and DEBUG

DEFAULT_MEMORY_MIN_GB = 0.01

_exec_env = os.name
# special variable set in the container
if os.getenv('IS_DOCKER_8395080871'):
    _exec_env = 'singularity'
    _cgroup = Path('/proc/1/cgroup')
    if _cgroup.exists() and 'docker' in _cgroup.read_text():
        _exec_env = 'docker'
        if os.getenv('DOCKER_VERSION_8395080871'):
            _exec_env = 'fmriprep-docker'
    del _cgroup

_fs_license = os.getenv('FS_LICENSE')
if _fs_license is None and os.getenv('FREESURFER_HOME'):
    _fs_license = os.path.join(os.getenv('FREESURFER_HOME'), 'license.txt')


class _Config:
    """An abstract class forbidding instantiation."""

    _paths = tuple()

    def __init__(self):
        """Avert instantiation."""
        raise RuntimeError('Configuration type is not instantiable.')

    @classmethod
    def load(cls, settings):
        """Store settings from a dictionary."""
        for k, v in settings.items():
            if v is None:
                continue
            if k in cls._paths:
                setattr(cls, k, Path(v).absolute())
                continue
            if hasattr(cls, k):
                setattr(cls, k, v)

    @classmethod
    def get(cls):
        """Return defined settings."""
        out = {}
        for k, v in cls.__dict__.items():
            if k.startswith('_') or v is None:
                continue
            if callable(getattr(cls, k)):
                continue
            if k in cls._paths:
                v = str(v)
            if isinstance(v, _SRs):
                v = ' '.join([str(s) for s in v.references]) or None
            if isinstance(v, _Ref):
                v = str(v) or None
            out[k] = v
        return out


class nipype(_Config):
    """Nipype configuration."""

    crashfile_format = 'txt'
    """The file format for crashfiles, either text or pickle."""
    get_linked_libs = False
    """Run NiPype's tool to enlist linked libraries for every interface."""
    memory_gb = None
    """Estimation in GB of the RAM this workflow can allocate at any given time."""
    nprocs = os.cpu_count()
    """Number of processes (compute tasks) that can be run in parallel (multiprocessing only)."""
    omp_nthreads = os.cpu_count()
    """Number of CPUs a single process can access for multithreaded execution."""
    plugin = 'MultiProc'
    """NiPype's execution plugin."""
    plugin_args = {
        'maxtasksperchild': 1,
        'raise_insufficient': False,
    }
    """Settings for NiPype's execution plugin."""
    resource_monitor = False
    """Enable resource monitor."""
    stop_on_first_crash = True
    """Whether the workflow should stop or continue after the first error."""
    version = _nipype_ver
    """Nipype's current version."""

    @classmethod
    def get_plugin(cls):
        """Format a dictionary for Nipype consumption."""
        out = {
            'plugin': cls.plugin,
            'plugin_args': cls.plugin_args,
        }
        if cls.plugin in ('MultiProc', 'LegacyMultiProc'):
            out['plugin_args']['nprocs'] = cls.nprocs
            out['plugin_args']['memory_gb'] = cls.memory_gb
        return out


class execution(_Config):
    """Configure workflow-level settings."""

    bids_dir = None
    """An existing path to the dataset, which must be BIDS-compliant."""
    boilerplate_only = False
    """Only generate a boilerplate."""
    debug = None
    """Run in sloppy mode (meaning, suboptimal parameters that minimize run-time)."""
    echo_idx = None
    """Select a particular echo for multi-echo EPI datasets."""
    exec_env = _exec_env
    """A string representing the execution platform."""
    fs_license_file = _fs_license
    """An existing file containing a FreeSurfer license."""
    fs_subjects_dir = None
    """FreeSurfer's subjects directory."""
    layout = None
    """The path to the exported index of a py:class:`~bids.layout.BIDSLayout` object."""
    log_dir = None
    """The path to a directory that contains execution logs."""
    log_level = 25
    """Output verbosity."""
    low_mem = None
    """Utilize uncompressed NIfTIs and other tricks to minimize memory allocation."""
    md_only_boilerplate = False
    """Do not convert boilerplate from MarkDown to LaTex and HTML."""
    notrack = False
    """Do not monitor *fMRIPrep* using Sentry.io."""
    output_dir = None
    """Folder where derivatives will be stored."""
    output_spaces = None
    """List of (non)standard spaces designated as spatial references for outputs."""
    reports_only = False
    """Only build the reports, based on the reportlets found in a cached working directory."""
    run_uuid = '%s_%s' % (strftime('%Y%m%d-%H%M%S'), uuid4())
    """Unique identifier of this particular run."""
    participant_label = None
    """List of participant identifiers that are to be preprocessed."""
    task_id = None
    """Select a particular task from all available in the dataset."""
    version = __version__
    """*fMRIPrep*'s version."""
    work_dir = Path('work').absolute()
    """Path to a working directory where intermediate results will be available."""
    write_graph = False
    """Write out the computational graph corresponding to the planned preprocessing."""

    _layout = None

    _paths = (
        'bids_dir',
        'fs_license_file',
        'fs_subjects_dir',
        'layout',
        'log_dir',
        'output_dir',
        'work_dir',
    )


# These variables are not necessary anymore
del _fs_license
del _exec_env
del _nipype_ver


class workflow(_Config):
    """Configure anatomical workflow."""

    anat_only = False
    """Execute the anatomical preprocessing only."""
    aroma_err_on_warn = None
    """Cast AROMA warnings to errors."""
    aroma_melodic_dim = None
    """Number of ICA components to be estimated by MELODIC
    (positive = exact, negative = maximum)."""
    bold2t1w_dof = None
    """Degrees of freedom of the BOLD-to-T1w registration steps."""
    cifti_output = None
    """Generate HCP Grayordinates, accepts either ``'91k'`` (default) or ``'170k'``."""
    dummy_scans = None
    """Set a number of initial scans to be considered nonsteady states."""
    fmap_bspline = None
    """Regularize fieldmaps with a field of B-Spline basis."""
    fmap_demean = None
    """Remove the mean from fieldmaps."""
    force_syn = None
    """Run *fieldmap-less* susceptibility-derived distortions estimation."""
    hires = None
    """Run FreeSurfer ``recon-all`` with the ``-hires`` flag."""
    ignore = None
    """Ignore particular steps for *fMRIPrep*."""
    internal_spaces = None
    """Standard and nonstandard spaces."""
    longitudinal = False
    """Run FreeSurfer ``recon-all`` with the ``-logitudinal`` flag."""
    medial_surface_nan = None
    """Fill medial surface with NaNs (not-a-number) when sampling."""
    regressors_all_comps = None
    regressors_dvars_th = None
    regressors_fd_th = None
    run_reconall = True
    """Run FreeSurfer's surface reconstruction."""
    skull_strip_fixed_seed = False
    """Fix a seed for skull-stripping."""
    skull_strip_template = 'OASIS30ANTs'
    """Change default brain extraction template."""
    spaces = None
    """Standard and nonstandard spaces."""
    t2s_coreg = None
    r"""Co-register echos before generating the T2\* reference of ME-EPI."""
    use_aroma = None
    """Run ICA-AROMA."""
    use_bbr = None
    """Run boundary-based registration for BOLD-to-T1w registration (default: ``True``)."""
    use_syn = None
    """Run *fieldmap-less* susceptibility-derived distortions estimation
    in the absence of any alternatives."""


class loggers(_Config):
    """Configure loggers."""

    default = logging.getLogger()
    cli = logging.getLogger('cli')
    workflow = nlogging.getLogger('nipype.workflow')
    interface = nlogging.getLogger('nipype.interface')
    utils = nlogging.getLogger('nipype.utils')


def from_dict(settings):
    """Read settings from a flat dictionary."""
    nipype.load(settings)
    execution.load(settings)
    workflow.load(settings)
    set_logger_level()


def load(filename):
    """Load settings from file."""
    from toml import loads
    filename = Path(filename)
    settings = loads(filename.read_text())
    for sectionname, configs in settings.items():
        section = getattr(sys.modules[__name__], sectionname)
        section.load(configs)
    set_logger_level()
    init_spaces()


def get(flat=False):
    """Get config as a dict."""
    settings = {
        'nipype': nipype.get(),
        'execution': execution.get(),
        'workflow': workflow.get(),
    }
    if not flat:
        return settings

    return {'.'.join((section, k)): v
            for section, configs in settings.items()
            for k, v in configs.items()}


def dumps():
    """Format config into toml."""
    from toml import dumps
    return dumps(get())


def to_filename(filename):
    """Write settings to file."""
    filename = Path(filename)
    filename.write_text(dumps())


def init_layout():
    """Init a new layout."""
    if execution._layout is None:
        import re
        from bids.layout import BIDSLayout
        work_dir = execution.work_dir / 'bids.db'
        work_dir.mkdir(exist_ok=True, parents=True)
        execution._layout = BIDSLayout(
            str(execution.bids_dir),
            validate=False,
            database_path=str(work_dir),
            ignore=("code", "stimuli", "sourcedata", "models",
                    "derivatives", re.compile(r'^\.')))
    execution.layout = execution._layout


def set_logger_level():
    """Set the current log level to all nipype loggers."""
    loggers.default.setLevel(execution.log_level)
    loggers.cli.setLevel(execution.log_level)
    loggers.interface.setLevel(execution.log_level)
    loggers.workflow.setLevel(execution.log_level)
    loggers.utils.setLevel(execution.log_level)


def init_spaces(checkpoint=True):
    """Get a spatial references."""
    from niworkflows.utils.spaces import Reference, SpatialReferences
    if getattr(workflow, 'spaces'):
        return

    spaces = getattr(execution, 'output_spaces')
    if spaces is not None and not isinstance(spaces, _SRs):
        spaces = SpatialReferences(
            [ref for s in execution.output_spaces.split(' ')
             for ref in Reference.from_string(s)]
        )
    if spaces is None:
        spaces = _SRs()

    if checkpoint:
        spaces.checkpoint()

    internal = getattr(workflow, 'internal_spaces')
    if internal is not None and internal.strip():
        spaces += [ref for s in internal.split(' ')
                   for ref in Reference.from_string(s)]
    workflow.spaces = spaces
