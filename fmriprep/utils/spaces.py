# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Managing spatial/resampling references."""
from argparse import Action
from niworkflows.utils.spaces import Space, SpatialReferences


class SpacesManager(SpatialReferences):
    """Extend the spatial references to allow snapshotting."""

    __slots__ = ('_snapshot',)

    def __init__(self, spaces=None):
        """Initialize the snapshot."""
        super().__init__(spaces=spaces)
        self._snapshot = None

    @property
    def snapshot(self):
        """Get a snapshot."""
        return self._snapshot

    def snap(self):
        """Overwrite the snapshot."""
        self._snapshot = tuple(self._spaces)


class SpacesManagerAction(Action):
    """Parse spatial references."""

    def __call__(self, parser, namespace, values, option_string=None):
        """Execute parser."""
        spaces = getattr(namespace, self.dest) or SpacesManager()
        for val in values:
            val = val.rstrip(":")
            # Should we support some sort of explicit "default" resolution?
            # if ":res-" not in val or ":resolution-" not in val:
            #     val = ":".join((val, "res-default"))
            for sp in Space.from_string(val):
                spaces.add(sp)
        setattr(namespace, self.dest, spaces)


def format_space(in_tuple):
    """
    Format a given space tuple.

    >>> format_space(('MNI152Lin', {'res': 1}))
    'MNI152Lin_res-1'

    >>> format_space(('MNIPediatricAsym:cohort-2', {'res': 2}))
    'MNIPediatricAsym_cohort-2_res-2'

    """
    out = in_tuple[0].split(':')
    res = in_tuple[1].get('res', None) or in_tuple[1].get('resolution', None)
    if res:
        out.append('-'.join(('res', str(res))))
    return '_'.join(out)
