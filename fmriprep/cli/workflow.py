"""
The workflow builder factory method.

All the checks and the construction of the workflow are done
inside this function that has pickleable inputs and output
dictionary (``retval``) to allow isolation using a
``multiprocessing.Process`` that allows fmriprep to enforce
a hard-limited memory-scope.

"""


def build_workflow(config_file, retval):
    """Create the Nipype Workflow that supports the whole execution graph."""
    from niworkflows.utils.bids import collect_participants, check_pipeline_version
    from niworkflows.reports import generate_reports
    from .. import config
    from ..utils.misc import check_deps
    from ..workflows.base import init_fmriprep_wf

    config.load(config_file)
    build_log = config.loggers.workflow

    output_dir = config.execution.output_dir
    version = config.execution.version

    retval['return_code'] = 1
    retval['workflow'] = None

    # warn if older results exist
    msg = check_pipeline_version(
        version, output_dir / 'fmriprep' / 'dataset_description.json'
    )
    if msg is not None:
        build_log.warning(msg)

    # First check that bids_dir looks like a BIDS folder
    config.init_layout()
    subject_list = collect_participants(
        config.execution.layout,
        participant_label=config.execution.participant_label
    )

    # Called with reports only
    if config.execution.reports_only:
        from pkg_resources import resource_filename as pkgrf

        build_log.log(25, 'Running --reports-only on participants %s', ', '.join(subject_list))
        retval['return_code'] = generate_reports(
            subject_list,
            config.execution.output_dir,
            config.execution.work_dir,
            config.execution.run_uuid,
            config=pkgrf('fmriprep', 'data/reports-spec.yml'),
            packagename='fmriprep')
        return retval

    # Build main workflow
    INIT_MSG = """
    Running fMRIPREP version {version}:
      * BIDS dataset path: {bids_dir}.
      * Participant list: {subject_list}.
      * Run identifier: {uuid}.
      * Output spaces: {spaces}.
    """.format
    build_log.log(25, INIT_MSG(
        version=config.execution.version,
        bids_dir=config.execution.bids_dir,
        subject_list=subject_list,
        uuid=config.execution.run_uuid,
        spaces=config.execution.output_spaces)
    )

    retval['workflow'] = init_fmriprep_wf()

    # Check workflow for missing commands
    missing = check_deps(retval['workflow'])
    if missing:
        build_log.critical(
            "Cannot run fMRIPrep. Missing dependencies:%s",
            '\n\t* %s'.join(["{} (Interface: {})".format(cmd, iface)
                             for iface, cmd in missing])
        )
        retval['return_code'] = 127  # 127 == command not found.
        return retval

    config.to_filename(config_file)
    build_log.info(
        "fMRIPrep workflow graph with %d nodes built successfully.",
        len(retval['workflow']._get_all_nodes())
    )
    retval['return_code'] = 0
    return retval


def build_boilerplate(config_file, workflow):
    """Write boilerplate in an isolated process."""
    from .. import config

    config.load(config_file)
    logs_path = config.execution.output_dir / 'fmriprep' / 'logs'
    boilerplate = workflow.visit_desc()

    if boilerplate:
        citation_files = {
            ext: logs_path / ('CITATION.%s' % ext)
            for ext in ('bib', 'tex', 'md', 'html')
        }
        # To please git-annex users and also to guarantee consistency
        # among different renderings of the same file, first remove any
        # existing one
        for citation_file in citation_files.values():
            try:
                citation_file.unlink()
            except FileNotFoundError:
                pass

        citation_files['md'].write_text(boilerplate)
        config.loggers.workflow.log(
            25, 'Works derived from this fMRIPrep execution should '
            'include the following boilerplate:\n\n%s', boilerplate
        )
