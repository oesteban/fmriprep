#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fMRI preprocessing workflow."""
from .. import config


def main():
    """Entry point."""
    import os
    import sys
    import gc
    from nipype import config as ncfg
    from multiprocessing import Process, Manager
    from .parser import parse_args
    from ..utils.bids import write_derivative_description

    parse_args()

    sentry_sdk = None
    if not config.execution.notrack:
        import sentry_sdk
        from ..utils.sentry import sentry_setup
        sentry_setup()

    config_file = config.execution.work_dir / '.fmriprep.toml'
    config.to_filename(config_file)

    # Call build_workflow(config_file, retval) in a subprocess
    with Manager() as mgr:
        from .workflow import build_workflow
        retval = mgr.dict()
        p = Process(target=build_workflow, args=(str(config_file), retval))
        p.start()
        p.join()

        retcode = p.exitcode or retval.get('return_code', 0)
        fmriprep_wf = retval.get('workflow', None)

    config.load(config_file)

    if config.execution.reports_only:
        sys.exit(int(retcode > 0))

    if fmriprep_wf and config.execution.write_graph:
        fmriprep_wf.write_graph(graph2use="colored", format='svg', simple_form=True)

    retcode = retcode or (fmriprep_wf is None) * os.EX_SOFTWARE
    if retcode != 0:
        sys.exit(retcode)

    # Generate boilerplate
    with Manager() as mgr:
        from .workflow import build_boilerplate
        p = Process(target=build_boilerplate,
                    args=(str(config_file), fmriprep_wf))
        p.start()
        p.join()

    if config.execution.boilerplate_only:
        sys.exit(int(retcode > 0))

    # Clean up master process before running workflow, which may create forks
    gc.collect()

    # Nipype config (logs and execution)
    ncfg.update_config({
        'logging': {
            'log_directory': str(config.execution.log_dir),
            'log_to_file': True
        },
        'execution': {
            'crashdump_dir': str(config.execution.log_dir),
            'crashfile_format': 'txt',
            'get_linked_libs': False,
            'stop_on_first_crash': config.nipype.stop_on_first_crash,
        },
        'monitoring': {
            'enabled': config.nipype.resource_monitor,
            'sample_frequency': '0.5',
            'summary_append': True,
        }
    })

    if config.nipype.resource_monitor:
        ncfg.enable_resource_monitor()

    # Sentry tracking
    if sentry_sdk is not None:
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag('run_uuid', config.execution.run_uuid)
            scope.set_tag('npart', len(config.execution.participant_label))
        sentry_sdk.add_breadcrumb(message='fMRIPrep started', level='info')
        sentry_sdk.capture_message('fMRIPrep started', level='info')

    config.loggers.workflow.log(25, 'fMRIPrep started!')
    errno = 1  # Default is error exit unless otherwise set
    try:
        fmriprep_wf.run(**config.nipype.get_plugin())
    except Exception as e:
        if not config.execution.notrack:
            from ..utils.sentry import process_crashfile
            crashfolders = [output_dir / 'fmriprep' / 'sub-{}'.format(s) / 'log' / run_uuid
                            for s in subject_list]
            for crashfolder in crashfolders:
                for crashfile in crashfolder.glob('crash*.*'):
                    process_crashfile(crashfile)

            if "Workflow did not execute cleanly" not in str(e):
                sentry_sdk.capture_exception(e)
        config.loggers.workflow.critical('fMRIPrep failed: %s', e)
        raise
    else:

        config.loggers.workflow.log(25, 'fMRIPrep finished successfully!')
        if not config.execution.notrack:
            success_message = 'fMRIPrep finished without errors'
            sentry_sdk.add_breadcrumb(message=success_message, level='info')
            sentry_sdk.capture_message(success_message, level='info')

        if config.workflow.run_reconall:
            from templateflow import api
            from niworkflows.utils.misc import _copy_any
            dseg_tsv = str(api.get('fsaverage', suffix='dseg', extension=['.tsv']))
            _copy_any(dseg_tsv,
                      str(output_dir / 'fmriprep' / 'desc-aseg_dseg.tsv'))
            _copy_any(dseg_tsv,
                      str(output_dir / 'fmriprep' / 'desc-aparcaseg_dseg.tsv'))
        errno = 0
    finally:
        from niworkflows.reports import generate_reports
        from subprocess import check_call, CalledProcessError, TimeoutExpired
        from pkg_resources import resource_filename as pkgrf
        from shutil import copyfile

        citation_files = {
            ext: output_dir / 'fmriprep' / 'logs' / ('CITATION.%s' % ext)
            for ext in ('bib', 'tex', 'md', 'html')
        }

        if not config.execution.md_only_boilerplate and citation_files['md'].exists():
            # Generate HTML file resolving citations
            cmd = ['pandoc', '-s', '--bibliography',
                   pkgrf('fmriprep', 'data/boilerplate.bib'),
                   '--filter', 'pandoc-citeproc',
                   '--metadata', 'pagetitle="fMRIPrep citation boilerplate"',
                   str(citation_files['md']),
                   '-o', str(citation_files['html'])]

            config.loggers.cli.info(
                'Generating an HTML version of the citation boilerplate...')
            try:
                check_call(cmd, timeout=10)
            except (FileNotFoundError, CalledProcessError, TimeoutExpired):
                config.loggers.cli.warning(
                    'Could not generate CITATION.html file:\n%s', ' '.join(cmd))

            # Generate LaTex file resolving citations
            cmd = ['pandoc', '-s', '--bibliography',
                   pkgrf('fmriprep', 'data/boilerplate.bib'),
                   '--natbib', str(citation_files['md']),
                   '-o', str(citation_files['tex'])]
            config.loggers.cli.info(
                'Generating a LaTeX version of the citation boilerplate...')
            try:
                check_call(cmd, timeout=10)
            except (FileNotFoundError, CalledProcessError, TimeoutExpired):
                config.loggers.cli.warning(
                    'Could not generate CITATION.tex file:\n%s', ' '.join(cmd))
            else:
                copyfile(pkgrf('fmriprep', 'data/boilerplate.bib'),
                         citation_files['bib'])
        else:
            config.loggers.cli.warning(
                'fMRIPrep could not find the markdown version of '
                'the citation boilerplate (%s). HTML and LaTeX versions'
                ' of it will not be available', citation_files['md'])

        # Generate reports phase
        failed_reports = generate_reports(
            subject_list, output_dir, work_dir, run_uuid,
            config=pkgrf('fmriprep', 'data/reports-spec.yml'),
            packagename='fmriprep')
        write_derivative_description(bids_dir, output_dir / 'fmriprep')

        if failed_reports and not config.execution.notrack:
            sentry_sdk.capture_message(
                'Report generation failed for %d subjects' % failed_reports,
                level='error')
        sys.exit(int((errno + failed_reports) > 0))


if __name__ == '__main__':
    raise RuntimeError("fmriprep/cli/run.py should not be run directly;\n"
                       "Please `pip install` fmriprep and use the `fmriprep` command")
