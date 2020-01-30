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
            for sp in Space.from_string(val):
                spaces.add(sp)
        setattr(namespace, self.dest, spaces)
