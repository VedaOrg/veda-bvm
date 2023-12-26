import pkg_resources
from typing import (
    Tuple,
    Type,
)

from veda.services.components.attach.component import (
    DbShellComponent,
    AttachComponent,
)

from veda.extensibility import (
    BaseComponentAPI,
)
from veda.services.components.fix_unclean_shutdown.component import (
    FixUncleanShutdownComponent
)

from veda.services.components.syncer.component import (
    SyncerComponent,
)

from veda.services.components.json_rpc.component import (
    JsonRpcServerComponent,
)

BASE_COMPONENTS: Tuple[Type[BaseComponentAPI], ...] = (
    DbShellComponent,
    AttachComponent,

    SyncerComponent,
    FixUncleanShutdownComponent,
    JsonRpcServerComponent,
)

def discover_components() -> Tuple[Type[BaseComponentAPI], ...]:
    # Components need to define entrypoints at 'veda.components' to automatically get loaded
    # https://packaging.python.org/guides/creating-and-discovering-components/#using-package-metadata

    return tuple(
        entry_point.load() for entry_point in pkg_resources.iter_entry_points('veda.components')
    )


def get_all_components(*extra_components: Type[BaseComponentAPI],
                       ) -> Tuple[Type[BaseComponentAPI], ...]:
    return BASE_COMPONENTS + extra_components + discover_components()
