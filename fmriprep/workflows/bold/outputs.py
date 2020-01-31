# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Writing out derivative files."""
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu

from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.interfaces.cifti import CiftiNameSource
from niworkflows.interfaces.surf import GiftiNameSource
from niworkflows.interfaces.utility import KeySelect

from ...config import DEFAULT_MEMORY_MIN_GB
from ...interfaces import DerivativesDataSink


def init_func_derivatives_wf(
    bids_root,
    cifti_output,
    freesurfer,
    metadata,
    output_dir,
    spaces,
    use_aroma,
    fslr_density=None,
    name='func_derivatives_wf',
):
    """
    Set up a battery of datasinks to store derivatives in the right location.

    Parameters
    ----------
    bids_root : str
        Original BIDS dataset path.
    cifti_output : bool
        Whether the ``--cifti-output`` flag was set.
    freesurfer : bool
        Whether FreeSurfer anatomical processing was run.
    metadata : dict
        Metadata dictionary associated to the BOLD run.
    output_dir : str
        Where derivatives should be written out to.
    spaces : :py:class:`~niworkflows.utils.spaces.SpatialReferences`
        Organize and filter spatial normalizations. Composed of internal and output lists
        of spaces in the form of (Template, Specs). `Template` is a string of either
        TemplateFlow IDs (e.g., ``MNI152Lin``, ``MNI152NLin6Asym``, ``MNI152NLin2009cAsym``, or
        ``fsLR``), nonstandard references (e.g., ``T1w`` or ``anat``, ``sbref``, ``run``, etc.),
        or paths pointing to custom templates organized in a TemplateFlow-like structure.
        Specs is a dictionary with template specifications (e.g., the specs for the template
        ``MNI152Lin`` could be ``{'resolution': 2}`` if one wants the resampling to be done on
        the 2mm resolution version of the selected template).
    use_aroma : bool
        Whether ``--use-aroma`` flag was set.
    fslr_density : str, optional
        Density of fsLR surface (32k or 59k)
    name : str
        This workflow's identifier (default: ``func_derivatives_wf``).

    """
    from smriprep.workflows.outputs import _bids_relative
    nonstd_spaces = set(spaces.get_nonstd_spaces())
    workflow = Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(fields=[
        'aroma_noise_ics', 'bold_aparc_std', 'bold_aparc_t1', 'bold_aseg_std',
        'bold_aseg_t1', 'bold_cifti', 'bold_mask_std', 'bold_mask_t1', 'bold_std',
        'bold_std_ref', 'bold_t1', 'bold_t1_ref', 'bold_native', 'bold_native_ref',
        'bold_mask_native', 'cifti_variant', 'cifti_metadata', 'cifti_density',
        'confounds', 'confounds_metadata', 'melodic_mix', 'nonaggr_denoised_file',
        'source_file', 'surf_files', 'surf_refs', 'template', 'spatial_reference']),
        name='inputnode')

    raw_sources = pe.Node(niu.Function(function=_bids_relative), name='raw_sources')
    raw_sources.inputs.bids_root = bids_root

    ds_confounds = pe.Node(DerivativesDataSink(
        base_directory=output_dir, desc='confounds', suffix='regressors'),
        name="ds_confounds", run_without_submitting=True,
        mem_gb=DEFAULT_MEMORY_MIN_GB)
    workflow.connect([
        (inputnode, raw_sources, [('source_file', 'in_files')]),
        (inputnode, ds_confounds, [('source_file', 'source_file'),
                                   ('confounds', 'in_file'),
                                   ('confounds_metadata', 'meta_dict')]),
    ])

    if nonstd_spaces.intersection(('func', 'run', 'bold', 'boldref', 'sbref')):
        ds_bold_native = pe.Node(
            DerivativesDataSink(base_directory=output_dir, desc='preproc',
                                keep_dtype=True, compress=True, SkullStripped=False,
                                RepetitionTime=metadata.get('RepetitionTime'),
                                TaskName=metadata.get('TaskName')),
            name='ds_bold_native', run_without_submitting=True,
            mem_gb=DEFAULT_MEMORY_MIN_GB)
        ds_bold_native_ref = pe.Node(
            DerivativesDataSink(base_directory=output_dir, suffix='boldref', compress=True),
            name='ds_bold_native_ref', run_without_submitting=True,
            mem_gb=DEFAULT_MEMORY_MIN_GB)
        ds_bold_mask_native = pe.Node(
            DerivativesDataSink(base_directory=output_dir, desc='brain',
                                suffix='mask', compress=True),
            name='ds_bold_mask_native', run_without_submitting=True,
            mem_gb=DEFAULT_MEMORY_MIN_GB)

        workflow.connect([
            (inputnode, ds_bold_native, [('source_file', 'source_file'),
                                         ('bold_native', 'in_file')]),
            (inputnode, ds_bold_native_ref, [('source_file', 'source_file'),
                                             ('bold_native_ref', 'in_file')]),
            (inputnode, ds_bold_mask_native, [('source_file', 'source_file'),
                                              ('bold_mask_native', 'in_file')]),
            (raw_sources, ds_bold_mask_native, [('out', 'RawSources')]),
        ])

    # Resample to T1w space
    if nonstd_spaces.intersection(('T1w', 'anat')):
        ds_bold_t1 = pe.Node(
            DerivativesDataSink(base_directory=output_dir, space='T1w', desc='preproc',
                                keep_dtype=True, compress=True, SkullStripped=False,
                                RepetitionTime=metadata.get('RepetitionTime'),
                                TaskName=metadata.get('TaskName')),
            name='ds_bold_t1', run_without_submitting=True,
            mem_gb=DEFAULT_MEMORY_MIN_GB)
        ds_bold_t1_ref = pe.Node(
            DerivativesDataSink(base_directory=output_dir, space='T1w',
                                suffix='boldref', compress=True),
            name='ds_bold_t1_ref', run_without_submitting=True,
            mem_gb=DEFAULT_MEMORY_MIN_GB)

        ds_bold_mask_t1 = pe.Node(
            DerivativesDataSink(base_directory=output_dir, space='T1w', desc='brain',
                                suffix='mask', compress=True),
            name='ds_bold_mask_t1', run_without_submitting=True,
            mem_gb=DEFAULT_MEMORY_MIN_GB)
        workflow.connect([
            (inputnode, ds_bold_t1, [('source_file', 'source_file'),
                                     ('bold_t1', 'in_file')]),
            (inputnode, ds_bold_t1_ref, [('source_file', 'source_file'),
                                         ('bold_t1_ref', 'in_file')]),
            (inputnode, ds_bold_mask_t1, [('source_file', 'source_file'),
                                          ('bold_mask_t1', 'in_file')]),
            (raw_sources, ds_bold_mask_t1, [('out', 'RawSources')]),
        ])
        if freesurfer:
            ds_bold_aseg_t1 = pe.Node(DerivativesDataSink(
                base_directory=output_dir, space='T1w', desc='aseg', suffix='dseg'),
                name='ds_bold_aseg_t1', run_without_submitting=True,
                mem_gb=DEFAULT_MEMORY_MIN_GB)
            ds_bold_aparc_t1 = pe.Node(DerivativesDataSink(
                base_directory=output_dir, space='T1w', desc='aparcaseg', suffix='dseg'),
                name='ds_bold_aparc_t1', run_without_submitting=True,
                mem_gb=DEFAULT_MEMORY_MIN_GB)
            workflow.connect([
                (inputnode, ds_bold_aseg_t1, [('source_file', 'source_file'),
                                              ('bold_aseg_t1', 'in_file')]),
                (inputnode, ds_bold_aparc_t1, [('source_file', 'source_file'),
                                               ('bold_aparc_t1', 'in_file')]),
            ])

    if use_aroma:
        ds_aroma_noise_ics = pe.Node(DerivativesDataSink(
            base_directory=output_dir, suffix='AROMAnoiseICs'),
            name="ds_aroma_noise_ics", run_without_submitting=True,
            mem_gb=DEFAULT_MEMORY_MIN_GB)
        ds_melodic_mix = pe.Node(DerivativesDataSink(
            base_directory=output_dir, desc='MELODIC', suffix='mixing'),
            name="ds_melodic_mix", run_without_submitting=True,
            mem_gb=DEFAULT_MEMORY_MIN_GB)
        ds_aroma_std = pe.Node(
            DerivativesDataSink(base_directory=output_dir, space='MNI152NLin6Asym',
                                desc='smoothAROMAnonaggr', keep_dtype=True),
            name='ds_aroma_std', run_without_submitting=True,
            mem_gb=DEFAULT_MEMORY_MIN_GB)

        workflow.connect([
            (inputnode, ds_aroma_noise_ics, [('source_file', 'source_file'),
                                             ('aroma_noise_ics', 'in_file')]),
            (inputnode, ds_melodic_mix, [('source_file', 'source_file'),
                                         ('melodic_mix', 'in_file')]),
            (inputnode, ds_aroma_std, [('source_file', 'source_file'),
                                       ('nonaggr_denoised_file', 'in_file')]),
        ])

    if not hasattr(spaces, 'snapshot'):  # For documentation building purposes
        return workflow

    # Store resamplings in standard spaces when listed in --output-spaces
    if spaces.snapshot:
        volume_std_spaces = [_gen_ref_name((s.name, s.spec))
                             for s in spaces.snapshot if s.dim == 3]
        select_std = pe.Node(KeySelect(
            fields=['template', 'bold_std', 'bold_std_ref', 'bold_mask_std']),
            name='select_std', run_without_submitting=True, mem_gb=DEFAULT_MEMORY_MIN_GB)
        select_std.iterables = [('key', volume_std_spaces)]

        ds_bold_std = pe.Node(
            DerivativesDataSink(base_directory=output_dir, desc='preproc',
                                keep_dtype=True, compress=True, SkullStripped=False,
                                RepetitionTime=metadata.get('RepetitionTime'),
                                TaskName=metadata.get('TaskName')),
            name='ds_bold_std', run_without_submitting=True, mem_gb=DEFAULT_MEMORY_MIN_GB)
        ds_bold_std_ref = pe.Node(
            DerivativesDataSink(base_directory=output_dir, suffix='boldref'),
            name='ds_bold_std_ref', run_without_submitting=True, mem_gb=DEFAULT_MEMORY_MIN_GB)
        ds_bold_mask_std = pe.Node(
            DerivativesDataSink(base_directory=output_dir, desc='brain',
                                suffix='mask'),
            name='ds_bold_mask_std', run_without_submitting=True, mem_gb=DEFAULT_MEMORY_MIN_GB)

        workflow.connect([
            (inputnode, select_std, [('bold_std', 'bold_std'),
                                     ('bold_std_ref', 'bold_std_ref'),
                                     ('bold_mask_std', 'bold_mask_std'),
                                     ('template', 'template'),
                                     ('spatial_reference', 'keys')]),
            (select_std, ds_bold_std, [('bold_std', 'in_file'),
                                       (('template', _fmt_space), 'space')]),
            (select_std, ds_bold_std_ref, [('bold_std_ref', 'in_file'),
                                           (('template', _fmt_space), 'space')]),
            (select_std, ds_bold_mask_std, [('bold_mask_std', 'in_file'),
                                            (('template', _fmt_space), 'space')]),
            (inputnode, ds_bold_std, [('source_file', 'source_file')]),
            (inputnode, ds_bold_std_ref, [('source_file', 'source_file')]),
            (inputnode, ds_bold_mask_std, [('source_file', 'source_file')]),
            (raw_sources, ds_bold_mask_std, [('out', 'RawSources')]),
        ])

        if freesurfer:
            select_fs_std = pe.Node(KeySelect(
                fields=['bold_aseg_std', 'bold_aparc_std', 'template']),
                name='select_fs_std', run_without_submitting=True, mem_gb=DEFAULT_MEMORY_MIN_GB)
            select_fs_std.iterables = [('key', volume_std_spaces)]

            ds_bold_aseg_std = pe.Node(DerivativesDataSink(
                base_directory=output_dir, desc='aseg', suffix='dseg'),
                name='ds_bold_aseg_std', run_without_submitting=True,
                mem_gb=DEFAULT_MEMORY_MIN_GB)
            ds_bold_aparc_std = pe.Node(DerivativesDataSink(
                base_directory=output_dir, desc='aparcaseg', suffix='dseg'),
                name='ds_bold_aparc_std', run_without_submitting=True,
                mem_gb=DEFAULT_MEMORY_MIN_GB)
            workflow.connect([
                (inputnode, select_fs_std, [('bold_aseg_std', 'bold_aseg_std'),
                                            ('bold_aparc_std', 'bold_aparc_std'),
                                            ('template', 'template'),
                                            ('spatial_reference', 'keys')]),
                (select_fs_std, ds_bold_aseg_std, [('bold_aseg_std', 'in_file'),
                                                   (('template', _fmt_space), 'space')]),
                (select_fs_std, ds_bold_aparc_std, [('bold_aparc_std', 'in_file'),
                                                    (('template', _fmt_space), 'space')]),
                (inputnode, ds_bold_aseg_std, [('source_file', 'source_file')]),
                (inputnode, ds_bold_aparc_std, [('source_file', 'source_file')])
            ])

    fs_outputs = [s for s in spaces.snapshot if s.name in ('fsaverage', 'fsnative')]
    if freesurfer and fs_outputs:
        select_fs_surf = pe.Node(KeySelect(
            fields=['surfaces', 'surf_kwargs']), name='select_fs_surf',
            run_without_submitting=True, mem_gb=DEFAULT_MEMORY_MIN_GB)
        select_fs_surf.iterables = [('key', [s.legacyname or s.name for s in fs_outputs])]
        select_fs_surf.inputs.surf_kwargs = [{'space': s.legacyname or s.name}
                                             for s in fs_outputs]

        name_surfs = pe.MapNode(GiftiNameSource(
            pattern=r'(?P<LR>[lr])h.\w+',
            template='space-{space}_hemi-{LR}.func'),
            iterfield=['in_file'], name='name_surfs',
            mem_gb=DEFAULT_MEMORY_MIN_GB, run_without_submitting=True)

        ds_bold_surfs = pe.MapNode(DerivativesDataSink(base_directory=output_dir),
                                   iterfield=['in_file', 'suffix'], name='ds_bold_surfs',
                                   run_without_submitting=True,
                                   mem_gb=DEFAULT_MEMORY_MIN_GB)

        workflow.connect([
            (inputnode, select_fs_surf, [
                ('surf_files', 'surfaces'),
                ('surf_refs', 'keys')]),
            (select_fs_surf, name_surfs, [('surfaces', 'in_file'),
                                          ('surf_kwargs', 'template_kwargs')]),
            (inputnode, ds_bold_surfs, [('source_file', 'source_file')]),
            (select_fs_surf, ds_bold_surfs, [('surfaces', 'in_file')]),
            (name_surfs, ds_bold_surfs, [('out_name', 'suffix')]),
        ])

    # CIFTI output
    if cifti_output:
        name_cifti = pe.MapNode(
            CiftiNameSource(), iterfield=['variant', 'density'], name='name_cifti',
            mem_gb=DEFAULT_MEMORY_MIN_GB, run_without_submitting=True)
        cifti_bolds = pe.MapNode(
            DerivativesDataSink(base_directory=output_dir, compress=False),
            iterfield=['in_file', 'suffix'], name='cifti_bolds',
            run_without_submitting=True, mem_gb=DEFAULT_MEMORY_MIN_GB)
        cifti_key = pe.MapNode(DerivativesDataSink(
            base_directory=output_dir), iterfield=['in_file', 'suffix'],
            name='cifti_key', run_without_submitting=True,
            mem_gb=DEFAULT_MEMORY_MIN_GB)
        workflow.connect([
            (inputnode, name_cifti, [('cifti_variant', 'variant'),
                                     ('cifti_density', 'density')]),
            (inputnode, cifti_bolds, [('bold_cifti', 'in_file'),
                                      ('source_file', 'source_file')]),
            (name_cifti, cifti_bolds, [('out_name', 'suffix')]),
            (name_cifti, cifti_key, [('out_name', 'suffix')]),
            (inputnode, cifti_key, [('source_file', 'source_file'),
                                    ('cifti_metadata', 'in_file')]),
        ])

    return workflow


def _gen_ref_name(in_tuple):
    return '_'.join(['space-%s' % in_tuple[0].split(':')[0]] + [
        '-'.join(item) for item in in_tuple[1].items()])


def _fmt_space(in_tuple):
    out = in_tuple[0].split(':')
    res = in_tuple[1].get('res', None) or in_tuple[1].get('resolution', None)
    if res:
        out.append('-'.join(('res', res)))
    return out


def _get_resolution(in_tuple):
    return


def _get_density(in_tuple):
    return in_tuple[1].get('den', None) or in_tuple[1].get('density', None)
